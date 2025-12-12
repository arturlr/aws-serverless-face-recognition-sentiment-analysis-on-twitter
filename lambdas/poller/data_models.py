"""
Data models for Twitter Poller optimization.

This module defines core data structures used throughout the poller implementation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class TweetData:
    """Represents a tweet with its essential data."""
    id: str
    id_str: str
    full_text: str
    extended_entities: Dict[str, Any]
    created_at: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization."""
        return {
            'id': self.id,
            'id_str': self.id_str,
            'full_text': self.full_text,
            'extended_entities': self.extended_entities,
            'created_at': self.created_at,
            'user_id': self.user_id
        }


@dataclass
class RateLimitStatus:
    """Rate limit status from X API headers."""
    remaining_requests: int
    reset_time: int
    limit: int
    should_wait: bool = False
    wait_seconds: int = 0

    @property
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining_requests <= 0

    @property
    def utilization_percentage(self) -> float:
        """Calculate percentage of rate limit used."""
        if self.limit == 0:
            return 0.0
        return ((self.limit - self.remaining_requests) / self.limit) * 100


@dataclass
class ExecutionMetrics:
    """Tracks metrics for a poller execution."""
    start_time: datetime
    end_time: Optional[datetime] = None
    tweets_processed: int = 0
    api_calls_made: int = 0
    errors_encountered: int = 0
    batches_sent: int = 0
    checkpoint_updates: int = 0
    rate_limit_waits: int = 0
    total_wait_seconds: float = 0.0

    @property
    def execution_duration_seconds(self) -> float:
        """Calculate execution duration in seconds."""
        if not self.end_time:
            return (datetime.utcnow() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.execution_duration_seconds,
            'tweets_processed': self.tweets_processed,
            'api_calls_made': self.api_calls_made,
            'errors_encountered': self.errors_encountered,
            'batches_sent': self.batches_sent,
            'checkpoint_updates': self.checkpoint_updates,
            'rate_limit_waits': self.rate_limit_waits,
            'total_wait_seconds': self.total_wait_seconds
        }


@dataclass
class ErrorContext:
    """Context information for errors."""
    error_type: str
    error_message: str
    attempt_number: int
    timestamp: datetime
    function_context: Dict[str, Any]
    api_response: Optional[Dict] = None
    is_retryable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'error_type': self.error_type,
            'error_message': self.error_message,
            'attempt_number': self.attempt_number,
            'timestamp': self.timestamp.isoformat(),
            'function_context': self.function_context,
            'api_response': self.api_response,
            'is_retryable': self.is_retryable
        }
