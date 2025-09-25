# Production Environment Configuration

## Critical Environment Variables for MVP Launch

### Required for Production Deployment

```bash
# Runtime Configuration
export WEB_CONCURRENCY=4                    # Gunicorn worker processes (2-4 for MVP)
export ENV=production                       # Enables production security settings
export SENTRY_DSN=https://your-sentry-dsn   # Error monitoring (required for ENV=production)

# Database (already configured)
export DATABASE_URL=postgresql://...        # PostgreSQL connection string

# Security (already configured)
export SESSION_SECRET=your-secret-key       # Flask session encryption
export ID_SALT=your-id-salt                # User ID hashing salt

# Authentication (already configured)  
export ADMIN_USER=admin                     # Admin username
export ADMIN_PASS=secure-password          # Admin password
```

### Performance Tuning for 200-500 Concurrent Users

```bash
# Gunicorn Configuration
WEB_CONCURRENCY=4                          # 4 worker processes
WORKER_CLASS=sync                          # Sync workers (default)
WORKER_TIMEOUT=30                          # Request timeout (seconds)
KEEP_ALIVE=2                               # Connection keep-alive

# Database Connection Pool (auto-configured)
# pool_size=10, max_overflow=20, pool_timeout=30
```

### Optional Configuration

```bash
# Redis (falls back to in-memory if unavailable)
export REDIS_URL=rediss://user:pass@host:port  # Rate limiting storage

# Feature Flags (defaults to enabled)
export AI_ENABLED=true                     # AI processing
export ENABLE_REPORTS=true                # Background reports
```

## Security Features (Auto-Enabled)

✅ **Cookie Security:** HttpOnly, Secure (HTTPS), SameSite=Lax  
✅ **CORS Protection:** Restricted to finbrain.app domains  
✅ **Database:** Connection pooling, SSL, prepared statements  
✅ **Rate Limiting:** 120 req/min global, 4 req/min per user  
✅ **Input Validation:** XSS prevention, SQL injection protection  

## Monitoring & Alerts

- **Sentry:** Error tracking and performance monitoring (required for production)
- **Health Checks:** `/health` endpoint for load balancer monitoring
- **Structured Logging:** JSON logs for log aggregation
- **Database Monitoring:** Connection pool metrics, query performance

## Capacity Planning

**Current MVP Capacity:**
- **50-100 users** without Redis (in-memory rate limiting)
- **200-500 users** with Redis + WEB_CONCURRENCY=4
- **2000+ users** with horizontal scaling

**Scaling Path:**
1. Increase WEB_CONCURRENCY (4 → 8)
2. Add Redis for persistent rate limiting  
3. Implement read replicas for analytics
4. Add load balancer for multiple instances