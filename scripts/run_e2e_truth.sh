#!/usr/bin/env bash
set -euo pipefail

APP="${APP_ORIGIN:-http://localhost:5000}"
OUTBASE="results/$(date -u +%FT%TZ)"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'no-git')"
OUTDIR="$OUTBASE/$COMMIT"
mkdir -p "$OUTDIR"

note(){ echo "• $*"; }
ok(){ echo "✓ $*"; }
fail(){ echo "✗ $*"; echo "See artifacts under $OUTDIR"; exit 1; }

echo "=== FinBrain E2E Truth Run ===" | tee "$OUTDIR/run.log"
echo "APP=$APP  COMMIT=$COMMIT  TIME=$(date -u +%FT%TZ)" | tee -a "$OUTDIR/run.log"

# ---------- Gate: health & readiness ----------
curl -fsS "$APP/health"  | tee "$OUTDIR/health.json"  >/dev/null || fail "/health failed"
curl -fsS "$APP/readyz" | tee "$OUTDIR/readyz.json" >/dev/null || fail "/readyz failed"
grep -q '"db":true' "$OUTDIR/readyz.json" || fail "readyz not ready (DB unavailable)"
ok "Health & readiness OK"

# ---------- CORS preflight (allowed & denied origins) ----------
ALLOWED_ORIGIN="${ALLOWED_ORIGIN:-http://localhost:5000}"
curl -is -X OPTIONS "$APP/ai-chat" -H "Origin: $ALLOWED_ORIGIN" \
  -H "Access-Control-Request-Method: POST" | tee "$OUTDIR/cors_allowed.txt" >/dev/null
grep -qi 'access-control-allow-origin' "$OUTDIR/cors_allowed.txt" || fail "CORS: allowed origin not granted"

curl -is -X OPTIONS "$APP/ai-chat" -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: POST" | tee "$OUTDIR/cors_denied.txt" >/dev/null
if grep -qi 'access-control-allow-origin: \*' "$OUTDIR/cors_denied.txt"; then
  fail "CORS: wildcard (*) detected for /ai-chat"
fi
ok "CORS posture sane"

# ---------- Chat contract + metadata ----------
curl -fsS -X POST "$APP/ai-chat" \
  -H 'Content-Type: application/json' -H 'X-User-ID: e2e-uid-1' \
  -d '{"message":"I spent 200 on lunch"}' | tee "$OUTDIR/chat_contract.json" >/dev/null
jq -e '.reply and .data and .user_id and .metadata.source and .metadata.latency_ms' \
  "$OUTDIR/chat_contract.json" >/dev/null || fail "Chat JSON envelope/metadata missing"
ok "Chat contract + metadata OK"

# ---------- Rate limit sanity (no 5xx) ----------
OK=0; ERR=0
for i in {1..6}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$APP/ai-chat" \
    -H 'Content-Type: application/json' -H 'X-User-ID: rate-uid' \
    -d "{\"message\":\"ping-$i\"}")
  echo "try $i -> $CODE" | tee -a "$OUTDIR/burst_codes.txt"
  [ "$CODE" = "200" ] && OK=$((OK+1)) || ERR=$((ERR+1))
done
grep -Eq '5(00|01|02|03|04|xx)' "$OUTDIR/burst_codes.txt" && fail "5xx observed under burst"
ok "Burst test OK (no 5xx). 200s:$OK non-200:$ERR (429 accepted)"

# ---------- Cross-user isolation quick check ----------
curl -s -X POST "$APP/ai-chat" -H 'Content-Type: application/json' -H 'X-User-ID: iso-A' \
  -d '{"message":"Log 300 for snacks"}' > "$OUTDIR/iso_A_msg.json"
curl -s -X POST "$APP/ai-chat" -H 'Content-Type: application/json' -H 'X-User-ID: iso-B' \
  -d '{"message":"What did I just log?"}' > "$OUTDIR/iso_B_query.json"
if grep -qi 'snack\|300' "$OUTDIR/iso_B_query.json"; then
  fail "Isolation breach: B appears to see A's content"
fi
ok "Cross-user isolation holds (black-box) 👍"

# ---------- Performance & path distribution (5 msgs, rate-limit aware) ----------
python3 - "$APP" "$OUTDIR" <<'PY'
import os, sys, json, time, urllib.request, urllib.error
APP=sys.argv[1]; OUTDIR=sys.argv[2]
msgs=[
 "I spent 200 lunch","Groceries 1450 at Shwapno","Coffee 120","Medicine 900","Transport 75"
]
lat=[]; srcs={}; rate_limited=0
for i, m in enumerate(msgs):
    try:
        req=urllib.request.Request(APP+"/ai-chat",
            data=json.dumps({"message":m}).encode(),
            headers={"Content-Type":"application/json","X-User-ID":f"perf-uid-{i}"})
        t=time.time()
        with urllib.request.urlopen(req, timeout=25) as r:
            body=json.loads(r.read().decode())
        rt=int((time.time()-t)*1000)
        lat.append(rt)
        s=(body.get("metadata") or {}).get("source","unknown")
        srcs[s]=srcs.get(s,0)+1
        print(json.dumps({"msg":m,"src":s,"roundtrip_ms":rt}))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            rate_limited += 1
            print(json.dumps({"msg":m,"src":"rate_limited","roundtrip_ms":-1}))
        else:
            raise
# Compute p50/p95 (if we have data)
if lat:
    lat.sort()
    def pct(p): return lat[int((p/100)*len(lat))-1] if lat else 0
    summary = f"count={len(lat)} p50={pct(50)}ms p95={pct(95)}ms src={srcs} rate_limited={rate_limited}\n"
else:
    summary = f"count=0 p50=0ms p95=0ms src={srcs} rate_limited={rate_limited}\n"
open(os.path.join(OUTDIR,"latency_summary.txt"),"w").write(summary)
print(f"SUMMARY: {summary.strip()}")
PY
# shell check
cat "$OUTDIR/latency_summary.txt" | tee -a "$OUTDIR/run.log"
P50=$(awk '{print $2}' "$OUTDIR/latency_summary.txt" | sed 's/p50=//;s/ms//')
P95=$(awk '{print $3}' "$OUTDIR/latency_summary.txt" | sed 's/p95=//;s/ms//')
[ "${P50:-99999}" -le 6000 ] || fail "p50 too high ($P50 ms)"
[ "${P95:-99999}" -le 8000 ] || fail "p95 too high ($P95 ms)"
ok "Latency within SLO (p50<=6s, p95<=8s for AI workloads)"

echo "All checks passed. Artifacts: $OUTDIR"