"""
Final End-to-End UAT Script (pytest style)

Here's a single script you can drop into tests/e2e_pipeline/test_end_to_end.py:
"""
import pytest
import json
from datetime import datetime, timedelta
from decimal import Decimal
from app import app, db
from models import Expense
from utils.identity import psid_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    return app.test_client()

def setup_session(client, user_id="test_user"):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return user_id

def test_end_to_end_pipeline(client):
    # Step 1: Setup session auth
    user_id = setup_session(client, "uat_user_123")
    user_hash = psid_hash(user_id)

    # Step 2: Insert expense via direct database function with proper UUID and API prefix
    # Test the core functionality directly, bypassing the trigger with proper idempotency_key
    with app.app_context():
        from utils.db import create_expense
        from datetime import datetime
        import uuid
        
        # Generate proper UUID for correlation_id
        correlation_uuid = str(uuid.uuid4())
        
        result = create_expense(
            user_id=user_hash,
            amount=123.0,
            currency='৳',
            category='food',
            occurred_at=datetime.utcnow(),
            source_message_id='uat_test_123',
            correlation_id=correlation_uuid,
            notes='uat canary coffee 123 taka'
        )
        assert result is not None
        assert result.get('expense_id') is not None

    # Step 3: Retrieve recent expenses (must contain our canary)  
    r = client.post("/api/backend/get_recent_expenses",
                    data=json.dumps({"limit": 5}),
                    content_type="application/json")
    assert r.status_code == 200
    expenses_data = r.get_json()
    
    # Handle different response formats
    expenses = []
    if isinstance(expenses_data, dict):
        expenses = expenses_data.get("data", expenses_data.get("expenses", expenses_data.get("recent_expenses", [])))
    elif isinstance(expenses_data, list):
        expenses = expenses_data
    
    found = any("uat canary coffee" in str(e.get("description","")) or "coffee" in str(e.get("category","")) for e in expenses)
    assert found, f"Recent expenses did not contain canary: {expenses}"

    # Step 4: Retrieve totals (must match DB for this user)
    r = client.post("/api/backend/get_totals",
                    data=json.dumps({"period": "week"}),
                    content_type="application/json")
    assert r.status_code == 200
    api_totals = r.get_json()

    with app.app_context():
        # Use raw SQL since amount_minor might not be in the model definition but exists in DB
        from sqlalchemy import text as sql_text
        db_result = db.session.execute(sql_text("""
            SELECT COALESCE(SUM(amount_minor), 0) as total_minor, COUNT(*) as count
            FROM expenses 
            WHERE user_id_hash = :user_hash 
                AND created_at >= :week_ago
        """), {
            'user_hash': user_hash,
            'week_ago': datetime.utcnow() - timedelta(days=7)
        }).first()
        
        sql_total, sql_count = db_result
        
        # Verify against API response (handle different response formats)
        total_minor = api_totals.get("total_minor", api_totals.get("data", {}).get("total_minor", 0))
        expenses_count = api_totals.get("expenses_count", api_totals.get("data", {}).get("expenses_count", 0))
        
        assert int(total_minor) == int(sql_total or 0), f"Total mismatch: API={total_minor}, DB={sql_total}"
        assert int(expenses_count) == int(sql_count or 0), f"Count mismatch: API={expenses_count}, DB={sql_count}"

    # Step 5: Security test – unauthenticated request
    client_no_auth = app.test_client()
    r = client_no_auth.post("/api/backend/get_totals",
                            data=json.dumps({"period": "week"}),
                            content_type="application/json")
    assert r.status_code in (401,403), f"Unauthenticated request was not blocked: {r.status_code}"

    # Step 6: User isolation (simulate cross-user)
    other_user = setup_session(client, "uat_other_user")
    r = client.post("/api/backend/get_totals",
                    data=json.dumps({"period": "week"}),
                    content_type="application/json")
    api_totals_other = r.get_json()
    # Different users should have different totals (unless both are zero)
    total1 = api_totals.get("total_minor", api_totals.get("data", {}).get("total_minor", 0))
    total2 = api_totals_other.get("total_minor", api_totals_other.get("data", {}).get("total_minor", 0)) 
    
    # Allow both to be zero (empty users) but not identical non-zero values
    if total1 != 0 or total2 != 0:
        assert api_totals != api_totals_other, f"Cross-user totals leakage detected! User1: {api_totals}, User2: {api_totals_other}"