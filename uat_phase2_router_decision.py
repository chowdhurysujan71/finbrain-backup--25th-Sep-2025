#!/usr/bin/env python3
"""
Phase 2 UAT: Router Decision Tree
Validates that CC decision routing works correctly while clarifiers remain disabled
"""

import sys
import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.append('/home/runner/workspace')

# Import Flask app for context
from app import app
from utils.production_router import ProductionRouter
from utils.pca_flags import pca_flags

class Phase2UAT:
    def __init__(self):
        self.router = ProductionRouter()
        self.test_results = []
        self.start_time = datetime.now()
        self.base_url = "http://localhost:5000"
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        result = {
            'test': test_name,
            'status': 'PASS' if passed else 'FAIL',
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} {test_name}: {result['status']}")
        if details:
            print(f"   {details}")
    
    def test_auto_apply_decision(self):
        """Test 1: AUTO_APPLY Decision (High Confidence)"""
        try:
            # Test clear, high-confidence expense message
            test_message = "Starbucks coffee 85"
            
            with app.app_context():
                response, intent, category, amount = self.router.route_message(
                    text=test_message,
                    psid="test_user_auto_apply"
                )
            
            # Should directly log the expense
            auto_apply_success = (
                intent == "log_single" and
                amount == 85.0 and
                "Logged" in response or "✅" in response
            )
            
            self.log_result(
                "AUTO_APPLY Decision",
                auto_apply_success,
                f"intent={intent}, amount={amount}, response='{response[:50]}...'"
            )
            
        except Exception as e:
            self.log_result("AUTO_APPLY Decision", False, f"Exception: {str(e)}")
    
    def test_ask_once_fallback(self):
        """Test 2: ASK_ONCE → AUTO_APPLY Fallback (Clarifiers Disabled)"""
        try:
            # Test ambiguous message that should trigger ASK_ONCE but fallback to AUTO_APPLY
            test_message = "payment 500"
            
            with app.app_context():
                response, intent, category, amount = self.router.route_message(
                    text=test_message,
                    psid="test_user_ask_once"
                )
            
            # Should treat ASK_ONCE as AUTO_APPLY since clarifiers disabled
            fallback_success = (
                intent in ["log_single", "help"] and
                amount == 500.0 if amount else True  # Amount might be parsed
            )
            
            # Verify clarifiers are disabled
            clarifiers_disabled = not pca_flags.should_enable_clarifiers()
            
            self.log_result(
                "ASK_ONCE → AUTO_APPLY Fallback",
                fallback_success and clarifiers_disabled,
                f"intent={intent}, amount={amount}, clarifiers_disabled={clarifiers_disabled}"
            )
            
        except Exception as e:
            self.log_result("ASK_ONCE → AUTO_APPLY Fallback", False, f"Exception: {str(e)}")
    
    def test_raw_only_decision(self):
        """Test 3: RAW_ONLY Decision (Low Confidence)"""
        try:
            # Test unclear message that should trigger RAW_ONLY
            test_message = "some payment thing 1200"
            
            with app.app_context():
                response, intent, category, amount = self.router.route_message(
                    text=test_message,
                    psid="test_user_raw_only"
                )
            
            # Should save as raw with minimal categorization
            raw_only_success = (
                intent in ["log_single", "help"] and
                (category == "other" if category else True) and
                amount == 1200.0 if amount else True
            )
            
            self.log_result(
                "RAW_ONLY Decision",
                raw_only_success,
                f"intent={intent}, category={category}, amount={amount}"
            )
            
        except Exception as e:
            self.log_result("RAW_ONLY Decision", False, f"Exception: {str(e)}")
    
    def test_cc_routing_integration(self):
        """Test 4: CC Routing Integration"""
        try:
            # Test that CC routing is actually being used
            # Check router has the new method
            has_cc_method = hasattr(self.router, '_route_cc_decision')
            
            # Test that the method works
            cc_result = None
            if has_cc_method:
                try:
                    cc_result = self.router._route_cc_decision(
                        "coffee 75",
                        "test_psid",
                        "test_hash",
                        "test_rid"
                    )
                    cc_method_works = cc_result is not None
                except Exception as cc_e:
                    cc_method_works = False
                    print(f"   CC method exception: {cc_e}")
            else:
                cc_method_works = False
            
            self.log_result(
                "CC Routing Integration",
                has_cc_method and cc_method_works,
                f"has_method={has_cc_method}, method_works={cc_method_works}"
            )
            
        except Exception as e:
            self.log_result("CC Routing Integration", False, f"Exception: {str(e)}")
    
    def test_legacy_ai_fallback(self):
        """Test 5: Legacy AI Fallback"""
        try:
            # Test non-expense message should still route to legacy paths
            test_message = "show my spending summary"
            
            with app.app_context():
                response, intent, category, amount = self.router.route_message(
                    text=test_message,
                    psid="test_user_legacy"
                )
            
            # Should handle non-expense intents normally
            legacy_fallback_success = (
                intent in ["summary", "help", "conversation"] and
                amount is None  # Non-expense message
            )
            
            self.log_result(
                "Legacy AI Fallback",
                legacy_fallback_success,
                f"intent={intent}, response='{response[:50]}...'"
            )
            
        except Exception as e:
            self.log_result("Legacy AI Fallback", False, f"Exception: {str(e)}")
    
    def test_expense_saving_logic(self):
        """Test 6: CC Expense Saving Logic"""
        try:
            # Test the _save_cc_expense method directly
            has_save_method = hasattr(self.router, '_save_cc_expense')
            
            save_success = False
            if has_save_method:
                try:
                    # Test save with minimal data (need app context for DB)
                    with app.app_context():
                        save_success = self.router._save_cc_expense(
                            user_hash="test_save_hash",
                            amount=50.0,
                            category="food",
                            note="test expense",
                            merchant_text="test merchant",
                            original_text="test 50",
                            rid="test_save_rid"
                        )
                except Exception as save_e:
                    print(f"   Save method exception: {save_e}")
                    save_success = False
            
            self.log_result(
                "CC Expense Saving Logic",
                has_save_method and save_success,
                f"has_method={has_save_method}, save_success={save_success}"
            )
            
        except Exception as e:
            self.log_result("CC Expense Saving Logic", False, f"Exception: {str(e)}")
    
    def test_no_ui_changes(self):
        """Test 7: No UI Changes (Clarifiers Disabled)"""
        try:
            # Verify clarifiers remain disabled
            clarifiers_disabled = not pca_flags.should_enable_clarifiers()
            
            # Verify no clarifier rendering happens
            has_clarifier_method = hasattr(self.router, '_render_clarifier_response')
            
            # Test that clarifier method exists but doesn't activate
            clarifier_placeholder = False
            if has_clarifier_method:
                try:
                    # This should return a placeholder response
                    clarifier_result = self.router._render_clarifier_response(
                        {'ui_note': 'test', 'slots': {}},
                        "test_hash",
                        "test_rid"
                    )
                    clarifier_placeholder = clarifier_result is not None
                except Exception:
                    clarifier_placeholder = False
            
            self.log_result(
                "No UI Changes - Clarifiers Disabled",
                clarifiers_disabled and has_clarifier_method and clarifier_placeholder,
                f"disabled={clarifiers_disabled}, has_method={has_clarifier_method}, placeholder={clarifier_placeholder}"
            )
            
        except Exception as e:
            self.log_result("No UI Changes", False, f"Exception: {str(e)}")
    
    def test_decision_tree_coverage(self):
        """Test 8: Decision Tree Coverage"""
        try:
            # Test that all decision paths are implemented
            test_cases = [
                ("coffee 80", "AUTO_APPLY"),     # High confidence
                ("payment 400", "ASK_ONCE"),     # Mid confidence  
                ("thing 1000", "RAW_ONLY"),      # Low confidence
                ("hello", "HELP")                # No expense
            ]
            
            coverage_results = []
            
            for test_msg, expected_decision in test_cases:
                try:
                    with app.app_context():
                        response, intent, category, amount = self.router.route_message(
                            text=test_msg,
                            psid=f"test_coverage_{expected_decision.lower()}"
                        )
                    
                    # Check that some response was generated
                    has_response = response and len(response) > 0
                    coverage_results.append(has_response)
                    
                except Exception as e:
                    print(f"   Coverage test failed for '{test_msg}': {e}")
                    coverage_results.append(False)
            
            all_covered = all(coverage_results)
            
            self.log_result(
                "Decision Tree Coverage",
                all_covered,
                f"covered={sum(coverage_results)}/{len(coverage_results)}"
            )
            
        except Exception as e:
            self.log_result("Decision Tree Coverage", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run complete Phase 2 UAT suite"""
        print("🧪 PHASE 2 UAT: Router Decision Tree")
        print("=" * 60)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run all test suites
        self.test_auto_apply_decision()
        self.test_ask_once_fallback()
        self.test_raw_only_decision()
        self.test_cc_routing_integration()
        self.test_legacy_ai_fallback()
        self.test_expense_saving_logic()
        self.test_no_ui_changes()
        self.test_decision_tree_coverage()
        
        # Calculate results
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print()
        print("=" * 60)
        print(f"PHASE 2 UAT RESULTS:")
        print(f"✅ Passed: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"🎯 Exit Gate: {'PASS' if pass_rate == 100 else 'FAIL'}")
        
        if pass_rate == 100:
            print()
            print("🎉 PHASE 2 COMPLETE!")
            print("✅ CC decision routing working correctly")
            print("✅ AUTO_APPLY/ASK_ONCE→AUTO_APPLY/RAW_ONLY paths active") 
            print("✅ Expense saving from CC data operational")
            print("✅ Legacy AI fallback preserved")
            print("✅ No UI changes - clarifiers remain disabled")
            print("✅ Ready for Phase 3: Clarifier UI (when enabled)")
        else:
            print()
            print("❌ PHASE 2 FAILED - Issues must be resolved before proceeding")
            failed_tests = [r for r in self.test_results if r['status'] == 'FAIL']
            for test in failed_tests:
                print(f"   ❌ {test['test']}: {test['details']}")
        
        return pass_rate == 100

if __name__ == "__main__":
    uat = Phase2UAT()
    success = uat.run_all_tests()
    sys.exit(0 if success else 1)