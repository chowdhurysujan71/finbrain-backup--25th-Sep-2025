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
        """Test basic health and readiness"""
        print("\n1. HEALTH & READINESS CHECKS")
        print("-" * 40)
        
        try:
            # Health check
            resp = self.session.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            if resp.status_code == 200 and "ok" in resp.text.lower():
                self.log_result("Health Endpoint", "PASS", f"Response time: {resp.elapsed.total_seconds():.2f}s")
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
    
    def test_auth_system(self):
        """Test authentication with CAPTCHA solving"""
        print("\n2. AUTHENTICATION WITH CAPTCHA")
        print("-" * 40)
        
        try:
            # Get CAPTCHA for registration
            resp = self.session.get(f"{BASE_URL}/auth/register", timeout=TIMEOUT)
            if resp.status_code != 200:
                self.log_result("CAPTCHA Generation", "FAIL", f"Status: {resp.status_code}")
                return False
                
            # Extract CAPTCHA from HTML (simple pattern matching)
            html = resp.text
            captcha_question = None
            encrypted_answer = None
            timestamp = None
            
            # Look for CAPTCHA data in the HTML
            if 'data-captcha-question=' in html:
                import re
                question_match = re.search(r'data-captcha-question="([^"]*)"', html)
                answer_match = re.search(r'data-captcha-answer="([^"]*)"', html)
                time_match = re.search(r'data-captcha-timestamp="([^"]*)"', html)
                
                if question_match and answer_match and time_match:
                    captcha_question = question_match.group(1)
                    encrypted_answer = answer_match.group(1)
                    timestamp = time_match.group(1)
            
            if not captcha_question:
                self.log_result("CAPTCHA Extraction", "WARN", "CAPTCHA not found - may be disabled")
                captcha_answer = None
            else:
                self.log_result("CAPTCHA Extraction", "PASS", f"Question: {captcha_question}")
                
                # Solve CAPTCHA
                captcha_answer = self.captcha_solver.solve_math_captcha(captcha_question)
                if captcha_answer is not None:
                    self.log_result("CAPTCHA Solving", "PASS", f"Answer: {captcha_answer}")
                else:
                    self.log_result("CAPTCHA Solving", "FAIL", "Could not solve CAPTCHA")
                    return False
            
            # Attempt registration
            register_data = {
                "email": self.test_user_email,
                "password": "DeployTest123!",
                "name": "Deploy Test User"
            }
            
            if captcha_answer is not None:
                register_data["captcha_answer"] = str(captcha_answer)
                register_data["captcha_encrypted"] = encrypted_answer or ""
                register_data["captcha_timestamp"] = timestamp or ""
            
            resp = self.session.post(f"{BASE_URL}/auth/register", 
                                   json=register_data, timeout=TIMEOUT)
            
            if resp.status_code in [200, 201]:
                self.log_result("User Registration", "PASS")
                return True
            elif resp.status_code == 409:
                self.log_result("User Registration", "PASS", "User already exists")
                return True
            else:
                self.log_result("User Registration", "FAIL", 
                              f"Status: {resp.status_code}, Response: {resp.text[:200]}")
                return False
                
        except Exception as e:
            self.log_result("Authentication System", "FAIL", str(e))
            return False
    
    def test_expense_pipeline(self):
        """Test core expense logging pipeline"""
        print("\n3. EXPENSE PIPELINE VALIDATION")
        print("-" * 40)
        
        try:
            # Login first
            login_data = {
                "email": self.test_user_email,
                "password": "DeployTest123!"
            }
            
            resp = self.session.post(f"{BASE_URL}/auth/login", 
                                   json=login_data, timeout=TIMEOUT)
            
            if resp.status_code not in [200, 201]:
                self.log_result("Login", "FAIL", f"Status: {resp.status_code}")
                return False
                
            self.log_result("Login", "PASS")
            
            # Test expense creation via AI chat
            chat_data = {
                "message": f"Deployment test: spent 150 taka on coffee at {int(time.time())}"
            }
            
            resp = self.session.post(f"{BASE_URL}/ai-chat", 
                                   json=chat_data, timeout=TIMEOUT)
            
            if resp.status_code == 200:
                self.log_result("AI Chat Expense", "PASS")
                
                # Parse response
                try:
                    data = resp.json()
                    if "reply" in data and data.get("reply"):
                        self.log_result("AI Response", "PASS", f"Reply: {data['reply'][:50]}...")
                    else:
                        self.log_result("AI Response", "WARN", "Empty reply")
                except Exception as e:  # narrowed from bare except (lint A1)
                    self.log_result("AI Response", "WARN", "Non-JSON response")
            else:
                self.log_result("AI Chat Expense", "FAIL", f"Status: {resp.status_code}")
                return False
            
            # Test backend API expense creation
            expense_data = {
                "description": f"Deployment validation expense {int(time.time())}",
                "amount_minor": 15000,  # 150.00 BDT
                "currency": "BDT",
                "category": "food",
                "source": "chat"
            }
            
            resp = self.session.post(f"{API_BASE}/add_expense", 
                                   json=expense_data, timeout=TIMEOUT)
            
            if resp.status_code == 200:
                self.log_result("Backend API Expense", "PASS")
                data = resp.json()
                expense_id = data.get("expense_id")
                if expense_id:
                    self.log_result("Expense ID Generation", "PASS", f"ID: {expense_id}")
                else:
                    self.log_result("Expense ID Generation", "WARN", "No expense_id returned")
            else:
                self.log_result("Backend API Expense", "FAIL", f"Status: {resp.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Expense Pipeline", "FAIL", str(e))
            return False
            
        return True
    
    def test_deprecated_endpoints(self):
        """Verify deprecated endpoints return proper 410 responses"""
        print("\n4. DEPRECATED ENDPOINT VALIDATION")
        print("-" * 40)
        
        try:
            # Test deprecated Messenger webhook
            payload = {
                "object": "page",
                "entry": [{"messaging": []}]
            }
            
            resp = self.session.post(f"{BASE_URL}/webhook/messenger", 
                                   json=payload, timeout=TIMEOUT)
            
            if resp.status_code == 410:
                self.log_result("Messenger Webhook Deprecation", "PASS", "Returns 410 Gone")
            else:
                self.log_result("Messenger Webhook Deprecation", "FAIL", 
                              f"Expected 410, got {resp.status_code}")
                
        except Exception as e:
            self.log_result("Deprecated Endpoints", "FAIL", str(e))
            
    def test_security_measures(self):
        """Test security configurations"""
        print("\n5. SECURITY VALIDATION")
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
        self.test_auth_system()
        self.test_expense_pipeline()
        self.test_deprecated_endpoints()
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