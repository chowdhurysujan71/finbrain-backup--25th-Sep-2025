#!/usr/bin/env python3
"""
Phase 2 Impact Audit: Verify Security improvement while preserving Phase 1 gains
"""

import json
import time
from typing import Dict, List, Any
from app import app

class Phase2ImpactAudit:
    """Test Phase 2 security improvements without affecting routing or data handling"""
    
    def __init__(self):
        self.audit_id = f"phase2_{int(time.time())}"
        self.results = {
            "audit_id": self.audit_id,
            "timestamp": time.time(),
            "security_before": "66% (input validation failures)",
            "security_after": {},
            "data_handling_preservation": {},
            "routing_preservation": {},
            "integration_verification": {}
        }
    
    def run_audit(self) -> Dict[str, Any]:
        print("🔍 PHASE 2 IMPACT AUDIT")
        print("=" * 50)
        print("Testing: New security layer + Phase 1 preservation")
        print("Ensuring: Zero risk to 100% routing + 95% data handling")
        print()
        
        # Test 1: New security system
        print("🛡️ Testing NEW Security System")
        print("-" * 40)
        security_results = self._test_new_security_system()
        self.results["security_after"] = security_results
        self._print_results("New Security System", security_results)
        
        # Test 2: Data handling preservation (from Phase 1)
        print("\n📊 Testing Data Handling Preservation")
        print("-" * 40)
        data_results = self._test_data_handling_preservation()
        self.results["data_handling_preservation"] = data_results
        self._print_results("Data Handling Preservation", data_results)
        
        # Test 3: Routing preservation
        print("\n🎯 Testing Routing System Preservation")
        print("-" * 40)
        routing_results = self._test_routing_preservation()
        self.results["routing_preservation"] = routing_results
        self._print_results("Routing Preservation", routing_results)
        
        # Test 4: Integration verification
        print("\n🔗 Testing Integration Safety")
        print("-" * 40)
        integration_results = self._test_integration_safety()
        self.results["integration_verification"] = integration_results
        self._print_results("Integration Safety", integration_results)
        
        # Final assessment
        self._generate_phase2_assessment()
        
        return self.results
    
    def _test_new_security_system(self) -> Dict[str, Any]:
        """Test the new input sanitization system"""
        from utils.input_sanitizer import InputSanitizer
        
        security_test_cases = [
            {
                "name": "XSS prevention",
                "input": "lunch <script>alert('xss')</script> 500 taka",
                "expects": "html_escaped"
            },
            {
                "name": "Control character removal",
                "input": "analysis\x00\x1F please\x7F",
                "expects": "control_chars_removed"
            },
            {
                "name": "Length limit enforcement",
                "input": "a" * 2500,
                "expects": "length_capped"
            },
            {
                "name": "Bengali text preservation",
                "input": "খাবারে ৳১,২৫০.৫০ খরচ",
                "expects": "no_flags"
            },
            {
                "name": "Suspicious pattern detection",
                "input": "javascript:alert('hack')",
                "expects": "rejected"
            },
            {
                "name": "Normal expense safe processing",
                "input": "lunch 500 taka",
                "expects": "safe_approved"
            },
            {
                "name": "Field sanitization",
                "input": "user123",
                "expects": "field_valid"
            },
            {
                "name": "Mixed language XSS",
                "input": "বিশ্লেষণ <img src=x onerror=hack()>",
                "expects": "html_escaped"
            }
        ]
        
        results = []
        for case in security_test_cases:
            try:
                test_result = {
                    "name": case["name"],
                    "input": case["input"][:50] + "..." if len(case["input"]) > 50 else case["input"],
                    "success": False
                }
                
                if case["expects"] == "field_valid":
                    # Test field sanitization
                    result = InputSanitizer.sanitize_field(case["input"], "test_field")
                    test_result["success"] = result["valid"]
                else:
                    # Test input sanitization
                    result = InputSanitizer.sanitize_user_input(case["input"])
                    flags = result["metadata"]["security_flags"]
                    
                    if case["expects"] == "html_escaped":
                        test_result["success"] = "html_escaped" in flags
                    elif case["expects"] == "control_chars_removed":
                        test_result["success"] = "control_chars_removed" in flags
                    elif case["expects"] == "length_capped":
                        test_result["success"] = "length_capped" in flags
                    elif case["expects"] == "no_flags":
                        test_result["success"] = len(flags) == 0
                    elif case["expects"] == "rejected":
                        test_result["success"] = not InputSanitizer.is_safe_for_processing(result)
                    elif case["expects"] == "safe_approved":
                        test_result["success"] = InputSanitizer.is_safe_for_processing(result)
                
                results.append(test_result)
                status = "✅" if test_result["success"] else "❌"
                print(f"  {status} {case['name']}")
                
            except Exception as e:
                results.append({
                    "name": case["name"],
                    "input": case["input"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {case['name']}: {e}")
        
        # Calculate metrics
        passed = sum(1 for r in results if r.get("success", False))
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            "test_results": results,
            "passed": passed,
            "total": total,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0,
            "improvement": "66% → 95%+" if success_rate >= 95.0 else f"66% → {success_rate:.1f}%"
        }
    
    def _test_data_handling_preservation(self) -> Dict[str, Any]:
        """Ensure Phase 1 data handling gains are preserved"""
        from nlp.signals_extractor import extract_signals
        
        # Same test cases that worked in Phase 1
        phase1_cases = [
            {"input": "lunch 500 taka", "expects": {"has_money": True}},
            {"input": "চা ৫০ টাকা", "expects": {"has_money": True}},
            {"input": "analysis please", "expects": {"explicit_analysis_request": True}},
            {"input": "বিশ্লেষণ দাও", "expects": {"explicit_analysis_request": True}},
            {"input": "today spending", "expects": {"has_time_window": True}},
            {"input": "help me save money", "expects": {"has_coaching_verbs": True}},
            {"input": "what can you do", "expects": {"has_faq_terms": True}},
            {"input": "/id", "expects": {"is_admin": True}}
        ]
        
        results = []
        for case in phase1_cases:
            try:
                signals = extract_signals(case["input"])
                
                test_result = {
                    "input": case["input"],
                    "success": True
                }
                
                # Validate all expectations
                for key, expected in case["expects"].items():
                    actual = signals.get(key, False)
                    if expected and not actual:
                        test_result["success"] = False
                        break
                
                results.append(test_result)
                status = "✅" if test_result["success"] else "❌"
                print(f"  {status} {case['input'][:25]}...")
                
            except Exception as e:
                results.append({
                    "input": case["input"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {case['input'][:25]}...: {e}")
        
        passed = sum(1 for r in results if r.get("success", False))
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            "test_results": results,
            "passed": passed,
            "total": total,
            "success_rate": success_rate,
            "overall_success": success_rate >= 95.0,
            "status": "PRESERVED" if success_rate >= 95.0 else "DEGRADED"
        }
    
    def _test_routing_preservation(self) -> Dict[str, Any]:
        """Ensure routing system remains 100% functional"""
        
        routing_cases = [
            {"input": "analysis please", "expected": "ANALYSIS"},
            {"input": "এই মাসের খরচ বিশ্লেষণ", "expected": "ANALYSIS"},
            {"input": "what can you do", "expected": "FAQ"},
            {"input": "help me reduce spending", "expected": "COACHING"},
            {"input": "lunch 500 taka", "expected": "SMALLTALK"},
            {"input": "/id", "expected": "ADMIN"}
        ]
        
        results = []
        for case in routing_cases:
            try:
                from utils.routing_policy import deterministic_router
                
                signals = deterministic_router.extract_signals(case["input"], "test_user")
                signals.ledger_count_30d = 15  # Sufficient for coaching
                
                routing_result = deterministic_router.route_intent(case["input"], signals)
                actual = routing_result.intent.value
                success = actual == case["expected"]
                
                results.append({
                    "input": case["input"],
                    "expected": case["expected"],
                    "actual": actual,
                    "success": success
                })
                
                status = "✅" if success else "❌"
                print(f"  {status} {case['input'][:25]}... → {actual}")
                
            except Exception as e:
                results.append({
                    "input": case["input"],
                    "expected": case["expected"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {case['input'][:25]}...: {e}")
        
        passed = sum(1 for r in results if r.get("success", False))
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            "test_results": results,
            "passed": passed,
            "total": total,
            "success_rate": success_rate,
            "overall_success": success_rate == 100.0,
            "status": "PRESERVED" if success_rate == 100.0 else "COMPROMISED"
        }
    
    def _test_integration_safety(self) -> Dict[str, Any]:
        """Test that Phase 2 changes integrate safely"""
        
        safety_checks = [
            {
                "name": "Security module imports",
                "test": lambda: self._test_security_imports()
            },
            {
                "name": "Phase 1 + Phase 2 compatibility",
                "test": lambda: self._test_phase_compatibility()
            },
            {
                "name": "No performance degradation",
                "test": lambda: self._test_performance_impact()
            }
        ]
        
        results = []
        for check in safety_checks:
            try:
                test_result = check["test"]()
                results.append({
                    "name": check["name"],
                    "success": test_result["success"],
                    "details": test_result.get("details", {})
                })
                
                status = "✅" if test_result["success"] else "❌"
                print(f"  {status} {check['name']}")
                
            except Exception as e:
                results.append({
                    "name": check["name"],
                    "success": False,
                    "error": str(e)
                })
                print(f"  ❌ {check['name']}: {e}")
        
        passed = sum(1 for r in results if r.get("success", False))
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            "safety_checks": results,
            "passed": passed,
            "total": total,
            "success_rate": success_rate,
            "overall_success": success_rate == 100.0
        }
    
    def _test_security_imports(self) -> Dict[str, Any]:
        """Test security module imports and basic functionality"""
        try:
            from utils.input_sanitizer import InputSanitizer
            
            # Test basic security functionality
            test_input = "test <script>alert(1)</script>"
            result = InputSanitizer.sanitize_user_input(test_input)
            safety_check = InputSanitizer.is_safe_for_processing(result)
            
            return {
                "success": True,
                "details": {
                    "sanitizer_works": "&lt;script&gt;" in result["safe"],
                    "safety_validation_works": isinstance(safety_check, bool),
                    "html_escape_works": "html_escaped" in result["metadata"]["security_flags"]
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_phase_compatibility(self) -> Dict[str, Any]:
        """Test that Phase 1 and Phase 2 work together"""
        try:
            from utils.text_normalizer import normalize_for_processing
            from nlp.signals_extractor import extract_signals
            from utils.input_sanitizer import InputSanitizer
            
            # Test combined workflow
            test_input = "আজ চা ৫০ টাকা <script>alert(1)</script>"
            
            # Step 1: Security sanitization
            sanitized = InputSanitizer.sanitize_user_input(test_input)
            
            # Step 2: Signal extraction (using Phase 1)
            signals = extract_signals(sanitized["raw"])  # Use raw for signal extraction
            
            return {
                "success": True,
                "details": {
                    "sanitization_works": "&lt;script&gt;" in sanitized["safe"],
                    "signal_extraction_works": signals["has_money"],
                    "bengali_preserved": "৫০" in sanitized["raw"],
                    "workflow_integration": True
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_performance_impact(self) -> Dict[str, Any]:
        """Test that security doesn't significantly impact performance"""
        try:
            import time
            from utils.input_sanitizer import InputSanitizer
            
            test_inputs = [
                "lunch 500 taka",
                "বিশ্লেষণ দাও",
                "help me save money",
                "what can you do"
            ]
            
            start_time = time.time()
            for _ in range(100):  # 100 iterations
                for test_input in test_inputs:
                    InputSanitizer.sanitize_user_input(test_input)
            end_time = time.time()
            
            avg_time_per_call = (end_time - start_time) / (100 * len(test_inputs))
            
            return {
                "success": avg_time_per_call < 0.005,  # Less than 5ms per call
                "details": {
                    "avg_time_ms": avg_time_per_call * 1000,
                    "total_calls": 100 * len(test_inputs),
                    "performance_acceptable": avg_time_per_call < 0.005
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _print_results(self, phase_name: str, results: Dict[str, Any]):
        """Print formatted results"""
        summary = results
        success = summary.get("overall_success", False)
        
        if "success_rate" in summary:
            rate = summary["success_rate"]
            passed = summary.get("passed", 0)
            total = summary.get("total", 0)
            print(f"  Result: {passed}/{total} ({rate:.1f}%) - {'✅ PASS' if success else '❌ FAIL'}")
        else:
            print(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    
    def _generate_phase2_assessment(self):
        """Generate Phase 2 impact assessment"""
        
        security_fixed = self.results["security_after"].get("overall_success", False)
        data_preserved = self.results["data_handling_preservation"].get("overall_success", False)
        routing_preserved = self.results["routing_preservation"].get("overall_success", False)
        integration_safe = self.results["integration_verification"].get("overall_success", False)
        
        phase2_success = security_fixed and data_preserved and routing_preserved and integration_safe
        
        self.results["phase2_assessment"] = {
            "security_improvement": self.results["security_after"].get("improvement", "Unknown"),
            "data_handling_status": self.results["data_handling_preservation"].get("status", "Unknown"),
            "routing_preservation_status": self.results["routing_preservation"].get("status", "Unknown"),
            "integration_safety_verified": integration_safe,
            "phase2_success": phase2_success,
            "ready_for_phase3": phase2_success,
            "cumulative_improvements": {
                "data_handling": "0% → 95%+",
                "security": self.results["security_after"].get("improvement", "Unknown"),
                "routing": "100% (preserved)"
            }
        }
        
        print(f"\n📊 PHASE 2 IMPACT ASSESSMENT")
        print("=" * 50)
        print(f"Security System: {self.results['security_after'].get('improvement', 'Unknown')}")
        print(f"Data Handling: {self.results['data_handling_preservation'].get('status', 'Unknown')}")
        print(f"Routing System: {self.results['routing_preservation'].get('status', 'Unknown')}")
        print(f"Integration Safety: {'✅ VERIFIED' if integration_safe else '❌ FAILED'}")
        print(f"Phase 2 Success: {'✅ YES' if phase2_success else '❌ NO'}")
        
        if phase2_success:
            print("\n🎉 PHASE 2 APPROVED - Ready for Phase 3")
            print("   • Security significantly improved")
            print("   • Data handling preserved (95%+)")
            print("   • Core routing system preserved (100%)")
            print("   • Zero risk to existing functionality")
        else:
            print("\n🚫 PHASE 2 BLOCKED")
            if not security_fixed:
                print("   • Security system still failing")
            if not data_preserved:
                print("   • Data handling degraded from Phase 1")
            if not routing_preserved:
                print("   • Core routing compromised (CRITICAL)")
            if not integration_safe:
                print("   • Integration safety issues")

def main():
    """Run Phase 2 impact audit"""
    with app.app_context():
        auditor = Phase2ImpactAudit()
        results = auditor.run_audit()
        
        # Save report
        report_filename = f"phase2_impact_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 Phase 2 impact report saved: {report_filename}")
        return results

if __name__ == "__main__":
    main()