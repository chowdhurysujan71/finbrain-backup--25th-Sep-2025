# Production Security Deployment Guide

## ✅ PRE-DEPLOYMENT SECURITY CHECKLIST

### 1. Gemini AI Security ✅
- [x] **Backend-only calls**: All AI processing server-side only
- [x] **API key protection**: GEMINI_API_KEY in secure environment variables
- [x] **Log sanitization**: Error messages sanitized, no API keys in logs
- [x] **Rate limiting**: RL-2 active (2/min per user, 10/min global)
- [x] **Kill switch**: AI_ENABLED=false instantly disables AI processing
- [x] **Request timeout**: 3-second limit prevents hanging requests

### 2. Facebook Webhook Security ✅
- [x] **Signature verification**: X-Hub-Signature-256 mandatory validation
- [x] **HTTPS enforcement**: HTTP requests rejected (Meta requirement)
- [x] **Token monitoring**: Automated Page Access Token expiry tracking
- [x] **Deduplication**: Message ID tracking prevents double processing

### 3. Admin Access Security ✅
- [x] **HTTP Basic Auth**: All admin endpoints protected
- [x] **Strong credentials**: ADMIN_USER/ADMIN_PASS from environment
- [x] **Endpoint isolation**: Admin routes separate from public API

### 4. Database Security ✅
- [x] **Connection pooling**: Secure PostgreSQL connection management
- [x] **PSID hashing**: All user IDs SHA-256 hashed
- [x] **No PII storage**: Raw personal data never stored
- [x] **SQL injection protection**: SQLAlchemy ORM used throughout

## 🎯 MANUAL ACTIONS REQUIRED

### Billing Protection (Critical)
**Status**: ⚠️ MANUAL SETUP REQUIRED

1. **Google Cloud Console Setup**:
   - Navigate to Google Cloud Console > Billing
   - Set up budget alerts:
     - Daily alert: $5 threshold
     - Monthly alert: $50 threshold
   - Configure quota limits for API usage

2. **Cost Monitoring**:
   - Enable detailed billing reports
   - Set up email notifications for budget alerts
   - Configure automatic quota enforcement

### API Key Rotation Schedule
**Status**: ✅ PLAN ESTABLISHED

- **Schedule**: Monthly rotation (next: September 13, 2025)
- **Process**:
  1. Generate new key in Google Cloud Console
  2. Update GEMINI_API_KEY in Replit Secrets
  3. Restart application (`kill switch -> restart`)
  4. Verify functionality with `/ops/ai/ping`
  5. Revoke old key
  6. Document rotation in security log

## 🚀 DEPLOYMENT VERIFICATION

Run this security verification before going live:

```bash
# 1. Verify all security measures
python security_audit.py

# 2. Test kill switch functionality
curl -X POST -u admin:pass http://your-domain.com/ops/ai/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# 3. Verify webhook security
curl -X POST http://your-domain.com/webhook/messenger \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}' 
# Should return 400/403 (signature required)

# 4. Test rate limiting
# Send 3+ messages from same user within 1 minute
# Should see 'path=fallback' after rate limit exceeded
```

## 📊 SECURITY MONITORING

### Real-time Monitoring
- **Health endpoint**: `/health` - system status and uptime
- **AI telemetry**: `/ops/ai/status` - AI usage and rate limiting
- **System telemetry**: `/ops/telemetry` - comprehensive metrics

### Key Security Metrics
- `ai_calls_blocked_per_psid`: Per-user rate limit enforcement
- `ai_calls_blocked_global`: Global rate limit enforcement  
- `ai_errors`: AI processing failures (monitor for attacks)
- `webhook_signature_failures`: Invalid webhook attempts

### Alerting Recommendations
1. **High AI error rate** (>10% failures) - potential attack
2. **Webhook signature failures** - unauthorized access attempts
3. **Unusual usage spikes** - potential quota abuse
4. **Health check failures** - system availability issues

## 🔒 PRODUCTION HARDENING

### Environment Configuration
```bash
# Required for production
ENV=production
AI_ENABLED=true
AI_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
FACEBOOK_PAGE_ACCESS_TOKEN=<your-token>
FACEBOOK_VERIFY_TOKEN=<your-verify-token>
FACEBOOK_APP_SECRET=<your-secret>
ADMIN_USER=<strong-username>
ADMIN_PASS=<strong-password>
DATABASE_URL=<postgres-connection>

# Optional but recommended
HEALTH_PING_ENABLED=true
AI_MAX_CALLS_PER_MIN=10
AI_MAX_CALLS_PER_MIN_PER_PSID=2
```

### Security Headers (Handled by Replit)
- HTTPS enforcement
- Security headers (HSTS, CSP, etc.)
- Rate limiting at edge
- DDoS protection

## ✅ COMPLIANCE STATUS

**OWASP Top 10**: ✅ Addressed  
**Meta Platform Security**: ✅ Compliant  
**Data Privacy**: ✅ No PII stored  
**API Security**: ✅ Rate limited, authenticated  
**Infrastructure Security**: ✅ Replit platform secured  

## 🆘 INCIDENT RESPONSE

### If API Key Compromised:
1. **Immediate**: Use kill switch (`AI_ENABLED=false`)
2. **Generate new key** in Google Cloud Console
3. **Update environment** with new key
4. **Restart application**
5. **Revoke compromised key**
6. **Review logs** for unauthorized usage
7. **Document incident** and improve procedures

### If Rate Limits Exceeded:
1. **Monitor** `/ops/telemetry` for usage patterns
2. **Adjust limits** if legitimate usage
3. **Investigate** potential abuse patterns
4. **Block abusive users** if necessary

### If System Compromise Suspected:
1. **Enable kill switch** immediately
2. **Review all logs** for unusual patterns
3. **Rotate all credentials** (API keys, admin passwords)
4. **Contact Replit support** if needed
5. **Update security measures** based on findings

**SECURITY POSTURE**: 🟢 PRODUCTION READY  
**LAST AUDIT**: August 13, 2025  
**NEXT REVIEW**: September 13, 2025 (with key rotation)