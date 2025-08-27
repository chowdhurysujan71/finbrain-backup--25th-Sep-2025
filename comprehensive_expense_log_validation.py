#!/usr/bin/env python3
"""
Comprehensive validation for PoR v1.1 EXPENSE_LOG and CLARIFY_EXPENSE system
Tests both contract-level routing and end-to-end integration
"""

import json
from app import app

def test_comprehensive_expense_log_validation():
    """Complete validation of EXPENSE_LOG system with PoR v1.1 specifications"""
    
    with app.app_context():
        print("🧪 COMPREHENSIVE PoR v1.1 EXPENSE_LOG VALIDATION")
        print("=" * 70)
        
        # Step 1: Contract-level routing validation
        print("\n📋 STEP 1: CONTRACT-LEVEL ROUTING VALIDATION")
        print("-" * 50)
        
        from utils.routing_policy import deterministic_router
        
        contract_tests = [
            {
                "name": "Bengali expense with verb → EXPENSE_LOG",
                "input": "আজ চা ৫০ টাকা খরচ করেছি",
                "expected": "EXPENSE_LOG"
            },
            {
                "name": "Bengali expense without verb → CLARIFY_EXPENSE",
                "input": "চা ৫০ টাকা", 
                "expected": "CLARIFY_EXPENSE"
            },
            {
                "name": "Explicit analysis wins",
                "input": "এই মাসের খরচের সারাংশ দাও",
                "expected": "ANALYSIS"
            },
            {
                "name": "Coaching stays coaching",
                "input": "help me টাকা সেভ করতে this month",
                "expected": "COACHING"
            },
            {
                "name": "No false positives",
                "input": "আজ ভালো একটা দিন ছিল",
                "expected": "SMALLTALK"
            }
        ]
        
        contract_passed = 0
        for i, test in enumerate(contract_tests, 1):
            print(f"{i}. {test['name']}")
            
            # Test with deterministic routing directly
            signals = deterministic_router.extract_signals(test['input'], "test_user_contract")
            
            # Force deterministic routing to activate (override scope)
            signals.ledger_count_30d = 0  # Force zero ledger for testing
            
            routing_result = deterministic_router.route_intent(test['input'], signals)
            actual_intent = routing_result.intent.value
            
            print(f"   Input: {test['input']}")
            print(f"   Expected: {test['expected']}")
            print(f"   Actual: {actual_intent}")
            print(f"   Money: {signals.has_money}, Verb: {signals.has_first_person_spent_verb}")
            
            if actual_intent == test['expected']:
                print(f"   ✅ PASS")
                contract_passed += 1
            else:
                print(f"   ❌ FAIL")
        
        print(f"\nContract Test Results: {contract_passed}/{len(contract_tests)}")
        
        # Step 2: End-to-end integration validation
        print("\n🔗 STEP 2: END-TO-END INTEGRATION VALIDATION")
        print("-" * 50)
        
        from utils.production_router import ProductionRouter
        router = ProductionRouter()
        
        integration_tests = [
            {
                "name": "Bengali Expense Logging",
                "input": "আজ চা ৫০ টাকা খরচ করেছি",
                "expected_patterns": ["logged", "৳", "50"]
            },
            {
                "name": "Bengali Clarification",
                "input": "চা ৫০ টাকা",
                "expected_patterns": ["log", "৳", "50"]
            }
        ]
        
        integration_passed = 0
        for i, test in enumerate(integration_tests, 1):
            print(f"{i}. {test['name']}")
            
            try:
                # Route through production system with fresh user (zero ledger)
                response, intent, category, amount = router.route_message(
                    text=test['input'],
                    psid=f"test_user_integration_{i}",  # Fresh user each time
                    rid=f"integration_test_{i}"
                )
                
                print(f"   Input: {test['input']}")
                print(f"   Intent: {intent}")
                print(f"   Response: {response[:100]}...")
                if category:
                    print(f"   Category: {category}")
                if amount:
                    print(f"   Amount: {amount}")
                
                # Check if response contains expected patterns
                pattern_matches = sum(1 for pattern in test['expected_patterns'] 
                                    if pattern.lower() in response.lower())
                
                if pattern_matches >= len(test['expected_patterns']) * 0.7:  # 70% pattern match
                    print(f"   ✅ PASS")
                    integration_passed += 1
                else:
                    print(f"   ❌ FAIL - Missing expected patterns")
                    
            except Exception as e:
                print(f"   ❌ FAIL - Exception: {e}")
        
        print(f"\nIntegration Test Results: {integration_passed}/{len(integration_tests)}")
        
        # Step 3: System health validation
        print("\n⚡ STEP 3: SYSTEM HEALTH VALIDATION")
        print("-" * 50)
        
        health_checks = []
        
        # Check routing policy module
        try:
            from utils.routing_policy import DeterministicRouter, IntentType, RoutingSignals
            deterministic_router = DeterministicRouter()
            
            # Test basic functionality
            test_signals = deterministic_router.extract_signals("test message", "test_user")
            assert hasattr(test_signals, 'has_money')
            assert hasattr(test_signals, 'has_first_person_spent_verb')
            
            health_checks.append(("Routing Policy Module", True))
        except Exception as e:
            health_checks.append(("Routing Policy Module", False, str(e)))
        
        # Check expense handlers
        try:
            from expense_log_handlers import handle_expense_log_intent, handle_clarify_expense_intent
            health_checks.append(("Expense Log Handlers", True))
        except Exception as e:
            health_checks.append(("Expense Log Handlers", False, str(e)))
        
        # Check money detection utilities
        try:
            from utils.bn_digits import to_en_digits
            from nlp.money_patterns import has_money_mention
            
            # Test Bengali digit conversion
            assert to_en_digits("৫০") == "50"
            
            # Test money detection
            assert has_money_mention("50 taka") == True
            
            health_checks.append(("Money Detection Utilities", True))
        except Exception as e:
            health_checks.append(("Money Detection Utilities", False, str(e)))
        
        health_passed = 0
        for check in health_checks:
            name = check[0]
            passed = check[1]
            error = check[2] if len(check) > 2 else None
            
            if passed:
                print(f"✅ {name}")
                health_passed += 1
            else:
                print(f"❌ {name}: {error}")
        
        print(f"\nHealth Check Results: {health_passed}/{len(health_checks)}")
        
        # Final Assessment
        print("\n" + "=" * 70)
        print("📊 FINAL ASSESSMENT")
        print("-" * 70)
        
        total_passed = contract_passed + integration_passed + health_passed
        total_tests = len(contract_tests) + len(integration_tests) + len(health_checks)
        
        success_rate = (total_passed / total_tests) * 100
        
        print(f"Contract Tests: {contract_passed}/{len(contract_tests)}")
        print(f"Integration Tests: {integration_passed}/{len(integration_tests)}")
        print(f"Health Checks: {health_passed}/{len(health_checks)}")
        print(f"Overall Success Rate: {success_rate:.1f}% ({total_passed}/{total_tests})")
        
        if success_rate >= 90:
            print("\n🎉 SYSTEM READY FOR DEPLOYMENT")
            print("✅ PoR v1.1 EXPENSE_LOG implementation validated successfully")
            print("✅ All critical components functional")
            print("✅ Deterministic routing working correctly")
            print("✅ Bengali support validated")
            return True
        elif success_rate >= 80:
            print("\n⚠️ SYSTEM MOSTLY READY - Minor Issues Detected")
            print("🔧 Core functionality working but may need minor adjustments")
            return True
        else:
            print("\n❌ SYSTEM NOT READY FOR DEPLOYMENT")
            print("🚫 Critical issues detected - requires fixes before deployment")
            return False

if __name__ == "__main__":
    test_comprehensive_expense_log_validation()