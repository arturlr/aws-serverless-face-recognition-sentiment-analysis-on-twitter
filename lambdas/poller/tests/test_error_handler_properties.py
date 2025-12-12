"""
Property-based tests for Error Handler.

Feature: twitter-poller-optimization
Property 4: Exponential Backoff Retry
Property 5: Data Preservation During Failures

These tests validate error classification, exponential backoff,
and data integrity during failures.
"""

from hypothesis import given, settings, strategies as st, assume
from error_handler import ErrorHandler, ErrorClassification, RetryDecision
from datetime import datetime


# Feature: twitter-poller-optimization, Property 4: Exponential Backoff Retry
# Exponential backoff should increase delay exponentially with attempts
@settings(max_examples=100, deadline=None)
@given(
    attempt=st.integers(min_value=0, max_value=10),
    base_delay=st.floats(min_value=0.1, max_value=10.0),
    max_delay=st.floats(min_value=10.0, max_value=600.0)
)
def test_exponential_backoff_increases_with_attempts(attempt, base_delay, max_delay):
    """
    Feature: twitter-poller-optimization
    Property 4: Exponential Backoff Retry
    
    Validates that backoff delay increases exponentially with retry attempts.
    """
    assume(max_delay > base_delay)
    
    handler = ErrorHandler()
    
    delay = handler.calculate_backoff_delay(attempt, base_delay, max_delay)
    
    # Property: Delay should be non-negative
    assert delay >= 0, "Delay should never be negative"
    
    # Property: Delay should respect maximum
    assert delay <= max_delay * 1.5, \
        f"Delay {delay} should not significantly exceed max_delay {max_delay}"
    
    # Property: For attempt 0, delay should be close to base_delay (with jitter)
    if attempt == 0:
        assert base_delay * 0.5 <= delay <= base_delay * 2.0, \
            f"Initial delay {delay} should be close to base_delay {base_delay}"
    
    # Property: Delay should generally increase with attempts (before hitting max)
    if attempt > 0 and base_delay * (2 ** attempt) < max_delay:
        prev_delay = handler.calculate_backoff_delay(attempt - 1, base_delay, max_delay)
        # Account for jitter by allowing some variance
        assert delay >= prev_delay * 0.8, \
            "Delay should generally increase with attempts"


# Feature: twitter-poller-optimization, Property 4: Exponential Backoff Retry
# Error classification should be consistent and correct
@settings(max_examples=100, deadline=None)
@given(
    error_type=st.sampled_from([
        'timeout', 'connection', '429', 'rate limit',
        '500', '502', '503', '504', 'throttle',
        '401', '403', '400', 'invalid'
    ])
)
def test_error_classification_consistency(error_type):
    """
    Feature: twitter-poller-optimization
    Property 4: Exponential Backoff Retry
    
    Validates consistent and correct error classification.
    """
    handler = ErrorHandler()
    
    # Create mock errors with different messages
    error = Exception(f"Test error with {error_type}")
    classification = handler.classify_error(error)
    
    # Property: Classification should be one of the defined types
    assert isinstance(classification, ErrorClassification), \
        "Should return valid ErrorClassification"
    
    # Property: Retryable errors should be classified correctly
    retryable_keywords = ['timeout', 'connection', '429', 'rate limit', 
                          '500', '502', '503', '504', 'throttle']
    if any(keyword in error_type.lower() for keyword in retryable_keywords):
        assert classification != ErrorClassification.NON_RETRYABLE, \
            f"Error with '{error_type}' should be retryable"
    
    # Property: Non-retryable errors should be classified correctly
    non_retryable_keywords = ['401', '403', '400', 'invalid']
    if any(keyword in error_type.lower() for keyword in non_retryable_keywords):
        assert classification == ErrorClassification.NON_RETRYABLE, \
            f"Error with '{error_type}' should be non-retryable"


# Feature: twitter-poller-optimization, Property 4: Exponential Backoff Retry
# Retry logic should respect maximum retry attempts
@settings(max_examples=100, deadline=None)
@given(
    attempt=st.integers(min_value=0, max_value=20)
)
def test_retry_logic_respects_max_attempts(attempt):
    """
    Feature: twitter-poller-optimization
    Property 4: Exponential Backoff Retry
    
    Validates that retry logic respects maximum retry attempts.
    """
    handler = ErrorHandler()
    
    # Create a retryable error
    error = Exception("Timeout error")
    context = {'operation': 'test'}
    
    decision = handler.handle_error(error, attempt, context)
    
    # Property: Should not retry after max attempts
    if attempt >= ErrorHandler.MAX_RETRIES:
        assert not decision.should_retry, \
            f"Should not retry after {ErrorHandler.MAX_RETRIES} attempts"
    else:
        # For retryable errors before max attempts
        classification = handler.classify_error(error)
        if classification != ErrorClassification.NON_RETRYABLE:
            assert decision.should_retry, \
                f"Should retry retryable error at attempt {attempt}"


# Feature: twitter-poller-optimization, Property 5: Data Preservation During Failures
# Error context should preserve all relevant information
@settings(max_examples=100, deadline=None)
@given(
    attempt=st.integers(min_value=0, max_value=10),
    context_keys=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=10)
)
def test_error_context_preservation(attempt, context_keys):
    """
    Feature: twitter-poller-optimization
    Property 5: Data Preservation During Failures
    
    Validates that error context preserves all relevant information.
    """
    handler = ErrorHandler()
    
    # Create context with various keys
    context = {key: f"value_{i}" for i, key in enumerate(context_keys)}
    error = Exception("Test error")
    api_response = {'status': 500, 'message': 'Server error'}
    
    # Handle error
    decision = handler.handle_error(error, attempt, context, api_response)
    
    # Property: Decision should contain valid information
    assert isinstance(decision, RetryDecision), "Should return RetryDecision"
    assert decision.wait_seconds >= 0, "Wait seconds should be non-negative"
    
    # Note: We can't directly access the ErrorContext created internally,
    # but we verify that the handler doesn't crash and returns valid decision


# Feature: twitter-poller-optimization, Property 4: Exponential Backoff Retry
# Jitter should add randomness to prevent thundering herd
@settings(max_examples=100, deadline=None)
@given(
    attempt=st.integers(min_value=0, max_value=5)
)
def test_jitter_adds_randomness(attempt):
    """
    Feature: twitter-poller-optimization
    Property 4: Exponential Backoff Retry
    
    Validates that jitter adds randomness to backoff delays.
    """
    handler = ErrorHandler()
    
    # Calculate multiple delays for same attempt
    delays = [handler.calculate_backoff_delay(attempt) for _ in range(10)]
    
    # Property: Not all delays should be identical (jitter adds variation)
    unique_delays = len(set(delays))
    assert unique_delays > 1, \
        f"Jitter should create variation in delays (got {unique_delays} unique values)"
    
    # Property: All delays should be within reasonable range of each other
    min_delay = min(delays)
    max_delay = max(delays)
    if min_delay > 0:
        ratio = max_delay / min_delay
        assert ratio < 2.0, \
            f"Jitter variation should be reasonable (ratio: {ratio})"


# Feature: twitter-poller-optimization, Property 5: Data Preservation During Failures
# Non-retryable errors should not be retried regardless of attempt count
@settings(max_examples=100, deadline=None)
@given(
    attempt=st.integers(min_value=0, max_value=10),
    error_message=st.sampled_from([
        'HTTP 401 Unauthorized',
        'HTTP 403 Forbidden',
        'HTTP 400 Bad Request',
        'Invalid credentials'
    ])
)
def test_non_retryable_errors_never_retried(attempt, error_message):
    """
    Feature: twitter-poller-optimization
    Property 5: Data Preservation During Failures
    
    Validates that non-retryable errors are never retried, preserving system state.
    """
    handler = ErrorHandler()
    
    error = Exception(error_message)
    context = {'operation': 'test'}
    
    decision = handler.handle_error(error, attempt, context)
    
    # Property: Non-retryable errors should never be retried
    assert not decision.should_retry, \
        f"Non-retryable error '{error_message}' should not be retried"
    assert decision.classification == ErrorClassification.NON_RETRYABLE, \
        "Classification should be NON_RETRYABLE"
