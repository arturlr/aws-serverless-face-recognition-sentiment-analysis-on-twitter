import json
import os
import sys

import boto3
import tweepy

from boto3.dynamodb.conditions import Attr, Or
from botocore.exceptions import ClientError

LAMBDA = boto3.client('lambda')
SSM = boto3.client('ssm')
DDB = boto3.resource('dynamodb')
TABLE = DDB.Table(os.getenv('SEARCH_CHECKPOINT_TABLE_NAME'))
RECORD_KEY = 'checkpoint'

SEARCH_TEXT = os.getenv('SEARCH_TEXT')
TWEET_PROCESSOR_FUNCTION_NAME = os.getenv('TWEET_PROCESSOR_FUNCTION_NAME')
BATCH_SIZE = int(os.getenv('BATCH_SIZE'))

SSM_PARAMETER_PREFIX = os.getenv("SSM_PARAMETER_PREFIX")
BEARER_TOKEN_PARAM_NAME = '/{}/bearer_token'.format(SSM_PARAMETER_PREFIX)

def handler(event, context):
    """Forward SQS messages to Kinesis Firehose Delivery Stream."""
    for batch in _search_batches():
        LAMBDA.invoke(
            FunctionName=TWEET_PROCESSOR_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(batch)
        )

def _search_batches():
    since_id = last_id()

    tweets = []
    while True:
        result = search(SEARCH_TEXT, since_id)
        if not result:
            # no more results
            break

        tweets = result
        size = len(tweets)
        for i in range(0, size, BATCH_SIZE):
            yield tweets[i:min(i + BATCH_SIZE, size)]
        
        # Update checkpoint with the newest tweet ID
        if tweets:
            newest_id = max(int(tweet['id']) for tweet in tweets)
            update(str(newest_id))

def last_id():
    """Return last checkpoint tweet id."""
    result = TABLE.get_item(
        Key={'id': RECORD_KEY}
    )
    if 'Item' in result:
        return result['Item']['since_id']
    return None


def update(since_id):
    """Update checkpoint to given tweet id."""
    try:
        TABLE.put_item(
            Item={
                'id': RECORD_KEY,
                'since_id': since_id
            },
            ConditionExpression=Or(
                Attr('id').not_exists(),
                Attr('since_id').lt(since_id)
            )
        )
    except ClientError as e:
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise


def search(search_text, since_id=None):
    """Search for tweets matching the given search text using X API v2."""
    try:
        # Build query parameters
        query_params = {
            'query': search_text,
            'max_results': 100,
            'tweet_fields': ['id', 'text', 'attachments', 'entities'],
            'expansions': ['attachments.media_keys'],
            'media_fields': ['type', 'url', 'preview_image_url']
        }
        
        if since_id:
            query_params['since_id'] = since_id
        
        # Search recent tweets
        response = X_CLIENT.search_recent_tweets(**query_params)
        
        if not response.data:
            return []
        
        # Build media lookup from includes
        media_lookup = {}
        if response.includes and 'media' in response.includes:
            for media in response.includes['media']:
                media_lookup[media.media_key] = media
        
        # Transform X API v2 format to match parser expectations
        transformed_tweets = []
        for tweet in response.data:
            # Check if tweet has media attachments
            if not hasattr(tweet, 'attachments') or not tweet.attachments:
                continue
            
            media_keys = tweet.attachments.get('media_keys', [])
            if not media_keys:
                continue
            
            # Build extended_entities structure for parser compatibility
            media_entities = []
            for media_key in media_keys:
                if media_key not in media_lookup:
                    continue
                
                media = media_lookup[media_key]
                # Only process photos
                if media.type == 'photo':
                    media_entities.append({
                        'id_str': str(tweet.id),
                        'media_url_https': media.url,
                        'type': 'photo'
                    })
            
            if media_entities:
                transformed_tweets.append({
                    'id': str(tweet.id),
                    'id_str': str(tweet.id),
                    'full_text': tweet.text,
                    'extended_entities': {
                        'media': media_entities
                    }
                })
        
        return transformed_tweets
        
    except Exception as e:
        print(f"Error searching tweets: {e}")
        return []


def _create_x_client():
    """Create X API v2 client with Bearer Token authentication."""
    result = SSM.get_parameters(
        Names=[BEARER_TOKEN_PARAM_NAME],
        WithDecryption=True
    )

    if result['InvalidParameters']:
        raise RuntimeError(
            'Could not find expected SSM parameter containing X API Bearer Token: {}'.format(BEARER_TOKEN_PARAM_NAME))

    param_lookup = {param['Name']: param['Value'] for param in result['Parameters']}
    bearer_token = param_lookup[BEARER_TOKEN_PARAM_NAME]

    return tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)


X_CLIENT = _create_x_client()

