"""
Rate limit manager for X API v2.

This module manages API rate limits, implements intelligent backoff,
and ensures compliance with X API rate limiting policies.
"""

import time
from datetime import datetime
from typing import Dict, Optional
import logging

from data_models import RateLimitStatus

logger = logging.getLogger(__name__)


class RateLimitManager:
    """Manages X API rate limits and implements intelligent backoff strategies."""
    
    # Conservative threshold: pause when 20% of requests remain
    PROACTIVE_THRESHOLD = 0.2
    
    # Minimum wait between requests when approaching limits (seconds)
    MIN_REQUEST_INTERVAL = 1.0
    
    def __init__(self):
        """Initialize rate limit manager."""
        self.current_status: Optional[RateLimitStatus] = None
        self.last_request_time: Optional[float] = None
    
    def parse_rate_limit_headers(self, headers: Dict[str, str]) -> RateLimitStatus:
        """
        Parse rate limit information from API response headers.
        
        Args:
            headers: HTTP response headers from X API
            
        Returns:
            RateLimitStatus with current rate limit information
        """
        try:
            limit = int(headers.get('x-rate-limit-limit', 0))
            remaining = int(headers.get('x-rate-limit-remaining', 0))
            reset = int(headers.get('x-rate-limit-reset', 0))
            
            # Calculate if we should proactively wait
            should_wait = False
            wait_seconds = 0
            
            if limit > 0:
                utilization = (limit - remaining) / limit
                if utilization >= (1.0 - self.PROACTIVE_THRESHOLD):
                    should_wait = True
                    current_time = int(time.time())
                    wait_seconds = max(0, reset - current_time)
            
            status = RateLimitStatus(
                remaining_requests=remaining,
                reset_time=reset,
                limit=limit,
                should_wait=should_wait,
                wait_seconds=wait_seconds
            )
            
            self.current_status = status
            return status
            
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")
            # Return conservative default status
            return RateLimitStatus(
                remaining_requests=1,
                reset_time=int(time.time()) + 900,  # 15 minutes
                limit=1,
                should_wait=False,
                wait_seconds=0
            )
    
    def calculate_wait_time(self, remaining_requests: int, reset_time: int) -> int:
        """
        Calculate optimal wait time based on rate limit status.
        
        Args:
            remaining_requests: Number of requests remaining
            reset_time: Unix timestamp when rate limit resets
            
        Returns:
            Number of seconds to wait
        """
        if remaining_requests <= 0:
            # Rate limit exhausted - wait until reset
            current_time = int(time.time())
            return max(0, reset_time - current_time)
        
        # Calculate time until reset
        current_time = int(time.time())
        time_until_reset = max(0, reset_time - current_time)
        
        if remaining_requests > 0 and time_until_reset > 0:
            # Distribute remaining requests evenly over time
            return min(int(time_until_reset / remaining_requests), 60)
        
        return 0
    
    def should_continue_requests(self) -> bool:
        """
        Determine if more requests can be made based on current rate limit status.
        
        Returns:
            True if more requests can be made, False otherwise
        """
        if not self.current_status:
            return True
        
        if self.current_status.is_exhausted:
            return False
        
        # Check if we're in proactive throttling mode
        if self.current_status.should_wait:
            current_time = int(time.time())
            if current_time < self.current_status.reset_time:
                return False
        
        return True
    
    def wait_if_needed(self, force: bool = False) -> int:
        """
        Wait if rate limits require it.
        
        Args:
            force: If True, wait even if not strictly necessary (proactive throttling)
            
        Returns:
            Number of seconds waited
        """
        if not self.current_status:
            return 0
        
        wait_seconds = 0
        
        # Handle exhausted rate limits
        if self.current_status.is_exhausted:
            wait_seconds = self.calculate_wait_time(
                self.current_status.remaining_requests,
                self.current_status.reset_time
            )
            if wait_seconds > 0:
                logger.info(f"Rate limit exhausted. Waiting {wait_seconds} seconds until reset.")
                time.sleep(wait_seconds)
                return wait_seconds
        
        # Handle proactive throttling
        if force or self.current_status.should_wait:
            wait_seconds = min(self.current_status.wait_seconds, 300)  # Cap at 5 minutes
            if wait_seconds > 0:
                logger.info(f"Proactive rate limit throttling. Waiting {wait_seconds} seconds.")
                time.sleep(wait_seconds)
                return wait_seconds
        
        # Enforce minimum interval between requests
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                interval_wait = self.MIN_REQUEST_INTERVAL - elapsed
                time.sleep(interval_wait)
                wait_seconds = interval_wait
        
        self.last_request_time = time.time()
        return wait_seconds
    
    def log_status(self) -> None:
        """Log current rate limit status."""
        if self.current_status:
            logger.info(
                f"Rate limit status: {self.current_status.remaining_requests}/"
                f"{self.current_status.limit} remaining "
                f"({self.current_status.utilization_percentage:.1f}% used)"
            )
