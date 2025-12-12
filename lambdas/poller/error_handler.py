"""
Error handler with exponential backoff for Twitter Poller.

This module provides robust error handling with classification,
exponential backoff retry logic, and comprehensive error logging.
"""

import random
import time
import logging
from datetime import datetime
from typing import Optional, Tuple
from enum import Enum

from data_models import ErrorContext

logger = logging.getLogger(__name__)


class ErrorClassification(Enum):
    """Classification of error types."""
    RETRYABLE_TRANSIENT = "retryable_transient"
    RETRYABLE_RATE_LIMIT = "retryable_rate_limit"
    NON_RETRYABLE = "non_retryable"


class RetryDecision:
    """Decision about whether and how to retry an operation."""
    
    def __init__(
        self,
        should_retry: bool,
        wait_seconds: float = 0.0,
        classification: ErrorClassification = ErrorClassification.NON_RETRYABLE
    ):
        self.should_retry = should_retry
        self.wait_seconds = wait_seconds
        self.classification = classification


class ErrorHandler:
    """Handles errors with exponential backoff and intelligent retry logic."""
    
    # Maximum number of retry attempts
    MAX_RETRIES = 5
    
    # Base delay for exponential backoff (seconds)
    BASE_DELAY = 1.0
    
    # Maximum delay between retries (seconds)
    MAX_DELAY = 300.0
    
    # Jitter range (percentage of delay)
    JITTER_MIN = 0.1
    JITTER_MAX = 0.3
    
    def __init__(self):
        """Initialize error handler."""
        self.error_counts = {}
    
    def classify_error(self, error: Exception) -> ErrorClassification:
        """
        Classify an error to determine if it's retryable.
        
        Args:
            error: The exception to classify
            
        Returns:
            ErrorClassification indicating retry strategy
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Rate limit errors
        if 'rate limit' in error_str or '429' in error_str:
            return ErrorClassification.RETRYABLE_RATE_LIMIT
        
        # Network and timeout errors (transient)
        if any(keyword in error_str for keyword in [
            'timeout', 'connection', 'network', 'temporary',
            'socket', 'dns', 'unreachable'
        ]):
            return ErrorClassification.RETRYABLE_TRANSIENT
        
        # HTTP 5xx errors (server-side, usually transient)
        if any(code in error_str for code in ['500', '502', '503', '504']):
            return ErrorClassification.RETRYABLE_TRANSIENT
        
        # DynamoDB throttling
        if 'throttl' in error_str or 'provisionedthroughputexceeded' in error_str.replace(' ', ''):
            return ErrorClassification.RETRYABLE_TRANSIENT
        
        # Non-retryable errors
        if any(keyword in error_str for keyword in [
            '401', '403', 'unauthorized', 'forbidden',
            '400', 'bad request', 'invalid'
        ]):
            return ErrorClassification.NON_RETRYABLE
        
        # Default to non-retryable for unknown errors
        logger.warning(f"Unknown error type '{error_type}': {error_str}. Treating as non-retryable.")
        return ErrorClassification.NON_RETRYABLE
    
    def calculate_backoff_delay(
        self,
        attempt: int,
        base_delay: float = None,
        max_delay: float = None
    ) -> float:
        """
        Calculate exponential backoff delay with jitter.
        
        Args:
            attempt: Current attempt number (0-indexed)
            base_delay: Base delay in seconds (uses class default if None)
            max_delay: Maximum delay in seconds (uses class default if None)
            
        Returns:
            Delay in seconds to wait before retry
        """
        if base_delay is None:
            base_delay = self.BASE_DELAY
        if max_delay is None:
            max_delay = self.MAX_DELAY
        
        # Calculate exponential delay: base * 2^attempt
        delay = min(base_delay * (2 ** attempt), max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(self.JITTER_MIN, self.JITTER_MAX) * delay
        
        return delay + jitter
    
    def handle_error(
        self,
        error: Exception,
        attempt: int,
        context: dict,
        api_response: Optional[dict] = None
    ) -> RetryDecision:
        """
        Handle an error and determine retry strategy.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)
            context: Context information about the operation
            api_response: Optional API response data
            
        Returns:
            RetryDecision indicating whether and how to retry
        """
        classification = self.classify_error(error)
        
        # Create error context for logging
        error_context = ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error),
            attempt_number=attempt,
            timestamp=datetime.utcnow(),
            function_context=context,
            api_response=api_response,
            is_retryable=classification != ErrorClassification.NON_RETRYABLE
        )
        
        # Log error with context
        self.log_error_context(error_context)
        
        # Check if we should retry
        if classification == ErrorClassification.NON_RETRYABLE:
            return RetryDecision(
                should_retry=False,
                classification=classification
            )
        
        if attempt >= self.MAX_RETRIES:
            logger.error(f"Max retries ({self.MAX_RETRIES}) exceeded for {error_context.error_type}")
            return RetryDecision(
                should_retry=False,
                classification=classification
            )
        
        # Calculate backoff delay
        if classification == ErrorClassification.RETRYABLE_RATE_LIMIT:
            # For rate limits, use longer delays
            wait_seconds = self.calculate_backoff_delay(attempt, base_delay=5.0)
        else:
            # For transient errors, use standard backoff
            wait_seconds = self.calculate_backoff_delay(attempt)
        
        logger.info(
            f"Retrying after {wait_seconds:.2f}s "
            f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
        )
        
        return RetryDecision(
            should_retry=True,
            wait_seconds=wait_seconds,
            classification=classification
        )
    
    def execute_with_retry(self, func, *args, context: dict = None, **kwargs):
        """
        Execute a function with automatic retry on failures.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            context: Context information for error logging
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func execution
            
        Raises:
            Exception: If all retries are exhausted
        """
        if context is None:
            context = {'function': func.__name__}
        
        last_error = None
        
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if attempt == self.MAX_RETRIES:
                    # Final attempt failed
                    logger.error(f"All retry attempts exhausted for {func.__name__}")
                    raise
                
                decision = self.handle_error(e, attempt, context)
                
                if not decision.should_retry:
                    raise
                
                # Wait before retry
                if decision.wait_seconds > 0:
                    time.sleep(decision.wait_seconds)
        
        # Should not reach here, but raise last error if we do
        raise last_error
    
    def log_error_context(self, error_context: ErrorContext) -> None:
        """
        Log detailed error context for debugging.
        
        Args:
            error_context: ErrorContext with error details
        """
        log_data = error_context.to_dict()
        
        if error_context.is_retryable:
            logger.warning(f"Retryable error encountered: {log_data}")
        else:
            logger.error(f"Non-retryable error encountered: {log_data}")
