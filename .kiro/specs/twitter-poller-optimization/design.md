# Twitter Poller Optimization Design

## Overview

The Twitter Poller Lambda function serves as the entry point for a tweet processing pipeline that searches for tweets with photo attachments, processes them through AWS Rekognition, and stores results for analysis. Currently limited to two daily executions, the system requires optimization to maximize data collection efficiency, improve reliability, and ensure robust error handling within API rate limits.

The optimization focuses on five key areas: intelligent pagination and rate limit management, robust error handling with exponential backoff, comprehensive logging and monitoring, memory-efficient batch processing, and atomic checkpoint management to prevent data loss and duplication.

## Architecture

### Current Architecture
```
CloudWatch Events (Schedule) → Poller Lambda → Parser Lambda → Step Functions → Rekognition/ProcessFaces
                                     ↓
                              DynamoDB (Checkpoints)
```

### Optimized Architecture
```
CloudWatch Events (Schedule) → Enhanced Poller Lambda → Parser Lambda → Step Functions
                                     ↓                        ↓
                              DynamoDB (Checkpoints)    CloudWatch Metrics/Logs
                                     ↓
                              Error Handling & Recovery
```

### Key Architectural Improvements

1. **Intelligent Pagination Controller**: Manages API pagination with rate limit awareness
2. **Exponential Backoff Handler**: Implements retry logic for transient failures
3. **Memory-Efficient Streaming**: Processes tweets in streams rather than loading all into memory
4. **Atomic Checkpoint Manager**: Ensures consistent checkpoint updates with conflict resolution
5. **Comprehensive Monitoring**: Detailed CloudWatch metrics and structured logging

## Components and Interfaces

### 1. Enhanced Poller Lambda (`TwitterPollerOptimized`)

**Primary Responsibilities:**
- Execute intelligent tweet search with pagination
- Manage API rate limits and implement backoff strategies
- Stream process results to minimize memory usage
- Maintain atomic checkpoints with conflict resolution
- Provide comprehensive logging and metrics

**Key Interfaces:**
```python
class TwitterPollerOptimized:
    def handler(event, context) -> Dict[str, Any]
    def search_with_pagination(search_text: str, since_id: str) -> Iterator[List[Dict]]
    def process_batch_stream(tweets: Iterator[List[Dict]]) -> None
    def update_checkpoint_atomic(since_id: str) -> bool
```

### 2. Rate Limit Manager (`RateLimitManager`)

**Responsibilities:**
- Monitor X API rate limit headers
- Implement intelligent backoff when approaching limits
- Calculate optimal request timing

**Interface:**
```python
class RateLimitManager:
    def check_rate_limits(response_headers: Dict) -> RateLimitStatus
    def calculate_wait_time(remaining_requests: int, reset_time: int) -> int
    def should_continue_requests() -> bool
```

### 3. Error Handler (`ErrorHandler`)

**Responsibilities:**
- Implement exponential backoff for retries
- Classify errors as retryable vs. permanent
- Log error context for debugging

**Interface:**
```python
class ErrorHandler:
    def handle_api_error(error: Exception, attempt: int) -> RetryDecision
    def exponential_backoff(attempt: int, base_delay: float) -> float
    def log_error_context(error: Exception, context: Dict) -> None
```

### 4. Checkpoint Manager (`CheckpointManager`)

**Responsibilities:**
- Atomic checkpoint updates with conflict resolution
- Handle concurrent execution scenarios
- Implement checkpoint recovery mechanisms

**Interface:**
```python
class CheckpointManager:
    def get_last_checkpoint() -> Optional[str]
    def update_checkpoint_atomic(since_id: str) -> bool
    def handle_checkpoint_conflict(current_id: str, new_id: str) -> str
```

### 5. Metrics and Logging (`MetricsLogger`)

**Responsibilities:**
- Structured logging with correlation IDs
- Custom CloudWatch metrics
- Performance tracking

**Interface:**
```python
class MetricsLogger:
    def log_execution_start(context: Dict) -> str
    def log_api_call(endpoint: str, response_time: float, status: int) -> None
    def emit_custom_metrics(metrics: Dict[str, float]) -> None
```

## Data Models

### Tweet Data Model
```python
@dataclass
class TweetData:
    id: str
    id_str: str
    full_text: str
    extended_entities: Dict[str, Any]
    created_at: Optional[str] = None
    user_id: Optional[str] = None
```

### Rate Limit Status
```python
@dataclass
class RateLimitStatus:
    remaining_requests: int
    reset_time: int
    limit: int
    should_wait: bool
    wait_seconds: int
```

### Execution Metrics
```python
@dataclass
class ExecutionMetrics:
    start_time: datetime
    end_time: Optional[datetime]
    tweets_processed: int
    api_calls_made: int
    errors_encountered: int
    batches_sent: int
    checkpoint_updates: int
```

### Error Context
```python
@dataclass
class ErrorContext:
    error_type: str
    error_message: str
    attempt_number: int
    timestamp: datetime
    function_context: Dict[str, Any]
    api_response: Optional[Dict] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, several properties can be consolidated to eliminate redundancy:

- Rate limit properties (1.1, 1.2, 6.1, 6.2) can be combined into comprehensive rate limit compliance
- Error handling properties (2.1, 2.4, 2.5) share common retry and logging patterns
- Logging properties (3.1-3.5) can be unified into comprehensive logging validation
- Memory management properties (4.1, 4.3, 4.5) address the same core concern
- Checkpoint properties (5.1, 5.2) both address atomicity and concurrency

### Core Properties

**Property 1: Rate Limit Compliance and Management**
*For any* API execution session, the system should respect all documented rate limits, implement appropriate backoff when limits are approached, and continue processing until quotas are exhausted or no more data exists
**Validates: Requirements 1.1, 1.2, 6.1, 6.2**

**Property 2: Pagination Completeness**
*For any* search query with available results, the system should continue fetching through all available pages until no more results exist or execution limits are reached, prioritizing most recent tweets
**Validates: Requirements 1.3, 1.5**

**Property 3: Graceful Termination**
*For any* execution that encounters quota exhaustion or execution time limits, the system should save all progress and terminate gracefully without data loss
**Validates: Requirements 1.4**

**Property 4: Exponential Backoff Retry**
*For any* temporary API failure, network issue, or checkpoint update failure, the system should implement exponential backoff retry logic up to a maximum threshold
**Validates: Requirements 2.1, 2.2, 2.4**

**Property 5: Data Preservation During Failures**
*For any* downstream processing failure or unrecoverable error, the system should preserve tweet data and maintain data integrity while logging detailed error context
**Validates: Requirements 2.3, 2.5**

**Property 6: Comprehensive Execution Logging**
*For any* execution, the system should log start/end times, tweet counts, rate limit encounters, errors, checkpoint updates, and batch processing status with sufficient context for debugging
**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

**Property 7: Memory-Efficient Processing**
*For any* result set size, the system should stream results rather than loading everything into memory, minimize object allocation during transformation, and implement memory management when approaching limits
**Validates: Requirements 4.1, 4.3, 4.5**

**Property 8: Optimal Batch Processing**
*For any* tweet collection, the system should create optimally-sized batches based on downstream capacity and efficiently process media lookup operations
**Validates: Requirements 4.2, 4.4**

**Property 9: Atomic Checkpoint Management**
*For any* checkpoint update operation, including concurrent executions, the system should ensure atomic updates, handle conflicts gracefully, and enable proper recovery from the last successful checkpoint
**Validates: Requirements 5.1, 5.2, 5.3**

**Property 10: Checkpoint Recovery and Initialization**
*For any* startup scenario, whether resuming after failure or starting fresh, the system should establish appropriate starting points and implement recovery mechanisms for corrupted checkpoint data
**Validates: Requirements 5.4, 5.5**

**Property 11: Secure Credential Handling**
*For any* API credential usage, the system should retrieve and handle credentials securely through AWS Systems Manager without exposing sensitive information
**Validates: Requirements 6.3**

**Property 12: Comprehensive Test Support**
*For any* testing scenario, the system should support mock API responses, error simulation, checkpoint validation, batch verification, and end-to-end testing capabilities
**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

<function_calls>
<invoke name="prework">
<parameter name="featureName">twitter-poller-optimization

## Error Handling

### Error Classification Strategy

**Retryable Errors:**
- Network timeouts and connection errors
- HTTP 429 (Rate Limited) - with appropriate backoff
- HTTP 500/502/503/504 (Server errors)
- Temporary DynamoDB throttling
- Lambda timeout approaching (graceful termination)

**Non-Retryable Errors:**
- HTTP 401/403 (Authentication/Authorization)
- HTTP 400 (Bad Request) - malformed queries
- Invalid API credentials
- Permanent DynamoDB errors (table not found)

### Exponential Backoff Implementation

```python
def calculate_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 300.0) -> float:
    """Calculate exponential backoff with jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0.1, 0.3) * delay
    return delay + jitter
```

### Error Context Preservation

All errors will be logged with:
- Correlation ID for request tracking
- Full API request/response context
- Current checkpoint state
- Memory and execution time metrics
- Retry attempt history

## Testing Strategy

### Dual Testing Approach

The system requires both unit testing and property-based testing to ensure comprehensive coverage:

**Unit Tests:**
- Specific API response scenarios
- Error condition handling
- Checkpoint edge cases
- Memory management boundaries
- Integration points between components

**Property-Based Tests:**
- Universal behaviors across all input variations
- Rate limit compliance across different scenarios
- Checkpoint atomicity under concurrent access
- Memory efficiency across varying data sizes
- Error handling consistency across failure types

### Property-Based Testing Framework

The implementation will use **Hypothesis** for Python property-based testing, configured to run a minimum of 100 iterations per property test. Each property-based test will be tagged with comments explicitly referencing the correctness property from this design document using the format: **Feature: twitter-poller-optimization, Property {number}: {property_text}**

### Testing Infrastructure Requirements

**Mock API Framework:**
- Configurable rate limit simulation
- Network failure injection
- Response pagination simulation
- Credential validation testing

**Checkpoint Testing:**
- Concurrent access simulation
- Corruption scenario testing
- Recovery mechanism validation
- Atomic operation verification

**Memory Testing:**
- Large dataset processing
- Memory leak detection
- Garbage collection monitoring
- Lambda limit simulation

### Integration Testing

End-to-end testing scenarios will validate:
- Complete execution cycles with real API responses
- Checkpoint persistence across Lambda invocations
- Downstream batch processing integration
- CloudWatch metrics and logging integration
- Error recovery and resumption flows