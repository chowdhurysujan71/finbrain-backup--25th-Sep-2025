#!/usr/bin/env python3
"""Manual test of the frozen contract implementation"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_frozen_contract():
    """Test the frozen contract: propose_expense → add_expense → get_recent_expenses/get_totals"""
    
    session = requests.Session()
    
    # Step 1: Test propose_expense (public endpoint)
    print("Step 1: Testing propose_expense...")
    propose_response = session.post(f"{BASE_URL}/api/backend/propose_expense", 
                                   json={"text": "uat canary coffee 123 taka"})
    print(f"Propose response: {propose_response.status_code}")
    print(f"Propose data: {json.dumps(propose_response.json(), indent=2)}")
    
    if propose_response.status_code != 200:
        print("❌ propose_expense failed")
        return False
    
    parsed = propose_response.json()["data"]
    
    # Validate parsing
    assert parsed["amount_minor"] == 12300
    assert parsed["category"] == "food"
    assert parsed["description"] == "uat canary coffee 123 taka"
    print("✅ propose_expense works correctly")
    
    # Step 2: Set up session authentication
    print("\nStep 2: Setting up session...")
    # Create a mock session by logging into the web interface
    login_response = session.get(f"{BASE_URL}/")
    print(f"Login response: {login_response.status_code}")
    
    # Manual session setup (this would normally be done via login form)
    # For testing, we need to see if we can access session-protected endpoints
    
    # Step 3: Test add_expense (session required)
    print("\nStep 3: Testing add_expense...")
    add_payload = {
        "amount_minor": parsed["amount_minor"],
        "currency": "BDT",
        "category": parsed["category"], 
        "description": parsed["description"],
        "source": "chat",
        "message_id": "test_unique_123"
    }
    
    add_response = session.post(f"{BASE_URL}/api/backend/add_expense", json=add_payload)
    print(f"Add expense response: {add_response.status_code}")
    print(f"Add expense data: {json.dumps(add_response.json(), indent=2)}")
    
    # Step 4: Test get_recent_expenses
    print("\nStep 4: Testing get_recent_expenses...")
    recent_response = session.post(f"{BASE_URL}/api/backend/get_recent_expenses", 
                                 json={"limit": 5})
    print(f"Recent expenses response: {recent_response.status_code}")
    if recent_response.status_code == 200:
        print(f"Recent expenses data: {json.dumps(recent_response.json(), indent=2)}")
    
    # Step 5: Test get_totals
    print("\nStep 5: Testing get_totals...")
    totals_response = session.post(f"{BASE_URL}/api/backend/get_totals", 
                                 json={"period": "week"})
    print(f"Totals response: {totals_response.status_code}")
    if totals_response.status_code == 200:
        print(f"Totals data: {json.dumps(totals_response.json(), indent=2)}")
    
    return True

if __name__ == "__main__":
    test_frozen_contract()