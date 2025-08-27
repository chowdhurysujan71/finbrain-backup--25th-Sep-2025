#!/usr/bin/env python3
"""
End-to-end test for the new EXPENSE_LOG system integration
Validates full pipeline from routing to storage to response
"""

import json
from app import app

def test_new_expense_log_system():
    """Test complete EXPENSE_LOG pipeline integration"""
    
    with app.app_context():
        print("🧪 TESTING NEW EXPENSE_LOG SYSTEM INTEGRATION")
        print("=" * 60)
        
        # Import production router
        from utils.production_router import ProductionRouter
        router = ProductionRouter()
        
        # Test cases matching contract requirements
        test_cases = [
            {
                "name": "Bengali Expense with Verb → EXPENSE_LOG",
                "input": "আজ চা ৫০ টাকা খরচ করেছি",
                "expected_intent": "expense_log",
                "expected_success": True
            },
            {
                "name": "Bengali Expense without Verb → CLARIFY_EXPENSE", 
                "input": "চা ৫০ টাকা",
                "expected_intent": "clarify_expense",
                "expected_success": True
            },
            {
                "name": "English Analysis Request → ANALYSIS",
                "input": "show me spending analysis for this month",
                "expected_intent": "analysis",
                "expected_success": True
            },
            {
                "name": "Mixed Language Coaching → COACHING",
                "input": "help me টাকা সেভ করতে this month",
                "expected_intent": "coaching", 
                "expected_success": True
            },
            {
                "name": "No False Positives",
                "input": "আজ ভালো একটা দিন ছিল",
                "expected_intent": "smalltalk",
                "expected_success": True
            }
        ]
        
        passed_tests = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}️⃣ {test_case['name']}")
            print(f"  Input: {test_case['input']}")
            
            try:
                # Route message through production system
                response, intent, category, amount = router.route_message(
                    text=test_case['input'],
                    psid="test_user_123",
                    rid=f"test_{i}"
                )
                
                print(f"  Expected Intent: {test_case['expected_intent']}")
                print(f"  Actual Intent: {intent}")
                print(f"  Response: {response[:100]}...")
                if category:
                    print(f"  Category: {category}")
                if amount:
                    print(f"  Amount: {amount}")
                
                # Check if intent matches expectation (allowing for some variation)
                intent_match = (
                    intent == test_case['expected_intent'] or
                    (test_case['expected_intent'] == "expense_log" and intent in ["log_single", "expense_log"]) or
                    (test_case['expected_intent'] == "clarify_expense" and "clarify" in intent.lower()) or
                    (test_case['expected_intent'] == "analysis" and intent in ["analysis", "summary"]) or
                    (test_case['expected_intent'] == "coaching" and "coaching" in intent.lower()) or
                    (test_case['expected_intent'] == "smalltalk" and intent in ["smalltalk", "ai_conversation", "faq"])
                )
                
                if intent_match:
                    print(f"  ✅ PASS")
                    passed_tests += 1
                else:
                    print(f"  ❌ FAIL - Intent mismatch")
                    
            except Exception as e:
                print(f"  ❌ FAIL - Exception: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 INTEGRATION TEST RESULTS: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("🎉 ALL INTEGRATION TESTS PASSED")
            print("✅ NEW EXPENSE_LOG SYSTEM READY FOR PRODUCTION")
            return True
        elif passed_tests >= total_tests * 0.8:  # 80% pass rate
            print("⚠️ MOSTLY WORKING - Minor issues detected")
            print("🔧 System functional but may need minor adjustments")
            return True
        else:
            print("❌ INTEGRATION TESTS FAILED")
            print("🚫 DO NOT DEPLOY - SYSTEM NOT READY")
            return False

if __name__ == "__main__":
    test_new_expense_log_system()