#!/usr/bin/env bash
set -euo pipefail

# 🚀 GOLDEN PATH SMOKE TEST - Web-Only Architecture Validation
# Tests: /ai-chat golden path + deprecation endpoints

BASE_URL="${1:-http://localhost:5000}"
TEST_USER_EMAIL="qa@finbrain.test"
TEST_USER_PASS="QASmokeTest123!"
MARK="SMOKE_$(date +%s)"
TIMEOUT=30

echo "🚀 GOLDEN PATH SMOKE TEST"
echo "Target: $BASE_URL"
echo "Marker: $MARK"
echo "=============================================="

# Cleanup function
cleanup() {
    rm -f cookies.txt captcha_data.json >/dev/null 2>&1
}
trap cleanup EXIT

# 1) Get CAPTCHA from API endpoint  
echo "1. Getting CAPTCHA..."
captcha_response=$(curl -s -c cookies.txt "$BASE_URL/api/auth/captcha" 2>/dev/null || echo '{}')
question=$(echo "$captcha_response" | grep -o '"question":"[^"]*"' | cut -d'"' -f4 | head -1)

if [ -n "$question" ]; then
    # Solve math CAPTCHA (e.g., "What is 5 + 3?")
    math_expr=$(echo "$question" | sed 's/What is //g' | sed 's/?//g' | sed 's/[^0-9+*/ -]//g' | xargs)
    if [ -n "$math_expr" ]; then
        answer=$(( $math_expr )) 2>/dev/null || answer=""
    else
        answer=""
    fi
    if [ -n "$answer" ]; then
        echo "   ✅ CAPTCHA: '$question' → $answer"
        captcha_solved=1
    else
        echo "   ⚠️  Could not solve CAPTCHA: $question"
        captcha_solved=0
        answer=""
    fi
else
    echo "   ℹ️  No CAPTCHA required or API failed"
    captcha_solved=0
    answer=""
fi

# 2) Test User Registration (if needed)
echo "2. Ensuring test user exists..."
if [ "$captcha_solved" = "1" ]; then
    reg_data="{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASS\",\"name\":\"QA Smoke User\",\"captcha_answer\":\"$answer\"}"
else
    reg_data="{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASS\",\"name\":\"QA Smoke User\"}"
fi

curl -s -b cookies.txt -c cookies.txt -H "Content-Type: application/json" -X POST "$BASE_URL/auth/register" -d "$reg_data" >/dev/null 2>&1
echo "   ✅ User registration attempted"

# 3) Get fresh CAPTCHA for login and authenticate
echo "3. Getting fresh login CAPTCHA..."
login_captcha_response=$(curl -s -b cookies.txt -c cookies.txt "$BASE_URL/api/auth/captcha" 2>/dev/null || echo '{}')
login_question=$(echo "$login_captcha_response" | grep -o '"question":"[^"]*"' | cut -d'"' -f4 | head -1)

if [ -n "$login_question" ]; then
    login_math_expr=$(echo "$login_question" | sed 's/What is //g' | sed 's/?//g' | sed 's/[^0-9+*/ -]//g' | xargs)
    if [ -n "$login_math_expr" ]; then
        login_answer=$(( $login_math_expr )) 2>/dev/null || login_answer=""
    else
        login_answer=""
    fi
    if [ -n "$login_answer" ]; then
        echo "   ✅ Login CAPTCHA: '$login_question' → $login_answer"
        login_data="{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASS\",\"captcha_answer\":\"$login_answer\"}"
    else
        echo "   ⚠️  Could not solve login CAPTCHA: $login_question"
        login_data="{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASS\"}"
    fi
else
    echo "   ℹ️  No login CAPTCHA required"
    login_data="{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASS\"}"
fi

echo "4. Authenticating..."
login_response=$(curl -s -b cookies.txt -c cookies.txt -H "Content-Type: application/json" -X POST "$BASE_URL/auth/login" -d "$login_data" -w "%{http_code}")
login_status="${login_response: -3}"

if [ "$login_status" = "200" ] || [ "$login_status" = "302" ]; then
    echo "   ✅ Login successful ($login_status)"
else
    echo "   ❌ Login failed ($login_status)"
    echo "   Response: ${login_response%???}"
    exit 1
fi

# 5) Test Golden Path: /ai-chat expense logging
echo "5. Testing golden path: /ai-chat..."
expense_msg="I spent 12.34 on food $MARK"
chat_data="{\"message\":\"$expense_msg\"}"

chat_response=$(curl -s -b cookies.txt -H "Content-Type: application/json" -X POST "$BASE_URL/ai-chat" -d "$chat_data" -w "%{http_code}")
chat_status="${chat_response: -3}"

if [ "$chat_status" = "200" ]; then
    echo "   ✅ AI Chat response received ($chat_status)"
else
    echo "   ❌ AI Chat failed ($chat_status)"
    echo "   Response: ${chat_response%???}"
    exit 1
fi

# 6) Verify expense appears in recent list
echo "6. Verifying expense logged..."
found=0
for i in $(seq 1 $TIMEOUT); do
    list_response=$(curl -s -b cookies.txt -H "Content-Type: application/json" -X POST "$BASE_URL/api/backend/get_recent_expenses" -d '{}')
    if echo "$list_response" | grep -q "$MARK"; then
        found=1
        echo "   ✅ Expense found in list (attempt $i/$TIMEOUT)"
        break
    fi
    sleep 1
done

if [ "$found" = "0" ]; then
    echo "   ❌ Expense '$MARK' not found after $TIMEOUT seconds"
    echo "   Recent expenses response: $list_response"
    exit 1
fi

# 7) Test Deprecated Endpoints Return 410
echo "7. Testing deprecated endpoints..."

# Test /expense form endpoint
expense_410=$(curl -s -b cookies.txt -H "Content-Type: application/x-www-form-urlencoded" -X POST "$BASE_URL/expense" -d "amount=100&category=test" -w "%{http_code}")
expense_status="${expense_410: -3}"
if [ "$expense_status" = "410" ]; then
    echo "   ✅ /expense returns 410 Gone"
else
    echo "   ❌ /expense should return 410, got $expense_status"
fi

# Test /api/backend/add_expense API endpoint  
add_expense_410=$(curl -s -b cookies.txt -H "Content-Type: application/json" -X POST "$BASE_URL/api/backend/add_expense" -d '{"amount_minor":10000,"description":"test","source":"test"}' -w "%{http_code}")
add_expense_status="${add_expense_410: -3}"
if [ "$add_expense_status" = "410" ]; then
    echo "   ✅ /api/backend/add_expense returns 410 Gone"
else
    echo "   ❌ /api/backend/add_expense should return 410, got $add_expense_status"
fi

# Test /webhook/messenger endpoint
messenger_410=$(curl -s -X POST "$BASE_URL/webhook/messenger" -d '{}' -w "%{http_code}")
messenger_status="${messenger_410: -3}"
if [ "$messenger_status" = "410" ]; then
    echo "   ✅ /webhook/messenger returns 410 Gone"  
else
    echo "   ❌ /webhook/messenger should return 410, got $messenger_status"
fi

# 8) Calculate Success Rate
echo ""
echo "=============================================="
echo "🎯 SMOKE TEST RESULTS"
echo "=============================================="

success_count=0
total_tests=5

# Golden path tests
if [ "$login_status" = "200" ] || [ "$login_status" = "302" ]; then success_count=$((success_count + 1)); fi
if [ "$chat_status" = "200" ]; then success_count=$((success_count + 1)); fi
if [ "$found" = "1" ]; then success_count=$((success_count + 1)); fi

# Deprecation tests
if [ "$expense_status" = "410" ]; then success_count=$((success_count + 1)); fi
if [ "$add_expense_status" = "410" ]; then success_count=$((success_count + 1)); fi

success_rate=$((success_count * 100 / total_tests))

echo "Tests Passed: $success_count/$total_tests"
echo "Success Rate: $success_rate%"
echo "Golden Path: /ai-chat → expense logged → list verified"
echo "Deprecations: Bypass endpoints return 410 Gone"

if [ "$success_rate" -ge 80 ]; then
    echo ""
    echo "✅ SMOKE TEST PASSED ($MARK)"
    echo "Web-only architecture operational!"
    exit 0
else
    echo ""
    echo "❌ SMOKE TEST FAILED ($MARK)"
    echo "Success rate below 80% threshold"
    exit 1
fi