"""
Property-based tests for Checkpoint Manager.

Feature: twitter-poller-optimization
Property 9: Atomic Checkpoint Management
Property 10: Checkpoint Recovery and Initialization

These tests validate atomic checkpoint operations, conflict resolution,
and recovery mechanisms.
"""

import os
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

from hypothesis import given, settings, strategies as st, assume
from checkpoint_manager import CheckpointManager
from unittest.mock import Mock, patch
import boto3
from moto import mock_aws


@mock_aws
def create_test_table(table_name='test-checkpoint-table'):
    """Helper to create test DynamoDB table."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    return table


# Feature: twitter-poller-optimization, Property 9: Atomic Checkpoint Management
# Checkpoint validation should correctly identify valid and invalid tweet IDs
@settings(max_examples=100, deadline=None)
@given(
    tweet_id=st.one_of(
        st.integers(min_value=1, max_value=10**20).map(str),
        st.text(min_size=1, max_size=30),
        st.just('')
    )
)
@mock_aws
def test_checkpoint_validation(tweet_id):
    """
    Feature: twitter-poller-optimization
    Property 10: Checkpoint Recovery and Initialization
    
    Validates that checkpoint validation correctly identifies valid tweet IDs.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    is_valid = manager.validate_checkpoint(tweet_id)
    
    # Property: Empty strings should be invalid
    if not tweet_id:
        assert not is_valid, "Empty checkpoint should be invalid"
        return
    
    # Property: Non-numeric strings should be invalid
    try:
        tweet_id_int = int(tweet_id)
        if tweet_id_int <= 0:
            assert not is_valid, "Non-positive tweet IDs should be invalid"
        elif len(tweet_id) >= 10 and len(tweet_id) <= 25:
            assert is_valid, f"Valid numeric tweet ID {tweet_id} should be valid"
    except ValueError:
        assert not is_valid, f"Non-numeric tweet ID {tweet_id} should be invalid"


# Feature: twitter-poller-optimization, Property 9: Atomic Checkpoint Management
# Updates should only succeed if new ID is greater than current ID
@settings(max_examples=100, deadline=None)
@given(
    first_id=st.integers(min_value=1000000000, max_value=9999999999999),
    second_id=st.integers(min_value=1000000000, max_value=9999999999999)
)
@mock_aws
def test_atomic_update_only_increases(first_id, second_id):
    """
    Feature: twitter-poller-optimization
    Property 9: Atomic Checkpoint Management
    
    Validates that checkpoint updates only succeed when moving forward.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    # First update should succeed
    success1 = manager.update_checkpoint_atomic(str(first_id))
    assert success1, "First checkpoint update should succeed"
    
    # Second update behavior depends on comparison
    success2 = manager.update_checkpoint_atomic(str(second_id))
    
    # Property: Update should succeed only if second_id > first_id
    if second_id > first_id:
        assert success2, \
            f"Update should succeed when new ID ({second_id}) > current ID ({first_id})"
    else:
        assert not success2, \
            f"Update should fail when new ID ({second_id}) <= current ID ({first_id})"
    
    # Verify final state
    final_checkpoint = manager.get_last_checkpoint()
    expected = str(max(first_id, second_id))
    assert final_checkpoint == expected, \
        f"Final checkpoint should be max ID: expected {expected}, got {final_checkpoint}"


# Feature: twitter-poller-optimization, Property 9: Atomic Checkpoint Management
# Conflict resolution should always choose the maximum tweet ID
@settings(max_examples=100, deadline=None)
@given(
    attempted_id=st.integers(min_value=1000000000, max_value=9999999999999),
    current_id=st.integers(min_value=1000000000, max_value=9999999999999)
)
@mock_aws
def test_conflict_resolution_chooses_maximum(attempted_id, current_id):
    """
    Feature: twitter-poller-optimization
    Property 9: Atomic Checkpoint Management
    
    Validates that conflict resolution always chooses the maximum tweet ID.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    result = manager.handle_checkpoint_conflict(str(attempted_id), str(current_id))
    
    # Property: Result should be the maximum of the two IDs
    expected = str(max(attempted_id, current_id))
    assert result == expected, \
        f"Conflict resolution should choose max: expected {expected}, got {result}"


# Feature: twitter-poller-optimization, Property 10: Checkpoint Recovery and Initialization
# Recovery should handle corrupted checkpoints gracefully
@settings(max_examples=100, deadline=None)
@given(
    corrupted_value=st.one_of(
        st.text(min_size=1, max_size=20).filter(lambda x: not x.isdigit()),
        st.just(''),
        st.just('-123'),
        st.just('0')
    )
)
@mock_aws
def test_recovery_handles_corruption(corrupted_value):
    """
    Feature: twitter-poller-optimization
    Property 10: Checkpoint Recovery and Initialization
    
    Validates graceful handling of corrupted checkpoint data.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    # Insert corrupted checkpoint
    if corrupted_value:
        table.put_item(Item={'id': 'checkpoint', 'since_id': corrupted_value})
    
    # Attempt recovery
    recovered = manager.recover_from_corruption()
    
    # Property: Should either recover valid checkpoint or return None
    if recovered:
        assert manager.validate_checkpoint(recovered), \
            "Recovered checkpoint should be valid"
    else:
        # None is acceptable (indicates starting fresh)
        assert recovered is None, "Invalid recovery should return None"


# Feature: twitter-poller-optimization, Property 9: Atomic Checkpoint Management
# Multiple sequential updates should maintain order
@settings(max_examples=100, deadline=None)
@given(
    ids=st.lists(
        st.integers(min_value=1000000000, max_value=9999999999999),
        min_size=2,
        max_size=10,
        unique=True
    )
)
@mock_aws
def test_sequential_updates_maintain_order(ids):
    """
    Feature: twitter-poller-optimization
    Property 9: Atomic Checkpoint Management
    
    Validates that sequential updates maintain checkpoint ordering.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    # Track the maximum value we've successfully written
    max_written = 0
    
    for tweet_id in ids:
        # Get current checkpoint before update
        current = manager.get_last_checkpoint()
        current_int = int(current) if current else 0
        
        success = manager.update_checkpoint_atomic(str(tweet_id))
        
        # Property: Update succeeds only if ID is greater than current checkpoint
        if tweet_id > current_int:
            assert success, \
                f"Update should succeed for increasing ID {tweet_id} (current: {current_int})"
            max_written = max(max_written, tweet_id)
        else:
            assert not success, \
                f"Update should fail for non-increasing ID {tweet_id} (current: {current_int})"
    
    # Property: Final checkpoint should be the maximum ID from all updates
    final = manager.get_last_checkpoint()
    expected = str(max(ids))
    assert final == expected, \
        f"Final checkpoint should be max ID: expected {expected}, got {final}"


# Feature: twitter-poller-optimization, Property 10: Checkpoint Recovery and Initialization
# First run should handle missing checkpoint gracefully
@settings(max_examples=100, deadline=None)
@given(
    initial_id=st.integers(min_value=1000000000, max_value=9999999999999)
)
@mock_aws
def test_first_run_initialization(initial_id):
    """
    Feature: twitter-poller-optimization
    Property 10: Checkpoint Recovery and Initialization
    
    Validates proper initialization when no checkpoint exists.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    # Get checkpoint when none exists
    checkpoint = manager.get_last_checkpoint()
    
    # Property: Should return None when no checkpoint exists
    assert checkpoint is None, "Should return None when no checkpoint exists"
    
    # Property: First update should succeed
    success = manager.update_checkpoint_atomic(str(initial_id))
    assert success, "First checkpoint update should always succeed"
    
    # Property: Retrieved checkpoint should match what was set
    retrieved = manager.get_last_checkpoint()
    assert retrieved == str(initial_id), \
        f"Retrieved checkpoint should match: expected {initial_id}, got {retrieved}"


# Feature: twitter-poller-optimization, Property 9: Atomic Checkpoint Management
# Conflict resolution with None current ID should return attempted ID
@settings(max_examples=100, deadline=None)
@given(
    attempted_id=st.integers(min_value=1000000000, max_value=9999999999999)
)
@mock_aws
def test_conflict_resolution_with_none(attempted_id):
    """
    Feature: twitter-poller-optimization
    Property 9: Atomic Checkpoint Management
    
    Validates conflict resolution when current checkpoint is None.
    """
    table = create_test_table()
    manager = CheckpointManager('test-checkpoint-table')
    
    result = manager.handle_checkpoint_conflict(str(attempted_id), None)
    
    # Property: When current is None, should return attempted ID
    assert result == str(attempted_id), \
        f"With no current checkpoint, should return attempted ID"
