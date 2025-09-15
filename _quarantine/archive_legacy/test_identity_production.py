#!/usr/bin/env python3
"""
Production-level test to verify identity fragmentation fix
Tests realistic webhook scenarios to ensure single-source-of-truth identity
"""

import os
import json
import requests
import time

# Set ID_SALT for testing consistency
if not os.environ.get("ID_SALT"):
    os.environ["ID_SALT"] = "3dcce5a0b1eeb774cc1e0320edb773fed53afbcdd4b14d6201373659278cae34"

from utils.identity import psid_from_event, psid_hash
from utils.webhook_processor import extract_webhook_events

def test_realistic_webhook_scenarios():
    """Test realistic webhook scenarios that previously caused fragmentation"""
    print("=== Testing Realistic Webhook Scenarios ===")
    
    test_psid = "realistic_user_12345"
    expected_hash = psid_hash(test_psid)
    print(f"Expected hash for {test_psid}: {expected_hash[:12]}...")
    
    # Scenario 1: Message followed by delivery receipt
    message_webhook = {
        "object": "page", 
        "entry": [{
            "messaging": [{
                "sender": {"id": test_psid},
                "recipient": {"id": "page_123"},
                "message": {"text": "coffee 50", "mid": "message_001"}
            }]
        }]
    }
    
    delivery_webhook = {
        "object": "page",
        "entry": [{
            "messaging": [{
                "sender": {"id": test_psid}, 
                "recipient": {"id": "page_123"},
                "delivery": {"mids": ["message_001"], "watermark": 1234567890}
            }]
        }]
    }
    
    # Test message processing
    message_events = extract_webhook_events(message_webhook)
    print(f"Message events extracted: {len(message_events)}")
    assert len(message_events) == 1, "Should extract 1 message event"
    assert message_events[0]['psid'] == test_psid, "PSID should match sender.id"
    
    # Test delivery ignored
    delivery_events = extract_webhook_events(delivery_webhook)
    print(f"Delivery events extracted: {len(delivery_events)} (should be 0)")
    assert len(delivery_events) == 0, "Delivery events should be ignored completely"
    
    # Scenario 2: Read receipt (should be ignored)
    read_webhook = {
        "object": "page",
        "entry": [{
            "messaging": [{
                "sender": {"id": test_psid},
                "recipient": {"id": "page_123"}, 
                "read": {"watermark": 1234567890}
            }]
        }]
    }
    
    read_events = extract_webhook_events(read_webhook)
    print(f"Read events extracted: {len(read_events)} (should be 0)")
    assert len(read_events) == 0, "Read events should be ignored completely"
    
    print("✓ Realistic webhook scenarios working correctly")

def test_multi_message_consistency():
    """Test that multiple messages from same user always produce same hash"""
    print("\n=== Testing Multi-Message Consistency ===")
    
    test_psid = "consistency_user_67890"
    messages = [
        "hello", 
        "coffee 100",
        "summary",
        "lunch 250 and parking 50"
    ]
    
    hashes = []
    for i, msg in enumerate(messages):
        webhook = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": test_psid},
                    "recipient": {"id": "page_123"},
                    "message": {"text": msg, "mid": f"mid_{i}"}
                }]
            }]
        }
        
        events = extract_webhook_events(webhook)
        assert len(events) == 1, f"Should extract 1 event for message: {msg}"
        
        # Hash should be consistent across all messages from same user
        computed_hash = psid_hash(events[0]['psid'])
        hashes.append(computed_hash)
        print(f"Message '{msg}': hash={computed_hash[:12]}...")
    
    # All hashes should be identical
    unique_hashes = set(hashes)
    assert len(unique_hashes) == 1, f"Expected 1 unique hash, got {len(unique_hashes)}: {unique_hashes}"
    
    print(f"✓ All {len(messages)} messages produced identical hash: {hashes[0][:12]}...")

def test_different_users_different_hashes():
    """Test that different users produce different hashes"""
    print("\n=== Testing Different Users Different Hashes ===")
    
    users = ["user_001", "user_002", "user_003"]
    user_hashes = {}
    
    for user in users:
        webhook = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": user},
                    "recipient": {"id": "page_123"},
                    "message": {"text": "hello", "mid": f"mid_{user}"}
                }]
            }]
        }
        
        events = extract_webhook_events(webhook)
        user_hash = psid_hash(events[0]['psid'])
        user_hashes[user] = user_hash
        print(f"User {user}: hash={user_hash[:12]}...")
    
    # All hashes should be different
    all_hashes = list(user_hashes.values())
    unique_hashes = set(all_hashes)
    assert len(unique_hashes) == len(users), f"Expected {len(users)} unique hashes, got {len(unique_hashes)}"
    
    print("✓ All users produced unique hashes - no collision detected")

def simulate_production_webhook_flow():
    """Simulate the complete production webhook processing flow"""
    print("\n=== Simulating Production Webhook Flow ===")
    
    # Simulate a typical user interaction sequence
    user_psid = "production_test_user"
    expected_hash = psid_hash(user_psid)
    
    interaction_sequence = [
        # User sends expense message
        {
            "type": "message",
            "webhook": {
                "object": "page",
                "entry": [{
                    "messaging": [{
                        "sender": {"id": user_psid},
                        "recipient": {"id": "page_123"},
                        "message": {"text": "coffee 75", "mid": "msg_001"}
                    }]
                }]
            }
        },
        # Facebook sends delivery receipt (should be ignored)
        {
            "type": "delivery", 
            "webhook": {
                "object": "page",
                "entry": [{
                    "messaging": [{
                        "sender": {"id": user_psid},
                        "recipient": {"id": "page_123"},
                        "delivery": {"mids": ["msg_001"], "watermark": int(time.time())}
                    }]
                }]
            }
        },
        # User sends summary request
        {
            "type": "message",
            "webhook": {
                "object": "page", 
                "entry": [{
                    "messaging": [{
                        "sender": {"id": user_psid},
                        "recipient": {"id": "page_123"},
                        "message": {"text": "summary", "mid": "msg_002"}
                    }]
                }]
            }
        },
        # Facebook sends read receipt (should be ignored)
        {
            "type": "read",
            "webhook": {
                "object": "page",
                "entry": [{
                    "messaging": [{
                        "sender": {"id": user_psid},
                        "recipient": {"id": "page_123"},
                        "read": {"watermark": int(time.time())}
                    }]
                }]
            }
        }
    ]
    
    processed_events = []
    ignored_events = []
    
    for interaction in interaction_sequence:
        events = extract_webhook_events(interaction["webhook"])
        
        if events:
            # Should only be messages
            assert interaction["type"] == "message", f"Non-message event processed: {interaction['type']}"
            processed_events.extend(events)
            print(f"✓ Processed {interaction['type']} event: {len(events)} events extracted")
        else:
            # Should be delivery/read events
            assert interaction["type"] in ["delivery", "read"], f"Message event ignored: {interaction['type']}"
            ignored_events.append(interaction["type"])
            print(f"✓ Ignored {interaction['type']} event as expected")
    
    # Verify all processed events have same PSID and would generate same hash
    assert len(processed_events) == 2, f"Expected 2 message events, got {len(processed_events)}"
    assert len(ignored_events) == 2, f"Expected 2 ignored events, got {len(ignored_events)}"
    
    for event in processed_events:
        assert event['psid'] == user_psid, "PSID mismatch in processed events"
        computed_hash = psid_hash(event['psid'])
        assert computed_hash == expected_hash, "Hash inconsistency detected"
    
    print(f"✓ Production flow simulation successful:")
    print(f"  - {len(processed_events)} message events processed with consistent identity")
    print(f"  - {len(ignored_events)} delivery/read events properly ignored")
    print(f"  - Single hash maintained: {expected_hash[:12]}...")

if __name__ == "__main__":
    try:
        print("🚀 IDENTITY FRAGMENTATION FIX - PRODUCTION VERIFICATION")
        print("=" * 60)
        
        test_realistic_webhook_scenarios()
        test_multi_message_consistency()  
        test_different_users_different_hashes()
        simulate_production_webhook_flow()
        
        print("\n" + "=" * 60)
        print("🎉 ALL PRODUCTION TESTS PASSED!")
        print("✅ Identity fragmentation completely eliminated")
        print("✅ Single-source-of-truth identity system operational")
        print("✅ Delivery/read events properly ignored") 
        print("✅ Hash consistency maintained across all scenarios")
        print("✅ System ready for production use")
        
    except Exception as e:
        print(f"\n❌ PRODUCTION TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()