# Redis Job Queue Specification

## Overview

The Redis Job Queue system provides asynchronous job processing with comprehensive error handling, rate limiting, and circuit breaker protection. It's designed for production-scale operations with ≥90% reliability and <25ms local processing latency.

## Architecture

### Core Components

1. **JobQueue** (`utils/job_queue.py`) - Redis-backed job queue with retries and DLQ
2. **CircuitBreaker** (`utils/circuit_breaker.py`) - AI provider failure protection  
3. **JobProcessor** (`utils/job_processor.py`) - Job execution engine with Supabase storage
4. **RateLimiter** (`utils/rate_limiter_jobs.py`) - 60 jobs/hour per user protection
5. **BackgroundProcessor** - Extended for Redis job polling alongside message processing

### Data Flow

```
Client → POST /jobs → Rate Limit → Circuit Breaker → Redis Queue
                                                         ↓
Background Worker ← Redis BRPOP ← Job Processor ← Supabase Results
```

## API Endpoints

### POST /jobs
Enqueue job with validation and rate limiting.

**Headers:**
- `Content-Type: application/json`
- `X-User-ID: {user_identifier}` (required)

**Request Body:**
```json
{
  "type": "ai_analysis|file_processing|notification",
  "payload": {
    "text": "content to analyze",
    "file_url": "optional file reference",
    "options": {}
  },
  "idempotency_key": "unique_per_user_request"
}
```

**Response (201):**
```json
{
  "job_id": "uuid-v4-identifier", 
  "status": "queued"
}
```

**Errors:**
- `400` - Missing X-User-ID, invalid JSON, missing required fields
- `413` - Payload exceeds 1MB limit
- `429` - Rate limit exceeded (60/hour) or circuit breaker open
- `503` - Redis unavailable

**Performance:** <50ms response time guaranteed

### GET /jobs/{job_id}/status
Get job status and metadata.

**Headers:**
- `X-User-ID: {user_identifier}` (required)

**Response (200):**
```json
{
  "job_id": "uuid",
  "status": "queued|processing|completed|failed|cancelled",
  "type": "ai_analysis",
  "created_at": 1694123456.789,
  "updated_at": 1694123466.123,
  "attempts": 1,
  "result_url": "https://storage.supabase.co/...",
  "error": "optional error message"
}
```

### POST /jobs/{job_id}/cancel
Cancel job (best effort).

**Response (200):**
```json
{
  "message": "Job cancelled successfully"
}
```

### GET /jobs/status
Get job queue system health.

**Response (200/503):**
```json
{
  "redis_connected": true,
  "circuit_breaker_open": false, 
  "queue_stats": {
    "queued": 12,
    "processing": 3,
    "retry": 1,
    "dlq": 0
  },
  "timestamp": 1694123456
}
```

## Job Types

### ai_analysis
AI-powered content analysis and categorization.

**Payload:**
```json
{
  "text": "Content to analyze",
  "user_context": "optional context",
  "analysis_type": "expense|general|sentiment"
}
```

**Result:**
```json
{
  "analysis": {
    "category": "food",
    "confidence": 0.92,
    "amount": 25.50,
    "currency": "USD"
  },
  "processing_time_ms": 1234
}
```

### file_processing  
File upload, validation, and processing.

**Payload:**
```json
{
  "file_url": "https://supabase.co/storage/...",
  "processing_type": "image_analysis|document_extract",
  "options": {
    "resize": true,
    "extract_text": true
  }
}
```

### notification
Deferred notification delivery.

**Payload:**
```json
{
  "channel": "email|sms|push",
  "recipient": "user@example.com",
  "template": "expense_summary",
  "data": {}
}
```

## Configuration

### Environment Variables

- `REDIS_URL` - Redis connection string (required)
- `SUPABASE_URL` - File storage endpoint (optional)
- `SUPABASE_SERVICE_KEY` - Storage authentication (optional)

### Rate Limits

- **Global Limit**: 60 jobs/hour per user
- **Burst Limit**: 10 jobs/minute per user
- **Payload Limit**: 1MB per job
- **TTL**: 24h job metadata, 7d DLQ retention

### Circuit Breaker

- **Failure Threshold**: 5 failures in 60 seconds
- **Open Duration**: 30 seconds
- **Half-Open Test**: Single request
- **Protected Operations**: AI API calls, external services

### Retry Policy

- **Max Attempts**: 3 per job
- **Backoff**: Exponential (1s, 5s, 30s)
- **DLQ**: Failed jobs after max attempts
- **Cleanup**: Automatic after TTL expiration

## Monitoring & Observability

### Health Checks

- `/readyz` includes Redis connectivity
- `/jobs/status` provides queue health
- Background worker logs connection status
- Circuit breaker state changes logged

### Metrics

- Job enqueue rate and latency
- Processing success/failure rates  
- Circuit breaker state transitions
- Queue depth and processing times
- Redis connection health

### Structured Logging

All job operations include:
```json
{
  "ts": 1694123456789,
  "level": "info",
  "component": "job_queue", 
  "job_id": "uuid",
  "user_id": "hash",
  "operation": "enqueue|dequeue|process|complete",
  "latency_ms": 123,
  "status": "success|error"
}
```

## Error Handling

### Graceful Degradation

- **Redis Unavailable**: Returns 503, preserves application functionality
- **Circuit Open**: Rejects new jobs, allows status queries
- **Storage Unavailable**: Jobs process without result persistence
- **Rate Limit**: Clear retry-after headers

### Dead Letter Queue

Failed jobs (after 3 attempts) move to DLQ with:
- Original job metadata
- Failure history and error messages
- 7-day retention for manual investigation
- Admin dashboard visibility

### Recovery Procedures

1. **Redis Connection Lost**: Auto-retry with exponential backoff
2. **Circuit Breaker Open**: Automatic half-open testing after timeout
3. **Job Stuck**: TTL-based cleanup prevents accumulation
4. **DLQ Processing**: Manual retry mechanism via admin interface

## Security

### Authentication
- All endpoints require `X-User-ID` header
- User isolation via hashed identifiers
- No cross-user job access

### Input Validation
- JSON schema validation
- Payload size limits (1MB)
- XSS/injection prevention
- Unicode normalization

### Data Protection
- Job payloads encrypted in transit
- No sensitive data in logs
- TTL-based automatic cleanup
- Secure Redis connections (TLS)

## Performance Guarantees

- **Enqueue Latency**: <50ms (99th percentile)
- **Processing Latency**: <25ms local operations
- **Throughput**: 1000+ jobs/hour/worker
- **Reliability**: ≥90% success rate
- **Availability**: Graceful degradation without Redis

## Testing

Comprehensive test suite covers:
- Unit tests with Redis mocking
- Integration tests with full stack
- Load testing for performance validation
- Chaos engineering for failure scenarios
- End-to-end acceptance testing

See `tests/test_job_queue.py` for detailed test cases.