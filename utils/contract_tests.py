"""
Contract Tests for PoR v1.1 Routing Policy
Ensures deterministic routing behavior across deployments
"""

import pytest
from typing import Dict, List, Tuple
from utils.routing_policy import deterministic_router, IntentType, RoutingSignals

class ContractTestSuite:
    """Contract test suite for routing policy validation"""
    
    def __init__(self):
        """Initialize contract test suite"""
        self.test_phrases = self._load_test_phrases()
    
    def _load_test_phrases(self) -> Dict[str, List[str]]:
        """Load canonical test phrases for each intent"""
        return {
            "ADMIN": [
                "/id",
                "/debug", 
                "/help"
            ],
            "ANALYSIS": [
                # English
                "analysis please",
                "what did I spend this week?",
                "spending summary",
                "expense report today",
                "show me this month's breakdown",
                "how much did I spend yesterday?",
                "monthly spending report",
                
                # Bengali
                "এই মাসের খরচ বিশ্লেষণ",
                "বিশ্লেষণ দাও",
                "খরচের সারাংশ",
                "আমি কত খরচ করেছি",
                "এই সপ্তাহের রিপোর্ট",
                
                # Mixed language
                "আজকের analysis please",
                "this month এর খরচ",
                "গত সপ্তাহের spending summary"
            ],
            "FAQ": [
                # English
                "what can you do",
                "how does it work",
                "is my data private",
                "what features do you have",
                "pricing information",
                "security measures",
                "subscription plans",
                
                # Bengali  
                "তুমি কী করতে পারো",
                "কিভাবে কাজ করে",
                "ডেটা নিরাপদ কি",
                "কী ফিচার আছে",
                "দাম কত",
                "নিরাপত্তা কেমন"
            ],
            "COACHING": [
                # English
                "help me reduce food spend",
                "how can I save money",
                "budget planning advice", 
                "cut my expenses",
                "reduce transport costs",
                
                # Bengali
                "খাবারের খরচ কমাতে চাই",
                "টাকা সেভ করবো কিভাবে",
                "বাজেট পরিকল্পনা",
                "খরচ কাট করতে চাই"
            ],
            "SMALLTALK": [
                # English
                "hi",
                "hello",
                "thanks",
                "good morning",
                "how are you",
                
                # Bengali
                "হাই",
                "ধন্যবাদ", 
                "সুপ্রভাত",
                "কেমন আছো"
            ]
        }
    
    def run_contract_tests(self) -> Tuple[int, int, List[str]]:
        """
        Run all contract tests
        
        Returns:
            Tuple of (passed_count, total_count, failed_tests)
        """
        passed = 0
        total = 0
        failures = []
        
        for expected_intent, phrases in self.test_phrases.items():
            for phrase in phrases:
                total += 1
                try:
                    # Test with typical user signals (moderate history)
                    signals = RoutingSignals(
                        ledger_count_30d=15,
                        has_time_window=False,
                        has_analysis_terms=False,
                        has_explicit_analysis=False,
                        has_coaching_verbs=False,
                        has_faq_terms=False,
                        in_coaching_session=False,
                        is_admin_command=False
                    )
                    
                    # Override signals based on phrase
                    signals = deterministic_router.extract_signals(phrase, "test_user")
                    result = deterministic_router.route_intent(phrase, signals)
                    
                    if result.intent.value == expected_intent:
                        passed += 1
                    else:
                        failures.append(
                            f"FAIL: '{phrase}' → {result.intent.value}, expected {expected_intent}"
                        )
                        
                except Exception as e:
                    failures.append(f"ERROR: '{phrase}' → Exception: {e}")
        
        return passed, total, failures
    
    def run_scope_tests(self) -> Tuple[int, int, List[str]]:
        """Test routing scope behavior"""
        passed = 0
        total = 0
        failures = []
        
        test_cases = [
            # (phrase, ledger_count, scope, expected_uses_deterministic)
            ("analysis please", 0, "zero_ledger_only", True),
            ("analysis please", 10, "zero_ledger_only", False),
            ("analysis please", 10, "analysis_keywords_only", True),
            ("hello", 10, "analysis_keywords_only", False),
            ("hello", 0, "all", True),
            ("hello", 10, "all", True),
        ]
        
        for phrase, ledger_count, scope, expected_deterministic in test_cases:
            total += 1
            try:
                # Mock scope setting
                from utils.routing_policy import RouterScope
                original_scope = deterministic_router.flags.scope
                deterministic_router.flags.scope = RouterScope(scope)
                
                signals = RoutingSignals(
                    ledger_count_30d=ledger_count,
                    has_time_window="this week" in phrase,
                    has_analysis_terms="analysis" in phrase,
                    has_explicit_analysis="analysis please" in phrase,
                    has_coaching_verbs=False,
                    has_faq_terms=False,
                    in_coaching_session=False,
                    is_admin_command=False
                )
                
                uses_deterministic = deterministic_router.should_use_deterministic_routing(signals)
                
                if uses_deterministic == expected_deterministic:
                    passed += 1
                else:
                    failures.append(
                        f"FAIL: Scope '{scope}' with ledger={ledger_count}, phrase='{phrase}' "
                        f"→ deterministic={uses_deterministic}, expected {expected_deterministic}"
                    )
                
                # Restore original scope
                deterministic_router.flags.scope = original_scope
                
            except Exception as e:
                failures.append(f"ERROR: Scope test '{phrase}' → Exception: {e}")
        
        return passed, total, failures
    
    def run_bilingual_tests(self) -> Tuple[int, int, List[str]]:
        """Test bilingual pattern matching"""
        passed = 0
        total = 0 
        failures = []
        
        test_cases = [
            # (phrase, expected_pattern_matches)
            ("analysis please", ["has_explicit_analysis"]),
            ("বিশ্লেষণ দাও", ["has_explicit_analysis"]),
            ("আজকের analysis", ["has_time_window", "has_analysis_terms"]),
            ("this month খরচ", ["has_time_window"]),
            ("help me save", ["has_coaching_verbs"]),
            ("টাকা সেভ করতে চাই", ["has_coaching_verbs"]),
            ("what can you do", ["has_faq_terms"]),
            ("তুমি কী করতে পারো", ["has_faq_terms"]),
        ]
        
        for phrase, expected_matches in test_cases:
            total += 1
            try:
                signals = deterministic_router.extract_signals(phrase, "test_user")
                
                actual_matches = []
                if signals.has_explicit_analysis:
                    actual_matches.append("has_explicit_analysis")
                if signals.has_time_window:
                    actual_matches.append("has_time_window")
                if signals.has_analysis_terms:
                    actual_matches.append("has_analysis_terms")
                if signals.has_coaching_verbs:
                    actual_matches.append("has_coaching_verbs")
                if signals.has_faq_terms:
                    actual_matches.append("has_faq_terms")
                
                if all(pattern in actual_matches for pattern in expected_matches):
                    passed += 1
                else:
                    failures.append(
                        f"FAIL: '{phrase}' → patterns {actual_matches}, expected {expected_matches}"
                    )
                    
            except Exception as e:
                failures.append(f"ERROR: Bilingual test '{phrase}' → Exception: {e}")
        
        return passed, total, failures

def run_all_contract_tests() -> Dict[str, any]:
    """Run complete contract test suite"""
    suite = ContractTestSuite()
    
    # Run routing tests
    routing_passed, routing_total, routing_failures = suite.run_contract_tests()
    
    # Run scope tests
    scope_passed, scope_total, scope_failures = suite.run_scope_tests()
    
    # Run bilingual tests
    bilingual_passed, bilingual_total, bilingual_failures = suite.run_bilingual_tests()
    
    # Calculate totals
    total_passed = routing_passed + scope_passed + bilingual_passed
    total_tests = routing_total + scope_total + bilingual_total
    all_failures = routing_failures + scope_failures + bilingual_failures
    
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    return {
        "success": len(all_failures) == 0,
        "passed": total_passed,
        "total": total_tests,
        "success_rate": round(success_rate, 1),
        "failures": all_failures,
        "breakdown": {
            "routing": {"passed": routing_passed, "total": routing_total},
            "scope": {"passed": scope_passed, "total": scope_total},
            "bilingual": {"passed": bilingual_passed, "total": bilingual_total}
        }
    }

if __name__ == "__main__":
    results = run_all_contract_tests()
    print(f"Contract Tests: {results['passed']}/{results['total']} passed ({results['success_rate']}%)")
    
    if results['failures']:
        print("\nFailures:")
        for failure in results['failures']:
            print(f"  {failure}")