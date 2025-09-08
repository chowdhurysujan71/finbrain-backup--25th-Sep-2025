#!/bin/bash
set -euo pipefail

echo "🔍 FinBrain System Verification Script"
echo "======================================"

# Test chat endpoint
echo "1. Testing chat endpoint..."
response=$(curl -s -w "%{http_code}" -X POST http://localhost:5000/ai-chat \
  -H 'Content-Type: application/json' \
  -H 'X-User-ID: test-uid-verify' \
  -d '{"message":"Hello world"}' -o /tmp/chat_response.json)

if [[ "$response" == "200" ]]; then
    echo "✅ Chat endpoint: PASS"
    echo "   Response: $(cat /tmp/chat_response.json)"
else
    echo "❌ Chat endpoint: FAIL (HTTP $response)"
fi

# Test health endpoints
echo ""
echo "2. Testing health endpoints..."
health_response=$(curl -s -w "%{http_code}" http://localhost:5000/health -o /tmp/health_response.json)
if [[ "$health_response" == "200" ]]; then
    echo "✅ Health endpoint: PASS"
else
    echo "❌ Health endpoint: FAIL (HTTP $health_response)"
fi

readyz_response=$(curl -s -w "%{http_code}" http://localhost:5000/readyz -o /tmp/readyz_response.json)
if [[ "$readyz_response" == "200" ]]; then
    echo "✅ Readiness endpoint: PASS"
else
    echo "❌ Readiness endpoint: FAIL (HTTP $readyz_response)"
fi

# Test database connection
echo ""
echo "3. Testing database connection..."
python3 -c "
import os
from sqlalchemy import create_engine, text
try:
    engine = create_engine(os.environ['DATABASE_URL'])
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ Database connection: PASS')
except Exception as e:
    print(f'❌ Database connection: FAIL ({e})')
"

# Check Redis connection (should gracefully degrade)
echo ""
echo "4. Testing Redis graceful degradation..."
python3 -c "
import os
try:
    import redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    # Fix malformed URLs like we do in the code
    if redis_url == 'rediss:6379':
        redis_url = 'redis://localhost:6379'
    client = redis.from_url(redis_url, socket_connect_timeout=2)
    client.ping()
    print('✅ Redis connection: PASS')
except Exception as e:
    print(f'⚠️  Redis degraded gracefully: {e}')
    print('   Application should continue with in-memory fallback')
"

# Check if attached_assets is ignored
echo ""
echo "5. Checking repository cleanup..."
if [[ -f .gitignore ]] && grep -q "attached_assets/" .gitignore; then
    echo "✅ Repository cleanup: attached_assets/ ignored"
else
    echo "❌ Repository cleanup: .gitignore missing or incomplete"
fi

# Check database indexes
echo ""
echo "6. Checking database indexes..."
python3 -c "
import os
from sqlalchemy import create_engine, text
try:
    engine = create_engine(os.environ['DATABASE_URL'])
    with engine.connect() as conn:
        result = conn.execute(text(\"SELECT indexname FROM pg_indexes WHERE tablename='expenses' AND indexname LIKE 'idx_expenses_%'\"))
        indexes = [row[0] for row in result]
        if 'idx_expenses_uid_created' in indexes or 'idx_expenses_recent_user' in indexes:
            print('✅ Database indexes: PASS')
            print(f'   Found indexes: {indexes}')
        else:
            print('❌ Database indexes: FAIL')
            print(f'   Available indexes: {indexes}')
except Exception as e:
    print(f'❌ Database indexes check failed: {e}')
"

echo ""
echo "🎉 Verification complete!"