"""
Property-based tests for Data Models and Metrics Logger.

Feature: twitter-poller-optimization
Property 6: Comprehensive Execution Logging
Property 7: Memory-Efficient Processing

These tests validate data model integrity and comprehensive logging.
"""

from hypothesis import given, settings, strategies as st, assume
from datetime import datetime, timedelta
from data_models import (
    TweetData, RateLimitStatus, ExecutionMetrics, ErrorContext
)
from metrics_logger import MetricsLogger


# Feature: twitter-poller-optimization, Property 7: Memory-Efficient Processing
# TweetData should properly serialize to dictionary
@settings(max_examples=100, deadline=None)
@given(
    tweet_id=st.integers(min_value=1, max_value=10**20).map(str),
    text=st.text(min_size=1, max_size=280),
    has_created_at=st.booleans(),
    has_user_id=st.booleans()
)
def test_tweet_data_serialization(tweet_id, text, has_created_at, has_user_id):
    """
    Feature: twitter-poller-optimization
    Property 7: Memory-Efficient Processing
    
    Validates that TweetData properly serializes without data loss.
    """
    created_at = '2024-01-01T00:00:00Z' if has_created_at else None
    user_id = '123456' if has_user_id else None
    
    tweet = TweetData(
        id=tweet_id,
        id_str=tweet_id,
        full_text=text,
        extended_entities={'media': []},
        created_at=created_at,
        user_id=user_id
    )
    
    # Serialize to dict
    data_dict = tweet.to_dict()
    
    # Property: All fields should be present in serialized form
    assert 'id' in data_dict
    assert 'id_str' in data_dict
    assert 'full_text' in data_dict
    assert 'extended_entities' in data_dict
    
    # Property: Values should match original
    assert data_dict['id'] == tweet_id
    assert data_dict['full_text'] == text
    assert data_dict['created_at'] == created_at
    assert data_dict['user_id'] == user_id


# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance
# RateLimitStatus calculations should be mathematically correct
@settings(max_examples=100, deadline=None)
@given(
    limit=st.integers(min_value=1, max_value=1000),
    remaining=st.integers(min_value=0, max_value=1000)
)
def test_rate_limit_status_calculations(limit, remaining):
    """
    Feature: twitter-poller-optimization
    Property 1: Rate Limit Compliance and Management
    
    Validates mathematical correctness of rate limit calculations.
    """
    # Ensure remaining doesn't exceed limit
    remaining = min(remaining, limit)
    
    status = RateLimitStatus(
        remaining_requests=remaining,
        reset_time=1234567890,
        limit=limit
    )
    
    # Property: is_exhausted should be True only when remaining is 0
    assert status.is_exhausted == (remaining == 0)
    
    # Property: Utilization percentage should be accurate
    expected_utilization = ((limit - remaining) / limit) * 100
    assert abs(status.utilization_percentage - expected_utilization) < 0.01, \
        f"Utilization calculation incorrect: expected {expected_utilization}, " \
        f"got {status.utilization_percentage}"
    
    # Property: Utilization should be in valid range
    assert 0 <= status.utilization_percentage <= 100


# Feature: twitter-poller-optimization, Property 6: Comprehensive Execution Logging
# ExecutionMetrics should track all required fields
@settings(max_examples=100, deadline=None)
@given(
    tweets=st.integers(min_value=0, max_value=10000),
    api_calls=st.integers(min_value=0, max_value=1000),
    errors=st.integers(min_value=0, max_value=100),
    batches=st.integers(min_value=0, max_value=500),
    duration_seconds=st.integers(min_value=1, max_value=3600)
)
def test_execution_metrics_completeness(tweets, api_calls, errors, batches, duration_seconds):
    """
    Feature: twitter-poller-optimization
    Property 6: Comprehensive Execution Logging
    
    Validates that ExecutionMetrics tracks all required information.
    """
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(seconds=duration_seconds)
    
    metrics = ExecutionMetrics(
        start_time=start_time,
        end_time=end_time,
        tweets_processed=tweets,
        api_calls_made=api_calls,
        errors_encountered=errors,
        batches_sent=batches
    )
    
    # Property: Duration calculation should be accurate
    expected_duration = duration_seconds
    actual_duration = metrics.execution_duration_seconds
    assert abs(actual_duration - expected_duration) < 1.0, \
        f"Duration calculation incorrect: expected {expected_duration}, got {actual_duration}"
    
    # Serialize to dict
    metrics_dict = metrics.to_dict()
    
    # Property: All essential fields should be present
    required_fields = [
        'start_time', 'end_time', 'duration_seconds',
        'tweets_processed', 'api_calls_made', 'errors_encountered',
        'batches_sent', 'checkpoint_updates'
    ]
    for field in required_fields:
        assert field in metrics_dict, f"Required field '{field}' missing from metrics"
    
    # Property: Numeric values should match
    assert metrics_dict['tweets_processed'] == tweets
    assert metrics_dict['api_calls_made'] == api_calls
    assert metrics_dict['errors_encountered'] == errors
    assert metrics_dict['batches_sent'] == batches


# Feature: twitter-poller-optimization, Property 5: Data Preservation During Failures
# ErrorContext should preserve all error information
@settings(max_examples=100, deadline=None)
@given(
    error_type=st.text(min_size=1, max_size=50),
    error_message=st.text(min_size=1, max_size=200),
    attempt=st.integers(min_value=0, max_value=10),
    is_retryable=st.booleans()
)
def test_error_context_preservation(error_type, error_message, attempt, is_retryable):
    """
    Feature: twitter-poller-optimization
    Property 5: Data Preservation During Failures
    
    Validates that ErrorContext preserves all error information.
    """
    timestamp = datetime.utcnow()
    context = {'operation': 'test', 'key': 'value'}
    api_response = {'status': 500}
    
    error_ctx = ErrorContext(
        error_type=error_type,
        error_message=error_message,
        attempt_number=attempt,
        timestamp=timestamp,
        function_context=context,
        api_response=api_response,
        is_retryable=is_retryable
    )
    
    # Serialize to dict
    error_dict = error_ctx.to_dict()
    
    # Property: All fields should be preserved
    assert error_dict['error_type'] == error_type
    assert error_dict['error_message'] == error_message
    assert error_dict['attempt_number'] == attempt
    assert error_dict['is_retryable'] == is_retryable
    assert error_dict['function_context'] == context
    assert error_dict['api_response'] == api_response


# Feature: twitter-poller-optimization, Property 6: Comprehensive Execution Logging
# MetricsLogger should generate valid correlation IDs
@settings(max_examples=100, deadline=None)
@given(
    has_correlation_id=st.booleans()
)
def test_metrics_logger_correlation_ids(has_correlation_id):
    """
    Feature: twitter-poller-optimization
    Property 6: Comprehensive Execution Logging
    
    Validates that MetricsLogger generates valid correlation IDs.
    """
    if has_correlation_id:
        correlation_id = 'test-correlation-123'
        logger = MetricsLogger(correlation_id=correlation_id)
        assert logger.correlation_id == correlation_id
    else:
        logger = MetricsLogger()
        # Property: Should generate a correlation ID automatically
        assert logger.correlation_id is not None
        assert len(logger.correlation_id) > 0
    
    # Property: Correlation ID should be consistent across operations
    context = {'test': 'data'}
    returned_id = logger.log_execution_start(context)
    assert returned_id == logger.correlation_id


# Feature: twitter-poller-optimization, Property 6: Comprehensive Execution Logging
# Logging should not crash with various input types
@settings(max_examples=100, deadline=None)
@given(
    endpoint=st.text(min_size=1, max_size=100),
    response_time=st.floats(min_value=0.0, max_value=300.0, allow_nan=False),
    status=st.integers(min_value=200, max_value=599)
)
def test_logging_robustness(endpoint, response_time, status):
    """
    Feature: twitter-poller-optimization
    Property 6: Comprehensive Execution Logging
    
    Validates that logging operations are robust to various inputs.
    """
    logger = MetricsLogger()
    
    # Should not raise exceptions
    try:
        logger.log_api_call(endpoint, response_time, status)
        logger.log_rate_limit_encounter(50, 100, 1234567890, 10)
        logger.log_checkpoint_update('123', '456', True)
        logger.log_batch_sent(1, 25, 'test-function', True)
        logger.log_error('TestError', 'Test message', {'key': 'value'})
        logger.emit_custom_metrics({'metric1': 1.0, 'metric2': 2.0})
    except Exception as e:
        assert False, f"Logging should not raise exception: {e}"


# Feature: twitter-poller-optimization, Property 7: Memory-Efficient Processing
# ExecutionMetrics should handle incomplete executions
@settings(max_examples=100, deadline=None)
@given(
    has_end_time=st.booleans()
)
def test_metrics_with_incomplete_execution(has_end_time):
    """
    Feature: twitter-poller-optimization
    Property 7: Memory-Efficient Processing
    
    Validates that metrics handle incomplete executions gracefully.
    """
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(seconds=60) if has_end_time else None
    
    metrics = ExecutionMetrics(
        start_time=start_time,
        end_time=end_time
    )
    
    # Property: Should calculate duration even without end_time
    duration = metrics.execution_duration_seconds
    assert duration >= 0, "Duration should be non-negative"
    
    # Property: to_dict() should work even with None end_time
    metrics_dict = metrics.to_dict()
    assert 'end_time' in metrics_dict
    assert 'duration_seconds' in metrics_dict
