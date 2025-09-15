#!/usr/bin/env python3
"""
Test the complete fixed conversational flow to verify consistent responses
"""

import sys
sys.path.insert(0, '.')

def test_fixed_conversational_flow():
    """Test that both code paths now give consistent responses"""
    from app import app
    from utils.production_router import ProductionRouter
    
    with app.app_context():
        print("🎯 TESTING FIXED CONVERSATIONAL FLOW")
        print("=" * 50)
        
        # Use the real user hash that has data
        real_user_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        # Test the exact messages from user screenshots that showed inconsistency
        test_messages = [
            "Do you know all my expenses so far?",
            "What about gambling",
            "Can you give me insight",
            "Show me summary",
            "Give me a detailed report"
        ]
        
        router = ProductionRouter()
        
        print(f"Testing with user hash: {real_user_hash[:16]}...")
        
        all_responses_have_data = True
        no_data_responses = []
        data_responses = []
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n{i}. Testing: '{message}'")
            
            try:
                response, intent, category, amount = router.route_message(
                    text=message,
                    psid=real_user_hash,  # Using hash directly
                    rid=f"consistency_test_{i}"
                )
                
                print(f"   Response: {response}")
                print(f"   Intent: {intent}")
                
                # Check for inconsistency patterns
                has_no_data_msg = any(phrase in response.lower() for phrase in [
                    "don't see any expense", "start logging", "no data", "haven't logged"
                ])
                
                has_specific_data = any(indicator in response for indicator in [
                    '$', '৳', 'spent', 'total', 'expenses', 'category', 'food', 'shopping'
                ])
                
                if has_no_data_msg:
                    print(f"   ❌ NO DATA MESSAGE")
                    no_data_responses.append(f"Message {i}: {message}")
                    all_responses_have_data = False
                elif has_specific_data:
                    print(f"   ✅ HAS SPENDING DATA")
                    data_responses.append(f"Message {i}: {message}")
                else:
                    print(f"   ⚠️  NEUTRAL RESPONSE")
                    
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
                all_responses_have_data = False
        
        print(f"\n" + "=" * 50)
        print(f"🎯 CONSISTENCY TEST RESULTS:")
        print(f"   Total messages tested: {len(test_messages)}")
        print(f"   Responses with data: {len(data_responses)}")
        print(f"   Responses with 'no data': {len(no_data_responses)}")
        
        if all_responses_have_data:
            print(f"   ✅ SUCCESS: All responses consistent")
        else:
            print(f"   ❌ INCONSISTENCY STILL EXISTS")
            if no_data_responses:
                print(f"   No data responses: {no_data_responses}")
        
        print(f"\n🎉 DOUBLE-HASHING FIX STATUS: {'SUCCESSFUL' if all_responses_have_data else 'NEEDS MORE WORK'}")

if __name__ == "__main__":
    test_fixed_conversational_flow()