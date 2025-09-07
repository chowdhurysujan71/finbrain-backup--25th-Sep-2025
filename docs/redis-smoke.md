# Redis Smoke Test Endpoint

## Purpose

The `/redis-smoke` endpoint provides a minimal, safe way to validate Redis connectivity for monitoring and troubleshooting purposes. It performs a simple SET/GET operation with a short-lived key to verify Redis is reachable and functioning correctly.

## Endpoint

**GET /redis-smoke**

No request parameters required.

## Response Examples

### Success Response (200)

```json
{
  "connected": true,
  "value": "ok"
}
```

### Failure Response (503)

```json
{
  "connected": false,
  "error": "redis connection failed: Connection refused"
}
```

## Response Fields

- `connected` (boolean): Whether Redis connectivity test succeeded
- `value` (string|null): Value retrieved from Redis test key (only present when connected=true)
- `error` (string): Error description (only present when connected=false)

## Test Operation

The endpoint performs these steps:

1. Checks if `REDIS_URL` environment variable is configured
2. Creates Redis client with 3-second connect/socket timeouts
3. Sets key `smoke:test` with value `"ok"` and 5-second TTL
4. Retrieves the key value
5. Returns success/failure with latency metrics

## Structured Logging

Each request generates a structured JSON log entry:

```json
{
  "event": "redis_smoke",
  "connected": true,
  "latency_ms": 45,
  "error": "optional error message"
}
```

## Error Scenarios

### Missing REDIS_URL

**Response:** 503
```json
{
  "connected": false,
  "error": "missing REDIS_URL"
}
```

**Solution:** Set the `REDIS_URL` environment variable with your Redis connection string.

### Connection Refused

**Response:** 503
```json
{
  "connected": false,
  "error": "redis connection failed: Connection refused"
}
```

**Troubleshooting:**
- Verify Redis server is running
- Check host and port in REDIS_URL
- Ensure network connectivity to Redis instance
- Check firewall/security group settings

### Authentication Failed

**Response:** 503
```json
{
  "connected": false,
  "error": "redis authentication failed: Authentication required"
}
```

**Troubleshooting:**
- Verify username/password in REDIS_URL
- Check Redis AUTH configuration
- Ensure credentials haven't expired

### Timeout

**Response:** 503
```json
{
  "connected": false,
  "error": "redis timeout: Timeout connecting to server"
}
```

**Troubleshooting:**
- Check network latency to Redis instance
- Verify Redis server performance/load
- Consider increasing timeout if needed
- Check for DNS resolution issues

### TLS/SSL Issues

**Response:** 503
```json
{
  "connected": false,
  "error": "redis connection failed: SSL connection error"
}
```

**Troubleshooting:**
- Verify REDIS_URL uses `rediss://` for SSL connections
- Check TLS certificate validity
- Ensure client supports required TLS version
- Verify CA certificates are available

### Wrong Database Password

**Response:** 503
```json
{
  "connected": false,
  "error": "redis authentication failed: invalid password"
}
```

**Troubleshooting:**
- Double-check password in REDIS_URL
- Verify no special characters need URL encoding
- Check if Redis requires specific authentication method

### Network Error

**Response:** 503
```json
{
  "connected": false,
  "error": "redis connection failed: Name or service not known"
}
```

**Troubleshooting:**
- Verify hostname in REDIS_URL is correct
- Check DNS resolution for Redis hostname
- Ensure network connectivity to Redis host
- Verify Redis instance is publicly accessible (if applicable)

## REDIS_URL Formats

The endpoint supports standard Redis URL formats:

### Basic Connection
```
redis://localhost:6379
redis://redis.example.com:6379
```

### With Authentication
```
redis://:password@redis.example.com:6379
redis://username:password@redis.example.com:6379
```

### SSL/TLS Connection
```
rediss://redis.example.com:6380
rediss://username:password@redis.example.com:6380
```

### With Database Selection
```
redis://redis.example.com:6379/0
redis://redis.example.com:6379/1
```

### Unix Socket
```
unix://path/to/redis.sock
```

## URL Format Handling

- URLs without protocol prefix get `redis://` prepended automatically
- `localhost:6379` becomes `redis://localhost:6379`
- Existing `redis://`, `rediss://`, and `unix://` prefixes are preserved

## Security Considerations

- The test key `smoke:test` has a 5-second TTL to minimize Redis memory usage
- No sensitive data is stored or transmitted
- Connection timeouts prevent indefinite hangs
- All exceptions are caught to prevent information leakage
- Credentials are never logged or returned in responses

## Monitoring Integration

Use this endpoint for:

- **Health Checks:** Include in load balancer health checks
- **Monitoring:** Alert on 503 responses or high latency
- **Troubleshooting:** Quick Redis connectivity validation
- **CI/CD:** Verify Redis availability before deployment

### Example Health Check Script

```bash
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/redis-smoke)
if [ "$response" = "200" ]; then
    echo "Redis OK"
    exit 0
else
    echo "Redis FAIL (HTTP $response)"
    exit 1
fi
```

### Example Monitoring Alert

```yaml
# Prometheus/AlertManager example
- alert: RedisConnectivityFailed
  expr: probe_success{job="redis-smoke"} == 0
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Redis connectivity test failing"
    description: "Redis smoke test endpoint returning 503 for {{ $labels.instance }}"
```

## Performance

- **Typical Latency:** 1-50ms for local Redis instances
- **Timeout:** 3 seconds maximum per operation
- **Memory Usage:** Minimal (single 5-second TTL key)
- **Redis Commands:** 2 per request (SET + GET)

## Integration with Existing Health Checks

This endpoint complements the existing `/readyz` and `/health` endpoints:

- `/health` - Basic application health
- `/readyz` - Production readiness (includes Redis check)
- `/redis-smoke` - Dedicated Redis connectivity test

The dedicated endpoint provides more detailed Redis-specific error information for troubleshooting purposes.