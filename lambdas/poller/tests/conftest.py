"""
Pytest configuration and fixtures for Twitter Poller tests.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import pytest
from unittest.mock import Mock, MagicMock
import boto3
from moto import mock_aws


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='test-checkpoint-table',
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        yield table


@pytest.fixture
def mock_ssm_parameters():
    """Create mock SSM parameters for testing."""
    with mock_aws():
        ssm = boto3.client('ssm', region_name='us-east-1')
        ssm.put_parameter(
            Name='/twitter-event-source/bearer_token',
            Value='test_bearer_token_123',
            Type='SecureString'
        )
        yield ssm


@pytest.fixture
def mock_lambda_client():
    """Create a mock Lambda client."""
    client = Mock()
    client.invoke = Mock(return_value={'StatusCode': 200})
    return client


@pytest.fixture
def mock_tweepy_client():
    """Create a mock Tweepy client."""
    client = Mock()
    return client
