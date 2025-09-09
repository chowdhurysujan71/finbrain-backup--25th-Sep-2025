# Evidence Annex - Technical Probe Results
**FinBrain System Analysis - September 9, 2025**

This document contains the raw technical evidence that supports all claims in the non-technical report.

## Probe Results Summary

All probes were executed against the live system running at `http://localhost:5000` on September 9, 2025 between 04:59-05:03 UTC. Evidence artifacts are stored in timestamped directories under `results/`.

### 1. Routes Analysis Probe

**Objective**: Count available endpoints and verify chat API exists  
**Method**: HTTP requests and code analysis  
**Results**:
- Found 16+ Flask route decorators across codebase files
- `/ai-chat` endpoint confirmed exists (returns 405 for GET, requires POST)
- Main UI routes active: `/chat`, `/report`, `/profile`, `/challenge`, `/offline`

**Evidence Files**:
- `results/20250909_045905/ai_chat_status.txt` (contains: "405")
- System logs show successful routing to endpoints

### 2. Chat Contract Test Probe  

**Objective**: Verify chat API returns proper JSON structure with metadata  
**Method**: POST request to `/ai-chat` with test message  
**Command**: `curl -X POST /ai-chat -H 'Content-Type: application/json' -d '{"message":"I spent 200 on lunch"}'`
**Results**:
- ✅ Returns valid JSON response
- ✅ Contains required fields: `reply`, `data`, `user_id`, `metadata`
- ✅ Metadata includes `latency_ms: 4925`, `source: "production_router"`  
- ✅ Processing successful with expense logging functionality

**Evidence Files**:
- `results/20250909_045905/chat_contract_test.json` (full response)
- System logs show request processing: `"status": 200, "latency_ms": 4933.28`

### 3. Performance Test Probe

**Objective**: Measure response times under load  
**Method**: Sequential POST requests with different user IDs  
**Results**:
- Request 1: 2300ms (successful)
- Request 2: 4971ms (successful) 
- Request 3: 2521ms (successful)
- Request 4: 43ms (rate limited - 429 error)
- Request 5: 43ms (rate limited - 429 error)

**Evidence Files**:
- `results/20250909_045905/performance_times.txt`
- System logs show rate limiting: `"status": 429, "latency_ms": 1.01`

### 4. Database Reality Probe

**Objective**: Count tables, records, and verify schema  
**Method**: SQL queries against PostgreSQL database  
**Results**:
- Total tables: 19 (confirmed via `information_schema.tables`)
- Main data tables: `expenses`, `users`, `monthly_summaries`, `telemetry_events`
- Support tables: `ai_request_audit`, `data_integrity_status`, `expense_edits` 
- Current records: 562 expenses, 106 users
- Operational tables: `rate_limits`, `real_users_allowlist`, `growth_counters`

**Evidence Files**:
- `results/20250909_045905/database_summary.txt`
- SQL probe results showing exact counts

**SQL Commands Executed**:
```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
-- Result: 19

SELECT COUNT(*) FROM expenses;  
-- Result: 562

SELECT COUNT(*) FROM users;
-- Result: 106
```

### 5. Security Posture Probe

**Objective**: Test CORS policy and access restrictions  
**Method**: OPTIONS requests with different Origin headers  
**Results**:
- ✅ Allowed origin (`http://localhost:5000`): Returns proper CORS headers
- ✅ Denied origin (`https://evil.example.com`): Restricted access (no wildcard)
- ✅ Rate limiting active: 4 requests per minute per IP enforced

**Evidence Files**:
- `results/20250909_045905/cors_allowed.txt` 
  - Contains: `Access-Control-Allow-Origin: http://localhost:5000`
- `results/20250909_045905/cors_denied.txt`
  - Shows restricted access for external domains

**Commands**:
```bash
curl -I -X OPTIONS /ai-chat -H "Origin: http://localhost:5000"
curl -I -X OPTIONS /ai-chat -H "Origin: https://evil.example.com"  
```

### 6. PWA Basics Probe

**Objective**: Verify Progressive Web App configuration  
**Method**: HTTP requests for manifest and service worker files  
**Results**:
- ✅ Web manifest exists at `/static/manifest.webmanifest`
- ✅ Service worker exists at `/static/js/sw.js`
- ✅ Manifest includes proper PWA metadata (name, icons, display mode)

**Evidence Files**:
- `results/20250909_045905/manifest_check.json` (full manifest content)
- `results/20250909_045905/sw_check.js` (service worker code)
- `results/20250909_045905/pwa_summary.txt` (verification status)

**Manifest Key Fields Verified**:
```json
{
  "name": "FinBrain - AI Expense Tracker",
  "short_name": "FinBrain", 
  "display": "standalone",
  "start_url": "/"
}
```

## System Startup Evidence

During probe execution, observed clean system startup sequence:
- ✅ Database connection verified  
- ✅ AI provider warm-up successful (1507ms)
- ✅ Background processor ready (3 workers)
- ✅ Rate limiting initialized
- ✅ PWA UI routes registered
- ✅ Cold-start mitigation completed

**Log Evidence**:
```
2025-09-09 05:02:36,778 - main - INFO - ✓ FinBrain application ready for deployment
```

## Limitations & Unknowns

**What we could not verify**:
- Facebook Messenger integration (requires live Facebook webhook)
- System behavior under heavy concurrent load (>10 users)
- Data accuracy rates for AI expense extraction
- Recovery behavior after database failures
- Performance with large datasets (>10,000 expenses per user)

**Probes that would require additional setup**:
- Load testing: `wrk -t10 -c50 http://localhost:5000/ai-chat` 
- Messenger testing: Requires Facebook webhook validation
- Failover testing: Requires controlled database outage simulation

## Probe Execution Environment

- **System**: Linux x86_64 (NixOS distribution)
- **Python**: 3.11.13  
- **Database**: PostgreSQL (version from DATABASE_URL connection)
- **Time Range**: 2025-09-09 04:59:00 to 05:03:00 UTC
- **Network**: localhost connections only
- **Authentication**: No login required (open system during testing)

---

*All evidence collected through direct system interaction. No simulated or mock data used.*