"""
Enhanced Twitter Poller with comprehensive optimizations.

This module implements the optimized Twitter poller with intelligent
pagination, rate limit management, error handling, and monitoring.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Iterator, List, Dict, Any, Optional

import boto3
import tweepy

from checkpoint_manager import CheckpointManager
from data_models import ExecutionMetrics, TweetData
from error_handler import ErrorHandler
from metrics_logger import MetricsLogger
from rate_limit_manager import RateLimitManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TwitterPollerOptimized:
    """Enhanced Twitter poller with comprehensive optimizations."""
    
    # Maximum execution time before graceful termination (seconds)
    MAX_EXECUTION_TIME = 840  # 14 minutes (Lambda timeout is typically 15 min)
    
    # Batch size for downstream processing
    DEFAULT_BATCH_SIZE = 25
    
    # Maximum tweets to process per execution
    MAX_TWEETS_PER_EXECUTION = 1000
    
    def __init__(
        self,
        search_text: str,
        checkpoint_table_name: str,
        processor_function_name: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        ssm_parameter_prefix: str = 'twitter-event-source'
    ):
        """
        Initialize enhanced Twitter poller.
        
        Args:
            search_text: Search query for tweets
            checkpoint_table_name: DynamoDB table for checkpoints
            processor_function_name: Lambda function for processing batches
            batch_size: Size of batches to send to processor
            ssm_parameter_prefix: Prefix for SSM parameters
        """
        self.search_text = search_text
        self.batch_size = batch_size
        self.processor_function_name = processor_function_name
        
        # Initialize components
        self.checkpoint_manager = CheckpointManager(checkpoint_table_name)
        self.rate_limit_manager = RateLimitManager()
        self.error_handler = ErrorHandler()
        self.metrics_logger = MetricsLogger()
        
        # AWS clients
        self.lambda_client = boto3.client('lambda')
        self.ssm_client = boto3.client('ssm')
        
        # Initialize X API client
        self.x_client = self._create_x_client(ssm_parameter_prefix)
        
        # Execution tracking
        self.metrics = ExecutionMetrics(start_time=datetime.utcnow())
        self.execution_start_time = time.time()
    
    def _create_x_client(self, ssm_parameter_prefix: str) -> tweepy.Client:
        """
        Create X API v2 client with Bearer Token authentication.
        
        Args:
            ssm_parameter_prefix: Prefix for SSM parameter
            
        Returns:
            Configured Tweepy client
        """
        bearer_token_param = f'/{ssm_parameter_prefix}/bearer_token'
        
        try:
            response = self.ssm_client.get_parameters(
                Names=[bearer_token_param],
                WithDecryption=True
            )
            
            if response['InvalidParameters']:
                raise RuntimeError(
                    f'Could not find SSM parameter: {bearer_token_param}'
                )
            
            bearer_token = response['Parameters'][0]['Value']
            
            # Note: wait_on_rate_limit=False because we manage rate limits manually
            return tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
            
        except Exception as e:
            logger.error(f"Failed to create X API client: {e}")
            raise
    
    def should_terminate(self) -> bool:
        """
        Check if execution should terminate gracefully.
        
        Returns:
            True if should terminate, False otherwise
        """
        elapsed = time.time() - self.execution_start_time
        
        if elapsed >= self.MAX_EXECUTION_TIME:
            logger.warning(
                f"Approaching execution time limit ({elapsed:.0f}s / "
                f"{self.MAX_EXECUTION_TIME}s). Terminating gracefully."
            )
            return True
        
        if self.metrics.tweets_processed >= self.MAX_TWEETS_PER_EXECUTION:
            logger.info(
                f"Reached tweet processing limit "
                f"({self.metrics.tweets_processed} / {self.MAX_TWEETS_PER_EXECUTION}). "
                f"Terminating gracefully."
            )
            return True
        
        return False
    
    def search_with_pagination(
        self,
        since_id: Optional[str] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Search tweets with intelligent pagination and rate limit management.
        
        Args:
            since_id: Start searching from tweets after this ID
            
        Yields:
            Lists of transformed tweet dictionaries
        """
        next_token = None
        page_count = 0
        
        while True:
            # Check if we should terminate
            if self.should_terminate():
                logger.info("Terminating pagination due to execution limits")
                break
            
            # Check rate limits before making request
            if not self.rate_limit_manager.should_continue_requests():
                logger.warning("Rate limit threshold reached. Stopping pagination.")
                break
            
            try:
                # Build query parameters
                query_params = {
                    'query': self.search_text,
                    'max_results': 100,
                    'tweet_fields': ['id', 'text', 'attachments', 'entities', 'created_at'],
                    'expansions': ['attachments.media_keys', 'author_id'],
                    'media_fields': ['type', 'url', 'preview_image_url']
                }
                
                if since_id:
                    query_params['since_id'] = since_id
                
                if next_token:
                    query_params['pagination_token'] = next_token
                
                # Make API call with timing
                call_start = time.time()
                response = self.x_client.search_recent_tweets(**query_params)
                call_duration = time.time() - call_start
                
                self.metrics.api_calls_made += 1
                
                # Parse rate limit headers
                if hasattr(response, 'headers') and response.headers:
                    rate_status = self.rate_limit_manager.parse_rate_limit_headers(
                        response.headers
                    )
                    self.rate_limit_manager.log_status()
                    
                    # Log rate limit encounter if approaching limits
                    if rate_status.should_wait:
                        self.metrics.rate_limit_waits += 1
                        self.metrics_logger.log_rate_limit_encounter(
                            rate_status.remaining_requests,
                            rate_status.limit,
                            rate_status.reset_time,
                            rate_status.wait_seconds
                        )
                
                # Log API call
                self.metrics_logger.log_api_call(
                    'search_recent_tweets',
                    call_duration,
                    200,
                    {'page': page_count, 'since_id': since_id}
                )
                
                # Check if we got results
                if not response.data:
                    logger.info("No more tweets found")
                    break
                
                # Transform tweets
                transformed_tweets = self._transform_tweets(response)
                
                if transformed_tweets:
                    page_count += 1
                    yield transformed_tweets
                
                # Check for next page
                if not hasattr(response, 'meta') or not response.meta.get('next_token'):
                    logger.info("No more pages available")
                    break
                
                next_token = response.meta['next_token']
                
                # Wait if rate limits require it
                wait_seconds = self.rate_limit_manager.wait_if_needed()
                if wait_seconds > 0:
                    self.metrics.total_wait_seconds += wait_seconds
                
            except Exception as e:
                self.metrics.errors_encountered += 1
                
                decision = self.error_handler.handle_error(
                    e,
                    self.metrics.errors_encountered - 1,
                    {'operation': 'search_tweets', 'page': page_count}
                )
                
                if not decision.should_retry:
                    logger.error(f"Non-retryable error during search: {e}")
                    break
                
                if decision.wait_seconds > 0:
                    time.sleep(decision.wait_seconds)
                    self.metrics.total_wait_seconds += decision.wait_seconds
    
    def _transform_tweets(self, response: tweepy.Response) -> List[Dict[str, Any]]:
        """
        Transform X API v2 response to parser-compatible format.
        
        Args:
            response: Tweepy API response
            
        Returns:
            List of transformed tweet dictionaries
        """
        # Build media lookup
        media_lookup = {}
        if response.includes and 'media' in response.includes:
            for media in response.includes['media']:
                media_lookup[media.media_key] = media
        
        transformed_tweets = []
        
        for tweet in response.data:
            # Skip tweets without attachments
            if not hasattr(tweet, 'attachments') or not tweet.attachments:
                continue
            
            media_keys = tweet.attachments.get('media_keys', [])
            if not media_keys:
                continue
            
            # Build media entities for photos only
            media_entities = []
            for media_key in media_keys:
                if media_key not in media_lookup:
                    continue
                
                media = media_lookup[media_key]
                if media.type == 'photo':
                    media_entities.append({
                        'id_str': str(tweet.id),
                        'media_url_https': media.url,
                        'type': 'photo'
                    })
            
            if media_entities:
                transformed_tweets.append({
                    'id': str(tweet.id),
                    'id_str': str(tweet.id),
                    'full_text': tweet.text,
                    'extended_entities': {
                        'media': media_entities
                    }
                })
        
        return transformed_tweets
    
    def process_batch_stream(
        self,
        tweets_iterator: Iterator[List[Dict[str, Any]]]
    ) -> None:
        """
        Process tweet batches from stream with memory efficiency.
        
        Args:
            tweets_iterator: Iterator yielding lists of tweets
        """
        batch_number = 0
        all_tweets_for_checkpoint = []
        
        for tweet_page in tweets_iterator:
            # Track all tweets for checkpoint update
            all_tweets_for_checkpoint.extend(tweet_page)
            
            # Process in batches
            for i in range(0, len(tweet_page), self.batch_size):
                batch = tweet_page[i:min(i + self.batch_size, len(tweet_page))]
                
                try:
                    self.lambda_client.invoke(
                        FunctionName=self.processor_function_name,
                        InvocationType='Event',
                        Payload=json.dumps(batch)
                    )
                    
                    batch_number += 1
                    self.metrics.batches_sent += 1
                    self.metrics.tweets_processed += len(batch)
                    
                    self.metrics_logger.log_batch_sent(
                        batch_number,
                        len(batch),
                        self.processor_function_name,
                        True
                    )
                    
                except Exception as e:
                    self.metrics.errors_encountered += 1
                    logger.error(f"Failed to send batch {batch_number}: {e}")
                    
                    self.metrics_logger.log_batch_sent(
                        batch_number,
                        len(batch),
                        self.processor_function_name,
                        False
                    )
            
            # Update checkpoint with newest tweet ID from this page
            if tweet_page:
                newest_id = max(int(tweet['id']) for tweet in tweet_page)
                self._update_checkpoint(str(newest_id))
    
    def _update_checkpoint(self, since_id: str) -> None:
        """
        Update checkpoint with atomic operation.
        
        Args:
            since_id: New checkpoint value
        """
        if not self.checkpoint_manager.validate_checkpoint(since_id):
            logger.error(f"Invalid checkpoint value: {since_id}")
            return
        
        previous_id = self.checkpoint_manager.get_last_checkpoint()
        success = self.checkpoint_manager.update_checkpoint_atomic(since_id, previous_id)
        
        if success:
            self.metrics.checkpoint_updates += 1
        
        self.metrics_logger.log_checkpoint_update(previous_id, since_id, success)
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute enhanced polling operation.
        
        Returns:
            Execution summary with metrics
        """
        # Log execution start
        self.metrics_logger.log_execution_start({
            'search_text': self.search_text,
            'batch_size': self.batch_size
        })
        
        try:
            # Get last checkpoint
            since_id = self.checkpoint_manager.recover_from_corruption()
            logger.info(f"Starting from checkpoint: {since_id or 'beginning'}")
            
            # Search and process tweets
            tweets_iterator = self.search_with_pagination(since_id)
            self.process_batch_stream(tweets_iterator)
            
            # Finalize metrics
            self.metrics.end_time = datetime.utcnow()
            
            # Log execution end
            self.metrics_logger.log_execution_end(self.metrics.to_dict())
            
            # Emit custom metrics
            self.metrics_logger.emit_custom_metrics({
                'TweetsProcessed': float(self.metrics.tweets_processed),
                'APICallsMade': float(self.metrics.api_calls_made),
                'ErrorsEncountered': float(self.metrics.errors_encountered),
                'BatchesSent': float(self.metrics.batches_sent),
                'ExecutionDurationSeconds': self.metrics.execution_duration_seconds
            })
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Polling completed successfully',
                    'metrics': self.metrics.to_dict()
                })
            }
            
        except Exception as e:
            logger.error(f"Poller execution failed: {e}", exc_info=True)
            self.metrics_logger.log_error(
                type(e).__name__,
                str(e),
                {'metrics': self.metrics.to_dict()}
            )
            
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Polling failed',
                    'error': str(e)
                })
            }
