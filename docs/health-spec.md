# Health & Readiness Spec (finbrain-app)

## Endpoints

### GET /health
- **Purpose**: Liveness probe - always available if process is running
- **Response**: 200 {"status":"ok"} 
- **Performance**: <100ms response time
- **Dependencies**: None - lightweight check only
- **Authentication**: None required

### GET /readyz
- **Purpose**: Readiness probe - validates system dependencies
- **Response**: 
  - 200 if DB OK AND AI key present
  - 503 if any critical dependency fails
- **Body Format**: {"db":bool,"redis":bool,"ai_key_present":bool}
- **Performance**: ≤2s total timeout budget

## Dependency Checks

### Database Check
- **Method**: psycopg3 direct connection with connect_timeout=2s
- **Query**: `SELECT 1`
- **Failure Conditions**: Connection timeout, query failure, missing DATABASE_URL

### Redis Check
- **Method**: redis.ping() with 1s socket timeout
- **Status**: Informational only (does not gate readiness)
- **Failure Conditions**: Connection timeout, ping failure, missing REDIS_URL

### AI Key Check
- **Method**: Environment variable presence check
- **Variables**: AI_API_KEY or GEMINI_API_KEY
- **Status**: Critical - gates readiness status

## Timeout Budget

- **Total /readyz execution**: ≤2s
- **DB connection timeout**: 2s
- **Redis socket timeout**: 1s
- **Warning logged**: If total exceeds 2s

## Runbook

### 503 Response Causes

#### Missing AI_API_KEY
```bash
# Diagnosis
curl -s /readyz | jq '.ai_key_present'
# false

# Resolution
export GEMINI_API_KEY="your-api-key"
# or set in Replit Secrets
```

#### Database Issues
```bash
# Diagnosis
curl -s /readyz | jq '.db'
# false

# Verify DATABASE_URL
echo $DATABASE_URL

# Check database health
psql $DATABASE_URL -c "SELECT 1;"
```

#### Redis Issues (Informational)
```bash
# Diagnosis
curl -s /readyz | jq '.redis'
# false - not critical but worth investigating

# Verify REDIS_URL
echo $REDIS_URL
```

## Acceptance Criteria

- [ ] `/health` returns 200 in <100ms consistently
- [ ] `/readyz` returns 200 only when DB OK and AI key present
- [ ] `/readyz` returns 503 with detailed status when dependencies fail
- [ ] Both endpoints include X-Request-ID header in responses
- [ ] `/__test_error` triggers Sentry event (when ENV=prod + SENTRY_DSN set)
- [ ] Request logging middleware captures all endpoint calls in JSON format

## Security

- Both endpoints are **public** (no authentication required)
- No sensitive information exposed in responses
- Error details logged but not returned in response body