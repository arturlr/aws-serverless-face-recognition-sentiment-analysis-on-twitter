"""
Metrics and logging module for Twitter Poller.

This module provides comprehensive logging with correlation IDs,
custom CloudWatch metrics, and performance tracking.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetricsLogger:
    """Comprehensive logging and metrics collection for poller execution."""
    
    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize metrics logger.
        
        Args:
            correlation_id: Optional correlation ID for request tracking
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.start_time = datetime.utcnow()
    
    def log_execution_start(self, context: Dict[str, Any]) -> str:
        """
        Log execution start with context.
        
        Args:
            context: Execution context information
            
        Returns:
            Correlation ID for this execution
        """
        log_data = {
            'event': 'execution_start',
            'correlation_id': self.correlation_id,
            'timestamp': self.start_time.isoformat(),
            'context': context
        }
        logger.info(json.dumps(log_data))
        return self.correlation_id
    
    def log_execution_end(self, metrics: Dict[str, Any]) -> None:
        """
        Log execution end with metrics.
        
        Args:
            metrics: Execution metrics to log
        """
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()
        
        log_data = {
            'event': 'execution_end',
            'correlation_id': self.correlation_id,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'metrics': metrics
        }
        logger.info(json.dumps(log_data))
    
    def log_api_call(
        self,
        endpoint: str,
        response_time: float,
        status: int,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log API call details.
        
        Args:
            endpoint: API endpoint called
            response_time: Response time in seconds
            status: HTTP status code
            details: Optional additional details
        """
        log_data = {
            'event': 'api_call',
            'correlation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'endpoint': endpoint,
            'response_time_seconds': response_time,
            'status_code': status,
            'details': details or {}
        }
        logger.info(json.dumps(log_data))
    
    def log_rate_limit_encounter(
        self,
        remaining: int,
        limit: int,
        reset_time: int,
        wait_seconds: int
    ) -> None:
        """
        Log rate limit encounter.
        
        Args:
            remaining: Remaining requests
            limit: Total request limit
            reset_time: Unix timestamp of reset
            wait_seconds: Seconds to wait
        """
        utilization = ((limit - remaining) / limit * 100) if limit > 0 else 0
        
        log_data = {
            'event': 'rate_limit_encounter',
            'correlation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'remaining_requests': remaining,
            'total_limit': limit,
            'utilization_percentage': utilization,
            'reset_timestamp': reset_time,
            'wait_seconds': wait_seconds
        }
        logger.warning(json.dumps(log_data))
    
    def log_checkpoint_update(
        self,
        previous_id: Optional[str],
        new_id: str,
        success: bool
    ) -> None:
        """
        Log checkpoint update operation.
        
        Args:
            previous_id: Previous checkpoint value
            new_id: New checkpoint value
            success: Whether update succeeded
        """
        log_data = {
            'event': 'checkpoint_update',
            'correlation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'previous_checkpoint': previous_id,
            'new_checkpoint': new_id,
            'success': success
        }
        logger.info(json.dumps(log_data))
    
    def log_batch_sent(
        self,
        batch_number: int,
        batch_size: int,
        function_name: str,
        success: bool
    ) -> None:
        """
        Log batch processing invocation.
        
        Args:
            batch_number: Batch sequence number
            batch_size: Number of tweets in batch
            function_name: Target Lambda function name
            success: Whether invocation succeeded
        """
        log_data = {
            'event': 'batch_sent',
            'correlation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'batch_number': batch_number,
            'batch_size': batch_size,
            'target_function': function_name,
            'success': success
        }
        logger.info(json.dumps(log_data))
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any]
    ) -> None:
        """
        Log error with context.
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Error context
        """
        log_data = {
            'event': 'error',
            'correlation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'context': context
        }
        logger.error(json.dumps(log_data))
    
    def emit_custom_metrics(self, metrics: Dict[str, float]) -> None:
        """
        Emit custom CloudWatch metrics.
        
        Note: This uses structured logging. In production, this would
        integrate with CloudWatch Embedded Metric Format.
        
        Args:
            metrics: Dictionary of metric name to value
        """
        log_data = {
            'event': 'custom_metrics',
            'correlation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': metrics
        }
        logger.info(json.dumps(log_data))
