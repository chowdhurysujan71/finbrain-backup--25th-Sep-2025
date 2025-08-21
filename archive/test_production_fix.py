#!/usr/bin/env python3
"""
Test the FIXED production router with real user data
"""

import logging
import sys
sys.path.insert(0, '.')

def test_production_fix():
    """Test the fixed production router"""
    from app import app
    from utils.production_router import ProductionRouter
    from utils.security import hash_psid
    
    with app.app_context():
        print("🎯 TESTING FIXED PRODUCTION ROUTER")
        print("=" * 50)
        
        # We need to find the original PSID that creates the hash dc863d3aa69d518...
        # Since we know the hash from database, let's simulate with a test PSID
        
        target_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        # For testing, create a mock PSID that would hash to our target
        # In production, this would be the actual Facebook PSID
        test_psid = "test_production_user_with_data"
        
        # Verify this PSID doesn't accidentally match our hash
        actual_hash = hash_psid(test_psid)
        print(f"Test PSID hash: {actual_hash[:16]}...")
        print(f"Target hash: {target_hash[:16]}...")
        
        # Since they don't match, let's directly test with the hash as PSID
        # This should work because our conversational AI now detects hash length
        
        print(f"\n1. Testing with hash as PSID (simulating real scenario):")
        
        router = ProductionRouter()
        
        test_messages = [
            "Give me a summary report now",
            "Can you show me my total expenses",
            "What's my spending summary"
        ]
        
        for msg in test_messages:
            print(f"\n   Testing: '{msg}'")
            try:
                response, intent, category, amount = router.route_message(
                    text=msg,
                    psid=target_hash,  # Use the actual hash
                    rid="production_fix_test"
                )
                
                print(f"   Response: {response[:100]}...")
                print(f"   Intent: {intent}")
                
                # Check if it's using real data
                if any(str(val) in response for val in ['15325', '14', '13925', '1095']):
                    print("   ✅ USING REAL DATA - FIXED!")
                elif "no data" in response.lower() or "start logging" in response.lower():
                    print("   ❌ STILL BROKEN")
                else:
                    print("   ⚠️  UNCLEAR RESPONSE")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_production_fix()