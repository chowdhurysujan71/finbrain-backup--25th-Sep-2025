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

## Current Issue
The production deployment is returning 500 Internal Server Error on all endpoints. This requires:
1. Fresh deployment via Replit Deploy button
2. Waiting for deployment completion
3. Retesting all endpoints

Once deployed successfully, the Meta webhook validation will work immediately.