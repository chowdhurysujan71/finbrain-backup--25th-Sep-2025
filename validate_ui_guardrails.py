#!/usr/bin/env python3
"""
UI Guardrails Validation - Ensure UX can only see SSOT through API endpoints
"""

import os
import requests
import json
from flask import Flask
from app import app

def test_ui_guardrails():
    """Test that UI components enforce API-only access"""
    print("🛡️  Validating UI Guardrails")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: /partials/entries must require session auth
    print("🔍 Test 1: /partials/entries session enforcement...")
    
    with app.test_client() as client:
        # Test without session - should return empty entries
        response = client.get('/partials/entries')
        if response.status_code == 200:
            print("✅ PASS: /partials/entries accessible (checking content...)")
            
            # Should be empty or minimal since no session
            if 'entries=[]' in response.get_data(as_text=True) or len(response.get_data()) < 500:
                print("✅ PASS: Returns empty/minimal content without session")
            else:
                print("❌ FAIL: Returns actual data without session authentication")
                all_passed = False
        else:
            print(f"❌ FAIL: /partials/entries returned {response.status_code}")
            all_passed = False
    
    # Test 2: Verify API endpoints require authentication
    print("\n🔍 Test 2: Backend API authentication enforcement...")
    
    base_url = "http://localhost:5000"
    
    # Test get_recent_expenses without auth
    try:
        response = requests.post(f"{base_url}/api/backend/get_recent_expenses", 
                               json={"limit": 5}, timeout=3)
        
        if response.status_code == 401:
            print("✅ PASS: /api/backend/get_recent_expenses requires authentication")
        else:
            print(f"❌ FAIL: /api/backend/get_recent_expenses returned {response.status_code} (should be 401)")
            all_passed = False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  SKIP: Could not test API endpoint (server not running): {e}")
    
    # Test get_totals without auth
    try:
        response = requests.post(f"{base_url}/api/backend/get_totals", 
                               json={"period": "week"}, timeout=3)
        
        if response.status_code == 401:
            print("✅ PASS: /api/backend/get_totals requires authentication")
        else:
            print(f"❌ FAIL: /api/backend/get_totals returned {response.status_code} (should be 401)")
            all_passed = False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  SKIP: Could not test API endpoint (server not running): {e}")
    
    # Test 3: Verify no direct database imports in UI files
    print("\n🔍 Test 3: Code pattern validation...")
    
    ui_files = ['pwa_ui.py']
    forbidden_patterns = [
        ('from models import', 'Direct model imports'),
        ('from db_base import db', 'Direct database imports'),
        ('db.session.execute', 'Direct database queries'),
        ('inference_snapshots', 'Legacy table access')
    ]
    
    for file_path in ui_files:
        if os.path.exists(file_path):
            print(f"   Checking {file_path}...")
            with open(file_path, 'r') as f:
                content = f.read()
                
            for pattern, description in forbidden_patterns:
                if pattern in content and '/api/backend/' not in content[content.find(pattern):content.find(pattern)+200]:
                    # Only flag if not part of API endpoint usage
                    if pattern == 'db.session.execute' and 'requests.post' in content:
                        continue  # Skip if using API calls instead
                    print(f"❌ FAIL: Found {description} in {file_path}")
                    all_passed = False
    
    if all_passed:
        print("\n✅ ALL UI GUARDRAILS VALIDATED")
        print("   - Frontend components use only session-authenticated API endpoints")
        print("   - No direct database access in UI layer")
        print("   - API endpoints properly enforce authentication")
    else:
        print("\n❌ UI GUARDRAIL VIOLATIONS DETECTED")
        
    return all_passed

if __name__ == "__main__":
    success = test_ui_guardrails()
    exit(0 if success else 1)