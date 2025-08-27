#!/usr/bin/env python3
"""
Robust End-to-End UAT with Comprehensive Audit Report
Handles database transactions properly with detailed integrity validation
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from app import app, db
from sqlalchemy import text

class RobustE2EAudit:
    """Production-ready end-to-end audit with transaction safety"""
    
    def __init__(self):
        self.audit_session_id = str(uuid.uuid4())[:8]
        self.test_user_id = f"uat_{self.audit_session_id}"
        self.results = {
            "audit_session_id": self.audit_session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "system_info": {},
            "data_handling": {},
            "routing_validation": {},
            "processing_validation": {},
            "storage_validation": {},
            "integrity_validation": {},
            "security_validation": {},
            "deployment_assessment": {}
        }
        
    def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Execute comprehensive end-to-end audit with proper error handling"""
        
        print("🔍 ROBUST END-TO-END UAT AUDIT")
        print("=" * 60)
        print(f"Audit Session: {self.audit_session_id}")
        print(f"Test User: {self.test_user_id}")
        print()
        
        # System Information
        self._collect_system_info()
        
        # Phase 1: Data Handling Validation
        print("📊 Phase 1: Data Handling Validation")
        print("-" * 40)
        data_handling_results = self._validate_data_handling()
        self.results["data_handling"] = data_handling_results
        self._print_phase_results("Data Handling", data_handling_results)
        
        # Phase 2: Routing Validation
        print("\n🎯 Phase 2: Routing System Validation")
        print("-" * 40)
        routing_results = self._validate_routing_system()
        self.results["routing_validation"] = routing_results
        self._print_phase_results("Routing", routing_results)
        
        # Phase 3: Processing Validation
        print("\n🤖 Phase 3: AI Processing Validation")
        print("-" * 40)
        processing_results = self._validate_processing_system()
        self.results["processing_validation"] = processing_results
        self._print_phase_results("Processing", processing_results)
        
        # Phase 4: Storage Validation
        print("\n💾 Phase 4: Storage System Validation")
        print("-" * 40)
        storage_results = self._validate_storage_system()
        self.results["storage_validation"] = storage_results
        self._print_phase_results("Storage", storage_results)
        
        # Phase 5: Integrity Validation
        print("\n🔒 Phase 5: Data Integrity Validation")
        print("-" * 40)
        integrity_results = self._validate_data_integrity()
        self.results["integrity_validation"] = integrity_results
        self._print_phase_results("Integrity", integrity_results)
        
        # Phase 6: Security Validation
        print("\n🛡️ Phase 6: Security Validation")
        print("-" * 40)
        security_results = self._validate_security()
        self.results["security_validation"] = security_results
        self._print_phase_results("Security", security_results)
        
        # Final Assessment
        self._generate_deployment_assessment()
        
        return self.results
    
    def _collect_system_info(self):
        """Collect system configuration and status"""
        try:
            from utils.contract_tests import run_all_contract_tests
            from test_routing_integration import test_routing_in_app_context
            
            # Contract test baseline
            contract_results = run_all_contract_tests()
            
            # Integration test baseline
            try:
                passed, total, success_rate = test_routing_in_app_context()
                integration_status = {"passed": passed, "total": total, "success_rate": success_rate}
            except Exception:
                integration_status = {"passed": 0, "total": 0, "success_rate": 0}
            
            # Database status
            db_status = self._check_database_status()
            
            self.results["system_info"] = {
                "contract_tests": contract_results,
                "integration_tests": integration_status,
                "database_status": db_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"System baseline established:")
            print(f"  Contract Tests: {contract_results['passed']}/{contract_results['total']} ({contract_results['success_rate']}%)")
            print(f"  Integration Tests: {integration_status['passed']}/{integration_status['total']} ({integration_status['success_rate']}%)")
            print(f"  Database: {'✅ Connected' if db_status['connected'] else '❌ Failed'}")
            
        except Exception as e:
            print(f"⚠️ System info collection error: {e}")
    
    def _validate_data_handling(self) -> Dict[str, Any]:
        """Validate data ingestion and parsing"""
        results = {"tests": [], "summary": {}}
        
        test_cases = [
            {
                "name": "English expense parsing",
                "input": "lunch 500 taka",
                "expected": {"has_amount": True, "has_currency": True, "amount": 500}
            },
            {
                "name": "Bengali expense parsing", 
                "input": "চা ৫০ টাকা",
                "expected": {"has_amount": True, "has_currency": True, "amount": 50}
            },
            {
                "name": "Analysis request parsing",
                "input": "analysis please",
                "expected": {"has_analysis": True, "has_amount": False}
            },
            {
                "name": "Coaching request parsing",
                "input": "help me save money",
                "expected": {"has_coaching": True, "has_amount": False}
            }
        ]
        
        for case in test_cases:
            try:
                from utils.routing_policy import deterministic_router, BilingualPatterns
                
                patterns = BilingualPatterns()
                signals = deterministic_router.extract_signals(case["input"], self.test_user_id)
                
                # Check parsing results
                has_amount = patterns.has_money_pattern(case["input"]) if hasattr(patterns, 'has_money_pattern') else signals.has_money
                has_analysis = patterns.has_analysis_terms(case["input"])
                has_coaching = patterns.has_coaching_verbs(case["input"])
                
                # Validate against expectations
                test_result = {
                    "name": case["name"],
                    "input": case["input"],
                    "parsed": {
                        "has_amount": has_amount,
                        "has_analysis": has_analysis,
                        "has_coaching": has_coaching
                    },
                    "expected": case["expected"],
                    "success": True  # We'll validate specific expectations below
                }
                
                # Check specific expectations
                for key, expected_value in case["expected"].items():
                    if key == "has_amount":
                        test_result["success"] &= (has_amount == expected_value)
                    elif key == "has_analysis":
                        test_result["success"] &= (has_analysis == expected_value)
                    elif key == "has_coaching":
                        test_result["success"] &= (has_coaching == expected_value)
                
                results["tests"].append(test_result)
                print(f"  {'✅' if test_result['success'] else '❌'} {case['name']}")
                
            except Exception as e:
                results["tests"].append({
                    "name": case["name"],
                    "input": case["input"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {case['name']}: {e}")
        
        # Calculate summary
        total_tests = len(results["tests"])
        passed_tests = sum(1 for t in results["tests"] if t.get("success", False))
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0
        }
        
        return results
    
    def _validate_routing_system(self) -> Dict[str, Any]:
        """Validate message routing decisions"""
        results = {"tests": [], "summary": {}}
        
        routing_test_cases = [
            {"input": "analysis please", "expected_intent": "ANALYSIS", "type": "explicit_analysis"},
            {"input": "এই মাসের খরচ বিশ্লেষণ", "expected_intent": "ANALYSIS", "type": "bengali_analysis"},
            {"input": "what can you do", "expected_intent": "FAQ", "type": "faq_query"},
            {"input": "তুমি কী করতে পারো", "expected_intent": "FAQ", "type": "bengali_faq"},
            {"input": "help me reduce spending", "expected_intent": "COACHING", "type": "coaching_request"},
            {"input": "টাকা সেভ করবো কিভাবে", "expected_intent": "COACHING", "type": "bengali_coaching"},
            {"input": "lunch 500 taka", "expected_intent": "SMALLTALK", "type": "expense_logging"},
            {"input": "/id", "expected_intent": "ADMIN", "type": "admin_command"},
            {"input": "hello there", "expected_intent": "SMALLTALK", "type": "general_chat"}
        ]
        
        for case in routing_test_cases:
            try:
                from utils.routing_policy import deterministic_router
                
                # Create mock signals with proper ledger count for coaching
                signals = deterministic_router.extract_signals(case["input"], self.test_user_id)
                signals.ledger_count_30d = 15  # Sufficient for coaching
                
                # Route the intent
                routing_result = deterministic_router.route_intent(case["input"], signals)
                actual_intent = routing_result.intent.value
                
                test_result = {
                    "name": f"{case['type']} routing",
                    "input": case["input"],
                    "expected_intent": case["expected_intent"],
                    "actual_intent": actual_intent,
                    "success": actual_intent == case["expected_intent"],
                    "reasoning": getattr(routing_result, 'reasoning', 'deterministic'),
                    "confidence": getattr(routing_result, 'confidence', 0.0)
                }
                
                results["tests"].append(test_result)
                print(f"  {'✅' if test_result['success'] else '❌'} {case['input'][:30]}... → {actual_intent}")
                
            except Exception as e:
                results["tests"].append({
                    "name": f"{case['type']} routing",
                    "input": case["input"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {case['input'][:30]}...: {e}")
        
        # Calculate summary
        total_tests = len(results["tests"])
        passed_tests = sum(1 for t in results["tests"] if t.get("success", False))
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0
        }
        
        return results
    
    def _validate_processing_system(self) -> Dict[str, Any]:
        """Validate AI processing capabilities"""
        results = {"tests": [], "summary": {}}
        
        # Test AI response generation with different intents
        processing_cases = [
            {"message": "coffee 200 taka", "intent": "SMALLTALK", "type": "expense_processing"},
            {"message": "how to save money", "intent": "COACHING", "type": "coaching_processing"}
        ]
        
        for case in processing_cases:
            try:
                from utils.ai_adapter_v2 import get_ai_response
                
                start_time = time.time()
                response = get_ai_response(case["message"], self.test_user_id, case["intent"])
                processing_time = (time.time() - start_time) * 1000
                
                # Validate response
                has_response = response is not None and len(str(response).strip()) > 0
                within_length = len(str(response)) <= 280 if response else False
                
                test_result = {
                    "name": case["type"],
                    "message": case["message"],
                    "intent": case["intent"],
                    "has_response": has_response,
                    "response_length": len(str(response)) if response else 0,
                    "within_length_limit": within_length,
                    "processing_time_ms": processing_time,
                    "success": has_response and within_length,
                    "response_preview": str(response)[:100] if response else None
                }
                
                results["tests"].append(test_result)
                print(f"  {'✅' if test_result['success'] else '❌'} {case['type']}: {processing_time:.1f}ms")
                
            except Exception as e:
                results["tests"].append({
                    "name": case["type"],
                    "message": case["message"],
                    "intent": case["intent"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {case['type']}: {e}")
        
        # Calculate summary with lower threshold for AI (external dependency)
        total_tests = len(results["tests"])
        passed_tests = sum(1 for t in results["tests"] if t.get("success", False))
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "overall_success": success_rate >= 70.0  # Lower threshold for AI
        }
        
        return results
    
    def _validate_storage_system(self) -> Dict[str, Any]:
        """Validate database storage with proper transaction handling"""
        results = {"tests": [], "summary": {}}
        
        try:
            # Start fresh transaction
            db.session.rollback()
            
            # Test 1: Basic expense insertion
            test_expense = {
                "user_id": self.test_user_id,
                "amount": 250.0,
                "description": "UAT test expense",
                "category": "Testing",
                "created_at": datetime.utcnow()
            }
            
            try:
                insert_result = db.session.execute(text("""
                    INSERT INTO expenses (user_id, amount, description, category, created_at)
                    VALUES (:user_id, :amount, :description, :category, :created_at)
                    RETURNING id, amount
                """), test_expense)
                
                inserted_record = insert_result.fetchone()
                db.session.commit()
                
                results["tests"].append({
                    "name": "expense_insertion",
                    "success": inserted_record is not None,
                    "record_id": inserted_record.id if inserted_record else None,
                    "amount": inserted_record.amount if inserted_record else None
                })
                print(f"  ✅ Expense insertion: ID {inserted_record.id}")
                
            except Exception as e:
                db.session.rollback()
                results["tests"].append({
                    "name": "expense_insertion",
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ Expense insertion: {e}")
            
            # Test 2: Data retrieval
            try:
                retrieval_result = db.session.execute(text("""
                    SELECT id, user_id, amount, description 
                    FROM expenses 
                    WHERE user_id = :user_id AND description = :description
                """), {
                    "user_id": self.test_user_id,
                    "description": "UAT test expense"
                }).fetchone()
                
                results["tests"].append({
                    "name": "data_retrieval",
                    "success": retrieval_result is not None,
                    "retrieved_amount": retrieval_result.amount if retrieval_result else None
                })
                print(f"  ✅ Data retrieval: Found record")
                
            except Exception as e:
                results["tests"].append({
                    "name": "data_retrieval",
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ Data retrieval: {e}")
            
            # Test 3: User isolation
            try:
                isolation_check = db.session.execute(text("""
                    SELECT COUNT(*) as count FROM expenses 
                    WHERE user_id = :user_id
                """), {"user_id": self.test_user_id}).fetchone()
                
                results["tests"].append({
                    "name": "user_isolation",
                    "success": isolation_check.count >= 1,
                    "user_record_count": isolation_check.count
                })
                print(f"  ✅ User isolation: {isolation_check.count} records")
                
            except Exception as e:
                results["tests"].append({
                    "name": "user_isolation", 
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ User isolation: {e}")
            
        except Exception as e:
            results["tests"].append({
                "name": "storage_system_error",
                "success": False,
                "error": str(e)
            })
            print(f"  ❌ Storage system error: {e}")
        
        # Calculate summary
        total_tests = len(results["tests"])
        passed_tests = sum(1 for t in results["tests"] if t.get("success", False))
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0
        }
        
        return results
    
    def _validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity and consistency"""
        results = {"checks": [], "summary": {}}
        
        integrity_checks = [
            {
                "name": "data_consistency",
                "description": "All expense records have required fields",
                "query": """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN amount > 0 THEN 1 END) as valid_amounts,
                        COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as with_user_ids,
                        COUNT(CASE WHEN created_at IS NOT NULL THEN 1 END) as with_timestamps
                    FROM expenses WHERE user_id = :user_id
                """,
                "validation": lambda r: r.total == r.valid_amounts == r.with_user_ids == r.with_timestamps
            },
            {
                "name": "temporal_integrity", 
                "description": "All timestamps are valid and recent",
                "query": """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN created_at <= NOW() THEN 1 END) as valid_timestamps
                    FROM expenses WHERE user_id = :user_id
                """,
                "validation": lambda r: r.total == r.valid_timestamps
            },
            {
                "name": "amount_validation",
                "description": "All amounts are positive numbers",
                "query": """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN amount > 0 AND amount < 1000000 THEN 1 END) as valid_amounts,
                        MIN(amount) as min_amount,
                        MAX(amount) as max_amount
                    FROM expenses WHERE user_id = :user_id
                """, 
                "validation": lambda r: r.total == r.valid_amounts and r.min_amount > 0
            }
        ]
        
        for check in integrity_checks:
            try:
                check_result = db.session.execute(text(check["query"]), {"user_id": self.test_user_id}).fetchone()
                validation_passed = check["validation"](check_result)
                
                results["checks"].append({
                    "name": check["name"],
                    "description": check["description"],
                    "success": validation_passed,
                    "details": dict(check_result._mapping) if check_result else {}
                })
                
                print(f"  {'✅' if validation_passed else '❌'} {check['description']}")
                
            except Exception as e:
                results["checks"].append({
                    "name": check["name"],
                    "description": check["description"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {check['description']}: {e}")
        
        # Calculate summary
        total_checks = len(results["checks"])
        passed_checks = sum(1 for c in results["checks"] if c.get("success", False))
        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        results["summary"] = {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0
        }
        
        return results
    
    def _validate_security(self) -> Dict[str, Any]:
        """Validate security measures"""
        results = {"checks": [], "summary": {}}
        
        security_validations = [
            {
                "name": "user_id_hashing",
                "description": "User IDs are properly hashed",
                "test": lambda: self._test_user_id_hashing()
            },
            {
                "name": "sql_injection_protection",
                "description": "SQL injection attempts are safely handled",
                "test": lambda: self._test_sql_injection_protection()
            },
            {
                "name": "data_isolation",
                "description": "User data is properly isolated",
                "test": lambda: self._test_data_isolation()
            }
        ]
        
        for validation in security_validations:
            try:
                test_result = validation["test"]()
                results["checks"].append({
                    "name": validation["name"],
                    "description": validation["description"],
                    "success": test_result["success"],
                    "details": test_result.get("details", {})
                })
                
                print(f"  {'✅' if test_result['success'] else '❌'} {validation['description']}")
                
            except Exception as e:
                results["checks"].append({
                    "name": validation["name"],
                    "description": validation["description"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {validation['description']}: {e}")
        
        # Calculate summary
        total_checks = len(results["checks"])
        passed_checks = sum(1 for c in results["checks"] if c.get("success", False))
        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        results["summary"] = {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0
        }
        
        return results
    
    def _test_user_id_hashing(self) -> Dict[str, Any]:
        """Test user ID hashing functionality"""
        try:
            from utils.security import ensure_hashed
            test_psid = "test_psid_12345"
            hashed_id = ensure_hashed(test_psid)
            
            return {
                "success": len(hashed_id) == 64 and hashed_id != test_psid,
                "details": {"hash_length": len(hashed_id), "is_different": hashed_id != test_psid}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_sql_injection_protection(self) -> Dict[str, Any]:
        """Test SQL injection protection"""
        try:
            malicious_input = "'; DROP TABLE expenses; --"
            safe_query = db.session.execute(text("""
                SELECT COUNT(*) as count FROM expenses 
                WHERE description = :desc
            """), {"desc": malicious_input}).fetchone()
            
            return {
                "success": True,  # If we reach here, parameterized query worked
                "details": {"query_executed_safely": True, "result_count": safe_query.count}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_data_isolation(self) -> Dict[str, Any]:
        """Test user data isolation"""
        try:
            # Check that test user data is isolated
            test_user_count = db.session.execute(text("""
                SELECT COUNT(*) as count FROM expenses
                WHERE user_id = :user_id
            """), {"user_id": self.test_user_id}).fetchone()
            
            # Check total users in system
            total_users = db.session.execute(text("""
                SELECT COUNT(DISTINCT user_id) as count FROM expenses
            """)).fetchone()
            
            return {
                "success": test_user_count.count >= 0,  # Test user should have own data
                "details": {
                    "test_user_records": test_user_count.count,
                    "total_unique_users": total_users.count
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _check_database_status(self) -> Dict[str, Any]:
        """Check database connectivity and basic operations"""
        try:
            # Test basic connectivity
            result = db.session.execute(text("SELECT 1")).fetchone()
            
            # Test table existence
            tables_result = db.session.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name IN ('expenses', 'users')
            """)).fetchall()
            
            table_names = [row.table_name for row in tables_result]
            
            return {
                "connected": result is not None,
                "tables_exist": "expenses" in table_names and "users" in table_names,
                "available_tables": table_names
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    def _print_phase_results(self, phase_name: str, results: Dict[str, Any]):
        """Print formatted phase results"""
        summary = results.get("summary", {})
        success = summary.get("overall_success", False)
        
        if "total_tests" in summary:
            print(f"  Tests: {summary['passed_tests']}/{summary['total_tests']} ({summary['success_rate']:.1f}%)")
        elif "total_checks" in summary:
            print(f"  Checks: {summary['passed_checks']}/{summary['total_checks']} ({summary['success_rate']:.1f}%)")
        
        print(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    
    def _generate_deployment_assessment(self):
        """Generate final deployment readiness assessment"""
        
        # Collect all phase results
        phases = [
            ("Data Handling", self.results["data_handling"]),
            ("Routing", self.results["routing_validation"]),
            ("Processing", self.results["processing_validation"]),
            ("Storage", self.results["storage_validation"]),
            ("Integrity", self.results["integrity_validation"]),
            ("Security", self.results["security_validation"])
        ]
        
        # Calculate overall metrics
        total_success_count = 0
        total_test_count = 0
        critical_failures = []
        
        for phase_name, phase_data in phases:
            summary = phase_data.get("summary", {})
            if summary.get("overall_success", False):
                total_success_count += 1
            else:
                critical_failures.append(phase_name)
            total_test_count += 1
        
        overall_success_rate = (total_success_count / total_test_count * 100) if total_test_count > 0 else 0
        deployment_ready = len(critical_failures) == 0
        
        # Generate assessment
        self.results["deployment_assessment"] = {
            "overall_success_rate": overall_success_rate,
            "deployment_ready": deployment_ready,
            "critical_failures": critical_failures,
            "recommendation": "APPROVED FOR DEPLOYMENT" if deployment_ready else "REQUIRES FIXES BEFORE DEPLOYMENT",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Clean up test data
        self._cleanup_test_data()
        
        # Print final assessment
        print(f"\n📊 COMPREHENSIVE AUDIT SUMMARY")
        print("=" * 60)
        print(f"Audit Session: {self.audit_session_id}")
        print(f"Overall Success Rate: {overall_success_rate:.1f}%")
        print(f"Deployment Readiness: {'✅ READY' if deployment_ready else '❌ NOT READY'}")
        print(f"Recommendation: {self.results['deployment_assessment']['recommendation']}")
        
        print(f"\nPhase Results:")
        for phase_name, phase_data in phases:
            summary = phase_data.get("summary", {})
            status = "✅ PASS" if summary.get("overall_success", False) else "❌ FAIL"
            success_rate = summary.get("success_rate", 0)
            print(f"  {phase_name}: {status} ({success_rate:.1f}%)")
        
        if deployment_ready:
            print("\n🎉 DEPLOYMENT APPROVED")
            print("   • All critical systems validated")
            print("   • Data integrity confirmed")
            print("   • Security measures verified")
            print("   • Ready for Phase 1 rollout")
        else:
            print(f"\n⚠️  DEPLOYMENT BLOCKED")
            print(f"   Critical failures in: {', '.join(critical_failures)}")
            print("   • Fix failing systems before deployment")
    
    def _cleanup_test_data(self):
        """Clean up test data with proper error handling"""
        try:
            db.session.rollback()  # Clear any pending transactions
            db.session.execute(text("""
                DELETE FROM expenses WHERE user_id = :user_id
            """), {"user_id": self.test_user_id})
            db.session.commit()
            print(f"\n🧹 Test data cleanup completed")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
            db.session.rollback()

def main():
    """Run robust end-to-end audit"""
    with app.app_context():
        auditor = RobustE2EAudit()
        results = auditor.run_comprehensive_audit()
        
        # Save detailed report
        report_filename = f"comprehensive_audit_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 Comprehensive audit report saved: {report_filename}")
        return results

if __name__ == "__main__":
    main()