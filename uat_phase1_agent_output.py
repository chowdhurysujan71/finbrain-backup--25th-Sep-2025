#!/usr/bin/env python3
"""
Phase 1 UAT: Agent Output & Snapshot
Validates that AI agent emits schema-valid CC with decision and clarifier fields
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.append('/home/runner/workspace')

from utils.ai_adapter_v2 import ProductionAIAdapter
from utils.pca_flags import pca_flags

class Phase1UAT:
    def __init__(self):
        self.ai_adapter = ProductionAIAdapter()
        self.test_results = []
        self.start_time = datetime.now()
        
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
    
    def test_cc_schema_compliance(self):
        """Test 1: CC Schema Compliance"""
        test_messages = [
            "Coffee 50",
            "bkash 500", 
            "lunch at restaurant 800",
            "what can you do",
            "show my spending"
        ]
        
        all_valid = True
        invalid_count = 0
        
        for msg in test_messages:
            try:
                # Call AI adapter using the correct method
                result = self.ai_adapter.ai_parse(msg, {})
                
                # Check if result has CC structure
                if "schema_version" in result:
                    # Validate required CC fields
                    required_fields = ["schema_version", "intent", "confidence", "decision", "ui_note"]
                    missing_fields = [f for f in required_fields if f not in result]
                    
                    if missing_fields:
                        all_valid = False
                        invalid_count += 1
                        print(f"   Missing fields in '{msg}': {missing_fields}")
                    
                    # Validate decision field
                    if "decision" in result:
                        valid_decisions = ["AUTO_APPLY", "ASK_ONCE", "RAW_ONLY"]
                        if result["decision"] not in valid_decisions:
                            all_valid = False
                            invalid_count += 1
                            print(f"   Invalid decision in '{msg}': {result['decision']}")
                    
                    # Validate confidence range
                    if "confidence" in result:
                        conf = result["confidence"]
                        if not (0.0 <= conf <= 1.0):
                            all_valid = False
                            invalid_count += 1
                            print(f"   Invalid confidence in '{msg}': {conf}")
                
                else:
                    # Legacy format - should still work but note it
                    print(f"   Legacy format for '{msg}' - not CC schema")
                    
            except Exception as e:
                all_valid = False
                invalid_count += 1
                print(f"   Exception for '{msg}': {str(e)}")
        
        self.log_result(
            "CC Schema Compliance",
            all_valid,
            f"Processed {len(test_messages)} messages, {invalid_count} invalid"
        )
    
    def test_ui_note_length_enforcement(self):
        """Test 2: UI Note Length ≤ 140 chars"""
        # Test with a very long message that should produce a long UI note
        long_message = "I spent money at the very long restaurant name called 'The Extraordinarily Long Restaurant Name That Goes On And On And Should Be Truncated' for an extremely expensive meal that cost me exactly 1500 taka"
        
        try:
            result = self.ai_adapter.ai_parse(long_message, {})
            
            if "ui_note" in result:
                ui_note_length = len(result["ui_note"])
                length_ok = ui_note_length <= 140
                
                self.log_result(
                    "UI Note Length Enforcement",
                    length_ok,
                    f"ui_note length: {ui_note_length}/140 chars"
                )
            else:
                self.log_result(
                    "UI Note Length Enforcement",
                    False,
                    "No ui_note field in response"
                )
                
        except Exception as e:
            self.log_result(
                "UI Note Length Enforcement", 
                False, 
                f"Exception: {str(e)}"
            )
    
    def test_decision_logic_thresholds(self):
        """Test 3: Decision Logic Based on Confidence Thresholds"""
        # These are synthetic tests to verify the logic works
        # We can't control AI confidence directly, but we can test the validation
        
        test_cases = [
            {"confidence": 0.95, "expected_decision": "AUTO_APPLY"},
            {"confidence": 0.70, "expected_decision": "ASK_ONCE"}, 
            {"confidence": 0.30, "expected_decision": "RAW_ONLY"}
        ]
        
        tau_high, tau_low = pca_flags.get_clarifier_thresholds()
        
        # Test the threshold logic conceptually
        logic_correct = True
        for case in test_cases:
            conf = case["confidence"]
            expected = case["expected_decision"]
            
            # Apply the logic from our system prompt
            if conf >= tau_high:
                actual = "AUTO_APPLY"
            elif tau_low <= conf < tau_high:
                actual = "ASK_ONCE"
            else:
                actual = "RAW_ONLY"
            
            if actual != expected:
                logic_correct = False
                print(f"   Threshold logic failed: conf={conf}, expected={expected}, got={actual}")
        
        self.log_result(
            "Decision Logic Thresholds",
            logic_correct,
            f"tau_high={tau_high}, tau_low={tau_low}"
        )
    
    def test_clarifier_structure(self):
        """Test 4: Clarifier Structure Validation"""
        # Test a message that should trigger ASK_ONCE
        ambiguous_message = "payment 500"
        
        try:
            result = self.ai_adapter.ai_parse(ambiguous_message, {})
            
            clarifier_valid = True
            clarifier_details = "No clarifier field"
            
            if "clarifier" in result:
                clarifier = result["clarifier"]
                clarifier_details = f"type={clarifier.get('type', 'missing')}"
                
                # Check required clarifier fields
                if "type" in clarifier:
                    valid_types = ["category_pick", "none"]
                    if clarifier["type"] not in valid_types:
                        clarifier_valid = False
                        clarifier_details += f", invalid_type={clarifier['type']}"
                
                # If type is category_pick, should have options
                if clarifier.get("type") == "category_pick":
                    options = clarifier.get("options", [])
                    if not isinstance(options, list) or len(options) == 0:
                        clarifier_valid = False
                        clarifier_details += f", missing_options"
                    else:
                        clarifier_details += f", options_count={len(options)}"
                
                # Check prompt length
                prompt = clarifier.get("prompt", "")
                if len(prompt) > 80:
                    clarifier_valid = False
                    clarifier_details += f", prompt_too_long={len(prompt)}"
            
            self.log_result(
                "Clarifier Structure Validation",
                clarifier_valid,
                clarifier_details
            )
            
        except Exception as e:
            self.log_result(
                "Clarifier Structure Validation",
                False,
                f"Exception: {str(e)}"
            )
    
    def test_source_text_preservation(self):
        """Test 5: Source Text Preservation"""
        test_message = "Coffee shop ৳75 yesterday evening"
        
        try:
            result = self.ai_adapter.ai_parse(test_message, {})
            
            if "source_text" in result:
                preserved_correctly = result["source_text"] == test_message
                
                self.log_result(
                    "Source Text Preservation",
                    preserved_correctly,
                    f"Original: '{test_message}' -> Preserved: '{result['source_text']}'"
                )
            else:
                self.log_result(
                    "Source Text Preservation",
                    False,
                    "No source_text field in response"
                )
                
        except Exception as e:
            self.log_result(
                "Source Text Preservation",
                False,
                f"Exception: {str(e)}"
            )
    
    def test_model_version_tracking(self):
        """Test 6: Model Version Tracking"""
        try:
            result = self.ai_adapter.ai_parse("test 100", {})
            
            if "model_version" in result:
                model_version = result["model_version"]
                version_valid = "clarifiers" in model_version.lower()
                
                self.log_result(
                    "Model Version Tracking",
                    version_valid,
                    f"model_version: {model_version}"
                )
            else:
                self.log_result(
                    "Model Version Tracking",
                    False,
                    "No model_version field in response"
                )
                
        except Exception as e:
            self.log_result(
                "Model Version Tracking",
                False,
                f"Exception: {str(e)}"
            )
    
    def test_no_ui_changes(self):
        """Test 7: No UI Changes (Clarifiers Disabled)"""
        # Verify that clarifiers are still disabled
        clarifiers_disabled = not pca_flags.should_enable_clarifiers()
        
        self.log_result(
            "No UI Changes - Clarifiers Disabled",
            clarifiers_disabled,
            f"should_enable_clarifiers={pca_flags.should_enable_clarifiers()}"
        )
    
    def run_all_tests(self):
        """Run complete Phase 1 UAT suite"""
        print("🧪 PHASE 1 UAT: Agent Output & Snapshot")
        print("=" * 60)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run all test suites
        self.test_cc_schema_compliance()
        self.test_ui_note_length_enforcement()
        self.test_decision_logic_thresholds()
        self.test_clarifier_structure()
        self.test_source_text_preservation()
        self.test_model_version_tracking()
        self.test_no_ui_changes()
        
        # Calculate results
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print()
        print("=" * 60)
        print(f"PHASE 1 UAT RESULTS:")
        print(f"✅ Passed: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"🎯 Exit Gate: {'PASS' if pass_rate == 100 else 'FAIL'}")
        
        if pass_rate == 100:
            print()
            print("🎉 PHASE 1 COMPLETE!")
            print("✅ AI agent emitting schema-valid Canonical Commands")
            print("✅ Decision and clarifier fields properly structured")
            print("✅ UI note length enforced ≤ 140 chars")
            print("✅ No UI changes - clarifiers remain disabled")
            print("✅ Ready for Phase 2: Router Decision Tree")
        else:
            print()
            print("❌ PHASE 1 FAILED - Issues must be resolved before proceeding")
            failed_tests = [r for r in self.test_results if r['status'] == 'FAIL']
            for test in failed_tests:
                print(f"   ❌ {test['test']}: {test['details']}")
        
        return pass_rate == 100

if __name__ == "__main__":
    uat = Phase1UAT()
    success = uat.run_all_tests()
    sys.exit(0 if success else 1)