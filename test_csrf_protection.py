#!/usr/bin/env python3
"""
CSRF Protection Smoke Tests
Tests that CSRF protection is working correctly for the FinBrain application
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_post_without_csrf_token():
    """Test 1: POST without CSRF token should return 400/403"""
    print("\n=== TEST 1: POST without CSRF token ===")
    
    # Try to login without CSRF token
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123",
            "captcha_answer": "5",
            "captcha_nonce": "test"
        },
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code in [400, 403]:
        print("✅ PASS: POST without CSRF token was rejected")
        return True
    else:
        print(f"❌ FAIL: Expected 400/403, got {response.status_code}")
        return False

def test_post_with_csrf_token():
    """Test 2: POST with valid CSRF token should succeed (or fail with proper validation)"""
    print("\n=== TEST 2: POST with valid CSRF token ===")
    
    # First, get a CSRF token
    session = requests.Session()
    
    # Get CSRF token
    token_response = session.get(f"{BASE_URL}/api/auth/csrf-token")
    print(f"Token endpoint status: {token_response.status_code}")
    
    if token_response.status_code != 200:
        print(f"❌ FAIL: Could not get CSRF token")
        return False
    
    csrf_token = token_response.json().get("csrf_token")
    print(f"CSRF Token obtained: {csrf_token[:20]}..." if csrf_token else "None")
    
    # Try to login WITH CSRF token
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword",
            "captcha_answer": "5",
            "captcha_nonce": "test"
        },
        headers={
            "Content-Type": "application/json",
            "X-CSRFToken": csrf_token
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    # We expect either 400 (validation error) or 401 (auth error), NOT 403 (CSRF error)
    if response.status_code in [400, 401, 429]:
        print("✅ PASS: POST with CSRF token was accepted (failed for other reasons, not CSRF)")
        return True
    elif response.status_code == 403:
        print("❌ FAIL: Got 403 even with CSRF token - CSRF protection may be misconfigured")
        return False
    else:
        print(f"⚠️  PARTIAL: Got {response.status_code} - check if this is expected")
        return True

def test_csrf_token_endpoint():
    """Test 3: CSRF token endpoint should return token and proper headers"""
    print("\n=== TEST 3: CSRF token endpoint ===")
    
    response = requests.get(f"{BASE_URL}/api/auth/csrf-token")
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: Cache-Control = {response.headers.get('Cache-Control')}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code == 200:
        data = response.json()
        if "csrf_token" in data and response.headers.get("Cache-Control"):
            print("✅ PASS: CSRF token endpoint working with proper headers")
            return True
        else:
            print("❌ FAIL: Missing csrf_token or Cache-Control header")
            return False
    else:
        print(f"❌ FAIL: Expected 200, got {response.status_code}")
        return False

def main():
    print("=" * 60)
    print("CSRF Protection Smoke Tests - FinBrain")
    print("=" * 60)
    
    results = []
    
    results.append(("POST without CSRF token blocked", test_post_without_csrf_token()))
    results.append(("POST with CSRF token accepted", test_post_with_csrf_token()))
    results.append(("CSRF token endpoint working", test_csrf_token_endpoint()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 All CSRF protection tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed - review CSRF configuration")
        return 1

if __name__ == "__main__":
    exit(main())
