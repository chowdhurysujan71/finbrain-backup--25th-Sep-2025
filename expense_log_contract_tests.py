#!/usr/bin/env python3
"""
Contract tests for EXPENSE_LOG intent implementation
These tests must pass before deployment to lock behavior
"""

from app import app


def test_expense_log_contracts():
    """Test all EXPENSE_LOG contract requirements"""
    
    with app.app_context():
        from utils.routing_policy import deterministic_router
        
        print("🧪 EXPENSE_LOG CONTRACT TESTS")
        print("=" * 50)
        
        tests_passed = 0
        total_tests = 5
        
        # Contract Test 1: BN expense with verb → EXPENSE_LOG
        print("\n1️⃣ Bengali expense with verb")
        bn_expense_message = "আজ চা ৫০ টাকা খরচ করেছি"
        bn_signals = deterministic_router.extract_signals(bn_expense_message, "test_user_bn")
        bn_result = deterministic_router.route_intent(bn_expense_message, bn_signals)
        
        expected_intent = "EXPENSE_LOG"
        actual_intent = bn_result.intent.value
        
        print(f"  Input: {bn_expense_message}")
        print(f"  Expected: {expected_intent}")
        print(f"  Actual: {actual_intent}")
        print(f"  Money detected: {bn_signals.has_money}")
        print(f"  Verb detected: {bn_signals.has_first_person_spent_verb}")
        
        if actual_intent == expected_intent:
            print("  ✅ PASS")
            tests_passed += 1
        else:
            print("  ❌ FAIL")
        
        # Contract Test 2: BN expense without verb → CLARIFY_EXPENSE
        print("\n2️⃣ Bengali expense without verb")
        bn_ambiguous_message = "চা ৫০ টাকা"
        bn_ambiguous_signals = deterministic_router.extract_signals(bn_ambiguous_message, "test_user_bn2")
        bn_ambiguous_result = deterministic_router.route_intent(bn_ambiguous_message, bn_ambiguous_signals)
        
        expected_intent = "CLARIFY_EXPENSE"
        actual_intent = bn_ambiguous_result.intent.value
        
        print(f"  Input: {bn_ambiguous_message}")
        print(f"  Expected: {expected_intent}")
        print(f"  Actual: {actual_intent}")
        print(f"  Money detected: {bn_ambiguous_signals.has_money}")
        print(f"  Verb detected: {bn_ambiguous_signals.has_first_person_spent_verb}")
        
        if actual_intent == expected_intent:
            print("  ✅ PASS")
            tests_passed += 1
        else:
            print("  ❌ FAIL")
        
        # Contract Test 3: Explicit analysis wins even with money
        print("\n3️⃣ Explicit analysis wins")
        analysis_message = "এই মাসের খরচের সারাংশ দাও"
        analysis_signals = deterministic_router.extract_signals(analysis_message, "test_user_analysis")
        analysis_result = deterministic_router.route_intent(analysis_message, analysis_signals)
        
        expected_intent = "ANALYSIS"
        actual_intent = analysis_result.intent.value
        
        print(f"  Input: {analysis_message}")
        print(f"  Expected: {expected_intent}")
        print(f"  Actual: {actual_intent}")
        print(f"  Explicit analysis: {analysis_signals.has_explicit_analysis}")
        
        if actual_intent == expected_intent:
            print("  ✅ PASS")
            tests_passed += 1
        else:
            print("  ❌ FAIL")
        
        # Contract Test 4: Coaching stays coaching
        print("\n4️⃣ Coaching stays coaching")
        coaching_message = "help me টাকা সেভ করতে this month"
        coaching_signals = deterministic_router.extract_signals(coaching_message, "test_user_coaching")
        coaching_signals.ledger_count_30d = 20  # Simulate eligible user
        coaching_result = deterministic_router.route_intent(coaching_message, coaching_signals)
        
        expected_intent = "COACHING"
        actual_intent = coaching_result.intent.value
        
        print(f"  Input: {coaching_message}")
        print(f"  Expected: {expected_intent}")
        print(f"  Actual: {actual_intent}")
        print(f"  Coaching verbs: {coaching_signals.has_coaching_verbs}")
        print(f"  Ledger count: {coaching_signals.ledger_count_30d}")
        
        if actual_intent == expected_intent:
            print("  ✅ PASS")
            tests_passed += 1
        else:
            print("  ❌ FAIL")
        
        # Contract Test 5: No false positives
        print("\n5️⃣ No false positives")
        no_expense_message = "আজ ভালো একটা দিন ছিল"
        no_expense_signals = deterministic_router.extract_signals(no_expense_message, "test_user_noexpense")
        no_expense_result = deterministic_router.route_intent(no_expense_message, no_expense_signals)
        
        not_expected_intent = "EXPENSE_LOG"
        actual_intent = no_expense_result.intent.value
        
        print(f"  Input: {no_expense_message}")
        print(f"  Should NOT be: {not_expected_intent}")
        print(f"  Actual: {actual_intent}")
        print(f"  Money detected: {no_expense_signals.has_money}")
        print(f"  Verb detected: {no_expense_signals.has_first_person_spent_verb}")
        
        if actual_intent != not_expected_intent:
            print("  ✅ PASS")
            tests_passed += 1
        else:
            print("  ❌ FAIL")
        
        # Final Summary
        print("\n" + "=" * 50)
        print(f"📊 CONTRACT TEST RESULTS: {tests_passed}/{total_tests}")
        
        if tests_passed == total_tests:
            print("🎉 ALL CONTRACT TESTS PASSED - READY FOR DEPLOYMENT")
            return True
        else:
            print("❌ CONTRACT TESTS FAILED - DO NOT DEPLOY")
            return False

if __name__ == "__main__":
    test_expense_log_contracts()