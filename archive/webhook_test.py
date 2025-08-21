#!/usr/bin/env python3
"""Simple webhook verification test script"""

import requests
import os

def test_webhook_verification():
    """Test webhook verification endpoint"""
    
    base_url = "https://finbrain-chowdhurysujan7.replit.app"
    verify_token = "finbrain_webhook_verify_2024"
    
    # Test parameters
    params = {
        'hub.mode': 'subscribe',
        'hub.challenge': 'VERIFICATION_TEST_123',
        'hub.verify_token': verify_token
    }
    
    print(f"Testing webhook at: {base_url}/webhook/messenger")
    print(f"Verify token: {verify_token}")
    print(f"Challenge: {params['hub.challenge']}")
    
    try:
        response = requests.get(f"{base_url}/webhook/messenger", params=params, timeout=10)
        print(f"\nResponse status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200 and response.text == params['hub.challenge']:
            print("✅ Webhook verification PASSED")
        else:
            print("❌ Webhook verification FAILED")
            
    except Exception as e:
        print(f"❌ Request failed: {str(e)}")

if __name__ == "__main__":
    test_webhook_verification()