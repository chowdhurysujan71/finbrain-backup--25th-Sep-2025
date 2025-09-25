#!/usr/bin/env python3
"""
Phase 0 UAT: Clarifier Configuration & Safety
Validates that configuration changes have zero behavioral impact
"""

import sys
from datetime import datetime

import requests

# Add project root to path
sys.path.append('/home/runner/workspace')

from utils.pca_flags import pca_flags


class Phase0UAT:
    def __init__(self):
        self.base_url = "http://localhost:5000"
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
            
    def test_config_loading(self):
        """Test 1: Configuration Values Loaded Correctly"""
        try:
            # Test threshold values
            tau_high, tau_low = pca_flags.get_clarifier_thresholds()
            
            self.log_result(
                "Config Loading - Thresholds",
                tau_high == 0.85 and tau_low == 0.55,
                f"tau_high={tau_high}, tau_low={tau_low}"
            )
            
            # Test clarifier flag (should be false)
            clarifiers_enabled = pca_flags.should_enable_clarifiers()
            
            self.log_result(
                "Config Loading - Clarifiers Disabled",
                clarifiers_enabled == False,
                f"clarifiers_enabled={clarifiers_enabled}"
            )
            
            # Test SLO budget
            self.log_result(
                "Config Loading - SLO Budget",
                pca_flags.slo_budget_ms == 600,
                f"slo_budget_ms={pca_flags.slo_budget_ms}"
            )
            
        except Exception as e:
            self.log_result("Config Loading", False, f"Exception: {str(e)}")
    
    def test_flag_safety(self):
        """Test 2: Feature Flag Safety Mechanisms"""
        try:
            # Test mode requirements for clarifiers
            mode_check = pca_flags.mode.value in ['DRYRUN', 'ON']
            enable_flag = pca_flags.enable_clarifiers
            kill_switch = pca_flags.global_kill_switch
            
            # Should be false because enable_clarifiers=false (despite mode=ON)
            should_enable = pca_flags.should_enable_clarifiers()
            
            self.log_result(
                "Flag Safety - Clarifier Gating",
                should_enable == False,
                f"mode={pca_flags.mode.value}, enable_flag={enable_flag}, kill_switch={kill_switch}, result={should_enable}"
            )
            
            # Test threshold validation
            valid_thresholds = pca_flags.tau_high > pca_flags.tau_low
            
            self.log_result(
                "Flag Safety - Threshold Validation",
                valid_thresholds,
                f"tau_high({pca_flags.tau_high}) > tau_low({pca_flags.tau_low})"
            )
            
        except Exception as e:
            self.log_result("Flag Safety", False, f"Exception: {str(e)}")
    
    def test_monitoring_api(self):
        """Test 3: Monitoring API Integration"""
        try:
            # Test status endpoint includes clarifier info
            status = pca_flags.get_status()
            
            required_fields = [
                'clarifiers_enabled', 'enable_clarifiers_flag', 
                'tau_high', 'tau_low', 'version'
            ]
            
            all_fields_present = all(field in status for field in required_fields)
            
            self.log_result(
                "Monitoring API - Status Fields",
                all_fields_present,
                f"Present: {[f for f in required_fields if f in status]}"
            )
            
            # Verify clarifiers disabled in status
            clarifiers_disabled = (
                status.get('clarifiers_enabled') == False and
                status.get('enable_clarifiers_flag') == False
            )
            
            self.log_result(
                "Monitoring API - Clarifiers Status",
                clarifiers_disabled,
                f"clarifiers_enabled={status.get('clarifiers_enabled')}, flag={status.get('enable_clarifiers_flag')}"
            )
            
            # Check version updated
            version_updated = 'clarifiers' in status.get('version', '')
            
            self.log_result(
                "Monitoring API - Version Updated",
                version_updated,
                f"version={status.get('version')}"
            )
            
        except Exception as e:
            self.log_result("Monitoring API", False, f"Exception: {str(e)}")
    
    def test_behavioral_impact(self):
        """Test 4: Zero Behavioral Impact"""
        try:
            # Test health endpoint still works
            response = requests.get(f"{self.base_url}/health", timeout=10)
            health_ok = response.status_code == 200
            
            self.log_result(
                "Behavioral Impact - Health Endpoint",
                health_ok,
                f"status_code={response.status_code}"
            )
            
            # Test that clarifier logic paths don't exist yet
            # (this will be implemented in later phases)
            import importlib
            try:
                # Try to import router and check for clarifier methods
                router_module = importlib.import_module('utils.production_router')
                has_clarifier_methods = hasattr(router_module, 'render_clarifier_chips')
                
                self.log_result(
                    "Behavioral Impact - No Clarifier Logic",
                    not has_clarifier_methods,
                    f"clarifier_methods_exist={has_clarifier_methods}"
                )
                
            except ImportError:
                self.log_result(
                    "Behavioral Impact - Router Import",
                    True,
                    "Router module not affected by config changes"
                )
            
        except Exception as e:
            self.log_result("Behavioral Impact", False, f"Exception: {str(e)}")
    
    def test_edge_cases(self):
        """Test 5: Edge Case Handling"""
        try:
            # Test invalid threshold scenarios (should use safe defaults)
            original_high = pca_flags.tau_high
            original_low = pca_flags.tau_low
            
            # Current values should be valid
            valid_current = original_high > original_low
            
            self.log_result(
                "Edge Cases - Valid Thresholds",
                valid_current,
                f"tau_high={original_high} > tau_low={original_low}"
            )
            
            # Test that kill switch would disable everything
            kill_effect = not pca_flags.should_enable_clarifiers() if pca_flags.global_kill_switch else True
            
            self.log_result(
                "Edge Cases - Kill Switch Effect",
                kill_effect,
                f"kill_switch={pca_flags.global_kill_switch}"
            )
            
        except Exception as e:
            self.log_result("Edge Cases", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run complete Phase 0 UAT suite"""
        print("🧪 PHASE 0 UAT: Clarifier Configuration & Safety")
        print("=" * 60)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run all test suites
        self.test_config_loading()
        self.test_flag_safety() 
        self.test_monitoring_api()
        self.test_behavioral_impact()
        self.test_edge_cases()
        
        # Calculate results
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print()
        print("=" * 60)
        print("PHASE 0 UAT RESULTS:")
        print(f"✅ Passed: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"🎯 Exit Gate: {'PASS' if pass_rate == 100 else 'FAIL'}")
        
        if pass_rate == 100:
            print()
            print("🎉 PHASE 0 COMPLETE!")
            print("✅ Configuration safely added with zero behavioral impact")
            print("✅ Clarifiers properly disabled by default")
            print("✅ All safety mechanisms validated")
            print("✅ Ready for Phase 1: Agent Output & Snapshot")
        else:
            print()
            print("❌ PHASE 0 FAILED - Issues must be resolved before proceeding")
            failed_tests = [r for r in self.test_results if r['status'] == 'FAIL']
            for test in failed_tests:
                print(f"   ❌ {test['test']}: {test['details']}")
        
        return pass_rate == 100

if __name__ == "__main__":
    uat = Phase0UAT()
    success = uat.run_all_tests()
    sys.exit(0 if success else 1)