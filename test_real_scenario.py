#!/usr/bin/env python3
"""
Test with actual PSID that would create the correct hash
"""

import sys
sys.path.insert(0, '.')

def find_original_psid():
    """Find what PSID would create our target hash"""
    from app import app
    from utils.security import hash_psid
    
    with app.app_context():
        target_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        # Since this is a SHA-256 hash, we need to find the original PSID
        # In production, this would be the actual Facebook PSID
        
        # For testing, let's try some common patterns
        test_psids = [
            "test_user_123",
            "1234567890",
            target_hash,  # Maybe it's stored as hash already
            "real_facebook_psid_example"
        ]
        
        print("🔍 Testing different PSIDs to find the correct hash:")
        for psid in test_psids:
            hashed = hash_psid(psid)
            print(f"PSID: '{psid[:20]}...' -> Hash: {hashed[:16]}...")
            
            if hashed == target_hash:
                print(f"✅ FOUND MATCH! PSID: {psid}")
                return psid
                
        print("❌ No match found. The PSID is likely a real Facebook PSID.")
        return None

def test_direct_hash_access():
    """Test accessing data using the hash directly"""
    from app import app
    from utils.conversational_ai import conversational_ai
    
    with app.app_context():
        target_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        print(f"\n🎯 Testing direct hash access...")
        
        # Test the direct method with the exact hash
        context = conversational_ai.get_user_expense_context_direct(target_hash, days=30)
        
        print(f"Direct hash access result:")
        print(f"  - Has data: {context['has_data']}")
        print(f"  - Total expenses: {context['total_expenses']}")
        print(f"  - Total amount: {context['total_amount']}")
        
        if context['has_data']:
            print("✅ SUCCESS: Direct hash access works!")
            
            # Generate a proper summary
            summary = f"Your spending summary: {context['total_expenses']} expenses totaling {context['total_amount']:.0f}. Top category is {context['top_category'][0]} at {context['top_category'][1]['amount']:.0f}."
            print(f"Generated summary: {summary}")
        else:
            print("❌ FAILURE: Direct hash access didn't find data")

if __name__ == "__main__":
    find_original_psid()
    test_direct_hash_access()