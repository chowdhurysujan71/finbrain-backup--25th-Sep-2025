# Circuit Breaker Implementation

## Overview

The Circuit Breaker pattern protects FinBrain from cascading failures when external AI providers become unavailable. It automatically opens when failures exceed thresholds, preventing resource exhaustion and providing graceful degradation.

## Architecture

### States

1. **CLOSED** - Normal operation, requests flow through
2. **OPEN** - Failures exceeded threshold, requests rejected immediately  
3. **HALF_OPEN** - Testing recovery, limited requests allowed

### State Transitions

```
CLOSED --[failures > threshold]--> OPEN
  ↑                                   ↓
  |                         [timeout elapsed]
  |                                   ↓
  └--[success in half-open]-- HALF_OPEN
```

## Configuration

### Default Thresholds

- **Failure Threshold**: 5 failures in 60 seconds
- **Open Duration**: 30 seconds before half-open
- **Recovery**: Single successful request closes circuit

### Customization

```python
from utils.circuit_breaker import CircuitBreaker

# Custom configuration
breaker = CircuitBreaker(
    failure_threshold=10,    # More tolerant
    window_seconds=120,      # Longer failure window  
    timeout_seconds=60       # Longer recovery time
)
```

## Usage

### Basic Integration

```python
from utils.circuit_breaker import circuit_breaker

# Check before expensive operations
if circuit_breaker.is_open():
    return {"error": "Service temporarily unavailable"}, 503

try:
    # Call external service (AI API, etc)
    result = external_service_call()
    circuit_breaker.record_success()
    return result
except Exception as e:
    circuit_breaker.record_failure()
    raise
```

### Job Queue Integration

The circuit breaker is automatically integrated into the job queue system:

```python
# In job enqueue endpoint
if circuit_breaker.is_open():
    return jsonify({"error": "temporarily unavailable"}), 429
```

### AI Provider Protection

```python
# In AI processing
@circuit_breaker.protect
def call_ai_provider(prompt):
    # This call is automatically protected
    return ai_client.generate(prompt)
```

## Monitoring

### State Tracking

```python
# Check current state
print(f"Circuit state: {circuit_breaker.state}")
print(f"Failure count: {circuit_breaker.failure_count}")
print(f"Last failure: {circuit_breaker.last_failure_time}")
```

### Health Endpoints

Circuit breaker state is exposed in multiple endpoints:

- `/jobs/status` - Shows `circuit_breaker_open` status
- `/readyz` - Factors circuit state into readiness
- `/health` - Overall system health including circuit state

### Logging

State transitions are automatically logged:

```json
{
  "ts": 1694123456789,
  "level": "warn", 
  "component": "circuit_breaker",
  "event": "state_change",
  "from_state": "closed",
  "to_state": "open",
  "failure_count": 5,
  "window_seconds": 60
}
```

## Protected Operations

### AI API Calls

- OpenAI/Gemini text generation
- Image analysis requests
- Embedding calculations
- Fine-tuning operations

### External Services

- File storage uploads/downloads
- Email/SMS notifications
- Webhook deliveries
- Third-party integrations

### Database Operations

Heavy database queries can be protected:

```python
@circuit_breaker.protect
def complex_analytics_query():
    # Expensive database operation
    return db.session.execute(complex_query)
```

## Error Handling

### Client Responses

When circuit is open:

```json
{
  "error": "temporarily unavailable",
  "retry_after": 30,
  "circuit_state": "open"
}
```

### Fallback Strategies

```python
def get_ai_analysis_with_fallback(text):
    try:
        if circuit_breaker.is_open():
            # Use cached/simple fallback
            return get_cached_analysis(text)
        
        return call_ai_provider(text)
    except CircuitOpenError:
        return {"analysis": "unavailable", "fallback": True}
```

### Recovery Testing

The circuit breaker automatically tests recovery:

1. After timeout, enters HALF_OPEN state
2. Allows single request to test service
3. On success: closes circuit, resumes normal operation
4. On failure: reopens circuit, resets timeout

## Implementation Details

### Thread Safety

The circuit breaker is thread-safe for concurrent access:

```python
class CircuitBreaker:
    def __init__(self):
        self._lock = threading.RLock()
        # ... rest of implementation
```

### Memory Efficiency

- No persistent storage required
- Minimal memory footprint per instance
- Automatic cleanup of old failure records

### Performance

- State checks are O(1) operations
- Failure recording is minimal overhead
- No network calls during state evaluation

## Testing

### Unit Tests

```python
def test_circuit_opens_after_failures():
    breaker = CircuitBreaker(failure_threshold=3)
    
    # Record failures
    for _ in range(3):
        breaker.record_failure()
    
    assert breaker.is_open()
```

### Integration Tests

```python
def test_protected_operation():
    @circuit_breaker.protect
    def failing_operation():
        raise Exception("Service down")
    
    # After enough failures, should raise CircuitOpenError
    with pytest.raises(CircuitOpenError):
        failing_operation()
```

### Load Testing

The circuit breaker is tested under concurrent load:

- 1000+ simultaneous requests
- Mix of success/failure scenarios  
- State transition validation
- Performance impact measurement

## Production Considerations

### Monitoring Alerts

Set up alerts for:
- Circuit state transitions (closed → open)
- High failure rates approaching threshold
- Extended open periods indicating persistent issues

### Capacity Planning

Circuit breakers prevent resource exhaustion:
- Reduces load on failing services
- Prevents cascading failures
- Maintains system responsiveness

### Configuration Tuning

Adjust thresholds based on:
- Service SLA requirements
- Expected failure rates
- Recovery time objectives
- User experience impact

## Common Patterns

### Multiple Circuit Breakers

Use separate breakers for different services:

```python
ai_breaker = CircuitBreaker(name="ai_provider")
storage_breaker = CircuitBreaker(name="file_storage") 
notification_breaker = CircuitBreaker(name="notifications")
```

### Graduated Responses

Different actions based on circuit state:

```python
def handle_request():
    if ai_breaker.is_open():
        return cached_response()
    elif ai_breaker.is_half_open():
        return limited_ai_response()
    else:
        return full_ai_response()
```

### Metric Collection

```python
# Custom metrics
circuit_breaker.on_state_change = lambda old, new: \
    metrics.record_state_transition(old, new)

circuit_breaker.on_failure = lambda: \
    metrics.increment_failure_count()
```

This circuit breaker implementation ensures FinBrain remains resilient and responsive even when external dependencies fail, maintaining the high availability required for production operations.