#!/usr/bin/env python3
"""
SMART_CORRECTIONS Development Simulation Script
End-to-end testing tool for correction system with realistic scenarios
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.expense import parse_expense, is_correction_message
from finbrain.router import contains_money_with_correction_fallback
from utils.feature_flags import is_smart_corrections_enabled
from templates.replies import format_corrected_reply, format_correction_no_candidate_reply

class CorrectionSimulator:
    """Simulates the complete correction flow for development testing"""
    
    def __init__(self):
        self.test_user = "dev_test_user_hash_12345"
        self.scenarios = self._load_test_scenarios()
        
    def _load_test_scenarios(self) -> List[Dict[str, Any]]:
        """Load comprehensive test scenarios"""
        return [
            {
                'name': 'Basic Amount Correction',
                'original': 'coffee 50',
                'correction': 'sorry, I meant 500',
                'expected_old_amount': 50,
                'expected_new_amount': 500,
                'expected_category': 'food'
            },
            {
                'name': 'K Shorthand Correction',
                'original': 'lunch 200',
                'correction': 'actually 1.5k',
                'expected_old_amount': 200,
                'expected_new_amount': 1500,
                'expected_category': 'food'
            },
            {
                'name': 'Decimal Amount Correction',
                'original': 'transport 100',
                'correction': 'typo, meant 25.50',
                'expected_old_amount': 100,
                'expected_new_amount': 25.50,
                'expected_category': 'transport'
            },
            {
                'name': 'Cross-Category Correction',
                'original': 'groceries 300',
                'correction': 'correction: should be 250',
                'expected_old_amount': 300,
                'expected_new_amount': 250,
                'expected_category': 'shopping'
            },
            {
                'name': 'No Candidate Scenario',
                'original': None,  # No prior expense
                'correction': 'meant 400 for dinner',
                'expected_old_amount': None,
                'expected_new_amount': 400,
                'expected_category': 'food'
            },
            {
                'name': 'Multiple Phrase Correction',
                'original': 'coffee 100 at Starbucks',
                'correction': 'not 100, actually 150',
                'expected_old_amount': 100,
                'expected_new_amount': 150,
                'expected_category': 'food',
                'expected_merchant': 'Starbucks'
            }
        ]
    
    def test_correction_detection(self) -> Dict[str, Any]:
        """Test correction message detection"""
        print("\n🔍 Testing Correction Detection...")
        results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        for scenario in self.scenarios:
            correction_text = scenario['correction']
            detected = is_correction_message(correction_text)
            
            result = {
                'scenario': scenario['name'],
                'text': correction_text,
                'detected': detected,
                'expected': True,
                'passed': detected == True
            }
            
            if result['passed']:
                results['passed'] += 1
                print(f"✅ {scenario['name']}: Detected correction in '{correction_text}'")
            else:
                results['failed'] += 1
                print(f"❌ {scenario['name']}: Failed to detect correction in '{correction_text}'")
            
            results['details'].append(result)
        
        return results
    
    def test_money_detection_fallback(self) -> Dict[str, Any]:
        """Test enhanced money detection with correction fallbacks"""
        print("\n💰 Testing Money Detection with Correction Fallbacks...")
        results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        # Test cases for fallback detection
        fallback_cases = [
            ("sorry, I meant 500", True, "Bare number in correction"),
            ("actually 1.5k", True, "K shorthand in correction"),
            ("typo, should be 25.50", True, "Decimal in correction"),
            ("coffee 50", True, "Standard money detection"),
            ("hello world", False, "No money"),
            ("sorry about that", False, "Correction phrase but no money")
        ]
        
        for text, expected, description in fallback_cases:
            detected = contains_money_with_correction_fallback(text, self.test_user)
            
            result = {
                'text': text,
                'description': description,
                'detected': detected,
                'expected': expected,
                'passed': detected == expected
            }
            
            if result['passed']:
                results['passed'] += 1
                print(f"✅ {description}: {'Detected' if detected else 'No detection'} in '{text}'")
            else:
                results['failed'] += 1
                print(f"❌ {description}: Expected {expected}, got {detected} for '{text}'")
                
            results['details'].append(result)
        
        return results
    
    def test_correction_parsing(self) -> Dict[str, Any]:
        """Test correction-context parsing"""
        print("\n📝 Testing Correction Parsing...")
        results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        now = datetime.now()
        
        # Test parsing in correction context
        correction_cases = [
            ("500", 500, "Bare number"),
            ("1.5k", 1500, "K shorthand"),  # Depends on normalization
            ("25.50", 25.50, "Decimal amount"),
            ("300", 300, "Integer amount")
        ]
        
        for text, expected_amount, description in correction_cases:
            try:
                parsed = parse_expense(text, now, correction_context=True)
                
                if parsed and parsed.get('amount'):
                    detected_amount = float(parsed['amount'])
                    passed = abs(detected_amount - expected_amount) < 0.01
                    
                    result = {
                        'text': text,
                        'description': description,
                        'parsed_amount': detected_amount,
                        'expected_amount': expected_amount,
                        'passed': passed,
                        'correction_context': parsed.get('correction_context', False)
                    }
                    
                    if passed:
                        results['passed'] += 1
                        print(f"✅ {description}: Parsed {detected_amount} from '{text}'")
                    else:
                        results['failed'] += 1
                        print(f"❌ {description}: Expected {expected_amount}, got {detected_amount}")
                else:
                    results['failed'] += 1
                    print(f"❌ {description}: Failed to parse '{text}'")
                    result = {
                        'text': text,
                        'description': description,
                        'parsed_amount': None,
                        'expected_amount': expected_amount,
                        'passed': False
                    }
                    
                results['details'].append(result)
                
            except Exception as e:
                results['failed'] += 1
                print(f"❌ {description}: Exception parsing '{text}': {e}")
        
        return results
    
    def test_reply_formatting(self) -> Dict[str, Any]:
        """Test correction reply formatting"""
        print("\n💬 Testing Reply Formatting...")
        results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        # Test correction reply formatting
        try:
            corrected_reply = format_corrected_reply(
                old_amount=100.0,
                old_currency='BDT',
                new_amount=500,
                new_currency='BDT',
                category='food',
                merchant='Starbucks'
            )
            
            # Check if reply contains expected elements
            required_elements = ['100', '500', 'food', '৳', '→']
            all_present = all(element in corrected_reply for element in required_elements)
            
            if all_present:
                results['passed'] += 1
                print(f"✅ Corrected reply: {corrected_reply}")
            else:
                results['failed'] += 1
                print(f"❌ Corrected reply missing elements: {corrected_reply}")
                
        except Exception as e:
            results['failed'] += 1
            print(f"❌ Error formatting corrected reply: {e}")
        
        # Test no candidate reply
        try:
            no_candidate_reply = format_correction_no_candidate_reply(
                amount=300,
                currency='BDT',
                category='transport'
            )
            
            required_elements = ['300', 'transport', '৳']
            all_present = all(element in no_candidate_reply for element in required_elements)
            
            if all_present:
                results['passed'] += 1
                print(f"✅ No candidate reply: {no_candidate_reply}")
            else:
                results['failed'] += 1
                print(f"❌ No candidate reply missing elements: {no_candidate_reply}")
                
        except Exception as e:
            results['failed'] += 1
            print(f"❌ Error formatting no candidate reply: {e}")
        
        return results
    
    def test_feature_flags(self) -> Dict[str, Any]:
        """Test feature flag system"""
        print("\n🚩 Testing Feature Flag System...")
        results = {
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        try:
            # Test feature flag check
            corrections_enabled = is_smart_corrections_enabled(self.test_user)
            
            result = {
                'user': self.test_user,
                'corrections_enabled': corrections_enabled,
                'expected': False,  # Default should be False
                'passed': corrections_enabled == False
            }
            
            if result['passed']:
                results['passed'] += 1
                print(f"✅ Feature flag: SMART_CORRECTIONS disabled by default")
            else:
                results['failed'] += 1
                print(f"❌ Feature flag: Expected disabled, got {corrections_enabled}")
                
            results['details'].append(result)
            
        except Exception as e:
            results['failed'] += 1
            print(f"❌ Error checking feature flags: {e}")
        
        return results
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        print("🧪 SMART_CORRECTIONS Development Simulation")
        print("=" * 50)
        
        start_time = time.time()
        
        # Run all tests
        detection_results = self.test_correction_detection()
        money_results = self.test_money_detection_fallback()
        parsing_results = self.test_correction_parsing()
        reply_results = self.test_reply_formatting()
        flag_results = self.test_feature_flags()
        
        # Aggregate results
        total_passed = (detection_results['passed'] + money_results['passed'] + 
                       parsing_results['passed'] + reply_results['passed'] + 
                       flag_results['passed'])
        total_failed = (detection_results['failed'] + money_results['failed'] + 
                       parsing_results['failed'] + reply_results['failed'] + 
                       flag_results['failed'])
        
        duration = time.time() - start_time
        
        # Summary report
        print("\n📊 Test Results Summary")
        print("=" * 30)
        print(f"✅ Passed: {total_passed}")
        print(f"❌ Failed: {total_failed}")
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"📈 Success Rate: {(total_passed / (total_passed + total_failed) * 100):.1f}%")
        
        if total_failed == 0:
            print("\n🎉 All tests passed! SMART_CORRECTIONS is ready for deployment.")
        else:
            print(f"\n⚠️  {total_failed} tests failed. Review issues before deployment.")
        
        return {
            'summary': {
                'passed': total_passed,
                'failed': total_failed,
                'duration_seconds': duration,
                'success_rate_percent': (total_passed / (total_passed + total_failed) * 100)
            },
            'detailed_results': {
                'correction_detection': detection_results,
                'money_detection_fallback': money_results,
                'correction_parsing': parsing_results,
                'reply_formatting': reply_results,
                'feature_flags': flag_results
            }
        }

def main():
    """Main entry point for development testing"""
    simulator = CorrectionSimulator()
    
    # Check if running individual tests
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
        if test_name == 'detection':
            simulator.test_correction_detection()
        elif test_name == 'money':
            simulator.test_money_detection_fallback()
        elif test_name == 'parsing':
            simulator.test_correction_parsing()
        elif test_name == 'replies':
            simulator.test_reply_formatting()
        elif test_name == 'flags':
            simulator.test_feature_flags()
        else:
            print(f"Unknown test: {test_name}")
            print("Available tests: detection, money, parsing, replies, flags")
    else:
        # Run comprehensive test suite
        results = simulator.run_comprehensive_test()
        
        # Save results to file for CI/CD
        with open('smart_corrections_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Exit with proper code
        sys.exit(0 if results['summary']['failed'] == 0 else 1)

if __name__ == '__main__':
    main()