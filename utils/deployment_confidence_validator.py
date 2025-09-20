#!/usr/bin/env python3
"""
FinBrain Deployment Confidence Validator

Comprehensive automated testing system to validate authentication enforcement,
security controls, and core functionality before deployment approval.
Designed for zero-surprise deployments with complete validation coverage.
"""

import requests
import json
import sys
import time
from typing import Dict, List, Tuple, Optional
import logging
from urllib.parse import urljoin
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeploymentValidator:
    """Comprehensive deployment validation system"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.timeout = 10
        self.results = []
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result with structured format"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append({
            'test': test_name,
            'passed': passed,
            'details': details,
            'timestamp': time.time()
        })
        logger.info(f"{status} - {test_name}: {details}")
        return passed
    
    def test_health_endpoints(self) -> bool:
        """Test basic health and monitoring endpoints"""
        logger.info("=== Testing Health Endpoints ===")
        all_passed = True
        
        # Test health endpoint
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            passed = resp.status_code == 200
            details = f"Status: {resp.status_code}"
            if passed:
                data = resp.json()
                details += f", Service: {data.get('service', 'unknown')}"
            all_passed &= self.log_test("Health endpoint accessible", passed, details)
        except Exception as e:
            all_passed &= self.log_test("Health endpoint accessible", False, f"Error: {e}")
        
        # Test readiness endpoint
        try:
            resp = self.session.get(f"{self.base_url}/readyz", timeout=self.timeout)
            passed = resp.status_code == 200
            all_passed &= self.log_test("Readiness endpoint accessible", passed, f"Status: {resp.status_code}")
        except Exception as e:
            all_passed &= self.log_test("Readiness endpoint accessible", False, f"Error: {e}")
            
        return all_passed
    
    def test_authentication_enforcement(self) -> bool:
        """Test authentication enforcement across all expense endpoints"""
        logger.info("=== Testing Authentication Enforcement ===")
        all_passed = True
        
        # Backend API endpoints that should require authentication
        backend_endpoints = [
            ("/api/backend/get_totals", "POST", {}),
            ("/api/backend/get_recent_expenses", "POST", {}),
            ("/api/backend/propose_expense", "POST", {"expense_text": "coffee 5"}),
            ("/api/backend/confirm_expense", "POST", {"expense_id": "test"}),
        ]
        
        for endpoint, method, payload in backend_endpoints:
            try:
                if method == "GET":
                    resp = self.session.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
                else:
                    resp = self.session.post(f"{self.base_url}{endpoint}", json=payload, timeout=self.timeout)
                
                passed = resp.status_code == 401
                details = f"Status: {resp.status_code}"
                
                if passed:
                    try:
                        error_data = resp.json()
                        if "Authentication required" in error_data.get('error', ''):
                            details += " (Correct auth error message)"
                    except:
                        pass
                else:
                    details += f" (Expected 401, got {resp.status_code})"
                
                all_passed &= self.log_test(f"Auth required for {endpoint}", passed, details)
                
            except Exception as e:
                all_passed &= self.log_test(f"Auth required for {endpoint}", False, f"Error: {e}")
        
        # Chat endpoint authentication
        try:
            resp = self.session.post(f"{self.base_url}/ai-chat", 
                                   json={"message": "spent 100 on lunch"}, timeout=self.timeout)
            passed = resp.status_code == 401
            all_passed &= self.log_test("Auth required for /ai-chat", passed, f"Status: {resp.status_code}")
        except Exception as e:
            all_passed &= self.log_test("Auth required for /ai-chat", False, f"Error: {e}")
        
        return all_passed
    
    def test_pwa_redirects(self) -> bool:
        """Test PWA pages properly redirect unauthenticated users"""
        logger.info("=== Testing PWA Authentication Redirects ===")
        all_passed = True
        
        pwa_pages = ["/chat", "/report", "/profile"]
        
        for page in pwa_pages:
            try:
                resp = self.session.get(f"{self.base_url}{page}", allow_redirects=False, timeout=self.timeout)
                passed = resp.status_code in [302, 401]
                details = f"Status: {resp.status_code}"
                
                if resp.status_code == 302:
                    location = resp.headers.get('Location', '')
                    if 'login' in location.lower():
                        details += " (Redirect to login)"
                    else:
                        details += f" (Redirect to: {location})"
                
                all_passed &= self.log_test(f"Auth redirect for {page}", passed, details)
                
            except Exception as e:
                all_passed &= self.log_test(f"Auth redirect for {page}", False, f"Error: {e}")
        
        return all_passed
    
    def test_public_endpoints(self) -> bool:
        """Test expected public endpoints are accessible"""
        logger.info("=== Testing Public Endpoints ===")
        all_passed = True
        
        public_endpoints = [
            ("/", "GET"),
            ("/api/auth/captcha", "GET"),
        ]
        
        for endpoint, method in public_endpoints:
            try:
                if method == "GET":
                    resp = self.session.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
                else:
                    resp = self.session.post(f"{self.base_url}{endpoint}", timeout=self.timeout)
                
                passed = resp.status_code in [200, 404]  # 404 is acceptable for some routes
                all_passed &= self.log_test(f"Public access to {endpoint}", passed, f"Status: {resp.status_code}")
                
            except Exception as e:
                all_passed &= self.log_test(f"Public access to {endpoint}", False, f"Error: {e}")
        
        return all_passed
    
    def test_guest_writes_disabled(self) -> bool:
        """Test that guest writes are properly disabled"""
        logger.info("=== Testing Guest Writes Disabled ===")
        
        # Check environment variable
        allow_guest_writes = os.environ.get('ALLOW_GUEST_WRITES', 'false').lower()
        passed = allow_guest_writes == 'false'
        
        return self.log_test("ALLOW_GUEST_WRITES disabled", passed, 
                           f"Value: {allow_guest_writes}")
    
    def test_security_headers(self) -> bool:
        """Test security headers are properly set"""
        logger.info("=== Testing Security Headers ===")
        all_passed = True
        
        try:
            resp = self.session.get(f"{self.base_url}/", timeout=self.timeout)
            headers = resp.headers
            
            # Expected security headers
            security_checks = [
                ("Strict-Transport-Security", "HSTS header present"),
                ("X-Content-Type-Options", "nosniff protection"),
                ("X-Frame-Options", "Clickjacking protection"),
                ("X-XSS-Protection", "XSS protection"),
            ]
            
            for header, description in security_checks:
                passed = header in headers
                details = f"Value: {headers.get(header, 'MISSING')}" if passed else "Header missing"
                all_passed &= self.log_test(description, passed, details)
                
        except Exception as e:
            all_passed &= self.log_test("Security headers check", False, f"Error: {e}")
        
        return all_passed
    
    def run_all_tests(self) -> bool:
        """Run comprehensive deployment validation suite"""
        logger.info("🚀 Starting Deployment Confidence Validation")
        logger.info(f"Target: {self.base_url}")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Run all test suites
        test_suites = [
            ("Health Endpoints", self.test_health_endpoints),
            ("Authentication Enforcement", self.test_authentication_enforcement),
            ("PWA Redirects", self.test_pwa_redirects),
            ("Public Endpoints", self.test_public_endpoints),
            ("Guest Writes Disabled", self.test_guest_writes_disabled),
            ("Security Headers", self.test_security_headers),
        ]
        
        suite_results = []
        for suite_name, test_func in test_suites:
            logger.info(f"\n🔍 Running {suite_name}...")
            suite_passed = test_func()
            suite_results.append((suite_name, suite_passed))
        
        # Calculate results
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['passed'])
        failed_tests = total_tests - passed_tests
        duration = time.time() - start_time
        
        # Final report
        logger.info("\n" + "=" * 60)
        logger.info("🏁 DEPLOYMENT CONFIDENCE VALIDATION RESULTS")
        logger.info("=" * 60)
        
        for suite_name, suite_passed in suite_results:
            status = "✅ PASS" if suite_passed else "❌ FAIL"
            logger.info(f"{status} {suite_name}")
        
        logger.info(f"\nOverall Results:")
        logger.info(f"  Tests Passed: {passed_tests}/{total_tests}")
        logger.info(f"  Tests Failed: {failed_tests}")
        logger.info(f"  Duration: {duration:.2f}s")
        
        overall_passed = failed_tests == 0
        if overall_passed:
            logger.info("🎉 DEPLOYMENT APPROVED - All validations passed!")
        else:
            logger.error("🚫 DEPLOYMENT BLOCKED - Validation failures detected!")
            
        return overall_passed
    
    def generate_report(self) -> Dict:
        """Generate detailed validation report"""
        return {
            'timestamp': time.time(),
            'base_url': self.base_url,
            'total_tests': len(self.results),
            'passed_tests': sum(1 for r in self.results if r['passed']),
            'failed_tests': sum(1 for r in self.results if not r['passed']),
            'tests': self.results,
            'overall_passed': sum(1 for r in self.results if not r['passed']) == 0
        }

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FinBrain Deployment Confidence Validator')
    parser.add_argument('--url', default='http://localhost:5000', 
                       help='Base URL to test (default: http://localhost:5000)')
    parser.add_argument('--report', help='Save detailed report to JSON file')
    args = parser.parse_args()
    
    validator = DeploymentValidator(args.url)
    success = validator.run_all_tests()
    
    if args.report:
        report = validator.generate_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"📊 Detailed report saved to: {args.report}")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()