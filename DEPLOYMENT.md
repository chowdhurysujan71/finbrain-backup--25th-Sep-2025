# FinBrain Production Deployment

## Production Configuration

### Environment Variables
All required environment variables must be set for production deployment:
- `DATABASE_URL` - PostgreSQL connection string
- `ADMIN_USER` - HTTP Basic Auth username for admin dashboard
- `ADMIN_PASS` - HTTP Basic Auth password for admin dashboard
- `FACEBOOK_PAGE_ACCESS_TOKEN` - Facebook Messenger API access token
- `FACEBOOK_VERIFY_TOKEN` - Facebook webhook verification token
- `ENV=production` - Enables production logging mode (INFO level, no reload)

### Production Logging
The application implements structured JSON logging for production observability:

#### Request Logging
Every inbound request is logged with:
```json
{
  "timestamp": "2025-08-12T13:45:00.000Z",
  "event_type": "request_start",
  "rid": "a1b2c3d4",
  "method": "POST",
  "route": "/webhook/messenger",
  "user_agent": "FacebookBot/1.0",
  "content_length": 256
}
```

#### Facebook Graph API Calls
Every outbound Facebook Graph API call is logged:
```json
{
  "timestamp": "2025-08-12T13:45:01.000Z",
  "event_type": "graph_api_call",
  "rid": "a1b2c3d4",
  "endpoint": "/v17.0/me/messages",
  "method": "POST",
  "status": 200,
  "duration_ms": 150.25
}
```

#### Webhook Processing
Successful message processing includes:
```json
{
  "timestamp": "2025-08-12T13:45:01.500Z",
  "event_type": "webhook_processed",
  "rid": "a1b2c3d4",
  "psid_hash": "sha256_hash_of_psid",
  "mid": "message_id_from_facebook",
  "intent": "log",
  "category": "food",
  "amount": 50,
  "processing_ms": 45.2
}
```

### Production Deployment Command
```bash
# Production mode (no reload, INFO logging)
ENV=production gunicorn --bind 0.0.0.0:5000 --reuse-port main:app
```

### Security Features
- ✅ Strict environment validation (boot failure if missing required vars)
- ✅ HTTP Basic Auth for all admin endpoints
- ✅ PSID hashing (no PII in logs)
- ✅ Request rate limiting
- ✅ 24-hour messaging policy compliance
- ✅ Webhook signature verification support

### Monitoring Endpoints
- `/health` - Service health with environment status
- `/ops` - Operational metrics (admin auth required)
- `/psid/<hash>` - User investigation tool (admin auth required)

## No PII Policy
The structured logging system ensures no personally identifiable information is logged:
- PSIDs are hashed using SHA-256
- Message content is not logged
- Only metadata and performance metrics are captured