"""
Checkpoint manager with atomic operations for Twitter Poller.

This module manages checkpoint state in DynamoDB with atomic updates,
conflict resolution, and recovery mechanisms.
"""

import logging
from typing import Optional
import boto3
from boto3.dynamodb.conditions import Attr, Or
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint state with atomic DynamoDB operations."""
    
    RECORD_KEY = 'checkpoint'
    
    def __init__(self, table_name: str):
        """
        Initialize checkpoint manager.
        
        Args:
            table_name: Name of DynamoDB table for checkpoints
        """
        self.ddb = boto3.resource('dynamodb')
        self.table = self.ddb.Table(table_name)
        self.table_name = table_name
    
    def get_last_checkpoint(self) -> Optional[str]:
        """
        Retrieve the last checkpoint (since_id).
        
        Returns:
            Last since_id if exists, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={'id': self.RECORD_KEY}
            )
            
            if 'Item' in response:
                since_id = response['Item'].get('since_id')
                logger.info(f"Retrieved checkpoint: {since_id}")
                return since_id
            
            logger.info("No existing checkpoint found")
            return None
            
        except ClientError as e:
            logger.error(f"Failed to retrieve checkpoint: {e}")
            # Return None to allow process to continue with fresh start
            return None
    
    def update_checkpoint_atomic(self, since_id: str, previous_id: Optional[str] = None) -> bool:
        """
        Update checkpoint atomically using conditional write.
        
        This ensures that:
        1. Updates only succeed if since_id is greater than current value
        2. Concurrent executions don't overwrite each other's progress
        3. Checkpoint always moves forward, never backward
        
        Args:
            since_id: New checkpoint value (tweet ID)
            previous_id: Expected previous checkpoint (for validation)
            
        Returns:
            True if update succeeded, False if rejected by condition
        """
        try:
            # Convert to integer for numeric comparison
            since_id_int = int(since_id)
            
            # Use conditional write to ensure atomicity
            # Only update if:
            # 1. Item doesn't exist (first run), OR
            # 2. New since_id is greater than current since_id
            # Store as both string (for compatibility) and number (for comparison)
            self.table.put_item(
                Item={
                    'id': self.RECORD_KEY,
                    'since_id': since_id,
                    'since_id_num': since_id_int  # Numeric version for comparison
                },
                ConditionExpression=Or(
                    Attr('id').not_exists(),
                    Attr('since_id_num').lt(since_id_int)
                )
            )
            
            logger.info(f"Checkpoint updated successfully: {since_id}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Condition failed - either checkpoint exists with higher value
                # or concurrent update occurred
                logger.warning(
                    f"Checkpoint update rejected (conditional check failed). "
                    f"Attempted value: {since_id}"
                )
                return False
            else:
                # Other error - log and raise
                logger.error(f"Failed to update checkpoint: {e}")
                raise
    
    def handle_checkpoint_conflict(self, attempted_id: str, current_id: Optional[str]) -> str:
        """
        Resolve checkpoint conflict when concurrent updates occur.
        
        Strategy: Use the maximum tweet ID to ensure forward progress.
        
        Args:
            attempted_id: The ID we tried to update to
            current_id: The current ID in the database
            
        Returns:
            The ID that should be considered current
        """
        if not current_id:
            return attempted_id
        
        # Compare as integers to find the maximum
        try:
            attempted_int = int(attempted_id)
            current_int = int(current_id)
            
            if attempted_int > current_int:
                logger.info(
                    f"Attempted ID {attempted_id} is newer than current {current_id}. "
                    f"Will retry update."
                )
                return attempted_id
            else:
                logger.info(
                    f"Current ID {current_id} is newer than or equal to attempted {attempted_id}. "
                    f"No update needed."
                )
                return current_id
                
        except ValueError as e:
            logger.error(f"Invalid ID format for comparison: {e}")
            # If we can't compare, prefer the current stable value
            return current_id or attempted_id
    
    def validate_checkpoint(self, since_id: str) -> bool:
        """
        Validate that a checkpoint value is well-formed.
        
        Args:
            since_id: Checkpoint value to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not since_id:
            return False
        
        # Tweet IDs should be numeric strings
        try:
            tweet_id = int(since_id)
            # Tweet IDs should be positive and reasonable length
            if tweet_id <= 0:
                return False
            if len(since_id) < 10 or len(since_id) > 25:
                logger.warning(f"Tweet ID length unusual: {len(since_id)} digits")
            return True
        except ValueError:
            logger.error(f"Invalid tweet ID format: {since_id}")
            return False
    
    def recover_from_corruption(self) -> Optional[str]:
        """
        Attempt to recover from corrupted checkpoint data.
        
        Returns:
            Recovered checkpoint if possible, None to start fresh
        """
        try:
            current = self.get_last_checkpoint()
            
            if current and self.validate_checkpoint(current):
                logger.info(f"Checkpoint validation passed: {current}")
                return current
            
            logger.warning("Checkpoint corrupted or invalid. Starting fresh.")
            # Clear the corrupted checkpoint
            try:
                self.table.delete_item(
                    Key={'id': self.RECORD_KEY}
                )
            except ClientError as e:
                logger.error(f"Failed to clear corrupted checkpoint: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error during checkpoint recovery: {e}")
            return None
