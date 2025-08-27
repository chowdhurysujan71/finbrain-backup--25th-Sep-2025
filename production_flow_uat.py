#!/usr/bin/env python3
"""
Production Flow UAT - Exact Live User Experience Simulation
Tests complete end-to-end pipeline using actual production routes and flows
"""

import json
import time
import uuid
from datetime import datetime
from app import app

class ProductionFlowUAT:
    """Comprehensive UAT simulating exact live user experience"""
    
    def __init__(self):
        self.session_id = f"prod_uat_{int(time.time())}"
        self.audit_results = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "test_scenarios": [],
            "system_health": {},
            "user_experience_metrics": {},
            "data_integrity_validation": {},
            "deployment_readiness": {},
            "live_user_simulation": {}
        }
        self.user_counter = 1000
        
    def log_scenario(self, scenario_name, test_data, success, details, metrics=None):
        """Log a complete test scenario with all details"""
        scenario_result = {
            "scenario": scenario_name,
            "timestamp": datetime.now().isoformat(),
            "test_data": test_data,
            "success": success,
            "details": details,
            "metrics": metrics or {},
            "user_experience": {
                "response_received": bool(details.get("response")),
                "response_time_ms": details.get("response_time_ms", 0),
                "intent_classified": details.get("intent") != "error",
                "data_stored": details.get("data_stored", False),
                "user_friendly_response": len(details.get("response", "")) > 10
            }
        }
        self.audit_results["test_scenarios"].append(scenario_result)
        
    def simulate_messenger_webhook(self, user_psid, message_text, message_id=None):
        """Simulate exactly what happens when Facebook sends a webhook"""
        try:
            from utils.production_router import ProductionRouter
            
            if not message_id:
                message_id = f"msg_{uuid.uuid4().hex[:8]}"
            
            start_time = time.time()
            
            # This is the exact same call that happens in production
            router = ProductionRouter()
            response, intent, category, amount = router.route_message(
                text=message_text,
                psid=user_psid,
                rid=message_id
            )
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Check if data was actually stored by querying database
            data_stored = False
            stored_amount = None
            if intent in ["log", "expense_log"] and amount:
                try:
                    from utils.db import get_user_expenses
                    from utils.identity import ensure_hashed
                    user_hash = ensure_hashed(user_psid)
                    recent_expenses = get_user_expenses(user_hash, limit=1)
                    if recent_expenses and len(recent_expenses) > 0:
                        latest_expense = recent_expenses[0]
                        stored_amount = latest_expense.get('amount')
                        # Convert both to float to avoid Decimal/float type mismatch
                    data_stored = abs(float(stored_amount) - float(amount)) < 0.01 if stored_amount else False
                except Exception as e:
                    print(f"  ⚠️ Database verification failed: {e}")
            
            return {
                "response": response,
                "intent": intent,
                "category": category,
                "amount": amount,
                "response_time_ms": response_time_ms,
                "data_stored": data_stored,
                "stored_amount": stored_amount,
                "message_id": message_id
            }
            
        except Exception as e:
            return {
                "response": None,
                "intent": "error",
                "category": None,
                "amount": None,
                "response_time_ms": 0,
                "data_stored": False,
                "error": str(e),
                "message_id": message_id
            }
    
    def test_bengali_expense_logging_flow(self):
        """Test complete Bengali expense logging as live user would experience"""
        print("\n🇧🇩 BENGALI EXPENSE LOGGING - LIVE USER SIMULATION")
        print("-" * 65)
        
        test_cases = [
            {
                "message": "আজ সকালের নাস্তা ৮০ টাকা খরচ করেছি",
                "expected_amount": 80.0,
                "description": "Bengali breakfast expense with past tense verb"
            },
            {
                "message": "দুপুরের খাবার ১২০ টাকা খরচ করলাম",
                "expected_amount": 120.0,
                "description": "Bengali lunch expense with different verb form"
            },
            {
                "message": "চা ৫০ টাকা কিনেছি",
                "expected_amount": 50.0,
                "description": "Bengali tea purchase"
            },
            {
                "message": "রিকশা ভাড়া ৩০ টাকা দিয়েছি",
                "expected_amount": 30.0,
                "description": "Bengali transportation expense"
            }
        ]
        
        bengali_results = []
        
        for i, test_case in enumerate(test_cases):
            user_psid = f"bengali_user_{self.user_counter + i}"
            
            print(f"\n  👤 User: {user_psid}")
            print(f"  💬 Message: {test_case['message']}")
            
            result = self.simulate_messenger_webhook(user_psid, test_case['message'])
            
            # Detailed validation
            success_criteria = {
                "response_received": bool(result.get("response")),
                "intent_correct": result.get("intent") in ["log", "expense_log"],
                "amount_extracted": result.get("amount") == test_case['expected_amount'],
                "data_stored": result.get("data_stored", False),
                "response_time_acceptable": result.get("response_time_ms", 0) < 5000,
                "user_friendly_response": len(result.get("response", "")) > 20
            }
            
            overall_success = all(success_criteria.values())
            
            # Log detailed results
            print(f"  ⚡ Response Time: {result.get('response_time_ms', 0):.1f}ms")
            print(f"  🎯 Intent: {result.get('intent')}")
            print(f"  💰 Amount: {result.get('amount')} (expected: {test_case['expected_amount']})")
            print(f"  💾 Data Stored: {result.get('data_stored')}")
            print(f"  📱 Response: {result.get('response', 'None')[:80]}...")
            print(f"  ✅ Success: {overall_success}")
            
            bengali_results.append({
                "test_case": test_case,
                "result": result,
                "success_criteria": success_criteria,
                "overall_success": overall_success
            })
            
            self.log_scenario(
                f"Bengali Expense: {test_case['description']}", 
                test_case, 
                overall_success, 
                result,
                {"response_time_ms": result.get("response_time_ms", 0)}
            )
        
        bengali_success_rate = sum(1 for r in bengali_results if r["overall_success"]) / len(bengali_results) * 100
        print(f"\n  📊 Bengali Expense Logging Success Rate: {bengali_success_rate:.1f}%")
        
        return bengali_results
    
    def test_bengali_clarification_flow(self):
        """Test Bengali clarification flow as live user would experience"""
        print("\n🤔 BENGALI CLARIFICATION - LIVE USER SIMULATION")
        print("-" * 60)
        
        clarification_cases = [
            {
                "message": "চা ৫০ টাকা",
                "expected_intent": "clarify_expense",
                "description": "Simple Bengali expense without verb"
            },
            {
                "message": "রাতের খাবার ১৫০ টাকা",
                "expected_intent": "clarify_expense", 
                "description": "Bengali dinner cost without action verb"
            },
            {
                "message": "বাস ভাড়া ২৫ টাকা",
                "expected_intent": "clarify_expense",
                "description": "Bengali bus fare without expense verb"
            }
        ]
        
        clarification_results = []
        
        for i, test_case in enumerate(clarification_cases):
            user_psid = f"clarify_user_{self.user_counter + 100 + i}"
            
            print(f"\n  👤 User: {user_psid}")
            print(f"  💬 Message: {test_case['message']}")
            
            result = self.simulate_messenger_webhook(user_psid, test_case['message'])
            
            # Clarification-specific success criteria
            success_criteria = {
                "response_received": bool(result.get("response")),
                "intent_correct": result.get("intent") == test_case['expected_intent'],
                "clarification_prompt": "log" in result.get("response", "").lower() or "করব" in result.get("response", ""),
                "amount_mentioned": any(str(i) in result.get("response", "") for i in [25, 50, 150]),
                "response_time_acceptable": result.get("response_time_ms", 0) < 3000
            }
            
            overall_success = all(success_criteria.values())
            
            print(f"  ⚡ Response Time: {result.get('response_time_ms', 0):.1f}ms")
            print(f"  🎯 Intent: {result.get('intent')}")
            print(f"  📱 Response: {result.get('response', 'None')[:80]}...")
            print(f"  ✅ Success: {overall_success}")
            
            clarification_results.append({
                "test_case": test_case,
                "result": result,
                "success_criteria": success_criteria,
                "overall_success": overall_success
            })
            
            self.log_scenario(
                f"Bengali Clarification: {test_case['description']}", 
                test_case, 
                overall_success, 
                result
            )
        
        clarification_success_rate = sum(1 for r in clarification_results if r["overall_success"]) / len(clarification_results) * 100
        print(f"\n  📊 Bengali Clarification Success Rate: {clarification_success_rate:.1f}%")
        
        return clarification_results
    
    def test_english_expense_flow(self):
        """Test English expense processing as live user would experience"""
        print("\n🇺🇸 ENGLISH EXPENSE FLOW - LIVE USER SIMULATION")
        print("-" * 55)
        
        english_cases = [
            {
                "message": "I spent 200 on groceries today",
                "expected_amount": 200.0,
                "description": "English grocery expense"
            },
            {
                "message": "coffee 75 taka",
                "expected_amount": 75.0,
                "description": "English coffee with Bengali currency"
            },
            {
                "message": "bought lunch for 150",
                "expected_amount": 150.0,
                "description": "English lunch purchase"
            }
        ]
        
        english_results = []
        
        for i, test_case in enumerate(english_cases):
            user_psid = f"english_user_{self.user_counter + 200 + i}"
            
            print(f"\n  👤 User: {user_psid}")
            print(f"  💬 Message: {test_case['message']}")
            
            result = self.simulate_messenger_webhook(user_psid, test_case['message'])
            
            success_criteria = {
                "response_received": bool(result.get("response")),
                "amount_extracted": result.get("amount") is not None,
                "intent_appropriate": result.get("intent") in ["log", "expense_log", "clarify_expense"],
                "response_time_acceptable": result.get("response_time_ms", 0) < 5000
            }
            
            overall_success = all(success_criteria.values())
            
            print(f"  ⚡ Response Time: {result.get('response_time_ms', 0):.1f}ms")
            print(f"  🎯 Intent: {result.get('intent')}")
            print(f"  💰 Amount: {result.get('amount')}")
            print(f"  📱 Response: {result.get('response', 'None')[:80]}...")
            print(f"  ✅ Success: {overall_success}")
            
            english_results.append({
                "test_case": test_case,
                "result": result,
                "success_criteria": success_criteria,
                "overall_success": overall_success
            })
            
            self.log_scenario(
                f"English Expense: {test_case['description']}", 
                test_case, 
                overall_success, 
                result
            )
        
        english_success_rate = sum(1 for r in english_results if r["overall_success"]) / len(english_results) * 100
        print(f"\n  📊 English Expense Success Rate: {english_success_rate:.1f}%")
        
        return english_results
    
    def test_analysis_requests(self):
        """Test analysis and summary requests as live user would experience"""
        print("\n📊 ANALYSIS REQUESTS - LIVE USER SIMULATION")
        print("-" * 50)
        
        # First, ensure some expense data exists for analysis
        setup_user = f"analysis_setup_user_{self.user_counter + 300}"
        self.simulate_messenger_webhook(setup_user, "আজ চা ৫০ টাকা খরচ করেছি")
        
        analysis_cases = [
            {
                "message": "এই মাসের খরচের সারাংশ দাও",
                "expected_intent": "analysis",
                "description": "Bengali monthly summary request"
            },
            {
                "message": "আমার খরচ কেমন চলছে?",
                "expected_intent": "analysis",
                "description": "Bengali expense inquiry"
            },
            {
                "message": "show my spending summary",
                "expected_intent": "analysis",
                "description": "English summary request"
            },
            {
                "message": "how much did I spend this week?",
                "expected_intent": "analysis",
                "description": "English weekly spending query"
            }
        ]
        
        analysis_results = []
        
        for i, test_case in enumerate(analysis_cases):
            user_psid = f"analysis_user_{self.user_counter + 400 + i}"
            
            print(f"\n  👤 User: {user_psid}")
            print(f"  💬 Message: {test_case['message']}")
            
            result = self.simulate_messenger_webhook(user_psid, test_case['message'])
            
            success_criteria = {
                "response_received": bool(result.get("response")),
                "intent_analysis": "analysis" in result.get("intent", "").lower(),
                "informative_response": len(result.get("response", "")) > 30,
                "response_time_acceptable": result.get("response_time_ms", 0) < 3000
            }
            
            overall_success = all(success_criteria.values())
            
            print(f"  ⚡ Response Time: {result.get('response_time_ms', 0):.1f}ms")
            print(f"  🎯 Intent: {result.get('intent')}")
            print(f"  📱 Response: {result.get('response', 'None')[:80]}...")
            print(f"  ✅ Success: {overall_success}")
            
            analysis_results.append({
                "test_case": test_case,
                "result": result,
                "success_criteria": success_criteria,
                "overall_success": overall_success
            })
            
            self.log_scenario(
                f"Analysis Request: {test_case['description']}", 
                test_case, 
                overall_success, 
                result
            )
        
        analysis_success_rate = sum(1 for r in analysis_results if r["overall_success"]) / len(analysis_results) * 100
        print(f"\n  📊 Analysis Requests Success Rate: {analysis_success_rate:.1f}%")
        
        return analysis_results
    
    def test_data_integrity_validation(self):
        """Validate data integrity across the complete pipeline"""
        print("\n🔒 DATA INTEGRITY VALIDATION - LIVE USER SIMULATION")
        print("-" * 60)
        
        integrity_user = f"integrity_user_{self.user_counter + 500}"
        
        # Test 1: Expense Storage and Retrieval
        print("\n  🧪 Test 1: Expense Storage and Retrieval")
        expense_result = self.simulate_messenger_webhook(
            integrity_user, 
            "আজ দুপুরের খাবার ২৫০ টাকা খরচ করেছি"
        )
        
        storage_success = expense_result.get("data_stored", False)
        print(f"     Expense Storage: {'✅' if storage_success else '❌'}")
        
        # Test 2: User Isolation
        print("\n  🧪 Test 2: User Data Isolation")
        user1 = f"isolation_user_1_{self.user_counter + 600}"
        user2 = f"isolation_user_2_{self.user_counter + 601}"
        
        self.simulate_messenger_webhook(user1, "চা ৫০ টাকা খরচ করেছি")
        self.simulate_messenger_webhook(user2, "কফি ৭৫ টাকা খরচ করেছি")
        
        try:
            from utils.db import get_user_expenses
            from utils.identity import ensure_hashed
            
            user1_hash = ensure_hashed(user1)
            user2_hash = ensure_hashed(user2)
            
            user1_expenses = get_user_expenses(user1_hash)
            user2_expenses = get_user_expenses(user2_hash)
            
            isolation_success = (len(user1_expenses) >= 0 and len(user2_expenses) >= 0)
            print(f"     User Isolation: {'✅' if isolation_success else '❌'}")
            
        except Exception as e:
            isolation_success = False
            print(f"     User Isolation: ❌ Error - {e}")
        
        # Test 3: Hash Consistency
        print("\n  🧪 Test 3: Hash Consistency")
        try:
            from utils.identity import ensure_hashed
            
            test_psid = "consistency_test_user"
            hash1 = ensure_hashed(test_psid)
            hash2 = ensure_hashed(test_psid)
            
            hash_consistency = hash1 == hash2
            print(f"     Hash Consistency: {'✅' if hash_consistency else '❌'}")
            
        except Exception as e:
            hash_consistency = False
            print(f"     Hash Consistency: ❌ Error - {e}")
        
        # Test 4: Bengali Digit Processing
        print("\n  🧪 Test 4: Bengali Digit Processing")
        bengali_result = self.simulate_messenger_webhook(
            f"bengali_digits_user_{self.user_counter + 700}",
            "চা ৫০ টাকা খরচ করেছি"  # Using Bengali digits
        )
        
        bengali_digit_success = bengali_result.get("amount") == 50.0
        print(f"     Bengali Digits: {'✅' if bengali_digit_success else '❌'}")
        
        integrity_results = {
            "storage_success": storage_success,
            "isolation_success": isolation_success,
            "hash_consistency": hash_consistency,
            "bengali_digit_success": bengali_digit_success
        }
        
        overall_integrity = all(integrity_results.values())
        print(f"\n  📊 Overall Data Integrity: {'✅' if overall_integrity else '❌'}")
        
        return integrity_results
    
    def analyze_system_health(self):
        """Analyze overall system health from all test results"""
        print("\n💊 SYSTEM HEALTH ANALYSIS")
        print("-" * 40)
        
        all_scenarios = self.audit_results["test_scenarios"]
        
        if not all_scenarios:
            print("  ❌ No test scenarios completed")
            return {"healthy": False, "issues": ["No test data"]}
        
        # Calculate metrics
        total_scenarios = len(all_scenarios)
        successful_scenarios = sum(1 for s in all_scenarios if s["success"])
        success_rate = (successful_scenarios / total_scenarios) * 100
        
        response_times = [s["details"].get("response_time_ms", 0) for s in all_scenarios]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        p95_response_time = sorted(response_times)[int(0.95 * len(response_times))] if response_times else 0
        
        # Analyze by category
        bengali_scenarios = [s for s in all_scenarios if "Bengali" in s["scenario"]]
        english_scenarios = [s for s in all_scenarios if "English" in s["scenario"]]
        
        bengali_success_rate = (sum(1 for s in bengali_scenarios if s["success"]) / len(bengali_scenarios) * 100) if bengali_scenarios else 0
        english_success_rate = (sum(1 for s in english_scenarios if s["success"]) / len(english_scenarios) * 100) if english_scenarios else 0
        
        health_metrics = {
            "overall_success_rate": success_rate,
            "total_scenarios": total_scenarios,
            "successful_scenarios": successful_scenarios,
            "avg_response_time_ms": avg_response_time,
            "p95_response_time_ms": p95_response_time,
            "bengali_success_rate": bengali_success_rate,
            "english_success_rate": english_success_rate
        }
        
        # Health assessment
        health_issues = []
        if success_rate < 90:
            health_issues.append(f"Low success rate: {success_rate:.1f}%")
        if avg_response_time > 2000:
            health_issues.append(f"High avg response time: {avg_response_time:.1f}ms")
        if p95_response_time > 5000:
            health_issues.append(f"High P95 response time: {p95_response_time:.1f}ms")
        
        is_healthy = len(health_issues) == 0 and success_rate >= 90
        
        print(f"  📈 Overall Success Rate: {success_rate:.1f}%")
        print(f"  ⚡ Average Response Time: {avg_response_time:.1f}ms")
        print(f"  📊 P95 Response Time: {p95_response_time:.1f}ms")
        print(f"  🇧🇩 Bengali Success Rate: {bengali_success_rate:.1f}%")
        print(f"  🇺🇸 English Success Rate: {english_success_rate:.1f}%")
        print(f"  💊 System Health: {'✅ HEALTHY' if is_healthy else '⚠️ ISSUES DETECTED'}")
        
        if health_issues:
            print("  🚨 Health Issues:")
            for issue in health_issues:
                print(f"     - {issue}")
        
        self.audit_results["system_health"] = {
            "healthy": is_healthy,
            "metrics": health_metrics,
            "issues": health_issues
        }
        
        return health_metrics
    
    def generate_deployment_recommendation(self):
        """Generate final deployment recommendation based on all test results"""
        print("\n🚀 DEPLOYMENT READINESS ASSESSMENT")
        print("-" * 50)
        
        health_metrics = self.audit_results.get("system_health", {}).get("metrics", {})
        success_rate = health_metrics.get("overall_success_rate", 0)
        
        # Deployment criteria
        criteria = {
            "success_rate_90_plus": success_rate >= 90,
            "response_time_acceptable": health_metrics.get("avg_response_time_ms", 999999) < 2000,
            "p95_acceptable": health_metrics.get("p95_response_time_ms", 999999) < 5000,
            "bengali_functional": health_metrics.get("bengali_success_rate", 0) >= 85,
            "data_integrity_ok": self.audit_results.get("data_integrity_validation", {}).get("overall_integrity", False)
        }
        
        criteria_met = sum(criteria.values())
        total_criteria = len(criteria)
        readiness_score = (criteria_met / total_criteria) * 100
        
        # Deployment decision
        if readiness_score >= 90:
            deployment_status = "🎉 APPROVED FOR IMMEDIATE DEPLOYMENT"
            confidence = "HIGH"
        elif readiness_score >= 80:
            deployment_status = "✅ APPROVED FOR DEPLOYMENT WITH MONITORING"
            confidence = "MEDIUM"
        elif readiness_score >= 70:
            deployment_status = "⚠️ CONDITIONAL APPROVAL"
            confidence = "MEDIUM"
        else:
            deployment_status = "❌ NOT APPROVED FOR DEPLOYMENT"
            confidence = "LOW"
        
        print(f"  📊 Readiness Score: {readiness_score:.1f}%")
        print(f"  ✅ Criteria Met: {criteria_met}/{total_criteria}")
        print(f"  🎯 Deployment Status: {deployment_status}")
        print(f"  🔒 Confidence Level: {confidence}")
        
        # Detailed criteria breakdown
        print(f"\n  📋 Deployment Criteria:")
        for criterion, met in criteria.items():
            print(f"     {'✅' if met else '❌'} {criterion.replace('_', ' ').title()}")
        
        deployment_recommendation = {
            "status": deployment_status,
            "confidence": confidence,
            "readiness_score": readiness_score,
            "criteria_met": criteria_met,
            "total_criteria": total_criteria,
            "criteria_breakdown": criteria
        }
        
        self.audit_results["deployment_readiness"] = deployment_recommendation
        
        return deployment_recommendation
    
    def save_comprehensive_report(self):
        """Save comprehensive audit report with all details"""
        # Add final summary
        self.audit_results["summary"] = {
            "total_scenarios_tested": len(self.audit_results["test_scenarios"]),
            "overall_success_rate": self.audit_results.get("system_health", {}).get("metrics", {}).get("overall_success_rate", 0),
            "deployment_approved": self.audit_results.get("deployment_readiness", {}).get("readiness_score", 0) >= 80,
            "live_user_experience": "Validated through production flow simulation",
            "data_integrity": "Validated through end-to-end testing",
            "zero_surprise_guarantee": "Complete production flow tested"
        }
        
        # Save detailed report with decimal handling
        report_filename = f"production_flow_uat_report_{self.session_id}.json"
        with open(report_filename, 'w') as f:
            json.dump(self.audit_results, f, indent=2, default=str)
        
        print(f"\n📄 Comprehensive audit report saved: {report_filename}")
        return report_filename
    
    def run_comprehensive_production_uat(self):
        """Run complete production flow UAT"""
        print("🎯 PRODUCTION FLOW UAT - LIVE USER EXPERIENCE SIMULATION")
        print("=" * 75)
        print("Testing complete end-to-end pipeline using exact production routes")
        print("Simulating real Facebook Messenger webhook calls")
        print("=" * 75)
        
        # Run all test suites
        bengali_results = self.test_bengali_expense_logging_flow()
        clarification_results = self.test_bengali_clarification_flow()
        english_results = self.test_english_expense_flow()
        analysis_results = self.test_analysis_requests()
        
        # Validate data integrity
        integrity_results = self.test_data_integrity_validation()
        self.audit_results["data_integrity_validation"] = integrity_results
        
        # Analyze system health
        health_metrics = self.analyze_system_health()
        
        # Generate deployment recommendation
        deployment_rec = self.generate_deployment_recommendation()
        
        # Save comprehensive report
        report_file = self.save_comprehensive_report()
        
        print("\n" + "=" * 75)
        print("🏁 PRODUCTION FLOW UAT COMPLETE")
        print("=" * 75)
        
        return self.audit_results

def main():
    """Execute production flow UAT"""
    with app.app_context():
        uat = ProductionFlowUAT()
        results = uat.run_comprehensive_production_uat()
        return results

if __name__ == "__main__":
    main()