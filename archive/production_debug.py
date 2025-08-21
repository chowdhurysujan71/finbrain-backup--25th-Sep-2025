#!/usr/bin/env python3
"""Debug production deployment issues"""

import requests
import time

def debug_production():
    """Comprehensive production debugging"""
    base_url = "https://finbrain-chowdhurysujan7.replit.app"
    
    print("=== Production Deployment Debug ===")
    
    # Test 1: Basic connectivity
    print("\n1. Testing basic connectivity...")
    try:
        response = requests.get(base_url, timeout=30)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        print(f"   Body (first 200 chars): {response.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"   Connection failed: {str(e)}")
    
    # Test 2: Health endpoint with verbose output
    print("\n2. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=30, headers={'User-Agent': 'FinBrain-Debug/1.0'})
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"   Body: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"   Health check failed: {str(e)}")
    
    # Test 3: Direct webhook test
    print("\n3. Testing webhook endpoint...")
    try:
        params = {
            'hub.mode': 'subscribe',
            'hub.challenge': 'DEBUG_TEST_123',
            'hub.verify_token': 'finbrain_verify_123'
        }
        response = requests.get(f"{base_url}/webhook/messenger", params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200 and response.text == 'DEBUG_TEST_123':
            print("   ✅ WEBHOOK VERIFICATION WORKING!")
        else:
            print("   ❌ Webhook verification failed")
    except requests.exceptions.RequestException as e:
        print(f"   Webhook test failed: {str(e)}")

if __name__ == "__main__":
    debug_production()