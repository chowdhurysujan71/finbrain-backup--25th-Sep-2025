#!/bin/bash
# E2E Local HTTP Testing for FinBrain Webhook
# Tests realistic Messenger-style payloads with proper signature verification bypass

set -euo pipefail

BASE_URL="http://localhost:5000"
ARTIFACTS_DIR="artifacts/e2e"
mkdir -p "$ARTIFACTS_DIR"

echo "=== FINBRAIN E2E LOCAL WEBHOOK TESTING ==="
echo "Timestamp: $(date)"
echo "Base URL: $BASE_URL"

# Test 1: New user, single text message
echo "TEST 1: New user single message"
cat > "$ARTIFACTS_DIR/test1_payload.json" << 'EOF'
{
  "object": "page",
  "entry": [
    {
      "id": "test_page_id",
      "time": 1692000000000,
      "messaging": [
        {
          "sender": {
            "id": "test_user_123456"
          },
          "recipient": {
            "id": "test_page_id"
          },
          "timestamp": 1692000000000,
          "message": {
            "mid": "test_message_001",
            "text": "bought coffee for 150 taka"
          }
        }
      ]
    }
  ]
}
EOF

# Test with dev bypass header if available
echo "Sending test 1..."
curl -s -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}\n" \
  -H "Content-Type: application/json" \
  -H "X-Local-Testing: true" \
  -d @"$ARTIFACTS_DIR/test1_payload.json" \
  "$BASE_URL/webhook" \
  > "$ARTIFACTS_DIR/test1_response.txt" 2>&1

# Test 2: Returning user, duplicate mid (idempotency test)
echo "TEST 2: Duplicate message ID (idempotency)"
sleep 2
curl -s -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}\n" \
  -H "Content-Type: application/json" \
  -H "X-Local-Testing: true" \
  -d @"$ARTIFACTS_DIR/test1_payload.json" \
  "$BASE_URL/webhook" \
  > "$ARTIFACTS_DIR/test2_response.txt" 2>&1

# Test 3: Multi-expense message
echo "TEST 3: Multi-expense parsing"
cat > "$ARTIFACTS_DIR/test3_payload.json" << 'EOF'
{
  "object": "page",
  "entry": [
    {
      "id": "test_page_id", 
      "time": 1692000100000,
      "messaging": [
        {
          "sender": {
            "id": "test_user_123456"
          },
          "recipient": {
            "id": "test_page_id"
          },
          "timestamp": 1692000100000,
          "message": {
            "mid": "test_message_002",
            "text": "lunch 200 taka and uber ride 100 and bought shoes 1500"
          }
        }
      ]
    }
  ]
}
EOF

curl -s -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}\n" \
  -H "Content-Type: application/json" \
  -H "X-Local-Testing: true" \
  -d @"$ARTIFACTS_DIR/test3_payload.json" \
  "$BASE_URL/webhook" \
  > "$ARTIFACTS_DIR/test3_response.txt" 2>&1

# Test 4: Summary request
echo "TEST 4: Summary command"
cat > "$ARTIFACTS_DIR/test4_payload.json" << 'EOF'
{
  "object": "page",
  "entry": [
    {
      "id": "test_page_id",
      "time": 1692000200000,
      "messaging": [
        {
          "sender": {
            "id": "test_user_123456"
          },
          "recipient": {
            "id": "test_page_id"
          },
          "timestamp": 1692000200000,
          "message": {
            "mid": "test_message_003", 
            "text": "summary"
          }
        }
      ]
    }
  ]
}
EOF

curl -s -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}\n" \
  -H "Content-Type: application/json" \
  -H "X-Local-Testing: true" \
  -d @"$ARTIFACTS_DIR/test4_payload.json" \
  "$BASE_URL/webhook" \
  > "$ARTIFACTS_DIR/test4_response.txt" 2>&1

# Test 5: Burst test (5 messages quickly)
echo "TEST 5: Burst test (5 messages)"
for i in {1..5}; do
  cat > "$ARTIFACTS_DIR/test5_${i}_payload.json" << EOF
{
  "object": "page",
  "entry": [
    {
      "id": "test_page_id",
      "time": $((1692000300000 + i * 1000)),
      "messaging": [
        {
          "sender": {
            "id": "test_user_burst_$i"
          },
          "recipient": {
            "id": "test_page_id"
          },
          "timestamp": $((1692000300000 + i * 1000)),
          "message": {
            "mid": "test_burst_$i",
            "text": "expense $i: coffee $(($i * 50)) taka"
          }
        }
      ]
    }
  ]
}
EOF

  curl -s -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}\n" \
    -H "Content-Type: application/json" \
    -H "X-Local-Testing: true" \
    -d @"$ARTIFACTS_DIR/test5_${i}_payload.json" \
    "$BASE_URL/webhook" \
    > "$ARTIFACTS_DIR/test5_${i}_response.txt" 2>&1 &
done

# Wait for all burst tests to complete
wait

echo "=== E2E TESTING COMPLETED ==="
echo "Results saved to: $ARTIFACTS_DIR/"
echo "Files created:"
ls -la "$ARTIFACTS_DIR/"

# Generate summary
echo "=== E2E TEST SUMMARY ===" > "$ARTIFACTS_DIR/summary.txt"
echo "Timestamp: $(date)" >> "$ARTIFACTS_DIR/summary.txt"
echo "" >> "$ARTIFACTS_DIR/summary.txt"

for i in {1..4}; do
  echo "Test $i:" >> "$ARTIFACTS_DIR/summary.txt"
  if [ -f "$ARTIFACTS_DIR/test${i}_response.txt" ]; then
    http_code=$(grep "HTTP_CODE:" "$ARTIFACTS_DIR/test${i}_response.txt" | cut -d: -f2)
    time_total=$(grep "TIME_TOTAL:" "$ARTIFACTS_DIR/test${i}_response.txt" | cut -d: -f2)
    echo "  HTTP Code: $http_code" >> "$ARTIFACTS_DIR/summary.txt"
    echo "  Response Time: ${time_total}s" >> "$ARTIFACTS_DIR/summary.txt"
  fi
  echo "" >> "$ARTIFACTS_DIR/summary.txt"
done

echo "Burst test results:" >> "$ARTIFACTS_DIR/summary.txt"
for i in {1..5}; do
  if [ -f "$ARTIFACTS_DIR/test5_${i}_response.txt" ]; then
    http_code=$(grep "HTTP_CODE:" "$ARTIFACTS_DIR/test5_${i}_response.txt" | cut -d: -f2)
    echo "  Burst $i: HTTP $http_code" >> "$ARTIFACTS_DIR/summary.txt"
  fi
done

echo "Summary generated: $ARTIFACTS_DIR/summary.txt"