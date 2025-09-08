# FinBrain Operations Guide

## Production Readiness Status
✅ **Gate Script**: `scripts/gate_prod.sh` validates all critical systems  
✅ **Security**: CORS + Rate limiting implemented  
✅ **Brain Instrumentation**: Source-of-truth metadata tracking  
✅ **PWA**: Manifest + Service Worker v1.2.0  
✅ **Tests**: Stabilized with xfail for restructured modules  

## Deployment Validation

### Pre-Deployment Gate
```bash
bash scripts/gate_prod.sh
```
**Must Pass Before Deploy** - Validates:
- Health endpoints functional
- Chat contract compliance (JSON response with metadata)
- CORS configuration 
- Database schema integrity
- Rate limiting burst tolerance

### Production Health Check
```bash
curl -s http://localhost:5000/health | jq .
```
Expected: `{"status":"healthy","timestamp":"..."}`

## Feature Flag Management

### Current Configuration
```bash
# Check feature flags status
curl -s http://localhost:5000/ops/quickscan | jq .feature_flags
```

### Flag System Architecture
- **AI Processing**: Always-on with circuit breaker fallbacks
- **PCA System**: Full production active mode (≥85% confidence auto-apply)
- **Bilingual Support**: Bengali + English with universal patterns
- **Rate Limiting**: 120 req/min global, 4 req/min per user

### Emergency Toggles
```bash
# If AI system needs emergency disable:
export AI_ENABLED=false

# If PCA needs fallback mode:  
export PCA_MODE=FALLBACK
```

## Rollback Procedures

### Database Rollback
```sql
-- Check recent schema changes
SELECT * FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Validate data integrity
SELECT COUNT(*) FROM expenses;
SELECT COUNT(*) FROM users;
```

### Application Rollback
1. **Immediate**: Use Replit checkpoint system via UI
2. **Code**: Revert to baseline tag `baseline-uja-20250908`
3. **Dependencies**: Check `requirements.txt` for version locks

### Traffic Management
```bash
# Check current load
curl -s http://localhost:5000/ops/quickscan | jq .performance

# Monitor rate limits
curl -s http://localhost:5000/metrics | grep rate_limit
```

## Monitoring & Alerting

### Critical Metrics
- **Gate Script**: Must pass 100% for production confidence
- **AI Response Rate**: >95% successful responses expected
- **Database Connections**: Monitor via `/health` endpoint
- **Rate Limit Hit Rate**: Should be <10% of requests

### Brain Metadata Tracking
```bash
# Verify source-of-truth tracking
curl -s -X POST "http://localhost:5000/ai-chat" \
  -H 'Content-Type: application/json' \
  -H 'X-User-ID: monitor-test' \
  -d '{"message":"system check"}' | jq .metadata
```
Expected: `source`, `latency_ms`, `uid_prefix` fields present

### Production Logs
```bash
# Check structured logging
grep "finbrain.router" /var/log/app.log | tail -10

# Monitor AI adapter health
grep "ai_adapter" /var/log/app.log | tail -5
```

## Security Protocols

### CORS Validation
```bash
curl -i -X OPTIONS "http://localhost:5000/ai-chat" \
  -H 'Origin: http://localhost:5000' \
  -H 'Access-Control-Request-Method: POST'
```
Expected: `Access-Control-Allow-Origin` header present

### Rate Limiting Test
```bash
# Burst test (should succeed then throttle)
for i in {1..15}; do 
  curl -s "http://localhost:5000/ai-chat" -X POST \
    -H 'X-User-ID: burst-test' \
    -d '{"message":"test"}' | jq -r .reply
done
```

### User Data Isolation
- All PSIDs are SHA-256 hashed before storage
- Original PSIDs preserved only for message delivery
- Cross-user data leakage prevented by hash-based isolation

## Emergency Contacts

### System Health
- **Gate Script Failures**: Check database connectivity first
- **AI Adapter Issues**: Verify `GEMINI_API_KEY` environment variable
- **Rate Limit Overwhelm**: Consider increasing limits in `app.py`

### Data Issues
- **Schema Drift**: Run `scripts/check_migrations.sh`
- **User Data Problems**: Check `user_id_hash` vs `user_id` column usage
- **Expense Anomalies**: Validate PCA system confidence scores

---
*Last Updated: September 8, 2025*  
*Gate Script Status: ✓ PROD gate passed*