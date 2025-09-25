#!/bin/bash
# Staging Soak Test - Drive 4 Core Flows
# Target: 10-20 RPM for 30-60 minutes

STAGING_URL=${STAGING_URL:-"https://staging.finbrain.app"}
TEST_DURATION=${TEST_DURATION:-1800}  # 30 minutes
RPM_TARGET=15

echo "=== STAGING SOAK TEST STARTED ==="
echo "Target: $STAGING_URL"
echo "Duration: $TEST_DURATION seconds"
echo "Rate: $RPM_TARGET RPM"

# Core Flow 1: Health Check
health_test() {
    curl -s -w '%{time_total}' "$STAGING_URL/health" -o /dev/null
}

# Core Flow 2: Main Route
main_test() {
    curl -s -w '%{time_total}' "$STAGING_URL/" -o /dev/null
}

# Core Flow 3: Backend API (Auth required)
backend_test() {
    curl -s -w '%{time_total}' "$STAGING_URL/api/backend/version" -o /dev/null
}

# Core Flow 4: Deploy Status
deploy_test() {
    curl -s -w '%{time_total}' "$STAGING_URL/deploy/status" -o /dev/null
}

# Performance tracking
declare -a latencies=()
error_count=0
request_count=0

# Soak test loop
END_TIME=$((SECONDS + TEST_DURATION))
while [ $SECONDS -lt $END_TIME ]; do
    # Rotate through flows
    for flow in health_test main_test backend_test deploy_test; do
        start_time=$(date +%s.%3N)
        latency=$($flow 2>/dev/null || echo "999")
        latencies+=("$latency")
        request_count=$((request_count + 1))
        
        if (( $(echo "$latency > 5" | bc -l) )); then
            error_count=$((error_count + 1))
        fi
        
        # Rate limiting to achieve target RPM
        sleep $(echo "scale=2; 60/$RPM_TARGET/4" | bc -l)
    done
done

# Calculate P95 latency
IFS=$'\n' sorted=($(sort -n <<<"${latencies[*]}"))
unset IFS
p95_index=$(echo "scale=0; ${#sorted[@]} * 0.95 / 1" | bc)
p95_latency=${sorted[$p95_index]}

# Calculate error rate
error_rate=$(echo "scale=2; $error_count * 100 / $request_count" | bc -l)

echo "=== STAGING SOAK RESULTS ==="
echo "Requests: $request_count"
echo "Errors: $error_count"
echo "Error rate: $error_rate%"
echo "P95 latency: $p95_latency s"

# Gate check
if (( $(echo "$error_rate > 0.5" | bc -l) )); then
    echo "❌ ERROR RATE TOO HIGH: $error_rate% > 0.5%"
    exit 1
fi

if (( $(echo "$p95_latency > 1.5" | bc -l) )); then
    echo "❌ P95 LATENCY TOO HIGH: $p95_latency s > 1.5s"
    exit 1
fi

echo "✅ STAGING SOAK PASSED - Ready for production"
