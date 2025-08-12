# FinBrain Deployment Guide

## Quick Deployment to Replit Reserved VM

### 1. VM Configuration
- **Type:** Web Server
- **Size:** 0.5 vCPU / 2 GB RAM
- **Always-On:** Enabled

### 2. Build & Run Commands
```bash
# Build Command
python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements.txt

# Run Command  
gunicorn --bind 0.0.0.0:5000 main:app
```

### 3. Required Environment Variables
```bash
# Facebook Integration (Required)
FACEBOOK_APP_SECRET=your_app_secret_here
FACEBOOK_APP_ID=your_app_id_here  
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_token_here
FACEBOOK_VERIFY_TOKEN=your_verify_token_here

# Database (Required)
DATABASE_URL=postgresql://user:pass@host:port/db

# Admin Access (Required)
ADMIN_USER=admin
ADMIN_PASS=secure_password_here

# Security (Required)
SESSION_SECRET=random_session_key

# Optional Configuration
AI_ENABLED=false
HEALTH_PING_ENABLED=true
ENABLE_REPORTS=false
```

### 4. Post-Deployment Testing
```bash
# Test health endpoint
curl https://your-app.replit.app/health

# Test version endpoint
curl https://your-app.replit.app/version

# Test webhook verification
curl https://your-app.replit.app/webhook/messenger?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test
```

### 5. Facebook Webhook Setup
1. Set webhook URL to: `https://your-app.replit.app/webhook/messenger`
2. Verify token matches FACEBOOK_VERIFY_TOKEN
3. Enable messages and messaging_postbacks events
4. Test with Facebook's webhook tester

## Security Features
✅ **HTTPS Enforcement** - Rejects HTTP requests  
✅ **Signature Verification** - Validates X-Hub-Signature-256  
✅ **Token Monitoring** - Tracks 60-day lifecycle  
✅ **Rate Limiting** - Per-user message limits  
✅ **Basic Auth** - Protects admin endpoints

## Monitoring Endpoints
- `/health` - System health and security status
- `/ops` - Operations metrics (Basic Auth required)
- `/ops/token-refresh-status` - Token monitoring (Basic Auth required)
- `/version` - Deployment version information

## Production Ready Features
- Comprehensive error handling
- Background job processing  
- Database connection pooling
- Structured logging
- Security hardening complete
- Automated health pings

Ready for production deployment!