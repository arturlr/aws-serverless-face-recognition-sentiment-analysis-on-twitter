# Deployment Verification Guide

This guide helps you verify that the X API v2 migration was successful after deployment.

## Pre-Deployment Checklist

- [ ] X API v2 Bearer Token obtained from X Developer Portal
- [ ] Bearer Token associated with a Project (required for v2 API)
- [ ] Bearer Token stored in SSM Parameter Store: `/twitter-event-source/bearer_token`
- [ ] Code built successfully: `sam build`
- [ ] Code deployed successfully: `sam deploy`

## Quick Verification Steps

### 1. Verify SSM Parameter

```bash
# Check if Bearer Token parameter exists
aws ssm get-parameter \
    --name /twitter-event-source/bearer_token \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text

# Expected: Your Bearer Token should be displayed
```

### 2. Check Poller Lambda Function

```bash
# Find your poller function name
aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `Poller`)].FunctionName' \
    --output text

# Tail the logs (replace <function-name> with actual name)
aws logs tail /aws/lambda/<function-name> --follow
```

**What to Look For**:
- ✅ No authentication errors
- ✅ Successful API calls to X API v2
- ✅ Tweets being retrieved and processed
- ✅ Batch invocations to parser Lambda

**Common Log Messages**:
```
# Success:
START RequestId: xxx-xxx-xxx
[INFO] Searching for tweets with query: selfie
[INFO] Found X tweets matching search criteria
[INFO] Processing batch of Y tweets
END RequestId: xxx-xxx-xxx

# Errors to Watch For:
Could not find expected SSM parameter containing X API Bearer Token
403 Forbidden
Rate limit exceeded
```

### 3. Verify Parser Lambda Receives Tweets

```bash
# Find your parser function name
aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `Parser`)].FunctionName' \
    --output text

# Check recent invocations
aws logs tail /aws/lambda/<parser-function-name> --follow
```

**What to Look For**:
- ✅ Parser Lambda is being invoked by Poller
- ✅ Tweets have expected format (extended_entities, media, full_text)
- ✅ Images are being processed
- ✅ Step Functions are being triggered

### 4. Check DynamoDB Tables

```bash
# List tables
aws dynamodb list-tables \
    --query 'TableNames[?contains(@, `twitter`) || contains(@, `SearchCheckpoint`)]'

# Check SearchCheckpoint for latest tweet ID
aws dynamodb scan \
    --table-name <your-search-checkpoint-table> \
    --query 'Items[0]'

# Expected: Should show latest since_id
```

### 5. Verify Rekognition Processing

```bash
# Check Rekognition Lambda logs
aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `Rekognition`)].FunctionName' \
    --output text

aws logs tail /aws/lambda/<rekognition-function-name> --since 10m
```

**What to Look For**:
- ✅ Images being analyzed
- ✅ Faces detected
- ✅ Emotions processed

### 6. Check S3 Bucket for Data

```bash
# Find your bucket name
aws cloudformation describe-stacks \
    --stack-name <your-stack-name> \
    --query 'Stacks[0].Outputs[?OutputKey==`S3Bucket`].OutputValue' \
    --output text

# List recent objects
aws s3 ls s3://<your-bucket-name>/data/ --recursive --human-readable
```

**What to Look For**:
- ✅ New parquet files being created
- ✅ Timestamps are recent

### 7. Test CloudWatch Metrics

```bash
# Check custom metrics
aws cloudwatch get-metric-statistics \
    --namespace TwitterRekognition \
    --metric-name TweetsProcessed \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum

# Expected: Should show tweets being processed
```

## Detailed Verification

### Test API Access Manually

Create a test script to verify X API v2 access:

```python
import boto3
import tweepy

# Get Bearer Token from SSM
ssm = boto3.client('ssm')
result = ssm.get_parameter(
    Name='/twitter-event-source/bearer_token',
    WithDecryption=True
)
bearer_token = result['Parameter']['Value']

# Create X API client
client = tweepy.Client(bearer_token=bearer_token)

# Test search
try:
    response = client.search_recent_tweets(
        query='selfie',
        max_results=10,
        tweet_fields=['id', 'text', 'attachments'],
        expansions=['attachments.media_keys'],
        media_fields=['type', 'url']
    )
    
    if response.data:
        print(f"✓ Successfully retrieved {len(response.data)} tweets")
        for tweet in response.data:
            print(f"  - Tweet ID: {tweet.id}")
    else:
        print("⚠ No tweets found matching query")
        
except Exception as e:
    print(f"✗ Error: {e}")
```

### Check Response Format Transformation

Add temporary logging to verify response format:

```python
# In lambdas/poller/index.py, temporarily add:
import json

def search(search_text, since_id=None):
    # ... existing code ...
    
    # Add before return:
    if transformed_tweets:
        print(f"Sample transformed tweet: {json.dumps(transformed_tweets[0], indent=2)}")
    
    return transformed_tweets
```

Deploy and check logs for the sample output. Verify it has:
- `id` and `id_str` fields
- `full_text` field
- `extended_entities` with `media` array
- Media objects with `id_str`, `media_url_https`, and `type`

## Troubleshooting

### Issue: "No tweets being retrieved"

**Checks**:
1. Verify search query matches recent tweets (last 7 days)
2. Check if tweets have photo attachments
3. Verify rate limits not exceeded

```bash
# Test with broader query
aws lambda invoke \
    --function-name <poller-function-name> \
    --payload '{}' \
    /tmp/response.json

cat /tmp/response.json
```

### Issue: "Authentication errors"

**Checks**:
1. Verify Bearer Token is correct
2. Ensure token is associated with a Project
3. Check token hasn't expired

```bash
# Test SSM parameter
aws ssm get-parameter \
    --name /twitter-event-source/bearer_token \
    --with-decryption

# If incorrect, update:
aws ssm put-parameter \
    --name /twitter-event-source/bearer_token \
    --value <new-bearer-token> \
    --type SecureString \
    --overwrite
```

### Issue: "Parser Lambda errors"

**Possible Cause**: Response format doesn't match expectations

**Check**:
```bash
# Review parser Lambda code expectations
cat lambdas/parser/index.py | grep -A 10 "extended_entities"

# Compare with poller transformation output in logs
```

### Issue: "Rate limit errors"

**Solution**:
1. X API v2 allows 450 requests per 15 minutes
2. Adjust polling frequency if needed
3. Verify `wait_on_rate_limit=True` is set

```bash
# Update polling frequency in template.yaml and redeploy
# Parameter: PollingFrequencyInMinutes
sam deploy --parameter-overrides PollingFrequencyInMinutes=15
```

## Success Indicators

✅ **All checks should show**:
- Poller Lambda executing without errors
- Bearer Token authentication working
- Tweets being retrieved from X API v2
- Parser Lambda receiving properly formatted tweets
- Step Functions processing images
- Rekognition analyzing faces
- Data flowing to S3
- CloudWatch metrics updating
- Frontend displaying results

## Performance Baselines

After successful deployment, expect:

- **Polling**: Every N minutes (default: 10)
- **Tweets per poll**: 0-100 (depends on activity)
- **Processing time**: 2-5 seconds per batch
- **End-to-end latency**: 10-30 seconds from tweet to Rekognition

## Monitoring Dashboard

Create CloudWatch Dashboard to monitor:

```bash
# Create dashboard
aws cloudwatch put-dashboard \
    --dashboard-name TwitterRekognition \
    --dashboard-body file://dashboard.json
```

**Key Metrics to Track**:
- `TwitterRekognition/TweetsProcessed`
- `TwitterRekognition/ImagesIdentified`
- Poller Lambda errors
- Parser Lambda invocations
- Step Functions executions

## Final Verification Checklist

- [ ] Poller Lambda runs without errors
- [ ] X API v2 authentication successful
- [ ] Tweets being retrieved and transformed correctly
- [ ] Parser Lambda processes tweets without errors
- [ ] Images analyzed by Rekognition
- [ ] Data appearing in S3 bucket
- [ ] CloudWatch metrics updating
- [ ] Frontend displays results
- [ ] No rate limit errors
- [ ] Response format compatible with parser

## Support

If issues persist after verification:

1. Review CloudWatch Logs for all Lambda functions
2. Check X Developer Portal for API status
3. Verify all IAM permissions are correct
4. Review MIGRATION_GUIDE.md for additional troubleshooting
5. Contact appropriate support channels

## Rollback

If migration fails and rollback is needed:

```bash
# 1. Restore previous version from git
git checkout <previous-commit>

# 2. Rebuild and redeploy
sam build
sam deploy

# 3. Restore old SSM parameters (if available)
# Note: Twitter API v1.1 may no longer be available
```
