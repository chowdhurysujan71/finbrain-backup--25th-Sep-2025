#!/usr/bin/env python3
"""
Smoke Test for Frozen Contract
Tests the full pipeline: propose → add → recents → totals
Requires authenticated session for backend API endpoints
"""
import os
import sys
from datetime import datetime
from typing import Any, Dict

import requests

# Configuration (override via ENV)
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000/api/backend")
WEB_BASE_URL = BASE_URL.replace('/api/backend', '')
SESSION_COOKIE = os.getenv("SESSION_COOKIE", "")
CANARY_DESC = os.getenv("CANARY_DESC", "uat canary coffee")
CANARY_AMOUNT_MAJOR = os.getenv("CANARY_AMOUNT_MAJOR", "123")
CANARY_SOURCE = os.getenv("CANARY_SOURCE", "chat")
PERIOD = os.getenv("PERIOD", "week")

def fail(msg: str) -> None:
    print(f"\n❌ FAIL: {msg}")
    sys.exit(1)

def post_json(url: str, data: dict[str, Any], headers: dict[str, str]) -> requests.Response:
    try:
        return requests.post(url, json=data, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        fail(f"Network error: {e}")
        # This line is never reached due to fail() calling sys.exit()
        # but needed for type checker
        raise

def expect_status(response: requests.Response, expected: int, operation: str) -> None:
    if response.status_code != expected:
        body = response.text[:500]
        fail(f"{operation} HTTP {response.status_code} != {expected} | Body: {body}")
    return  # Explicit return for clarity

def create_test_session() -> str:
    """Create a test user and return session cookie"""
    print("Creating test session...")
    
    # Create test user
    register_data = {
        "email": f"smoke_test_{int(datetime.now().timestamp())}@test.com",
        "password": "SmokeTe5t!Pass",
        "name": "Smoke Test User"
    }
    
    register_resp = requests.post(f"{WEB_BASE_URL}/auth/register", 
                                 json=register_data, timeout=30)
    
    if register_resp.status_code not in [200, 409]:  # 200 = created, 409 = already exists
        fail(f"Failed to create test user: {register_resp.status_code} - {register_resp.text[:200]}")
    
    # Extract session cookie from response
    for cookie in register_resp.headers.get('Set-Cookie', '').split(';'):
        if cookie.strip().startswith('session='):
            return cookie.strip()
    
    fail("No session cookie received from registration")

def main() -> None:
    # Use provided SESSION_COOKIE or create new test session
    session_cookie = SESSION_COOKIE or create_test_session()
    
    headers = {
        "Content-Type": "application/json",
        "Cookie": session_cookie
    }
    
    print("🚀 Frozen Contract Smoke Test")
    print(f"Base URL: {BASE_URL}")
    print(f"Test expense: {CANARY_DESC} {CANARY_AMOUNT_MAJOR}")
    
    # Step 1: Get baseline totals
    print("\n1. Baseline totals...")
    baseline_resp = post_json(f"{BASE_URL}/get_totals", {"period": PERIOD}, headers)
    expect_status(baseline_resp, 200, "get_totals")
    baseline = baseline_resp.json()
    baseline_total = baseline.get("data", {}).get("total_minor", 0)
    baseline_count = baseline.get("data", {}).get("expenses_count", 0)
    print(f"   Baseline: {baseline_total/100:.2f} BDT ({baseline_count} expenses)")
    
    # Step 2: Propose expense (public endpoint)
    print("2. Propose expense...")
    propose_text = f"{CANARY_DESC} {CANARY_AMOUNT_MAJOR} taka"
    propose_resp = post_json(f"{BASE_URL}/propose_expense", {"text": propose_text}, headers)
    expect_status(propose_resp, 200, "propose_expense")
    
    proposed = propose_resp.json().get("data", {})
    amount_minor = proposed.get("amount_minor")
    category = proposed.get("category")
    description = proposed.get("description")
    
    if not amount_minor or not category or not description:
        fail(f"Invalid proposal response: {proposed}")
    
    print(f"   Proposed: {amount_minor/100:.2f} BDT, category={category}")
    
    # Step 3: Add expense (session required)
    print("3. Add expense...")
    add_data = {
        "amount_minor": amount_minor,
        "currency": "BDT", 
        "category": category,
        "description": description,
        "source": CANARY_SOURCE,
        "message_id": f"smoke_test_{int(datetime.now().timestamp())}"
    }
    
    add_resp = post_json(f"{BASE_URL}/add_expense", add_data, headers)
    expect_status(add_resp, 200, "add_expense")
    
    added = add_resp.json().get("data", {})
    expense_id = added.get("expense_id")
    correlation_id = added.get("correlation_id")
    idempotency_key = added.get("idempotency_key")
    
    if not expense_id or not correlation_id or not idempotency_key:
        fail(f"Invalid add_expense response: {added}")
    
    print(f"   Added: ID={expense_id}, correlation_id={correlation_id[:8]}...")
    
    # Step 4: Verify in recent expenses
    print("4. Check recent expenses...")
    recent_resp = post_json(f"{BASE_URL}/get_recent_expenses", {"limit": 10}, headers)
    expect_status(recent_resp, 200, "get_recent_expenses")
    
    recent = recent_resp.json().get("data", [])
    found = any(e.get("id") == expense_id for e in recent)
    
    if not found:
        fail(f"Expense {expense_id} not found in recent expenses")
    
    print(f"   ✓ Found expense {expense_id} in recent list")
    
    # Step 5: Verify delta in totals
    print("5. Verify totals delta...")
    totals_resp = post_json(f"{BASE_URL}/get_totals", {"period": PERIOD}, headers)
    expect_status(totals_resp, 200, "get_totals")
    
    totals = totals_resp.json()
    final_total = totals.get("data", {}).get("total_minor", 0)
    final_count = totals.get("data", {}).get("expenses_count", 0)
    
    expected_total = baseline_total + amount_minor
    expected_count = baseline_count + 1
    
    if final_total != expected_total:
        fail(f"Total mismatch: expected {expected_total}, got {final_total}")
    
    if final_count != expected_count:
        fail(f"Count mismatch: expected {expected_count}, got {final_count}")
    
    print(f"   ✓ Totals delta verified: +{amount_minor/100:.2f} BDT (+1 expense)")
    
    print("\n🎉 PASS: All frozen contract endpoints working correctly!")

if __name__ == "__main__":
    main()