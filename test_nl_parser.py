#!/usr/bin/env python3
"""
Natural Language Parser Test Runner
Validates Phase E implementation against comprehensive test set
Target: 90%+ accuracy, <10% fallback rate
"""

import csv
import json
import sys
from typing import Dict, List, Tuple
from datetime import datetime

# Import our implementation
from utils.nl_expense_parser import parse_nl_expense, ExpenseParseResult

class NLParserTester:
    """Test runner for natural language expense parser"""
    
    def __init__(self, test_file: str = "docs/nl-test-set.csv"):
        self.test_file = test_file
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        
    def load_test_cases(self) -> List[Dict]:
        """Load test cases from CSV file"""
        test_cases = []
        with open(self.test_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                test_cases.append(row)
        return test_cases
    
    def run_single_test(self, test_case: Dict) -> Dict:
        """Run a single test case and evaluate results"""
        input_text = test_case['input_text']
        expected_amount = float(test_case['expected_amount']) if test_case['expected_amount'].replace('.', '').isdigit() else 0
        expected_category = test_case['expected_category']
        expected_language = test_case['language']
        
        # Parse with our implementation
        result = parse_nl_expense(input_text, "test_user")
        
        # Evaluate results
        scores = {
            'intent_recognition': 1.0 if result.success else 0.0,
            'amount_accuracy': self._score_amount(result.amount, expected_amount),
            'category_accuracy': self._score_category(result.category, expected_category),
            'language_detection': self._score_language(result.language, expected_language),
            'confidence_calibration': self._score_confidence(result.confidence, result.success, expected_amount > 0)
        }
        
        overall_score = sum(scores.values()) / len(scores)
        
        return {
            'test_id': test_case.get('id', ''),
            'input_text': input_text,
            'expected': {
                'amount': expected_amount,
                'category': expected_category,
                'language': expected_language
            },
            'actual': {
                'amount': result.amount,
                'category': result.category,
                'language': result.language,
                'confidence': result.confidence,
                'needs_clarification': result.needs_clarification
            },
            'scores': scores,
            'overall_score': overall_score,
            'passed': overall_score >= 0.8,  # 80% threshold for individual test
            'notes': test_case.get('notes', ''),
            'is_edge_case': test_case.get('is_edge_case', 'false').lower() == 'true'
        }
    
    def _score_amount(self, actual: float, expected: float) -> float:
        """Score amount extraction accuracy"""
        if expected == 0:
            # For low-confidence cases where no amount is expected
            return 1.0 if actual is None or actual == 0 else 0.5
        
        if actual is None or actual == 0:
            return 0.0
        
        # Calculate percentage difference
        diff_pct = abs(actual - expected) / expected * 100
        
        if diff_pct == 0:
            return 1.0
        elif diff_pct <= 5:
            return 0.8
        elif diff_pct <= 20:
            return 0.5
        else:
            return 0.0
    
    def _score_category(self, actual: str, expected: str) -> float:
        """Score category classification accuracy"""
        if actual == expected:
            return 1.0
        
        # Related categories get partial credit
        related_categories = {
            'food': ['other'],
            'transport': ['other'],
            'shopping': ['other'],
            'bills': ['other'],
            'health': ['other'],
            'education': ['other'],
            'entertainment': ['food', 'other'],
            'other': []
        }
        
        if actual in related_categories.get(expected, []):
            return 0.5
        
        return 0.0
    
    def _score_language(self, actual: str, expected: str) -> float:
        """Score language detection accuracy"""
        if actual == expected:
            return 1.0
        
        # Partial credit for mixed language detection
        if expected == 'mixed' and actual in ['bangla', 'english']:
            return 0.5
        
        return 0.0
    
    def _score_confidence(self, confidence: float, success: bool, has_amount: bool) -> float:
        """Score confidence calibration"""
        if success and has_amount and confidence >= 0.8:
            return 1.0  # High confidence with correct results
        elif success and has_amount and confidence >= 0.6:
            return 0.8  # Medium confidence with correct results
        elif not has_amount and confidence < 0.6:
            return 0.6  # Correctly identified low confidence case
        elif confidence >= 0.8 and not success:
            return 0.0  # Overconfident on wrong results
        else:
            return 0.4  # Reasonable but not optimal
    
    def run_all_tests(self) -> Dict:
        """Run all test cases and generate comprehensive report"""
        print("🧪 Starting Natural Language Parser Test Suite...")
        print("=" * 60)
        
        test_cases = self.load_test_cases()
        self.total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Running test {i}/{self.total_tests}: {test_case['input_text'][:50]}...")
            
            result = self.run_single_test(test_case)
            self.results.append(result)
            
            if result['passed']:
                self.passed_tests += 1
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
            
            print(f"  {status} (Score: {result['overall_score']:.2f})")
            
        return self._generate_report()
    
    def _generate_report(self) -> Dict:
        """Generate comprehensive test report"""
        # Calculate overall metrics
        overall_accuracy = (self.passed_tests / self.total_tests) * 100
        
        # Calculate specific metrics
        amount_scores = [r['scores']['amount_accuracy'] for r in self.results]
        category_scores = [r['scores']['category_accuracy'] for r in self.results]
        language_scores = [r['scores']['language_detection'] for r in self.results]
        confidence_scores = [r['scores']['confidence_calibration'] for r in self.results]
        
        amount_accuracy = (sum(amount_scores) / len(amount_scores)) * 100
        category_accuracy = (sum(category_scores) / len(category_scores)) * 100
        language_accuracy = (sum(language_scores) / len(language_scores)) * 100
        confidence_accuracy = (sum(confidence_scores) / len(confidence_scores)) * 100
        
        # Calculate fallback rate
        clarification_needed = sum(1 for r in self.results if r['actual']['needs_clarification'])
        fallback_rate = (clarification_needed / self.total_tests) * 100
        
        # Performance by language
        bangla_results = [r for r in self.results if r['expected']['language'] == 'bangla']
        english_results = [r for r in self.results if r['expected']['language'] == 'english']
        mixed_results = [r for r in self.results if r['expected']['language'] == 'mixed']
        
        bangla_accuracy = (sum(1 for r in bangla_results if r['passed']) / len(bangla_results)) * 100 if bangla_results else 0
        english_accuracy = (sum(1 for r in english_results if r['passed']) / len(english_results)) * 100 if english_results else 0
        mixed_accuracy = (sum(1 for r in mixed_results if r['passed']) / len(mixed_results)) * 100 if mixed_results else 0
        
        # Failed cases analysis
        failed_cases = [r for r in self.results if not r['passed']]
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': self.total_tests,
                'passed_tests': self.passed_tests,
                'overall_accuracy': overall_accuracy,
                'amount_accuracy': amount_accuracy,
                'category_accuracy': category_accuracy,
                'language_accuracy': language_accuracy,
                'confidence_accuracy': confidence_accuracy,
                'fallback_rate': fallback_rate
            },
            'language_performance': {
                'bangla_accuracy': bangla_accuracy,
                'english_accuracy': english_accuracy,
                'mixed_accuracy': mixed_accuracy
            },
            'target_achievement': {
                'overall_target_met': overall_accuracy >= 90,
                'amount_target_met': amount_accuracy >= 95,
                'category_target_met': category_accuracy >= 85,
                'language_target_met': language_accuracy >= 95,
                'confidence_target_met': confidence_accuracy >= 80,
                'fallback_target_met': fallback_rate < 10
            },
            'failed_cases': len(failed_cases),
            'detailed_results': self.results
        }
        
        return report
    
    def print_summary(self, report: Dict):
        """Print human-readable test summary"""
        print("\n" + "=" * 60)
        print("🎯 NATURAL LANGUAGE PARSER TEST RESULTS")
        print("=" * 60)
        
        summary = report['summary']
        targets = report['target_achievement']
        
        print(f"📊 OVERALL PERFORMANCE")
        print(f"   Tests Passed: {summary['passed_tests']}/{summary['total_tests']} ({summary['overall_accuracy']:.1f}%)")
        print(f"   Target Met: {'✅ YES' if targets['overall_target_met'] else '❌ NO'} (≥90% required)")
        
        print(f"\n📏 DETAILED METRICS")
        print(f"   Amount Extraction: {summary['amount_accuracy']:.1f}% {'✅' if targets['amount_target_met'] else '❌'} (≥95% required)")
        print(f"   Category Classification: {summary['category_accuracy']:.1f}% {'✅' if targets['category_target_met'] else '❌'} (≥85% required)")
        print(f"   Language Detection: {summary['language_accuracy']:.1f}% {'✅' if targets['language_target_met'] else '❌'} (≥95% required)")
        print(f"   Confidence Calibration: {summary['confidence_accuracy']:.1f}% {'✅' if targets['confidence_target_met'] else '❌'} (≥80% required)")
        print(f"   Fallback Rate: {summary['fallback_rate']:.1f}% {'✅' if targets['fallback_target_met'] else '❌'} (<10% required)")
        
        print(f"\n🌐 LANGUAGE PERFORMANCE")
        lang_perf = report['language_performance']
        print(f"   Bangla: {lang_perf['bangla_accuracy']:.1f}%")
        print(f"   English: {lang_perf['english_accuracy']:.1f}%")
        print(f"   Mixed: {lang_perf['mixed_accuracy']:.1f}%")
        
        if report['failed_cases'] > 0:
            print(f"\n❌ FAILED CASES: {report['failed_cases']}")
            failed = [r for r in report['detailed_results'] if not r['passed']]
            for i, case in enumerate(failed[:5], 1):  # Show first 5 failures
                print(f"   {i}. \"{case['input_text'][:40]}...\" (Score: {case['overall_score']:.2f})")
        
        # Production readiness assessment
        all_targets_met = all(targets.values())
        print(f"\n🚀 PRODUCTION READINESS")
        print(f"   Status: {'✅ READY' if all_targets_met else '❌ NOT READY'}")
        print(f"   Recommendation: {'Deploy to production' if all_targets_met else 'Requires improvement before deployment'}")

def main():
    """Main test execution"""
    tester = NLParserTester()
    
    try:
        report = tester.run_all_tests()
        tester.print_summary(report)
        
        # Save detailed report
        with open('test_results.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed results saved to: test_results.json")
        
        # Exit with appropriate code
        all_targets_met = all(report['target_achievement'].values())
        sys.exit(0 if all_targets_met else 1)
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()