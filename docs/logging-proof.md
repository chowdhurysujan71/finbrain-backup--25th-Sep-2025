# Logging Proof (finbrain-app)

## Overview

**Logger**: Existing utils/logger.py structured system  
**Format**: JSON lines to stdout  
**Integration**: Flask middleware captures all HTTP requests  

## Log Fields

Each request generates one JSON log line with these fields:

```json
{
  "ts": 1757226276242,          // epoch milliseconds
  "level": "info",              // log level  
  "request_id": "uuid4-string", // unique request identifier
  "method": "GET",              // HTTP method
  "path": "/health",            // request path
  "status": 200,                // HTTP status code
  "latency_ms": 0.12,          // request duration in milliseconds
  "user_id": "optional"         // from X-User-ID header if present
}
```

## Request ID Handling

- **Header Propagation**: X-Request-ID header value used if present
- **Generation**: UUID4 generated if no header provided
- **Response Echo**: X-Request-ID header added to all responses
- **Correlation**: Same request_id used across all logs for the request

## Verification Steps

### 1. Basic Health Check with Logging
```bash
curl -i http://localhost:5000/health
```

**Expected**:
- HTTP 200 response
- X-Request-ID header present in response
- JSON log line in console with ~0.1ms latency

**Sample Log**:
```json
{"ts": 1757226276242, "level": "info", "request_id": "a64f6a5d-fa78-4b9e-9954-7b56a1821352", "method": "GET", "path": "/health", "status": 200, "latency_ms": 0.12}
```

### 2. Readiness Check with Status Variation
```bash
# With AI key set and DB reachable → 200
curl -s http://localhost:5000/readyz

# Expected log shows status 200, latency <2000ms
```

### 3. Request ID Propagation Test
```bash
curl -H "X-Request-ID: test-123" http://localhost:5000/health
```

**Expected**:
- Response header: `X-Request-ID: test-123`
- Log contains: `"request_id": "test-123"`

### 4. User ID Header Test
```bash
curl -H "X-User-ID: user-456" http://localhost:5000/health
```

**Expected**:
- Log contains: `"user_id": "user-456"`

### 5. Sentry Test (Production Only)
```bash
# Only if ENV=prod and SENTRY_DSN set
curl http://localhost:5000/__test_error
```

**Expected**:
- HTTP 500 response
- Sentry event created with request_id correlation
- Log line shows status 500

## Log Output Examples

### Successful Health Check
```json
{"ts": 1757226276242, "level": "info", "request_id": "a64f6a5d-fa78-4b9e-9954-7b56a1821352", "method": "GET", "path": "/health", "status": 200, "latency_ms": 0.12}
```

### Readiness Check with Dependencies
```json
{"ts": 1757226280125, "level": "info", "request_id": "b72e8f3a-1234-5678-9abc-def012345678", "method": "GET", "path": "/readyz", "status": 200, "latency_ms": 45.67}
```

### Error Endpoint Test
```json
{"ts": 1757226285890, "level": "info", "request_id": "c83f9e4b-abcd-1234-5678-9ef0abcd1234", "method": "GET", "path": "/__test_error", "status": 500, "latency_ms": 12.34}
```

### Request with User Context
```json
{"ts": 1757226290555, "level": "info", "request_id": "d94e0f5c-def0-abcd-9876-fedcba098765", "method": "GET", "path": "/health", "status": 200, "latency_ms": 0.08, "user_id": "user-456"}
```

## Integration with Existing Logger

The middleware integrates with the existing `utils/logger.py` system:

- **No Duplication**: Guards against existing logging to prevent duplicate entries
- **Same Infrastructure**: Uses `structured_logger.logger.info()` 
- **Consistent Format**: Maintains JSON structure used by existing system
- **Performance**: Minimal overhead, logging errors don't break responses

## Monitoring & Observability

- **Request Tracking**: Every HTTP request logged with unique ID
- **Performance Monitoring**: Latency captured for all endpoints
- **Error Correlation**: Failed requests linked to Sentry events via request_id
- **User Context**: Optional user identification when available
- **Structured Search**: JSON format enables easy log parsing and filtering