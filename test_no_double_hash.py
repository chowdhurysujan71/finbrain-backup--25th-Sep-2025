#!/usr/bin/env python3
"""
Test the simplified no-double-hash approach
"""

import sys
sys.path.insert(0, '.')

def test_no_double_hash():
    """Test the new approach without double hashing"""
    from app import app
    from utils.production_router import ProductionRouter
    from utils.security import hash_psid
    
    with app.app_context():
        print("🎯 TESTING NO-DOUBLE-HASH APPROACH")
        print("=" * 50)
        
        # Simulate real production flow
        original_psid = "test_production_user_12345"
        
        print(f"1. Original PSID: {original_psid}")
        
        # This is what happens in production router
        router = ProductionRouter()
        
        # The router computes the hash once
        psid_hash = hash_psid(original_psid)
        print(f"2. Hash computed once: {psid_hash[:16]}...")
        
        # Then passes it directly to conversational AI (no more hashing)
        from utils.conversational_ai import conversational_ai
        
        # Test the new method that accepts pre-computed hash
        response, intent = conversational_ai.handle_conversational_query_with_hash(
            psid_hash, "Give me a summary"
        )
        
        print(f"3. Conversational AI response: {response[:50]}...")
        print(f"4. Intent: {intent}")
        
        # Test with real user hash that has data
        real_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        print(f"\n5. Testing with real user hash: {real_hash[:16]}...")
        
        response, intent = conversational_ai.handle_conversational_query_with_hash(
            real_hash, "Give me a summary"
        )
        
        print(f"6. Response: {response[:100]}...")
        print(f"7. Intent: {intent}")
        
        # Check if it finds real data
        if any(str(val) in response for val in ['15325', '14', '13925']):
            print("✅ SUCCESS: Found real user data without double hashing!")
        else:
            print("❌ FAILURE: Still not finding data")

if __name__ == "__main__":
    test_no_double_hash()