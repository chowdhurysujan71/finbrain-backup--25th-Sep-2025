#!/usr/bin/env python3
"""
Test production conversational scenario with existing user data
"""

import logging
import sys
sys.path.insert(0, '.')

def test_production_scenario():
    """Test the exact production scenario with existing user"""
    from app import app
    from utils.production_router import ProductionRouter
    from utils.conversational_ai import conversational_ai
    from utils.security import hash_psid
    
    with app.app_context():
        print("🎯 TESTING PRODUCTION CONVERSATIONAL SCENARIO")
        print("=" * 60)
        
        # Simulate the exact scenario from screenshots
        # User has logged expenses and asks for summary
        
        # Find a PSID that would hash to our test user
        user_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        # Let's use the hash as the PSID for this test since that's the issue
        test_psid = user_hash  # This represents the original Facebook PSID
        
        print(f"Testing with PSID: {test_psid[:16]}...")
        
        # Test the direct conversational AI response
        print("\n1. Testing direct conversational AI:")
        response, intent = conversational_ai.generate_summary_response(test_psid, "Give me a summary report now")
        print(f"   Response: {response}")
        print(f"   Intent: {intent}")
        
        # Test the production router (complete flow)
        print("\n2. Testing production router:")
        router = ProductionRouter()
        
        # Test different summary requests
        test_messages = [
            "Give me a summary report now",
            "Can you provide a full summary of my expenses",
            "What is my spending summary"
        ]
        
        for msg in test_messages:
            print(f"\n   Testing: '{msg}'")
            try:
                response, intent, category, amount = router.route_message(
                    text=msg,
                    psid=test_psid,
                    rid="test_scenario"
                )
                print(f"   ✅ Response: {response}")
                print(f"   ✅ Intent: {intent}")
                
                # Check if response contains actual data or arbitrary data
                if "coffee" in response.lower() or "start logging" in response.lower():
                    print("   ❌ STILL GENERATING ARBITRARY DATA!")
                elif any(str(amt) in response for amt in [1000, 100, 1815, 2915]):
                    print("   ✅ USING REAL USER DATA!")
                else:
                    print("   ⚠️  Response unclear")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_production_scenario()