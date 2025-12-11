# Migration Guide: Twitter API v1.1 to X API v2

This document describes the migration from Twitter API v1.1 to X API v2 for the AWS Serverless Face Recognition Sentiment Analysis application.

## Overview

The application has been migrated from:
- **From**: Twitter API v1.1 with OAuth 1.0a authentication (python-twitter library)
- **To**: X API v2 with OAuth 2.0 Bearer Token authentication (tweepy v4+ library)

## What Changed

### 1. Authentication Method

**Before (OAuth 1.0a)**:
- Required 4 credentials: Consumer Key, Consumer Secret, Access Token, Access Token Secret
- SSM Parameters: `/twitter-event-source/consumer_key`, `/twitter-event-source/consumer_secret`, `/twitter-event-source/access_token`, `/twitter-event-source/access_token_secret`

**After (OAuth 2.0)**:
- Requires 1 credential: Bearer Token
- SSM Parameter: `/twitter-event-source/bearer_token`

### 2. Python Library

**Before**:
```python
import twitter
api = twitter.Api(consumer_key=..., consumer_secret=..., access_token_key=..., access_token_secret=...)
```

**After**:
```python
import tweepy
client = tweepy.Client(bearer_token=...)
```

### 3. Search API Endpoint

**Before**:
```python
result = api.GetSearch(term=search_text, count=100, return_json=True, since_id=since_id)
tweets = result['statuses']
```

**After**:
```python
response = client.search_recent_tweets(
    query=search_text,
    max_results=100,
    since_id=since_id,
    tweet_fields=['id', 'text', 'attachments', 'entities'],
    expansions=['attachments.media_keys'],
    media_fields=['type', 'url', 'preview_image_url']
)
tweets = response.data
```

### 4. Response Format

The X API v2 response format is different from v1.1. The poller Lambda function now transforms v2 responses to maintain compatibility with the parser Lambda:

**X API v2 Response Structure**:
```json
{
  "data": [
    {
      "id": "1234567890",
      "text": "Check out my selfie!",
      "attachments": {
        "media_keys": ["3_1234567890"]
      }
    }
  ],
  "includes": {
    "media": [
      {
        "media_key": "3_1234567890",
        "type": "photo",
        "url": "https://pbs.twimg.com/media/..."
      }
    ]
  }
}
```

**Transformed Format (for parser compatibility)**:
```json
{
  "id": "1234567890",
  "id_str": "1234567890",
  "full_text": "Check out my selfie!",
  "extended_entities": {
    "media": [
      {
        "id_str": "1234567890",
        "media_url_https": "https://pbs.twimg.com/media/...",
        "type": "photo"
      }
    ]
  }
}
```

## Files Modified

### 1. `lambdas/poller/index.py`
- Replaced `python-twitter` library with `tweepy`
- Updated authentication to use OAuth 2.0 Bearer Token
- Implemented `search_recent_tweets()` instead of `GetSearch()`
- Added response transformation logic to maintain backward compatibility with parser Lambda
- Updated error handling and pagination logic

### 2. `lambdas/poller/requirements.txt`
```diff
- python-twitter
+ tweepy>=4.14.0
  requests
  boto3
```

### 3. `README.md`
- Updated credential setup instructions for X API v2
- Replaced references to "Twitter API v1.1" with "X API v2"
- Added instructions for obtaining Bearer Token from X Developer Portal
- Noted that credentials must be associated with a Project
- Updated authentication flow documentation

### 4. `template.yaml`
- Updated parameter descriptions to reference X API v2
- Updated SearchText parameter description
- Updated SSMParameterPrefix description to mention Bearer Token requirement

## Migration Steps for Existing Deployments

If you have an existing deployment using Twitter API v1.1, follow these steps to migrate:

### Step 1: Obtain X API v2 Credentials

1. Visit the [X Developer Portal](https://developer.x.com/en/portal/dashboard)
2. Create a new Project or use an existing one (required for v2 API access)
3. Create an App within your Project
4. Navigate to "Keys and tokens" tab
5. Generate a Bearer Token
6. Save the Bearer Token securely

### Step 2: Update SSM Parameters

```bash
# Add the new Bearer Token parameter
aws ssm put-parameter \
    --name /twitter-event-source/bearer_token \
    --value <your-bearer-token> \
    --type SecureString \
    --overwrite

# Optional: Remove old OAuth 1.0a parameters (after confirming migration works)
# aws ssm delete-parameter --name /twitter-event-source/consumer_key
# aws ssm delete-parameter --name /twitter-event-source/consumer_secret
# aws ssm delete-parameter --name /twitter-event-source/access_token
# aws ssm delete-parameter --name /twitter-event-source/access_token_secret
```

### Step 3: Build and Deploy Updated Code

```bash
# Build the SAM application
sam build

# Deploy the updated application
sam deploy
```

### Step 4: Verify Migration

1. Check CloudWatch Logs for the Poller Lambda function:
```bash
aws logs tail /aws/lambda/<your-poller-function-name> --follow
```

2. Monitor for successful tweet searches and processing:
   - Look for successful API calls to X API v2
   - Verify tweets are being processed by the parser Lambda
   - Check that images are being analyzed by Rekognition

3. Run the validation test:
```bash
python3 test_migration.py
```

## Breaking Changes

### For End Users
- **None**: The application functionality remains the same from an end-user perspective

### For Developers/Operators
1. **Authentication**: Must obtain new X API v2 Bearer Token
2. **SSM Parameters**: Different parameter structure (1 parameter instead of 4)
3. **API Limits**: X API v2 has different rate limits than v1.1
   - Recent search: 450 requests per 15 minutes (app-based auth)
   - Max results per request: 100 tweets
4. **Search Window**: Recent search endpoint returns tweets from the last 7 days only (for standard access)

## API Rate Limits

X API v2 rate limits (with Bearer Token authentication):
- **Recent Search**: 450 requests per 15 minutes
- **Results per request**: 10-100 tweets (default: 10, max: 100)

The poller Lambda uses:
- `max_results=100` to maximize efficiency
- `wait_on_rate_limit=True` to automatically handle rate limiting

## Troubleshooting

### Issue: "Could not find expected SSM parameter containing X API Bearer Token"

**Solution**: Ensure the Bearer Token is stored in SSM Parameter Store:
```bash
aws ssm put-parameter \
    --name /twitter-event-source/bearer_token \
    --value <your-bearer-token> \
    --type SecureString \
    --overwrite
```

### Issue: "403 Forbidden" errors when calling X API

**Possible Causes**:
1. Invalid Bearer Token
2. Bearer Token not associated with a Project in X Developer Portal
3. App doesn't have appropriate permissions

**Solution**:
1. Verify Bearer Token is correct
2. Ensure your app is created within a Project (not standalone)
3. Check app permissions in X Developer Portal

### Issue: No tweets being returned

**Possible Causes**:
1. Recent search only returns tweets from last 7 days
2. Search query doesn't match any recent tweets
3. Tweets don't contain photos

**Solution**:
1. Wait for new tweets matching your search criteria
2. Adjust the SearchText parameter
3. Verify tweets have photo attachments

### Issue: "Rate limit exceeded" errors

**Solution**: The tweepy client is configured with `wait_on_rate_limit=True`, which automatically waits when rate limits are hit. If you see these errors:
1. Check if PollingFrequencyInMinutes is too aggressive
2. Consider increasing the polling interval
3. Monitor CloudWatch Logs for rate limit warnings

## Testing

A validation test script is provided: `test_migration.py`

Run it to verify the migration:
```bash
python3 test_migration.py
```

The test validates:
- Code structure and imports
- Requirements.txt updates
- README.md updates
- template.yaml updates
- Response format compatibility with parser Lambda

## Rollback Procedure

If you need to rollback to Twitter API v1.1:

1. Restore the original files from version control
2. Restore OAuth 1.0a credentials to SSM Parameter Store
3. Run `sam build` and `sam deploy`

**Note**: Twitter API v1.1 was deprecated and may not be available, so rollback may not be possible.

## Additional Resources

- [X API v2 Documentation](https://developer.x.com/en/docs/twitter-api)
- [Tweepy Documentation](https://docs.tweepy.org/)
- [X API v2 Authentication](https://developer.x.com/en/docs/authentication/oauth-2-0)
- [X API Rate Limits](https://developer.x.com/en/docs/twitter-api/rate-limits)

## Support

For issues related to:
- **X API**: Contact X Developer Support
- **AWS Services**: Open AWS Support case
- **Application Code**: Create an issue in the GitHub repository
