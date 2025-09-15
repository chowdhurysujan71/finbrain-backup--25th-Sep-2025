#!/usr/bin/env python3
"""
Test script to verify the canonical identity system is working correctly
and prevents identity fragmentation
"""

import os
import json

# Set ID_SALT for testing (if not already set)
if not os.environ.get("ID_SALT"):
    os.environ["ID_SALT"] = "test_salt_for_identity_verification_12345"

from utils.identity import psid_from_event, psid_hash

def test_psid_extraction():
    """Test PSID extraction from different event types"""
    print("=== Testing PSID Extraction ===")
    
    # Test message event (should extract)
    message_event = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "test_psid_123"},
                        "recipient": {"id": "page_id_456"},
                        "message": {"text": "hello", "mid": "mid_123"}
                    }
                ]
            }
        ]
    }
    
    psid = psid_from_event(message_event)
    print(f"Message event PSID: {psid}")
    assert psid == "test_psid_123", f"Expected 'test_psid_123', got '{psid}'"
    
    # Test delivery event (should return None)
    delivery_event = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "test_psid_123"},
                        "recipient": {"id": "page_id_456"},
                        "delivery": {"mids": ["mid_123"], "watermark": 1234567890}
                    }
                ]
            }
        ]
    }
    
    psid_delivery = psid_from_event(delivery_event)
    print(f"Delivery event PSID: {psid_delivery}")
    assert psid_delivery is None, f"Expected None for delivery event, got '{psid_delivery}'"
    
    # Test read event (should return None)  
    read_event = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "test_psid_123"},
                        "recipient": {"id": "page_id_456"},
                        "read": {"watermark": 1234567890}
                    }
                ]
            }
        ]
    }
    
    psid_read = psid_from_event(read_event)
    print(f"Read event PSID: {psid_read}")
    assert psid_read is None, f"Expected None for read event, got '{psid_read}'"
    
    print("✓ PSID extraction working correctly")

def test_hash_consistency():
    """Test hash consistency - same PSID should always produce same hash"""
    print("\n=== Testing Hash Consistency ===")
    
    test_psid = "test_psid_12345"
    
    hash1 = psid_hash(test_psid)
    hash2 = psid_hash(test_psid)
    hash3 = psid_hash(test_psid)
    
    print(f"Hash 1: {hash1}")
    print(f"Hash 2: {hash2}")
    print(f"Hash 3: {hash3}")
    
    assert hash1 == hash2 == hash3, "Hash inconsistency detected!"
    assert len(hash1) == 64, f"Expected 64-char hash, got {len(hash1)}"
    
    # Test different PSIDs produce different hashes
    different_hash = psid_hash("different_psid")
    assert different_hash != hash1, "Different PSIDs produced same hash!"
    
    print("✓ Hash consistency verified")

def test_webhook_event_processing():
    """Test complete webhook event processing flow"""
    print("\n=== Testing Webhook Event Processing ===")
    
    from utils.webhook_processor import extract_webhook_events
    
    webhook_payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "sender_123"},
                        "recipient": {"id": "page_456"},
                        "message": {"text": "coffee 50", "mid": "mid_123"}
                    }
                ]
            }
        ]
    }
    
    events = extract_webhook_events(webhook_payload)
    print(f"Extracted events: {json.dumps(events, indent=2)}")
    
    assert len(events) == 1, f"Expected 1 event, got {len(events)}"
    event = events[0]
    
    assert event['psid'] == 'sender_123', f"PSID mismatch: {event['psid']}"
    assert event['text'] == 'coffee 50', f"Text mismatch: {event['text']}"
    assert event['mid'] == 'mid_123', f"MID mismatch: {event['mid']}"
    
    print("✓ Webhook event processing working correctly")

if __name__ == "__main__":
    try:
        test_psid_extraction()
        test_hash_consistency()
        test_webhook_event_processing()
        
        print("\n🎉 ALL TESTS PASSED - Identity system is working correctly!")
        print("✓ Single-source-of-truth identity extraction")
        print("✓ Delivery/read events properly ignored")
        print("✓ Hash consistency maintained")
        print("✓ Webhook processing using canonical identity")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()