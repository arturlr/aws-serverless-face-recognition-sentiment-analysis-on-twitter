"""
Property-based tests for Rate Limit Manager.

Feature: twitter-poller-optimization
Property 1: Rate Limit Compliance and Management

These tests validate that the rate limit manager respects API rate limits,
implements appropriate backoff, and continues processing correctly.
"""

import time
from hypothesis import given, settings, strategies as st
from rate_limit_manager import RateLimitManager
from data_models import RateLimitStatus


# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance and Management
# For any API execution session, the system should respect all documented rate limits
@settings(max_examples=100, deadline=None)
@given(
    limit=st.integers(min_value=1, max_value=1000),
    remaining=st.integers(min_value=0, max_value=1000),
    reset_offset=st.integers(min_value=0, max_value=3600)
)
def test_rate_limit_never_exceeds_api_limits(limit, remaining, reset_offset):
    """
    Feature: twitter-poller-optimization
    Property 1: Rate Limit Compliance and Management
    
    Validates that rate limit manager never allows requests when limit is exhausted.
    """
    # Ensure remaining is within limit
    remaining = min(remaining, limit)
    reset_time = int(time.time()) + reset_offset
    
    manager = RateLimitManager()
    
    # Parse mock rate limit headers
    headers = {
        'x-rate-limit-limit': str(limit),
        'x-rate-limit-remaining': str(remaining),
        'x-rate-limit-reset': str(reset_time)
    }
    
    status = manager.parse_rate_limit_headers(headers)
    
    # Property: When rate limit is exhausted, should_continue_requests must return False
    if remaining == 0:
        assert not manager.should_continue_requests(), \
            "Manager should not allow requests when rate limit is exhausted"
        assert status.is_exhausted, "Status should indicate exhaustion"
    
    # Property: Remaining requests should never be negative
    assert status.remaining_requests >= 0, \
        "Remaining requests should never be negative"
    
    # Property: Utilization should be between 0 and 100
    assert 0 <= status.utilization_percentage <= 100, \
        "Utilization percentage should be between 0 and 100"


# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance and Management
# For any API execution session, implement appropriate backoff when limits are approached
@settings(max_examples=100, deadline=None)
@given(
    limit=st.integers(min_value=10, max_value=100),
    utilization=st.floats(min_value=0.0, max_value=1.0)
)
def test_proactive_throttling_when_approaching_limits(limit, utilization):
    """
    Feature: twitter-poller-optimization
    Property 1: Rate Limit Compliance and Management
    
    Validates proactive throttling when approaching rate limits.
    """
    remaining = max(0, int(limit * (1 - utilization)))
    reset_time = int(time.time()) + 900  # 15 minutes
    
    manager = RateLimitManager()
    
    headers = {
        'x-rate-limit-limit': str(limit),
        'x-rate-limit-remaining': str(remaining),
        'x-rate-limit-reset': str(reset_time)
    }
    
    status = manager.parse_rate_limit_headers(headers)
    
    # Property: When utilization exceeds threshold, should recommend waiting
    threshold = 1.0 - RateLimitManager.PROACTIVE_THRESHOLD
    if utilization >= threshold:
        assert status.should_wait, \
            f"Should recommend waiting when utilization ({utilization:.2f}) " \
            f"exceeds threshold ({threshold:.2f})"


# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance and Management
# Wait time calculation should be reasonable and never negative
@settings(max_examples=100, deadline=None)
@given(
    remaining=st.integers(min_value=0, max_value=100),
    time_until_reset=st.integers(min_value=0, max_value=3600)
)
def test_wait_time_calculation_is_reasonable(remaining, time_until_reset):
    """
    Feature: twitter-poller-optimization
    Property 1: Rate Limit Compliance and Management
    
    Validates that wait time calculations are reasonable and safe.
    """
    manager = RateLimitManager()
    current_time = int(time.time())
    reset_time = current_time + time_until_reset
    
    wait_seconds = manager.calculate_wait_time(remaining, reset_time)
    
    # Property: Wait time should never be negative
    assert wait_seconds >= 0, "Wait time should never be negative"
    
    # Property: When exhausted, wait time should equal time until reset
    if remaining == 0:
        assert wait_seconds == time_until_reset, \
            "When exhausted, wait time should equal time until reset"
    
    # Property: Wait time should not exceed time until reset
    assert wait_seconds <= time_until_reset + 1, \
        "Wait time should not exceed time until reset"


# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance and Management
# Rate limit status parsing should be robust to malformed headers
@settings(max_examples=100, deadline=None)
@given(
    has_limit=st.booleans(),
    has_remaining=st.booleans(),
    has_reset=st.booleans()
)
def test_rate_limit_parsing_handles_missing_headers(has_limit, has_remaining, has_reset):
    """
    Feature: twitter-poller-optimization
    Property 1: Rate Limit Compliance and Management
    
    Validates robust handling of malformed or missing rate limit headers.
    """
    manager = RateLimitManager()
    
    headers = {}
    if has_limit:
        headers['x-rate-limit-limit'] = '100'
    if has_remaining:
        headers['x-rate-limit-remaining'] = '50'
    if has_reset:
        headers['x-rate-limit-reset'] = str(int(time.time()) + 900)
    
    # Should not raise exception
    status = manager.parse_rate_limit_headers(headers)
    
    # Property: Should always return a valid RateLimitStatus
    assert isinstance(status, RateLimitStatus), \
        "Should always return a RateLimitStatus object"
    
    # Property: All fields should have non-None values
    assert status.remaining_requests is not None
    assert status.reset_time is not None
    assert status.limit is not None


# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance and Management
# Minimum interval between requests should be enforced
@settings(max_examples=100, deadline=None)
@given(
    interval_count=st.integers(min_value=1, max_value=10)
)
def test_minimum_request_interval_enforcement(interval_count):
    """
    Feature: twitter-poller-optimization
    Property 1: Rate Limit Compliance and Management
    
    Validates that minimum interval between requests is enforced.
    """
    manager = RateLimitManager()
    
    # Set up a status that doesn't require waiting
    headers = {
        'x-rate-limit-limit': '100',
        'x-rate-limit-remaining': '100',
        'x-rate-limit-reset': str(int(time.time()) + 900)
    }
    manager.parse_rate_limit_headers(headers)
    
    # First request should not wait
    wait1 = manager.wait_if_needed()
    start_time = time.time()
    
    # Subsequent rapid requests should enforce minimum interval
    total_wait = 0
    for _ in range(interval_count):
        wait = manager.wait_if_needed()
        total_wait += wait
    
    elapsed = time.time() - start_time
    
    # Property: Total elapsed time should be at least minimum interval * count
    # (with some tolerance for timing precision)
    expected_minimum = RateLimitManager.MIN_REQUEST_INTERVAL * interval_count
    assert elapsed >= expected_minimum * 0.9, \
        f"Should enforce minimum interval. Expected ~{expected_minimum}s, got {elapsed}s"
