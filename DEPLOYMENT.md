# FinBrain Deployment Guide

## Replit Deployment Configuration

### 1. Run Command Configuration
Set the deployment run command to:
```bash
gunicorn -w 2 -k gthread --threads 8 --timeout 30 --graceful-timeout 30 --bind 0.0.0.0:$PORT main:app
```

This configuration provides:
- **2 workers** for concurrent request handling
- **gthread worker** class with 8 threads per worker (16 total threads)
- **30-second timeout** for request processing
- **30-second graceful timeout** for shutdown
- **Dynamic port binding** using Replit's $PORT variable

### 2. App Settings
- **App Type**: Web Server
- **Always-On**: Enable (for 24/7 availability)
- **Autoscaling**: Enable for traffic-based scaling

### 3. Required Environment Variables

#### Core Secrets (Essential)
```
DATABASE_URL=postgresql://...
FACEBOOK_PAGE_ACCESS_TOKEN=EAA...
FACEBOOK_VERIFY_TOKEN=your_webhook_verify_token
ADMIN_USER=admin
ADMIN_PASS=secure_admin_password
```

#### Optional Secrets
```
SENTRY_DSN=https://...  (if using error monitoring)
```

### 4. Removed Secrets
The following secrets have been removed from the deployment (no longer needed):
- All TWILIO_* secrets (WhatsApp integration removed)
- Magic-link authentication secrets (using PSID-only for MVP)
- FACEBOOK_APP_SECRET (webhook signature verification not required for MVP)
- AI enhancement keys (future feature)
- CSV encryption keys (not needed for MVP)

### 5. Performance Characteristics
- **Webhook Response Time**: <300ms (typically ~1.5ms)
- **Concurrent Users**: Up to 16 simultaneous requests
- **Database**: PostgreSQL with connection pooling
- **Message Processing**: Async background processing

### 6. Health Check
The application includes a health check endpoint at `/health` that verifies:
- Application status
- Database connectivity
- Platform support confirmation

### 7. Security Features
- SHA-256 hashing for all user identifiers
- Message deduplication by Facebook message ID
- Rate limiting (50 messages/day, 10/hour per user)
- No raw personal data storage

## Post-Deployment Verification

1. **Health Check**: Visit `/health` endpoint
2. **Webhook Test**: Verify Facebook webhook responds with 200
3. **Dashboard Access**: Test admin login functionality
4. **Message Processing**: Send test expense message via Messenger
5. **Performance**: Confirm sub-300ms webhook response times