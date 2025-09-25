#!/usr/bin/env python3
"""
Focused End-to-End UAT for PoR v1.1 EXPENSE_LOG System
Comprehensive validation from input to database storage
"""

import json
import time
from datetime import datetime

from app import app


def run_comprehensive_e2e_uat():
    """Execute comprehensive end-to-end UAT with detailed audit reporting"""
    
    with app.app_context():
        print("🧪 COMPREHENSIVE END-TO-END UAT AUDIT")
        print("=" * 60)
        
        audit_results = {
            "session_id": f"uat_e2e_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "test_results": {},
            "summary": {},
            "deployment_recommendation": ""
        }
        
        # PHASE 1: DATA HANDLING VALIDATION
        print("\n🔍 PHASE 1: DATA HANDLING VALIDATION")
        print("-" * 50)
        
        data_handling_results = []
        
        # Test Bengali digit conversion
        try:
            from utils.bn_digits import to_en_digits
            test_input = "৫০ টাকা"
            converted = to_en_digits(test_input)
            expected = "50 টাকা"
            passed = "50" in converted
            data_handling_results.append({
                "test": "Bengali Digit Conversion",
                "input": test_input,
                "output": converted,
                "expected": expected,
                "passed": passed
            })
            print(f"  {'✅' if passed else '❌'} Bengali Digit Conversion: {test_input} → {converted}")
        except Exception as e:
            data_handling_results.append({"test": "Bengali Digit Conversion", "passed": False, "error": str(e)})
            print(f"  ❌ Bengali Digit Conversion: Error - {e}")
        
        # Test money pattern detection
        try:
            from nlp.money_patterns import extract_money_amount, has_money_mention
            test_cases = [
                "চা ৫০ টাকা",
                "coffee 75 taka", 
                "৳১০০ খরচ",
                "no money here"
            ]
            
            for test_case in test_cases:
                has_money = has_money_mention(test_case)
                amount = extract_money_amount(test_case)
                expected_money = any(char.isdigit() or char in "৳০১২৩৪৫৬৭৮৯" for char in test_case)
                
                passed = has_money == expected_money
                data_handling_results.append({
                    "test": f"Money Detection: {test_case}",
                    "has_money": has_money,
                    "amount": amount,
                    "passed": passed
                })
                print(f"  {'✅' if passed else '❌'} Money Detection '{test_case}': Money={has_money}, Amount={amount}")
        except Exception as e:
            data_handling_results.append({"test": "Money Pattern Detection", "passed": False, "error": str(e)})
            print(f"  ❌ Money Pattern Detection: Error - {e}")
        
        audit_results["test_results"]["data_handling"] = data_handling_results
        
        # PHASE 2: ROUTING VALIDATION
        print("\n🧭 PHASE 2: ROUTING VALIDATION")
        print("-" * 50)
        
        routing_results = []
        
        try:
            from utils.routing_policy import deterministic_router
            
            routing_test_cases = [
                {
                    "input": "আজ চা ৫০ টাকা খরচ করেছি",
                    "expected_intent": "EXPENSE_LOG",
                    "description": "Bengali expense with verb"
                },
                {
                    "input": "চা ৫০ টাকা",
                    "expected_intent": "CLARIFY_EXPENSE",
                    "description": "Bengali expense without verb"
                },
                {
                    "input": "এই মাসের খরচের সারাংশ দাও",
                    "expected_intent": "ANALYSIS",
                    "description": "Bengali analysis request"
                },
                {
                    "input": "এই সপ্তাহ?",
                    "expected_intent": "ANALYSIS", 
                    "description": "Time window query (OR logic)"
                },
                {
                    "input": "I spent 100 on food",
                    "expected_intent": "EXPENSE_LOG",
                    "description": "English expense with verb"
                }
            ]
            
            for test_case in routing_test_cases:
                signals = deterministic_router.extract_signals(test_case["input"], "uat_routing_user")
                signals.ledger_count_30d = 0  # Force deterministic routing
                
                should_use = deterministic_router.should_use_deterministic_routing(signals)
                
                if should_use:
                    result = deterministic_router.route_intent(test_case["input"], signals)
                    actual_intent = result.intent.value
                    passed = actual_intent == test_case["expected_intent"]
                    
                    routing_results.append({
                        "test": test_case["description"],
                        "input": test_case["input"],
                        "expected_intent": test_case["expected_intent"],
                        "actual_intent": actual_intent,
                        "reason_codes": result.reason_codes,
                        "confidence": result.confidence,
                        "passed": passed
                    })
                    print(f"  {'✅' if passed else '❌'} {test_case['description']}: {test_case['input']} → {actual_intent}")
                else:
                    routing_results.append({
                        "test": test_case["description"],
                        "passed": False,
                        "error": "Deterministic routing not activated"
                    })
                    print(f"  ❌ {test_case['description']}: Deterministic routing not activated")
                    
        except Exception as e:
            routing_results.append({"test": "Routing System", "passed": False, "error": str(e)})
            print(f"  ❌ Routing System: Error - {e}")
        
        audit_results["test_results"]["routing"] = routing_results
        
        # PHASE 3: DATABASE OPERATIONS
        print("\n💾 PHASE 3: DATABASE OPERATIONS")
        print("-" * 50)
        
        database_results = []
        
        try:
            from utils.db import get_user_expenses, save_expense
            
            # Test expense storage
            test_user = f"uat_db_user_{int(time.time())}"
            test_expense_data = {
                "user_identifier": test_user,
                "description": "UAT Test - Bengali Tea Expense",
                "amount": 50.0,
                "category": "Food & Dining",
                "currency": "BDT"
            }
            
            # Store expense
            expense_record = save_expense(**test_expense_data)
            storage_passed = expense_record is not None
            
            database_results.append({
                "test": "Expense Storage",
                "data": test_expense_data,
                "record_created": storage_passed,
                "record_id": getattr(expense_record, 'id', None) if expense_record else None,
                "passed": storage_passed
            })
            print(f"  {'✅' if storage_passed else '❌'} Expense Storage: Record created = {storage_passed}")
            
            # Test expense retrieval
            if storage_passed:
                user_expenses = get_user_expenses(test_user)
                retrieval_passed = len(user_expenses) > 0
                
                database_results.append({
                    "test": "Expense Retrieval",
                    "user": test_user,
                    "expenses_found": len(user_expenses),
                    "passed": retrieval_passed
                })
                print(f"  {'✅' if retrieval_passed else '❌'} Expense Retrieval: Found {len(user_expenses)} expenses")
                
                # Test data integrity
                if user_expenses:
                    latest_expense = user_expenses[0]
                    integrity_passed = (
                        latest_expense.description == test_expense_data["description"] and
                        abs(float(latest_expense.amount) - test_expense_data["amount"]) < 0.01
                    )
                    
                    database_results.append({
                        "test": "Data Integrity",
                        "stored_description": latest_expense.description,
                        "stored_amount": float(latest_expense.amount),
                        "expected_description": test_expense_data["description"],
                        "expected_amount": test_expense_data["amount"],
                        "passed": integrity_passed
                    })
                    print(f"  {'✅' if integrity_passed else '❌'} Data Integrity: Description and amount match = {integrity_passed}")
            
        except Exception as e:
            database_results.append({"test": "Database Operations", "passed": False, "error": str(e)})
            print(f"  ❌ Database Operations: Error - {e}")
        
        audit_results["test_results"]["database"] = database_results
        
        # PHASE 4: END-TO-END INTEGRATION
        print("\n🔄 PHASE 4: END-TO-END INTEGRATION")
        print("-" * 50)
        
        integration_results = []
        
        try:
            from utils.production_router import ProductionRouter
            router = ProductionRouter()
            
            e2e_test_cases = [
                {
                    "name": "Bengali Expense Logging",
                    "input": "আজ দুপুরের খাবার ১২০ টাকা খরচ করেছি",
                    "expected_contains": ["120", "৳", "logged"]
                },
                {
                    "name": "Bengali Clarification",
                    "input": "রাতের খাবার ৮০ টাকা", 
                    "expected_contains": ["80", "৳", "log"]
                },
                {
                    "name": "English Analysis",
                    "input": "show my spending summary",
                    "expected_contains": ["summary", "spending"]
                }
            ]
            
            for test_case in e2e_test_cases:
                try:
                    start_time = time.time()
                    response, intent, category, amount = router.route_message(
                        text=test_case["input"],
                        psid=f"uat_e2e_{test_case['name'].replace(' ', '_').lower()}",
                        rid=f"e2e_{int(time.time())}"
                    )
                    end_time = time.time()
                    
                    response_time_ms = (end_time - start_time) * 1000
                    
                    # Check if response contains expected patterns
                    pattern_matches = sum(1 for pattern in test_case["expected_contains"] 
                                        if pattern.lower() in response.lower())
                    
                    passed = (
                        response and 
                        len(response) > 10 and
                        pattern_matches >= len(test_case["expected_contains"]) * 0.5  # 50% pattern match
                    )
                    
                    integration_results.append({
                        "test": test_case["name"],
                        "input": test_case["input"],
                        "intent": intent,
                        "category": category,
                        "amount": amount,
                        "response_preview": response[:100] + "..." if len(response) > 100 else response,
                        "response_time_ms": round(response_time_ms, 1),
                        "pattern_matches": f"{pattern_matches}/{len(test_case['expected_contains'])}",
                        "passed": passed
                    })
                    print(f"  {'✅' if passed else '❌'} {test_case['name']}: Intent={intent}, Time={response_time_ms:.1f}ms")
                    
                except Exception as e:
                    integration_results.append({
                        "test": test_case["name"], 
                        "passed": False, 
                        "error": str(e)
                    })
                    print(f"  ❌ {test_case['name']}: Error - {e}")
                    
        except Exception as e:
            integration_results.append({"test": "End-to-End Integration", "passed": False, "error": str(e)})
            print(f"  ❌ End-to-End Integration: Error - {e}")
        
        audit_results["test_results"]["integration"] = integration_results
        
        # GENERATE AUDIT SUMMARY
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE AUDIT SUMMARY")
        print("=" * 60)
        
        # Calculate overall statistics
        all_tests = []
        for category, tests in audit_results["test_results"].items():
            all_tests.extend(tests)
        
        total_tests = len(all_tests)
        passed_tests = len([test for test in all_tests if test.get("passed", False)])
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Category breakdown
        for category, tests in audit_results["test_results"].items():
            category_passed = len([test for test in tests if test.get("passed", False)])
            category_total = len(tests)
            category_rate = (category_passed / category_total * 100) if category_total > 0 else 0
            
            print(f"\n🔹 {category.upper().replace('_', ' ')}")
            print(f"   Tests: {category_passed}/{category_total} ({category_rate:.1f}%)")
            
            # Show failures
            failed_tests = [test for test in tests if not test.get("passed", False)]
            if failed_tests:
                print("   ❌ Failed Tests:")
                for failed in failed_tests:
                    error_msg = failed.get("error", "Test failed")
                    print(f"      - {failed.get('test', 'Unknown')}: {error_msg}")
        
        # Overall assessment
        print("\n📈 OVERALL ASSESSMENT")
        print(f"   Total Tests: {passed_tests}/{total_tests}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        # Deployment recommendation
        if success_rate >= 95:
            deployment_status = "🎉 APPROVED FOR IMMEDIATE DEPLOYMENT"
            recommendation = "All systems validated - ready for production"
        elif success_rate >= 90:
            deployment_status = "✅ APPROVED FOR DEPLOYMENT"
            recommendation = "Minor issues detected but core functionality verified"
        elif success_rate >= 80:
            deployment_status = "⚠️ CONDITIONAL APPROVAL"
            recommendation = "Address identified issues before deployment"
        else:
            deployment_status = "❌ NOT APPROVED FOR DEPLOYMENT"
            recommendation = "Critical failures detected - requires fixes"
        
        print("\n🚀 DEPLOYMENT RECOMMENDATION")
        print(f"   Status: {deployment_status}")
        print(f"   Recommendation: {recommendation}")
        
        # Update audit results
        audit_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "deployment_approved": success_rate >= 90
        }
        audit_results["deployment_recommendation"] = {
            "status": deployment_status,
            "recommendation": recommendation
        }
        
        # Save detailed audit report
        report_filename = f"comprehensive_uat_audit_{audit_results['session_id']}.json"
        with open(report_filename, 'w') as f:
            json.dump(audit_results, f, indent=2)
        
        print(f"\n📄 Detailed audit report saved: {report_filename}")
        print("\n" + "=" * 60)
        print("✅ COMPREHENSIVE END-TO-END UAT COMPLETE")
        print("=" * 60)
        
        return audit_results

if __name__ == "__main__":
    run_comprehensive_e2e_uat()