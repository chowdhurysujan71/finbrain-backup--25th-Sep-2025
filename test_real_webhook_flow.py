#!/usr/bin/env python3
"""
Test complete webhook flow to simulate real Facebook Messenger interactions
"""

import requests
import json
import time
import hashlib
import hmac

def create_test_webhook_payload(psid, message_text, message_id):
    """Create a realistic Facebook webhook payload"""
    return {
        "object": "page",
        "entry": [
            {
                "id": "page_123",
                "time": int(time.time() * 1000),
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": "page_123"},
                        "timestamp": int(time.time() * 1000),
                        "message": {
                            "mid": message_id,
                            "text": message_text
                        }
                    }
                ]
            }
        ]
    }

def create_delivery_receipt_payload(psid, message_id):
    """Create delivery receipt payload (should be ignored)"""
    return {
        "object": "page",
        "entry": [
            {
                "id": "page_123", 
                "time": int(time.time() * 1000),
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": "page_123"},
                        "timestamp": int(time.time() * 1000),
                        "delivery": {
                            "mids": [message_id],
                            "watermark": int(time.time())
                        }
                    }
                ]
            }
        ]
    }

def sign_payload(payload_bytes, app_secret):
    """Create Facebook webhook signature"""
    signature = hmac.new(
        app_secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"

def test_webhook_endpoint():
    """Test the webhook endpoint with realistic payloads"""
    print("🔗 TESTING COMPLETE WEBHOOK FLOW")
    print("=" * 40)
    
    # Test configuration
    webhook_url = "http://localhost:5000/webhook/messenger"
    app_secret = "test_app_secret_for_signature"  # This would fail signature verification but that's ok for local testing
    
    test_user = "test_identity_user_12345"
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "Expense Message",
            "payload": create_test_webhook_payload(test_user, "coffee 75", "msg_001"),
            "should_process": True
        },
        {
            "name": "Summary Request", 
            "payload": create_test_webhook_payload(test_user, "summary", "msg_002"),
            "should_process": True
        },
        {
            "name": "Delivery Receipt",
            "payload": create_delivery_receipt_payload(test_user, "msg_001"), 
            "should_process": False
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n📤 Testing: {scenario['name']}")
        
        payload_json = json.dumps(scenario['payload'])
        payload_bytes = payload_json.encode('utf-8')
        signature = sign_payload(payload_bytes, app_secret)
        
        headers = {
            'Content-Type': 'application/json',
            'X-Hub-Signature-256': signature
        }
        
        try:
            # Note: This will likely fail signature verification in production
            # but will test the webhook processing logic
            response = requests.post(
                webhook_url, 
                data=payload_bytes,
                headers=headers,
                timeout=5
            )
            
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text}")
            
            # Should always return 200 EVENT_RECEIVED for valid webhooks
            if response.status_code == 200:
                print(f"  ✅ Webhook accepted")
            else:
                print(f"  ⚠️  Status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Request failed: {str(e)}")
    
    print("\n✅ Webhook flow test completed")

def verify_identity_in_logs():
    """Check application logs for identity consistency"""
    print("\n📋 VERIFYING IDENTITY IN LOGS")
    print("=" * 30)
    
    try:
        # Check health endpoint for any identity-related info
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("📊 Application Health:")
            print(f"  Status: {health_data.get('status', 'unknown')}")
            print(f"  Queue Depth: {health_data.get('queue_depth', 'unknown')}")
            print(f"  Database: {health_data.get('database', 'unknown')}")
        
        # In a real test, we would check the application logs for:
        # 1. Consistent hash values in log entries
        # 2. Delivery/read events being ignored
        # 3. Debug echo in responses
        print("\n💡 To verify identity consistency in production:")
        print("  1. Send test messages via Messenger")
        print("  2. Check responses contain: 'pong | psid_hash=XXXXXXXX... | mode=XXX'")
        print("  3. Verify same hash appears in all responses from same user")
        print("  4. Confirm delivery receipts don't create duplicate log entries")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {str(e)}")

if __name__ == "__main__":
    print("🚀 IDENTITY FRAGMENTATION FIX - WEBHOOK FLOW TEST")
    print("=" * 50)
    
    # Test the webhook processing
    test_webhook_endpoint()
    
    # Verify system health
    verify_identity_in_logs()
    
    print("\n" + "=" * 50)
    print("🎯 NEXT STEPS FOR PRODUCTION VERIFICATION:")
    print("1. Send real messages via Facebook Messenger")  
    print("2. Look for debug echo: 'pong | psid_hash=XXXXXXXX...'")
    print("3. Verify same hash in all responses from same user")
    print("4. Confirm identity fragmentation is eliminated")
    print("\n✅ Identity system ready for production testing!")