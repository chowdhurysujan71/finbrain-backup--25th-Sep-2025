#!/usr/bin/env python3
"""
Debug the exact hash flow to understand the double hashing
"""

import sys
sys.path.insert(0, '.')

def debug_hash_flow():
    """Debug the complete hash flow"""
    from app import app
    from utils.security import hash_psid
    
    with app.app_context():
        print("🔍 DEBUGGING HASH FLOW")
        print("=" * 40)
        
        # Let's trace what should happen:
        # 1. Facebook sends PSID (e.g., "1234567890")
        # 2. We hash it ONCE for storage: hash_psid("1234567890") = "abc123..."
        # 3. We store expenses with user_id = "abc123..."
        # 4. When querying, we should use the SAME hash "abc123..."
        
        # Simulate this flow
        original_psid = "test_facebook_psid_12345"
        stored_hash = hash_psid(original_psid)
        
        print(f"1. Original PSID: {original_psid}")
        print(f"2. Stored hash: {stored_hash[:16]}...")
        
        # Now simulate what happens in conversational AI
        print(f"\n3. In conversational AI:")
        print(f"   - Receives PSID: {original_psid}")
        print(f"   - Should query with hash: {stored_hash[:16]}...")
        
        # But if we hash again:
        double_hash = hash_psid(stored_hash)
        print(f"   - If we hash again: {double_hash[:16]}...")
        print(f"   - Result: NO DATA FOUND (different hash)")
        
        print(f"\n🎯 SOLUTION:")
        print(f"   - Production router: Pass original PSID")
        print(f"   - Conversational AI: Hash ONCE, then query")
        print(f"   - Never hash an already-hashed value")

if __name__ == "__main__":
    debug_hash_flow()