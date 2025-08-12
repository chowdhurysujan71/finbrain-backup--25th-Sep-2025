#!/usr/bin/env python3
"""Production deployment test"""

import requests
import os

def test_production():
    """Test production deployment endpoints"""
    base_url = "https://finbrain-chowdhurysujan7.replit.app"
    
    print("=== Production Deployment Test ===")
    
    # Test 1: Basic health check
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"Health check: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"Health check failed: {str(e)}")
    
    # Test 2: Home page
    try:
        response = requests.get(base_url, timeout=10)
        print(f"Home page: {response.status_code} - {len(response.text)} bytes")
    except Exception as e:
        print(f"Home page failed: {str(e)}")
    
    # Test 3: Webhook verification
    try:
        params = {
            'hub.mode': 'subscribe',
            'hub.challenge': 'TEST_123',
            'hub.verify_token': 'finbrain_verify_123'
        }
        response = requests.get(f"{base_url}/webhook/messenger", params=params, timeout=10)
        print(f"Webhook verification: {response.status_code} - {response.text}")
        
        if response.status_code == 200 and response.text == 'TEST_123':
            print("✅ Webhook verification WORKING!")
        else:
            print("❌ Webhook verification FAILED")
            
    except Exception as e:
        print(f"Webhook test failed: {str(e)}")

if __name__ == "__main__":
    test_production()