# Twitter Poller Optimization

This directory contains the enhanced Twitter Poller Lambda function with comprehensive optimizations for intelligent pagination, rate limit management, error handling, and monitoring.

## Overview

The optimized Twitter Poller implements five key improvements:

1. **Intelligent Pagination and Rate Limit Management** - Efficiently handles X API v2 pagination while respecting rate limits
2. **Robust Error Handling with Exponential Backoff** - Classifies errors and implements intelligent retry logic
3. **Comprehensive Logging and Monitoring** - Structured logging with correlation IDs and CloudWatch metrics
4. **Memory-Efficient Batch Processing** - Streams results to minimize memory usage
5. **Atomic Checkpoint Management** - Prevents data loss and duplication with DynamoDB conditional writes

## Architecture

### Components

- **`index.py`** - Lambda handler entry point
- **`twitter_poller_optimized.py`** - Main poller orchestration
- **`rate_limit_manager.py`** - X API rate limit management
- **`error_handler.py`** - Error classification and exponential backoff
- **`checkpoint_manager.py`** - Atomic checkpoint operations
- **`metrics_logger.py`** - Comprehensive logging and metrics
- **`data_models.py`** - Core data structures

### Data Flow

```
CloudWatch Events → Handler → TwitterPollerOptimized
                                     ↓
                            ┌────────┴────────┐
                            ↓                 ↓
                    RateLimitManager   CheckpointManager
                            ↓                 ↓
                    X API v2 Search    DynamoDB Checkpoint
                            ↓
                    Tweet Batches → Parser Lambda
```

## Features

### 1. Rate Limit Management

- **Proactive Throttling**: Slows requests when 80% of rate limit is consumed
- **Intelligent Wait Times**: Distributes remaining requests over time window
- **Minimum Request Intervals**: Enforces 1-second minimum between requests
- **Rate Limit Headers Parsing**: Monitors X API rate limit status

### 2. Error Handling

- **Error Classification**:
  - Retryable: Network timeouts, 429, 5xx errors, DynamoDB throttling
  - Non-retryable: 401, 403, 400, invalid credentials
- **Exponential Backoff**: Base delay of 1s, max 300s, with jitter
- **Max Retries**: 5 attempts with increasing delays
- **Error Context Preservation**: Logs full context for debugging

### 3. Checkpoint Management

- **Atomic Updates**: Uses DynamoDB conditional writes
- **Numeric Comparison**: Stores both string and numeric IDs for proper ordering
- **Conflict Resolution**: Chooses maximum tweet ID on conflicts
- **Corruption Recovery**: Validates and recovers from corrupted checkpoints
- **Concurrent Execution**: Safely handles multiple executions

### 4. Logging and Metrics

- **Structured Logging**: JSON format with correlation IDs
- **Execution Tracking**: Start/end times, duration, tweets processed
- **API Call Logging**: Endpoint, response time, status codes
- **Rate Limit Events**: Remaining requests, wait times
- **Checkpoint Updates**: Previous and new values, success status
- **Batch Processing**: Batch sizes, delivery status

### 5. Memory Efficiency

- **Streaming Processing**: Processes tweets as they arrive
- **Batch Sizing**: Configurable batch sizes (default: 25)
- **Graceful Termination**: Stops before Lambda timeout (14 min limit)
- **Maximum Tweet Limit**: Caps at 1000 tweets per execution

## Configuration

Environment variables (set in SAM template):

- `SEARCH_TEXT` - Search query for tweets
- `SEARCH_CHECKPOINT_TABLE_NAME` - DynamoDB table for checkpoints
- `TWEET_PROCESSOR_FUNCTION_NAME` - Target Lambda for batch processing
- `BATCH_SIZE` - Tweets per batch (default: 25)
- `SSM_PARAMETER_PREFIX` - Prefix for SSM parameters (default: twitter-event-source)

## Testing

The implementation includes comprehensive property-based tests using Hypothesis:

### Test Coverage

- **25 property-based tests** with minimum 100 iterations each
- **Rate Limit Properties** (5 tests): Rate limit compliance, proactive throttling, wait time calculation
- **Error Handler Properties** (6 tests): Exponential backoff, error classification, retry logic
- **Checkpoint Properties** (7 tests): Atomic updates, conflict resolution, recovery
- **Data Models Properties** (7 tests): Serialization, calculations, logging robustness

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_rate_limit_properties.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Property Test Tags

Each test is tagged with comments referencing the design document:

```python
# Feature: twitter-poller-optimization, Property 1: Rate Limit Compliance and Management
# For any API execution session, the system should respect all documented rate limits
```

## Deployment

The poller is deployed as part of the SAM application:

```bash
# Build the application
sam build

# Deploy with guided setup
sam deploy --guided --capabilities CAPABILITY_NAMED_IAM
```

## Monitoring

### CloudWatch Metrics

The poller emits custom metrics:
- `TweetsProcessed` - Total tweets processed
- `APICallsMade` - Number of API calls
- `ErrorsEncountered` - Total errors
- `BatchesSent` - Batches sent to parser
- `ExecutionDurationSeconds` - Execution time

### CloudWatch Logs

Structured JSON logs include:
- `correlation_id` - Request tracking ID
- `event` - Event type (execution_start, api_call, error, etc.)
- `timestamp` - ISO format timestamp
- Context-specific data

### Example Log Entries

```json
{
  "event": "execution_start",
  "correlation_id": "abc-123",
  "timestamp": "2024-01-01T00:00:00Z",
  "context": {"search_text": "selfie", "batch_size": 25}
}

{
  "event": "rate_limit_encounter",
  "correlation_id": "abc-123",
  "remaining_requests": 10,
  "utilization_percentage": 90.0,
  "wait_seconds": 60
}

{
  "event": "checkpoint_update",
  "correlation_id": "abc-123",
  "previous_checkpoint": "123456789",
  "new_checkpoint": "987654321",
  "success": true
}
```

## Performance Characteristics

### Execution Limits

- **Maximum Execution Time**: 14 minutes (before graceful termination)
- **Maximum Tweets Per Execution**: 1000 tweets
- **API Rate Limit**: Respects X API v2 limits (~180 requests per 15 minutes)
- **Memory**: Optimized for streaming, minimal heap usage

### Expected Throughput

With 2 daily executions:
- **Best Case**: ~200 tweets per execution (no rate limit issues)
- **Typical**: ~100-150 tweets per execution (with rate limiting)
- **Daily Total**: ~200-400 tweets with selfies

## Error Recovery

### Automatic Recovery

- **Transient Errors**: Automatic retry with exponential backoff
- **Rate Limits**: Waits and continues
- **Checkpoint Corruption**: Validates and recovers or starts fresh
- **Concurrent Executions**: Resolves conflicts using maximum tweet ID

### Manual Recovery

If issues persist:

1. Check CloudWatch logs for errors with correlation ID
2. Verify SSM parameter contains valid Bearer Token
3. Check DynamoDB checkpoint table for corruption
4. Manually reset checkpoint if needed:
   ```bash
   aws dynamodb delete-item \
     --table-name SearchCheckpoint \
     --key '{"id": {"S": "checkpoint"}}'
   ```

## Maintenance

### Updating Dependencies

```bash
# Update tweepy for X API changes
pip install --upgrade tweepy
sam build
sam deploy
```

### Adjusting Rate Limits

Modify `RateLimitManager.PROACTIVE_THRESHOLD` in `rate_limit_manager.py`:
- Lower value (e.g., 0.1) = More conservative, waits earlier
- Higher value (e.g., 0.3) = More aggressive, uses more of rate limit

### Changing Batch Size

Update `BATCH_SIZE` in SAM template parameters or environment variables.

## Troubleshooting

### High Error Rate

Check logs for error patterns:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/YourPollerFunction \
  --filter-pattern '"event":"error"'
```

### Missing Tweets

Verify checkpoint is advancing:
```bash
aws dynamodb get-item \
  --table-name SearchCheckpoint \
  --key '{"id": {"S": "checkpoint"}}'
```

### Rate Limit Issues

Check rate limit encounters:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/YourPollerFunction \
  --filter-pattern '"event":"rate_limit_encounter"'
```

## Design Documentation

For complete design details, see:
- `.kiro/specs/twitter-poller-optimization/requirements.md` - Requirements
- `.kiro/specs/twitter-poller-optimization/design.md` - Architecture and design
- `.kiro/specs/twitter-poller-optimization/tasks.md` - Implementation tasks

## License

See repository LICENSE file.
