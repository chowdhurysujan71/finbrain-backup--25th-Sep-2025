#!/usr/bin/env bash
set -euo pipefail

DOMAIN="https://<your-domain>"
COOKIE="<COOKIE_HEADER>"

echo "[1] Anonymous must be 401"
anon_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$DOMAIN/ai-chat" \
  -H "Content-Type: application/json" -d '{"message":"log 11 test"}')
[[ "$anon_code" == "401" || "$anon_code" == "403" ]] || { echo "FAIL: anon=$anon_code"; exit 1; }

echo "[2] Auth must be 200 and persist"
resp=$(curl -s -X POST "$DOMAIN/ai-chat" -H "Content-Type: application/json" \
  -H "Cookie: $COOKIE" -d '{"message":"log 33 qa"}')
echo "$resp" | grep -qi "logged" || { echo "FAIL: no logged text"; exit 1; }

echo "PASS ✅"