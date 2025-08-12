# FinBrain Production Deployment Guide

## Production Status
- ✅ **Local Development**: All endpoints working (health: 200, webhook verification: ✅)
- ✅ **Safety Fixes Applied**: Lazy imports and optional scheduler for production stability
- ⚠️ **Production Deployment**: Needs fresh deployment to resolve 500 errors

## Current Production URL
```
https://finbrain-chowdhurysujan7.replit.app
```

## Meta Webhook Configuration
**Use these exact values in Meta Developer Console:**

```
Callback URL: https://finbrain-chowdhurysujan7.replit.app/webhook/messenger
Verify Token: finbrain_verify_123
Webhook Fields: messages, messaging_postbacks
```

## Environment Variables (Required)
All required environment variables are properly configured:
- ✅ `DATABASE_URL`: PostgreSQL connection
- ✅ `ADMIN_USER`: Dashboard authentication  
- ✅ `ADMIN_PASS`: Dashboard authentication
- ✅ `FACEBOOK_PAGE_ACCESS_TOKEN`: Facebook Messenger API access
- ✅ `FACEBOOK_VERIFY_TOKEN`: Webhook verification (finbrain_verify_123)

## Production Safety Features
- **Lazy imports**: Critical dependencies loaded only when needed
- **Optional scheduler**: Background reports disabled by default (ENABLE_REPORTS=false)
- **Strict validation**: App refuses to start if any required environment variable is missing
- **Error resilience**: Graceful degradation for optional features

## Deployment Steps
1. **Click Deploy**: Use Replit's Deploy button in the interface
2. **Wait for Build**: Allow Replit to build and deploy the application  
3. **Verify Health**: Test `/health` endpoint returns 200 OK
4. **Configure Webhook**: Use the webhook URL in Meta Developer Console
5. **Test Integration**: Send test message to verify end-to-end flow

## Production Testing Commands
```bash
# Test health endpoint
curl https://finbrain-chowdhurysujan7.replit.app/health

# Test webhook verification
curl "https://finbrain-chowdhurysujan7.replit.app/webhook/messenger?hub.mode=subscribe&hub.challenge=TEST123&hub.verify_token=finbrain_verify_123"

# Expected: Should return "TEST123" with 200 status
```

## **CRITICAL: Production Deployment Issue Confirmed**

**Current Status:**
- ✅ **Local Development**: All endpoints working perfectly (`health: 200 OK`, `webhook verification: ✅`)
- ❌ **Production Deployment**: 500 Internal Server Error on ALL endpoints
- 🔧 **Root Cause**: Production deployment is broken/outdated

**Debug Results:**
```
Production URL: https://finbrain-chowdhurysujan7.replit.app
- Health endpoint: 500 Internal Server Error  
- Home page: 500 Internal Server Error
- Webhook endpoint: 500 Internal Server Error
```

**Solution Required:**
1. **DEPLOY NOW**: Click the **Deploy** button in Replit interface
2. **Wait for completion**: Allow build and deployment to finish
3. **Verify endpoints**: Test health and webhook after deployment
4. **Configure Meta**: Once working, set up webhook in Meta Developer Console

**The webhook verification code is correct and ready** - just needs working production deployment.

## **Dependencies Fixed**
✅ Added `requests` dependency to `pyproject.toml` for production deployment  
✅ All required Python packages now properly configured