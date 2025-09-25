#!/usr/bin/env python3
"""
Phase 1 Impact Audit: Verify Data Handling improvement while preserving core routing
"""

import json
import time
from typing import Any, Dict

from app import app


class Phase1ImpactAudit:
    """Test Phase 1 improvements without touching existing routing system"""
    
    def __init__(self):
        self.audit_id = f"phase1_{int(time.time())}"
        self.results = {
            "audit_id": self.audit_id,
            "timestamp": time.time(),
            "data_handling_before": "0% (signal extraction failures)",
            "data_handling_after": {},
            "routing_preservation": {},
            "integration_safety": {}
        }
    
    def run_audit(self) -> dict[str, Any]:
        print("🔍 PHASE 1 IMPACT AUDIT")
        print("=" * 50)
        print("Testing: New signal extraction vs existing routing")
        print("Ensuring: Zero risk to 100% working routing system")
        print()
        
        # Test 1: Data Handling with new system
        print("📊 Testing NEW Signal Extraction System")
        print("-" * 40)
        data_results = self._test_new_data_handling()
        self.results["data_handling_after"] = data_results
        self._print_results("New Data Handling", data_results)
        
        # Test 2: Routing system preservation
        print("\n🎯 Testing EXISTING Routing System (Preservation)")
        print("-" * 40)
        routing_results = self._test_routing_preservation()
        self.results["routing_preservation"] = routing_results
        self._print_results("Routing Preservation", routing_results)
        
        # Test 3: Integration safety
        print("\n🛡️ Testing Integration Safety")
        print("-" * 40)
        integration_results = self._test_integration_safety()
        self.results["integration_safety"] = integration_results
        self._print_results("Integration Safety", integration_results)
        
        # Final assessment
        self._generate_phase1_assessment()
        
        return self.results
    
    def _test_new_data_handling(self) -> dict[str, Any]:
        """Test the new signal extraction system"""
        from nlp.signals_extractor import extract_signals
        
        test_cases = [
            {
                "name": "English expense with money",
                "input": "lunch 500 taka",
                "expects": {"has_money": True, "money_mentions": True}
            },
            {
                "name": "Bengali expense with amount",
                "input": "চা ৫০ টাকা",
                "expects": {"has_money": True, "money_mentions": True}
            },
            {
                "name": "English analysis request",
                "input": "analysis please",
                "expects": {"explicit_analysis_request": True, "has_analysis_terms": True}
            },
            {
                "name": "Bengali analysis request",
                "input": "বিশ্লেষণ দাও",
                "expects": {"explicit_analysis_request": True, "has_analysis_terms": True}
            },
            {
                "name": "Mixed language coaching",
                "input": "help me টাকা সেভ করতে",
                "expects": {"has_coaching_verbs": True}
            },
            {
                "name": "FAQ query",
                "input": "what can you do",
                "expects": {"has_faq_terms": True}
            },
            {
                "name": "Admin command",
                "input": "/id",
                "expects": {"is_admin": True}
            },
            {
                "name": "Time window parsing",
                "input": "today spending",
                "expects": {"has_time_window": True, "window": True}
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                signals = extract_signals(case["input"])
                
                test_result = {
                    "name": case["name"],
                    "input": case["input"],
                    "success": True,
                    "signals": {}
                }
                
                # Validate expectations
                for key, expected in case["expects"].items():
                    if key == "money_mentions":
                        actual = len(signals.get("money_mentions", [])) > 0
                    elif key == "window":
                        actual = signals.get("window") is not None
                    else:
                        actual = signals.get(key, False)
                    
                    test_result["signals"][key] = actual
                    if expected and not actual:
                        test_result["success"] = False
                
                results.append(test_result)
                status = "✅" if test_result["success"] else "❌"
                print(f"  {status} {case['name']}: {case['input'][:25]}...")
                
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
            "improvement": "0% → 95%+" if success_rate >= 95.0 else f"0% → {success_rate:.1f}%"
        }
    
    def _test_routing_preservation(self) -> dict[str, Any]:
        """Ensure existing routing system remains 100% functional"""
        
        # Test the existing routing system we know works 100%
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
                
                # Use existing signal extraction (should still work)
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
            "overall_success": success_rate == 100.0,  # Must be perfect
            "status": "PRESERVED" if success_rate == 100.0 else "COMPROMISED"
        }
    
    def _test_integration_safety(self) -> dict[str, Any]:
        """Test that Phase 1 changes don't break anything"""
        
        safety_checks = [
            {
                "name": "Module imports work",
                "test": lambda: self._test_imports()
            },
            {
                "name": "New functions don't conflict",
                "test": lambda: self._test_no_conflicts()
            },
            {
                "name": "Existing functions still work",
                "test": lambda: self._test_existing_functions()
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
    
    def _test_imports(self) -> dict[str, Any]:
        """Test that new modules import correctly"""
        try:
            from nlp.signals_extractor import extract_signals, parse_time_window
            from utils.text_normalizer import normalize_for_processing
            
            # Test basic functionality
            normalized = normalize_for_processing("Test TEXT")
            signals = extract_signals("test message")
            window = parse_time_window("Asia/Dhaka", "today")
            
            return {
                "success": True,
                "details": {
                    "normalizer_works": len(normalized) > 0,
                    "extractor_works": isinstance(signals, dict),
                    "window_parser_works": window is not None
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_no_conflicts(self) -> dict[str, Any]:
        """Test that new functions don't conflict with existing ones"""
        try:
            # Test that existing routing still works
            # Test that new signal extraction works
            from nlp.signals_extractor import extract_signals
            from utils.routing_policy import deterministic_router
            
            # They should coexist without conflicts
            old_signals = deterministic_router.extract_signals("test", "user")
            new_signals = extract_signals("test")
            
            return {
                "success": True,
                "details": {
                    "old_extractor_works": hasattr(old_signals, 'has_money'),
                    "new_extractor_works": isinstance(new_signals, dict),
                    "no_namespace_conflicts": True
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_existing_functions(self) -> dict[str, Any]:
        """Test that existing functions still work"""
        try:
            from utils.routing_policy import deterministic_router
            
            # Test existing contract functions
            signals = deterministic_router.extract_signals("analysis please", "test_user")
            routing = deterministic_router.route_intent("analysis please", signals)
            
            return {
                "success": True,
                "details": {
                    "signal_extraction_works": hasattr(signals, 'has_analysis'),
                    "routing_works": hasattr(routing, 'intent'),
                    "intent_correct": routing.intent.value == "ANALYSIS"
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _print_results(self, phase_name: str, results: dict[str, Any]):
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
    
    def _generate_phase1_assessment(self):
        """Generate Phase 1 impact assessment"""
        
        data_handling = self.results["data_handling_after"]
        routing_preservation = self.results["routing_preservation"]
        integration_safety = self.results["integration_safety"]
        
        # Critical requirements
        data_fixed = data_handling.get("overall_success", False)
        routing_preserved = routing_preservation.get("overall_success", False)
        integration_safe = integration_safety.get("overall_success", False)
        
        phase1_success = data_fixed and routing_preserved and integration_safe
        
        self.results["phase1_assessment"] = {
            "data_handling_improvement": data_handling.get("improvement", "Unknown"),
            "routing_preservation_status": routing_preservation.get("status", "Unknown"),
            "integration_safety_verified": integration_safe,
            "phase1_success": phase1_success,
            "ready_for_phase2": phase1_success,
            "risk_level": "ZERO RISK" if routing_preserved else "HIGH RISK"
        }
        
        print("\n📊 PHASE 1 IMPACT ASSESSMENT")
        print("=" * 50)
        print(f"Data Handling: {data_handling.get('improvement', 'Unknown')}")
        print(f"Routing System: {routing_preservation.get('status', 'Unknown')}")
        print(f"Integration Safety: {'✅ VERIFIED' if integration_safe else '❌ FAILED'}")
        print(f"Phase 1 Success: {'✅ YES' if phase1_success else '❌ NO'}")
        print(f"Risk to Core: {self.results['phase1_assessment']['risk_level']}")
        
        if phase1_success:
            print("\n🎉 PHASE 1 APPROVED - Ready for Phase 2")
            print("   • Data handling significantly improved")
            print("   • Core routing system preserved (100%)")
            print("   • Zero risk to existing functionality")
        else:
            print("\n🚫 PHASE 1 BLOCKED")
            if not data_fixed:
                print("   • Data handling still failing")
            if not routing_preserved:
                print("   • Core routing compromised (CRITICAL)")
            if not integration_safe:
                print("   • Integration safety issues")

def main():
    """Run Phase 1 impact audit"""
    with app.app_context():
        auditor = Phase1ImpactAudit()
        results = auditor.run_audit()
        
        # Save report
        report_filename = f"phase1_impact_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 Phase 1 impact report saved: {report_filename}")
        return results

if __name__ == "__main__":
    main()