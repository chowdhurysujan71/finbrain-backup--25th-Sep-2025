#!/usr/bin/env python3
"""
FinBrain Deployment Confidence Script
Comprehensive automated validation with CAPTCHA solver for zero-surprise deployments
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import requests

# Configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
API_BASE = f"{BASE_URL}/api/backend"
TIMEOUT = 30

class CaptchaSolver:
    """Automatic CAPTCHA solver for deployment testing"""
    
    def solve_math_captcha(self, question: str) -> int | None:
        """Solve simple math CAPTCHA questions"""
        try:
            # Parse "What is X + Y?" format
            if "What is" in question and "?" in question:
                math_part = question.replace("What is", "").replace("?", "").strip()
                
                # Handle different operations
                if "+" in math_part:
                    parts = math_part.split("+")
                    return int(parts[0].strip()) + int(parts[1].strip())
                elif "-" in math_part:
                    parts = math_part.split("-")
                    return int(parts[0].strip()) - int(parts[1].strip())
                elif "*" in math_part or "×" in math_part:
                    parts = math_part.replace("*", "×").split("×")
                    return int(parts[0].strip()) * int(parts[1].strip())
                    
            return None
        except Exception as e:
            print(f"   ❌ CAPTCHA solver error: {e}")
            return None

class DeploymentValidator:
    """Comprehensive deployment validation"""
    
    def __init__(self):
        self.captcha_solver = CaptchaSolver()
        self.session = requests.Session()
        self.test_user_email = f"deploy_test_{int(time.time())}@finbrain.app"
        self.results = []
        
    def log_result(self, test: str, status: str, details: str = ""):
        """Log test result"""
        result = {
            "test": test,
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.results.append(result)
        
        emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"   {emoji} {test}: {status}")
        if details:
            print(f"      {details}")
    
    def test_health_endpoints(self):
        """Test basic health and readiness for web application"""
        print("\n1. HEALTH & READINESS CHECKS")
        print("-" * 40)
        
        try:
            # Health check - finbrain returns JSON with "status":"healthy"
            resp = self.session.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            if resp.status_code == 200:
                try:
                    health_data = resp.json()
                    if health_data.get("status") == "healthy":
                        self.log_result("Health Endpoint", "PASS", f"Service healthy, response time: {resp.elapsed.total_seconds():.2f}s")
                    else:
                        self.log_result("Health Endpoint", "FAIL", f"Unhealthy status: {health_data.get('status')}")
                        return False
                except:
                    # Fallback for non-JSON responses
                    if "healthy" in resp.text.lower() or "ok" in resp.text.lower():
                        self.log_result("Health Endpoint", "PASS", f"Response time: {resp.elapsed.total_seconds():.2f}s")
                    else:
                        self.log_result("Health Endpoint", "FAIL", f"Unexpected response format")
                        return False
            else:
                self.log_result("Health Endpoint", "FAIL", f"Status: {resp.status_code}")
                return False
                
            # Readiness check
            resp = self.session.get(f"{BASE_URL}/readyz", timeout=TIMEOUT)
            if resp.status_code == 200:
                self.log_result("Readiness Endpoint", "PASS")
            else:
                self.log_result("Readiness Endpoint", "WARN", f"Status: {resp.status_code}")
                
        except Exception as e:
            self.log_result("Health Endpoints", "FAIL", str(e))
            return False
            
        return True
    
    def test_web_application(self):
        """Test web application functionality"""
        print("\n2. WEB APPLICATION VALIDATION")
        print("-" * 40)
        
        try:
            # Test main finbrain page
            resp = self.session.get(f"{BASE_URL}/", timeout=TIMEOUT)
            if resp.status_code == 200 and "finbrain" in resp.text.lower():
                self.log_result("Main Application Page", "PASS", "finbrain web interface accessible")
            else:
                self.log_result("Main Application Page", "FAIL", f"Status: {resp.status_code}")
                return False
                
            # Test backend API availability (for expense processing)
            resp = self.session.get(f"{API_BASE}/version", timeout=TIMEOUT)
            if resp.status_code == 401:  # Expected - auth required
                self.log_result("Backend API", "PASS", "API secured with auth requirement")
            elif resp.status_code == 200:
                self.log_result("Backend API", "PASS", "API accessible")
            else:
                self.log_result("Backend API", "WARN", f"Unexpected status: {resp.status_code}")
                
            return True
                
        except Exception as e:
            self.log_result("Web Application", "FAIL", str(e))
            return False
    
    def test_web_chat_functionality(self):
        """Test web chat functionality"""
        print("\n3. WEB CHAT FUNCTIONALITY VALIDATION")
        print("-" * 40)
        
        try:
            # Test that chat interface is accessible
            resp = self.session.get(f"{BASE_URL}/chat", timeout=TIMEOUT)
            if resp.status_code == 200:
                self.log_result("Chat Interface", "PASS", "Web chat interface accessible")
            else:
                self.log_result("Chat Interface", "WARN", f"Status: {resp.status_code}")
                
            # Test report interface
            resp = self.session.get(f"{BASE_URL}/report", timeout=TIMEOUT)
            if resp.status_code == 200:
                self.log_result("Report Dashboard", "PASS", "Expense reports accessible")
            else:
                self.log_result("Report Dashboard", "WARN", f"Status: {resp.status_code}")
                
            # Test login page
            resp = self.session.get(f"{BASE_URL}/login", timeout=TIMEOUT)
            if resp.status_code == 200:
                self.log_result("Login Page", "PASS", "Login interface accessible")
            else:
                self.log_result("Login Page", "WARN", f"Status: {resp.status_code}")
            
            # Test ai-chat endpoint (should require authentication)
            chat_data = {
                "message": f"Deployment test: spent 150 taka on coffee at {int(time.time())}"
            }
            
            resp = self.session.post(f"{BASE_URL}/ai-chat", 
                                   json=chat_data, timeout=TIMEOUT)
            
            if resp.status_code == 401:
                self.log_result("AI Chat Security", "PASS", "Properly protected with authentication")
            elif resp.status_code == 200:
                self.log_result("AI Chat Security", "WARN", "Endpoint accessible without auth")
            else:
                self.log_result("AI Chat Security", "WARN", f"Unexpected status: {resp.status_code}")
                
        except Exception as e:
            self.log_result("Web Chat Functionality", "FAIL", str(e))
            return False
            
        return True
    
            
    def test_security_measures(self):
        """Test security configurations"""
        print("\n4. SECURITY VALIDATION")
        print("-" * 40)
        
        try:
            # Test CORS headers
            resp = self.session.options(f"{BASE_URL}/ai-chat", 
                                      headers={"Origin": BASE_URL})
            
            if "Access-Control-Allow-Origin" in resp.headers:
                self.log_result("CORS Configuration", "PASS")
            else:
                self.log_result("CORS Configuration", "WARN", "CORS headers not found")
            
            # Test content type validation
            resp = self.session.post(f"{BASE_URL}/ai-chat",
                                   data="invalid", 
                                   headers={"Content-Type": "text/plain"},
                                   timeout=TIMEOUT)
            
            if resp.status_code in [400, 415]:
                self.log_result("Content-Type Validation", "PASS")
            else:
                self.log_result("Content-Type Validation", "WARN", 
                              f"Expected 400/415, got {resp.status_code}")
                
        except Exception as e:
            self.log_result("Security Measures", "FAIL", str(e))
    
    def generate_report(self):
        """Generate deployment confidence report"""
        print("\n" + "="*60)
        print("DEPLOYMENT CONFIDENCE REPORT")
        print("="*60)
        
        total_tests = len(self.results)
        passed = len([r for r in self.results if r["status"] == "PASS"])
        failed = len([r for r in self.results if r["status"] == "FAIL"])
        warnings = len([r for r in self.results if r["status"] == "WARN"])
        
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warnings: {warnings}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if failed == 0 and success_rate >= 80:
            verdict = "✅ DEPLOYMENT READY"
            exit_code = 0
        elif failed == 0:
            verdict = "⚠️ DEPLOYMENT READY WITH WARNINGS"
            exit_code = 0
        else:
            verdict = "❌ DEPLOYMENT NOT READY"
            exit_code = 1
            
        print(f"\nVerdict: {verdict}")
        
        # Save detailed report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "base_url": BASE_URL,
            "verdict": verdict,
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "success_rate": success_rate
            },
            "detailed_results": self.results
        }
        
        report_file = f"deployment_confidence_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"Detailed report saved: {report_file}")
        return exit_code
    
    def run_full_validation(self):
        """Run complete deployment validation suite"""
        print("🚀 FINBRAIN DEPLOYMENT CONFIDENCE VALIDATOR")
        print(f"Target: {BASE_URL}")
        print(f"Started: {datetime.utcnow().isoformat()}Z")
        print("="*60)
        
        # Run all test suites
        self.test_health_endpoints()
        self.test_web_application()
        self.test_web_chat_functionality()
        self.test_security_measures()
        
        # Generate final report
        return self.generate_report()

def main():
    """Main execution"""
    validator = DeploymentValidator()
    exit_code = validator.run_full_validation()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()