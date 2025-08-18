# FinBrain — Diagnosis Report

## Summary (5 bullets max)
- **Critical**: `utils.user_manager` exports `resolve_user_id` but NOT `user_manager` — causing ImportError in production_router.py (4 occurrences)
- **Graph API Version Drift**: Mixed versions (v17.0 in utils, v19.0 in fb_client.py) need consolidation to single env var
- **Intent Routing Works**: Summary/Insight handlers properly bypass AI rate limits via new priority routing
- **Webhook Security Disabled**: Signature verification commented out (line 27, webhook_processor.py)
- **Health Endpoint OK**: `/health` exists with uptime, queue_depth, ai_status fields already present

## Critical Errors

### [utils/production_router.py:348,420,453,492] ImportError: cannot import name 'user_manager'
**Issue**: Trying to import non-existent `user_manager` from `utils.user_manager`
**Proof**: 
```python
# utils/user_manager.py only exports:
def resolve_user_id(*, psid: str = None, psid_hash: str = None) -> str
# No 'user_manager' object or UserManager class exists
```
**Impact**: Runtime failures when these code paths execute

### [utils/webhook_processor.py:27] Signature Verification Disabled
**Issue**: `verify_webhook_signature()` always returns `True` — security bypass
**Proof**:
```python
def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Verify Facebook webhook signature - TEMPORARILY DISABLED FOR LOCAL TESTING"""
    return True  # Line 27
```

## High-Priority Fixes

1. **Fix user_manager imports** [utils/production_router.py]
   - Replace all `from utils.user_manager import user_manager` with:
   - `from utils.user_manager import resolve_user_id`
   - Update usage from `user_manager.resolve_user_id()` to `resolve_user_id()`

2. **Consolidate Graph API versions**
   - Add `FB_GRAPH_VERSION=v19.0` to environment
   - Update all files to use `os.environ.get('FB_GRAPH_VERSION', 'v19.0')`
   - Files to update: utils/token_manager.py, utils/quick_reply_system.py, fb_client.py

3. **Re-enable signature verification** [utils/webhook_processor.py:27-45]
   - Uncomment the actual verification code
   - Remove the `return True` bypass

4. **Filter non-message events** [utils/webhook_processor.py:72-95]
   - Add check for delivery/read/typing events in `extract_webhook_events()`
   - Log these to DEBUG only, don't enqueue them

## Warnings / Cleanups

1. **No event filtering**: webhook_processor.py doesn't filter delivery/read/typing events
2. **Parser handles single amounts**: Multi-expense parsing works but categories need context improvement
3. **OpenAI references**: Cold-start mitigation still pings api.openai.com (should be conditional)
4. **Dead imports**: No Supabase found ✅, No unused providers found ✅

## Import Graph (text)

### Circular Dependencies
- None detected ✅

### Broken Import Chains
- `production_router.py` → `utils.user_manager.user_manager` (doesn't exist)
- `test_existing_user.py` → `utils.user_manager.user_manager` (doesn't exist)
- `test_hash_consistency.py` → `utils.user_manager.UserManager` (doesn't exist)

### Working Import Chains
- `production_router.py` → `utils.user_manager.resolve_user_id` ✅
- `handlers/*` → database models ✅
- `utils/dispatcher.py` → `utils/intent_router.detect_intent` ✅

## API Version Map

| File | Version | Action |
|------|---------|--------|
| utils/token_manager.py | v17.0 | Update to env var |
| utils/quick_reply_system.py | v17.0 | Update to env var |
| fb_client.py | v19.0 | Update to env var |

## Acceptance Criteria

After fixes, the following must pass:

- ✅ **Summary/Insight commands work without AI**: Already implemented via handlers/summary.py and handlers/insight.py
- ❌ **No ImportError on user_manager**: Fix the 4 broken imports in production_router.py
- ❌ **Signature verification enabled**: Uncomment webhook verification code
- ❌ **Single Graph API version**: All files use FB_GRAPH_VERSION env var
- ✅ **Health endpoint shows fields**: Already has uptime_s, queue_depth, ai_status
- ❌ **No non-message events enqueued**: Add filtering for delivery/read/typing events
- ✅ **Multi-expense parsing**: Parser extracts multiple amounts (100 on Uber, 500 on shoes)

## Immediate Actions Required

1. **CRITICAL FIX** (2 minutes):
```python
# utils/production_router.py - Lines 348, 420, 453, 492
# REPLACE: from utils.user_manager import user_manager
# WITH: user_id = resolve_user_id(psid=psid)
```

2. **SECURITY FIX** (1 minute):
```python
# utils/webhook_processor.py - Line 27
# DELETE: return True
# UNCOMMENT: Lines 30-45 (actual verification logic)
```

3. **VERSION CONSOLIDATION** (3 minutes):
```python
# Add to .env: FB_GRAPH_VERSION=v19.0
# Update all Graph API URLs to use this variable
```

---
*Generated: August 18, 2025*
*Status: Bot stuck in log-ack due to ImportError on user_manager*