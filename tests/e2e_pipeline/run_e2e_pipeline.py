"""
E2E Pipeline Test Runner

Comprehensive test runner for the complete end-to-end expense data pipeline.
Executes all test modules in the correct order and provides detailed reporting.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List


class E2EPipelineRunner:
    """Main runner for E2E pipeline tests"""
    
    def __init__(self):
        self.test_modules = [
            'test_chat_path',
            'test_form_path', 
            'test_messenger_path',
            'test_totals_verification',
            'test_recent_expenses',
            'test_idempotency',
            'test_user_isolation',
            'test_audit_trail',
            'test_ci_cd_integration'
        ]
        self.results = {}
        self.start_time = None
        self.end_time = None

    def run_all_tests(self, verbose: bool = True, stop_on_failure: bool = False) -> dict[str, Any]:
        """Run all E2E pipeline tests"""
        self.start_time = datetime.now()
        
        print("🚀 Starting E2E Pipeline Test Suite")
        print("=" * 60)
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Test modules: {len(self.test_modules)}")
        print("=" * 60)
        
        overall_success = True
        
        for i, module in enumerate(self.test_modules, 1):
            print(f"\n📝 [{i}/{len(self.test_modules)}] Running {module}...")
            
            result = self._run_test_module(module, verbose)
            self.results[module] = result
            
            if result['success']:
                print(f"✅ {module} PASSED ({result['duration']:.2f}s)")
            else:
                print(f"❌ {module} FAILED ({result['duration']:.2f}s)")
                if verbose and result.get('errors'):
                    print(f"   Errors: {result['errors']}")
                
                overall_success = False
                if stop_on_failure:
                    print("\n🛑 Stopping on first failure")
                    break
        
        self.end_time = datetime.now()
        
        # Generate summary report
        self._generate_summary_report(overall_success)
        
        return {
            'success': overall_success,
            'results': self.results,
            'duration': (self.end_time - self.start_time).total_seconds(),
            'start_time': self.start_time.isoformat() if self.start_time else '',
            'end_time': self.end_time.isoformat() if self.end_time else ''
        }

    def _run_test_module(self, module: str, verbose: bool) -> dict[str, Any]:
        """Run individual test module"""
        module_path = f"tests.e2e_pipeline.{module}"
        start_time = time.time()
        
        try:
            # Run pytest for specific module
            cmd = [
                'python', '-m', 'pytest',
                f"tests/e2e_pipeline/{module}.py",
                '-v' if verbose else '-q',
                '--tb=short',
                '--json-report',
                f'--json-report-file=/tmp/e2e_report_{module}.json'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per module
            )
            
            duration = time.time() - start_time
            
            # Parse JSON report if available
            report_file = f'/tmp/e2e_report_{module}.json'
            test_details = {}
            
            if os.path.exists(report_file):
                try:
                    with open(report_file) as f:
                        report_data = json.load(f)
                        test_details = {
                            'tests_collected': report_data.get('summary', {}).get('collected', 0),
                            'tests_passed': report_data.get('summary', {}).get('passed', 0),
                            'tests_failed': report_data.get('summary', {}).get('failed', 0),
                            'tests_skipped': report_data.get('summary', {}).get('skipped', 0)
                        }
                except Exception:
                    pass
            
            return {
                'success': result.returncode == 0,
                'duration': duration,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'errors': result.stderr if result.returncode != 0 else None,
                'test_details': test_details
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'duration': time.time() - start_time,
                'return_code': -1,
                'errors': 'Test module timed out after 5 minutes',
                'test_details': {}
            }
        except Exception as e:
            return {
                'success': False,
                'duration': time.time() - start_time,
                'return_code': -1,
                'errors': str(e),
                'test_details': {}
            }

    def _generate_summary_report(self, overall_success: bool):
        """Generate comprehensive summary report"""
        total_duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        print("\n" + "=" * 60)
        print("📊 E2E PIPELINE TEST SUMMARY")
        print("=" * 60)
        
        print(f"Overall Result: {'✅ PASSED' if overall_success else '❌ FAILED'}")
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Modules Tested: {len(self.test_modules)}")
        
        # Module breakdown
        passed_modules = [m for m, r in self.results.items() if r['success']]
        failed_modules = [m for m, r in self.results.items() if not r['success']]
        
        print(f"Modules Passed: {len(passed_modules)}")
        print(f"Modules Failed: {len(failed_modules)}")
        
        if failed_modules:
            print("\n❌ Failed Modules:")
            for module in failed_modules:
                result = self.results[module]
                print(f"  - {module} ({result['duration']:.2f}s)")
                if result.get('errors'):
                    error_lines = result['errors'].strip().split('\n')
                    for line in error_lines[:3]:  # Show first 3 error lines
                        print(f"    {line}")
                    if len(error_lines) > 3:
                        print(f"    ... ({len(error_lines) - 3} more lines)")
        
        # Test statistics
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        
        for result in self.results.values():
            details = result.get('test_details', {})
            total_tests += details.get('tests_collected', 0)
            total_passed += details.get('tests_passed', 0)
            total_failed += details.get('tests_failed', 0)
            total_skipped += details.get('tests_skipped', 0)
        
        if total_tests > 0:
            print("\n📋 Test Statistics:")
            print(f"  Total Tests: {total_tests}")
            print(f"  Passed: {total_passed}")
            print(f"  Failed: {total_failed}")
            print(f"  Skipped: {total_skipped}")
            print(f"  Success Rate: {(total_passed / total_tests * 100):.1f}%")
        
        # Coverage summary
        print("\n🎯 Coverage Summary:")
        coverage_areas = [
            ("Chat Path", "test_chat_path"),
            ("Form Path", "test_form_path"),
            ("Messenger Path", "test_messenger_path"),
            ("Totals Verification", "test_totals_verification"),
            ("Recent Expenses", "test_recent_expenses"),
            ("Idempotency", "test_idempotency"),
            ("User Isolation (IDOR)", "test_user_isolation"),
            ("Audit Trail", "test_audit_trail"),
            ("CI/CD Integration", "test_ci_cd_integration")
        ]
        
        for area, module in coverage_areas:
            status = "✅" if self.results.get(module, {}).get('success') else "❌"
            print(f"  {status} {area}")
        
        # Generate report file
        report_data = {
            'overall_success': overall_success,
            'total_duration': total_duration,
            'start_time': self.start_time.isoformat() if self.start_time else '',
            'end_time': self.end_time.isoformat() if self.end_time else '',
            'modules': self.results,
            'summary': {
                'total_modules': len(self.test_modules),
                'passed_modules': len(passed_modules),
                'failed_modules': len(failed_modules),
                'total_tests': total_tests,
                'passed_tests': total_passed,
                'failed_tests': total_failed,
                'skipped_tests': total_skipped
            }
        }
        
        report_file = f'/tmp/e2e_pipeline_report_{int(time.time())}.json'
        try:
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)
            print(f"\n📄 Detailed report saved to: {report_file}")
        except Exception as e:
            print(f"\n⚠️  Could not save report: {e}")
        
        print("=" * 60)

    def run_specific_modules(self, modules: list[str], verbose: bool = True) -> dict[str, Any]:
        """Run specific test modules"""
        if not modules:
            print("No modules specified")
            return {'success': False, 'results': {}}
        
        # Validate module names
        invalid_modules = [m for m in modules if m not in self.test_modules]
        if invalid_modules:
            print(f"Invalid modules: {invalid_modules}")
            print(f"Available modules: {self.test_modules}")
            return {'success': False, 'results': {}}
        
        self.start_time = datetime.now()
        
        print(f"🚀 Running specific E2E modules: {', '.join(modules)}")
        print("=" * 60)
        
        overall_success = True
        
        for i, module in enumerate(modules, 1):
            print(f"\n📝 [{i}/{len(modules)}] Running {module}...")
            
            result = self._run_test_module(module, verbose)
            self.results[module] = result
            
            if result['success']:
                print(f"✅ {module} PASSED ({result['duration']:.2f}s)")
            else:
                print(f"❌ {module} FAILED ({result['duration']:.2f}s)")
                overall_success = False
        
        self.end_time = datetime.now()
        self._generate_summary_report(overall_success)
        
        return {
            'success': overall_success,
            'results': self.results,
            'duration': (self.end_time - self.start_time).total_seconds()
        }


def main():
    """Main entry point for E2E pipeline runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='E2E Pipeline Test Runner')
    parser.add_argument('--modules', nargs='+', help='Specific modules to run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--stop-on-failure', action='store_true', help='Stop on first failure')
    parser.add_argument('--list-modules', action='store_true', help='List available modules')
    
    args = parser.parse_args()
    
    runner = E2EPipelineRunner()
    
    if args.list_modules:
        print("Available E2E test modules:")
        for module in runner.test_modules:
            print(f"  - {module}")
        return
    
    try:
        if args.modules:
            result = runner.run_specific_modules(args.modules, args.verbose)
        else:
            result = runner.run_all_tests(args.verbose, args.stop_on_failure)
        
        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Test runner error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()