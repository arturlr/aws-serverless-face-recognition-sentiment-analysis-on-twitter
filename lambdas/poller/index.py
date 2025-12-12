"""
Enhanced Twitter Poller Lambda Handler.

This module serves as the entry point for the optimized Twitter poller,
integrating all enhanced components for production use.
"""

import os
from twitter_poller_optimized import TwitterPollerOptimized


def handler(event, context):
    """
    Lambda handler for enhanced Twitter polling.
    
    Args:
        event: Lambda event (unused for scheduled execution)
        context: Lambda context
        
    Returns:
        Response with execution status and metrics
    """
    # Get configuration from environment variables
    search_text = os.getenv('SEARCH_TEXT')
    checkpoint_table_name = os.getenv('SEARCH_CHECKPOINT_TABLE_NAME')
    processor_function_name = os.getenv('TWEET_PROCESSOR_FUNCTION_NAME')
    batch_size = int(os.getenv('BATCH_SIZE', '25'))
    ssm_parameter_prefix = os.getenv('SSM_PARAMETER_PREFIX', 'twitter-event-source')
    
    # Create and execute enhanced poller
    poller = TwitterPollerOptimized(
        search_text=search_text,
        checkpoint_table_name=checkpoint_table_name,
        processor_function_name=processor_function_name,
        batch_size=batch_size,
        ssm_parameter_prefix=ssm_parameter_prefix
    )
    
    return poller.execute()

