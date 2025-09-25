#!/usr/bin/env python3
"""
Comprehensive Test Suite for Bengali Food Alias Enhancements
===========================================================

This script validates all Bengali food alias enhancements implemented in parsers/expense.py.
Tests cover the complete parsing pipeline to ensure all enhancements work together correctly.

Test Categories:
1. Vague token stoplist fix - Description inference overrides vague trailing tokens
2. Bengali script aliases - Native Bengali script food items 
3. Emoji aliases - Food emoji recognition
4. Morphology handling - Bengali suffix stripping and matching
5. ZWJ/ZWNJ normalization - Zero-width character cleanup
6. Word boundary prevention - No false positives from generic terms
7. Transliteration variants - Various spellings of Bengali food terms

Usage:
    python test_bengali_food_enhancements.py
"""

import os
import sys
from datetime import datetime
from decimal import Decimal

# Add the project root to the Python path so we can import parsers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from parsers.expense import extract_all_expenses, parse_expense
    print("✓ Successfully imported expense parser functions")
except ImportError as e:
    print(f"✗ Failed to import expense parser: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

class TestResult:
    """Container for individual test results"""
    def __init__(self, name, input_text, expected_category, actual_result, passed=False, notes=""):
        self.name = name
        self.input_text = input_text
        self.expected_category = expected_category
        self.actual_result = actual_result
        self.actual_category = actual_result.get('category') if actual_result else None
        self.actual_amount = actual_result.get('amount') if actual_result else None
        self.passed = passed
        self.notes = notes

    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        amount_info = f" | Amount: {self.actual_amount}" if self.actual_amount else ""
        notes_info = f" | Notes: {self.notes}" if self.notes else ""
        return f"{status} | {self.name} | Input: '{self.input_text}' | Expected: {self.expected_category} | Got: {self.actual_category}{amount_info}{notes_info}"

class BengaliFoodEnhancementTester:
    """Comprehensive tester for Bengali food alias enhancements"""
    
    def __init__(self):
        self.test_results = []
        self.now = datetime.now()
    
    def run_test(self, name, input_text, expected_category, expected_amount=None, notes=""):
        """Run a single test case and record the result"""
        try:
            # Test the complete parsing pipeline
            result = parse_expense(input_text, self.now)
            
            if result is None:
                passed = expected_category is None
                test_result = TestResult(name, input_text, expected_category, None, passed, 
                                       notes or "No expense parsed")
            else:
                actual_category = result.get('category')
                actual_amount = result.get('amount')
                
                # Check category match (primary criteria)
                category_match = actual_category == expected_category
                
                # Check amount match if specified
                amount_match = True
                if expected_amount is not None:
                    amount_match = actual_amount == Decimal(str(expected_amount))
                
                passed = category_match and amount_match
                
                # Add helpful notes
                if not category_match and not notes:
                    notes = f"Category mismatch: expected {expected_category}, got {actual_category}"
                if expected_amount and not amount_match and not notes:
                    notes = f"Amount mismatch: expected {expected_amount}, got {actual_amount}"
                
                test_result = TestResult(name, input_text, expected_category, result, passed, notes)
            
            self.test_results.append(test_result)
            return test_result
            
        except Exception as e:
            test_result = TestResult(name, input_text, expected_category, None, False, f"Exception: {e}")
            self.test_results.append(test_result)
            return test_result
    
    def test_vague_token_stoplist_fix(self):
        """Test that description inference overrides vague trailing tokens"""
        print("\n" + "="*60)
        print("1. TESTING: Vague Token Stoplist Fix")
        print("="*60)
        print("Testing that food aliases beat vague trailing tokens like 'general', 'misc'")
        
        # Test cases where food aliases should beat vague tokens
        self.run_test(
            "Coffee with vague 'general'", 
            "Coffee 120 general", 
            "food",
            120,
            "coffee alias (strength 9) should beat vague 'general'"
        )
        
        self.run_test(
            "Biryani with vague 'misc'", 
            "Biryani 250 misc", 
            "food",
            250,
            "biryani alias (strength 10) should beat vague 'misc'"
        )
        
        # Test case where no description hits, should remain uncategorized
        self.run_test(
            "Generic with vague 'general'", 
            "Something 120 general", 
            "uncategorized",
            120,
            "No food alias hit, should remain uncategorized"
        )
        
        # Additional vague token tests
        self.run_test(
            "Tea with vague 'miscellaneous'", 
            "Tea 80 miscellaneous", 
            "food",
            80,
            "tea alias should beat vague 'miscellaneous'"
        )

    def test_bengali_script_aliases(self):
        """Test Bengali script food aliases"""
        print("\n" + "="*60)
        print("2. TESTING: Bengali Script Food Aliases")
        print("="*60)
        print("Testing native Bengali script food terms with Bengali numerals")
        
        # Critical Bengali food terms that were mentioned as missing
        self.run_test(
            "Bengali kachchi", 
            "কাচ্চি ৩৫০", 
            "food",
            350,
            "কাচ্চি (kachchi) is a key Bengali food term"
        )
        
        self.run_test(
            "Bengali biryani", 
            "বিরিয়ানি ২৫০", 
            "food",
            250,
            "বিরিয়ানি (biryani) in Bengali script"
        )
        
        self.run_test(
            "Bengali coffee", 
            "কফি ১২০", 
            "food",
            120,
            "কফি (coffee) - critical for 'Coffee 120 general' fix"
        )
        
        self.run_test(
            "Bengali tea", 
            "চা ৫০", 
            "food",
            50,
            "চা (tea) basic Bengali beverage"
        )
        
        # Additional Bengali food terms
        self.run_test(
            "Bengali bharta", 
            "ভর্তা ৮০", 
            "food",
            80,
            "ভর্তা (bharta) traditional Bengali dish"
        )
        
        self.run_test(
            "Bengali haleem", 
            "হালিম ১৫০", 
            "food",
            150,
            "হালিম (haleem) Bengali street food"
        )

    def test_emoji_aliases(self):
        """Test emoji food aliases"""
        print("\n" + "="*60)
        print("3. TESTING: Emoji Food Aliases")  
        print("="*60)
        print("Testing food emoji recognition in modern user inputs")
        
        # Core food emojis that should be recognized
        self.run_test(
            "Coffee emoji", 
            "☕ 120", 
            "food",
            120,
            "☕ coffee emoji should be recognized as food"
        )
        
        self.run_test(
            "Burger emoji", 
            "🍔 350", 
            "food",
            350,
            "🍔 burger emoji should be recognized as food"
        )
        
        self.run_test(
            "Curry emoji", 
            "🍛 250", 
            "food",
            250,
            "🍛 curry emoji good for Bengali context"
        )
        
        # Additional emoji tests
        self.run_test(
            "Pizza emoji", 
            "🍕 400", 
            "food",
            400,
            "🍕 pizza emoji should be food"
        )
        
        self.run_test(
            "Tea emoji", 
            "🍵 75", 
            "food",
            75,
            "🍵 tea cup emoji should be food"
        )

    def test_morphology_handling(self):
        """Test Bengali morphological suffix handling"""
        print("\n" + "="*60)
        print("4. TESTING: Bengali Morphology Handling")
        print("="*60)
        print("Testing Bengali suffix stripping for proper word matching")
        
        # Test plural marker 'গুলো'
        self.run_test(
            "Biryani with plural marker", 
            "বিরিয়ানিগুলো ৩৫০", 
            "food",
            350,
            "বিরিয়ানিগুলো → বিরিয়ানি (strip গুলো suffix)"
        )
        
        # Test counter/quantifier 'টা' 
        self.run_test(
            "Bharta with quantifier", 
            "ভর্তাটা ১২০", 
            "food",
            120,
            "ভর্তাটা → ভর্তা (strip টা suffix)"
        )
        
        # Test postposition 'তে'
        self.run_test(
            "Coffee with postposition", 
            "কফিতে ১০০", 
            "food",
            100,
            "কফিতে → কফি (strip তে suffix)"
        )
        
        # Test phonological change with genitive 'এর'
        self.run_test(
            "Tea with genitive", 
            "চায়ের ৫০", 
            "food",
            50,
            "চায়ের → চা (handle phonological change য় + এর)"
        )
        
        # Additional morphology tests
        self.run_test(
            "Kachchi with plural", 
            "কাচ্চিগুলো ৪০০", 
            "food",
            400,
            "কাচ্চিগুলো → কাচ্চি (strip গুলো)"
        )

    def test_zwj_zwnj_normalization(self):
        """Test Zero Width Joiner/Non-Joiner normalization"""
        print("\n" + "="*60)
        print("5. TESTING: ZWJ/ZWNJ Normalization")
        print("="*60)
        print("Testing zero-width character cleanup for proper matching")
        
        # Test with Zero Width Joiner (ZWJ) - \u200D
        self.run_test(
            "Biryani with ZWJ", 
            "বিরি‌য়ানি ২০০", 
            "food",
            200,
            "বিরি‌য়ানি contains ZWJ, should normalize to match বিরিয়ানি"
        )
        
        # Test with Zero Width Non-Joiner (ZWNJ) - \u200C  
        self.run_test(
            "Haleem with ZWNJ", 
            "হা‌লিম ১৫০", 
            "food",
            150,
            "হা‌লিম contains ZWNJ, should normalize to match হালিম"
        )
        
        # Test mixed ZWJ/ZWNJ characters
        self.run_test(
            "Coffee with zero-width chars", 
            "ক‌ফি ৯০", 
            "food",
            90,
            "ক‌ফি with ZWNJ should normalize to match কফি"
        )

    def test_word_boundary_prevention(self):
        """Test that generic terms don't create false positives"""
        print("\n" + "="*60)
        print("6. TESTING: Word Boundary Prevention")
        print("="*60)
        print("Testing that generic terms don't falsely match food aliases")
        
        # Test that substring matches don't trigger false positives
        self.run_test(
            "No false positive for substring", 
            "Uncoffee shop 150", 
            "uncategorized",
            150,
            "Should not match 'coffee' within 'uncoffee'"
        )
        
        # Test normal non-food expenses remain uncategorized
        self.run_test(
            "Generic item", 
            "Something random 200", 
            "uncategorized",
            200,
            "Generic item should remain uncategorized"
        )
        
        # Test that proper word boundaries work for legitimate food terms
        self.run_test(
            "Proper coffee word boundary", 
            "bought coffee 100", 
            "food",
            100,
            "Real 'coffee' word should match properly"
        )

    def test_transliteration_variants(self):
        """Test various transliterations of Bengali food terms"""
        print("\n" + "="*60)
        print("7. TESTING: Transliteration Variants")
        print("="*60)
        print("Testing various English spellings of Bengali food terms")
        
        # Test specific terms mentioned in user issues
        self.run_test(
            "Beef bhuna variant", 
            "beef-bhuna 220", 
            "food",
            220,
            "beef-bhuna (hyphenated) should be recognized"
        )
        
        self.run_test(
            "Morog polao", 
            "morog polao 300", 
            "food",
            300,
            "morog polao (chicken polao) popular Bengali dish"
        )
        
        self.run_test(
            "Short kachchi", 
            "kachchi 400", 
            "food",
            400,
            "kachchi (short for kacchi biryani) critical term"
        )
        
        # Additional transliteration tests
        self.run_test(
            "Biryani spelling variant", 
            "biriyani 350", 
            "food",
            350,
            "biriyani alternative spelling"
        )
        
        self.run_test(
            "Tehari spelling", 
            "tehari 280", 
            "food",
            280,
            "tehari (Bengali rice dish)"
        )

    def run_all_tests(self):
        """Run all test categories and generate comprehensive report"""
        print("BENGALI FOOD ALIAS ENHANCEMENTS - COMPREHENSIVE TEST SUITE")
        print("=" * 70)
        print("Testing complete parsing pipeline with all Bengali food enhancements")
        
        # Run all test categories
        self.test_vague_token_stoplist_fix()
        self.test_bengali_script_aliases()
        self.test_emoji_aliases()
        self.test_morphology_handling()
        self.test_zwj_zwnj_normalization()
        self.test_word_boundary_prevention()
        self.test_transliteration_variants()
        
        # Generate comprehensive report
        self.generate_final_report()
    
    def generate_final_report(self):
        """Generate final test report with statistics and details"""
        print("\n" + "="*70)
        print("FINAL TEST REPORT")
        print("="*70)
        
        # Calculate statistics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for t in self.test_results if t.passed)
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Show all test results
        print("\nDETAILED TEST RESULTS:")
        print("-" * 70)
        for result in self.test_results:
            print(result)
        
        # Show failed tests summary
        failed_tests_list = [t for t in self.test_results if not t.passed]
        if failed_tests_list:
            print(f"\nFAILED TESTS SUMMARY ({len(failed_tests_list)} failures):")
            print("-" * 70)
            for result in failed_tests_list:
                print(f"✗ {result.name}: {result.input_text} → Expected: {result.expected_category}, Got: {result.actual_category}")
                if result.notes:
                    print(f"  Notes: {result.notes}")
        else:
            print("\n🎉 ALL TESTS PASSED! Bengali food alias enhancements are working correctly.")
        
        # Critical enhancements status
        print("\nCRITICAL ENHANCEMENTS STATUS:")
        print("-" * 70)
        critical_tests = {
            "Vague token override": ["Coffee with vague 'general'", "Biryani with vague 'misc'"],
            "Bengali script support": ["Bengali kachchi", "Bengali coffee", "Bengali tea"],
            "Emoji recognition": ["Coffee emoji", "Burger emoji"],
            "Morphology handling": ["Biryani with plural marker", "Coffee with postposition"],
            "ZWJ normalization": ["Biryani with ZWJ", "Haleem with ZWNJ"],
            "Transliteration variants": ["Short kachchi", "Morog polao"]
        }
        
        for enhancement, test_names in critical_tests.items():
            enhancement_results = [t for t in self.test_results if t.name in test_names]
            enhancement_passed = all(t.passed for t in enhancement_results)
            status = "✓ WORKING" if enhancement_passed else "✗ ISSUES"
            print(f"{status} | {enhancement}")
        
        return success_rate >= 80  # Return True if 80% or more tests pass


def main():
    """Main function to run all tests"""
    print("Starting Bengali Food Alias Enhancement Tests...")
    print("Testing complete parsing pipeline with real expense inputs\n")
    
    tester = BengaliFoodEnhancementTester()
    success = tester.run_all_tests()
    
    print(f"\nTest run completed. {'SUCCESS' if success else 'NEEDS ATTENTION'}")
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())