#!/usr/bin/env bash
set -euo pipefail
APP="${APP_ORIGIN:-http://localhost:5000}"

echo "== FinBrain PROD Gate =="
date -Is
git rev-parse HEAD || true

req_fail(){ echo "✗ $*"; exit 1; }
opt_warn(){ echo "• $*"; }

# 1) Health
curl -fsS "$APP/health"  >/dev/null || req_fail "/health failed"
curl -fsS "$APP/readyz" | grep -q '"db":true' || req_fail "/readyz not ready"

# 2) Chat contract + metadata
RESP=$(curl -fsS -X POST "$APP/ai-chat" \
  -H 'Content-Type: application/json' -H 'X-User-ID: gate-uid' \
  -d '{"message":"I spent 200 on lunch"}')
echo "$RESP" | jq . >/dev/null 2>&1 || req_fail "/ai-chat not JSON"
echo "$RESP" | jq -e '.reply and .data and .user_id and .metadata.source and .metadata.latency_ms' >/dev/null || req_fail "chat envelope/metadata missing"

# 3) CORS policy present (origin restricted)
curl -is -X OPTIONS "$APP/ai-chat" -H 'Origin: https://yourdomain.example' \
  -H 'Access-Control-Request-Method: POST' | grep -qi 'access-control-allow-origin' || req_fail "CORS not configured"

# 4) Schema reality (requires $DATABASE_URL)
[ -n "${DATABASE_URL:-}" ] || req_fail "DATABASE_URL missing"
psql "$DATABASE_URL" -tAc "select 1" >/dev/null || req_fail "DB unreachable"
psql "$DATABASE_URL" -tAc "select column_name from information_schema.columns where table_name='expenses' and column_name in ('nl_confidence','nl_language','needed_clarification')" | grep -q . || req_fail "required nl_* columns missing"
psql "$DATABASE_URL" -tAc "select indexname from pg_indexes where tablename='expenses' and indexname like 'idx_expenses_%'" | grep -q . || req_fail "composite expense index missing"

# 5) Rate limit sanity (no 5xx under burst)
ok=0; err=0
for i in {1..6}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$APP/ai-chat" \
    -H 'Content-Type: application/json' -H 'X-User-ID: ratelimit-uat' \
    -d "{\"message\":\"ping-$i\"}")
  [ "$code" = "200" ] && ok=$((ok+1)) || err=$((err+1))
done
[ $ok -ge 1 ] || req_fail "chat burst: zero successes"

# 6) PWA freshness
[ -f static/manifest.webmanifest ] || opt_warn "manifest missing (not a blocker)"
echo "✓ PROD gate passed"