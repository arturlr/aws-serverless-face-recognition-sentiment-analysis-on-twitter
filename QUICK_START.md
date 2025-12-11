# Quick Start: X API v2 Migration

This is a quick reference for deploying the migrated application. For detailed information, see MIGRATION_GUIDE.md.

## Prerequisites

- AWS Account with appropriate permissions
- AWS SAM CLI installed
- X Developer Portal account
- Python 3.8 or Docker

## 1. Get X API v2 Credentials (5 minutes)

1. Go to https://developer.x.com/en/portal/dashboard
2. Create a **Project** (required for v2 API)
3. Create an **App** within the Project
4. Go to "Keys and tokens" tab
5. Click "Generate" under "Bearer Token"
6. **Save the token** - you won't see it again!

## 2. Store Credentials in AWS (1 minute)

```bash
aws ssm put-parameter \
    --name /twitter-event-source/bearer_token \
    --value <your-bearer-token-here> \
    --type SecureString \
    --overwrite
```

## 3. Build the Application (2-3 minutes)

```bash
# Clone/navigate to repository
cd aws-serverless-face-recognition-sentiment-analysis-on-twitter

# Build with SAM
sam build
```

## 4. Deploy to AWS (5-10 minutes)

```bash
sam deploy --guided --capabilities CAPABILITY_NAMED_IAM
```

When prompted:
- Stack Name: `twitter-demo` (or your choice)
- AWS Region: Choose a region where Rekognition is available
- SearchText: `selfie` (or your search term)
- SSMParameterPrefix: `twitter-event-source` (must match Step 2)
- PollingFrequencyInMinutes: `10` (or adjust)
- BatchSize: `15` (or adjust)
- Confirm changes: `y`
- Allow IAM role creation: `y`

## 5. Verify Deployment (2 minutes)

```bash
# Get your poller function name
POLLER_FUNCTION=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `Poller`)].FunctionName' --output text)

# Watch the logs
aws logs tail /aws/lambda/$POLLER_FUNCTION --follow
```

Look for:
- ✅ No authentication errors
- ✅ "Found X tweets" messages
- ✅ Successful batch processing

## 6. Access the Frontend

```bash
# Get CloudFront URL
aws cloudformation describe-stacks \
    --stack-name <your-stack-name> \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
    --output text
```

Visit the URL to see the dashboard!

## Common Issues

### "Could not find expected SSM parameter"
→ Run Step 2 again with correct parameter name

### "403 Forbidden" from X API
→ Ensure Bearer Token is from an App within a Project

### "No tweets found"
→ Wait a few minutes for recent tweets, or try different search term

### Rate limit errors
→ Normal - the app handles this automatically

## What Changed from v1.1?

- **Authentication**: 1 Bearer Token instead of 4 OAuth keys
- **Library**: `tweepy` instead of `python-twitter`
- **Search window**: Last 7 days (standard access)
- **Everything else**: Works the same!

## Need More Help?

- **Detailed guide**: See MIGRATION_GUIDE.md
- **Verification steps**: See DEPLOYMENT_VERIFICATION.md
- **X API docs**: https://developer.x.com/en/docs/twitter-api
- **Tweepy docs**: https://docs.tweepy.org/

## Architecture

```
X API v2 → Poller Lambda → Parser Lambda → Step Functions
                                              ↓
                                         Rekognition
                                              ↓
                                         Process Faces
                                              ↓
                                      Kinesis Firehose
                                              ↓
                                         S3 (Parquet)
                                              ↓
                                         Athena/Frontend
```

## Next Steps

1. Monitor CloudWatch Logs for first hour
2. Check S3 bucket for parquet files
3. View results in CloudFront dashboard
4. Adjust PollingFrequencyInMinutes if needed
5. Optional: Remove old OAuth 1.0a SSM parameters

That's it! Your application is now running with X API v2. 🎉
