#!/usr/bin/env python3
"""
Debug test to isolate deterministic routing issues
"""

from app import app

def debug_deterministic_routing():
    """Debug the deterministic routing step by step"""
    
    with app.app_context():
        from utils.routing_policy import DeterministicRouter, RoutingSignals
        from utils.routing_policy import deterministic_router
        
        print("🐛 DEBUGGING DETERMINISTIC ROUTING")
        print("=" * 50)
        
        # Test Case 1: Bengali expense with verb
        test_input = "আজ চা ৫০ টাকা খরচ করেছি"
        print(f"\n1. Testing: {test_input}")
        
        # Extract signals step by step
        signals = deterministic_router.extract_signals(test_input, "debug_user")
        print(f"   Raw signals:")
        print(f"   - has_money: {signals.has_money}")
        print(f"   - has_first_person_spent_verb: {signals.has_first_person_spent_verb}")
        print(f"   - has_explicit_analysis: {signals.has_explicit_analysis}")
        print(f"   - ledger_count_30d: {signals.ledger_count_30d}")
        
        # Force zero ledger
        signals.ledger_count_30d = 0
        print(f"   - ledger_count_30d (forced): {signals.ledger_count_30d}")
        
        # Check if deterministic routing should activate
        should_use = deterministic_router.should_use_deterministic_routing(signals)
        print(f"   - should_use_deterministic_routing: {should_use}")
        
        # Try routing
        if should_use:
            routing_result = deterministic_router.route_intent(test_input, signals)
            print(f"   - Routing result: {routing_result.intent.value}")
            print(f"   - Reason codes: {routing_result.reason_codes}")
            print(f"   - Matched patterns: {routing_result.matched_patterns}")
        else:
            print(f"   ❌ Deterministic routing not activated!")
            
        # Test Case 2: Bengali clarification
        test_input2 = "চা ৫০ টাকা"
        print(f"\n2. Testing: {test_input2}")
        
        signals2 = deterministic_router.extract_signals(test_input2, "debug_user_2")
        signals2.ledger_count_30d = 0
        
        print(f"   - has_money: {signals2.has_money}")
        print(f"   - has_first_person_spent_verb: {signals2.has_first_person_spent_verb}")
        print(f"   - has_explicit_analysis: {signals2.has_explicit_analysis}")
        
        should_use2 = deterministic_router.should_use_deterministic_routing(signals2)
        print(f"   - should_use_deterministic_routing: {should_use2}")
        
        if should_use2:
            routing_result2 = deterministic_router.route_intent(test_input2, signals2)
            print(f"   - Routing result: {routing_result2.intent.value}")
        else:
            print(f"   ❌ Deterministic routing not activated!")
            
        # Test Case 3: Analysis query
        test_input3 = "এই মাসের খরচের সারাংশ দাও"
        print(f"\n3. Testing: {test_input3}")
        
        signals3 = deterministic_router.extract_signals(test_input3, "debug_user_3")
        signals3.ledger_count_30d = 0
        
        print(f"   - has_explicit_analysis: {signals3.has_explicit_analysis}")
        print(f"   - has_time_window: {signals3.has_time_window}")
        print(f"   - has_analysis_terms: {signals3.has_analysis_terms}")
        
        should_use3 = deterministic_router.should_use_deterministic_routing(signals3)
        print(f"   - should_use_deterministic_routing: {should_use3}")
        
        if should_use3:
            routing_result3 = deterministic_router.route_intent(test_input3, signals3)
            print(f"   - Routing result: {routing_result3.intent.value}")
        else:
            print(f"   ❌ Deterministic routing not activated!")

        # Check the configuration
        print(f"\n🔧 CONFIGURATION CHECK")
        print(f"   - Router flags: {deterministic_router.flags}")
        print(f"   - Routing scope: {getattr(deterministic_router.flags, 'routing_scope', 'not_set')}")

if __name__ == "__main__":
    debug_deterministic_routing()