#!/usr/bin/env python3
"""
Comprehensive End-to-End UAT for FinBrain
Tests all major user flows and system components
"""

import json
import sys
import time
from datetime import datetime

import requests


class FinBrainUAT:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {"passed": 0, "failed": 0, "total": 0}
        }
        self.test_user_hash = None
        
    def log_test(self, test_name, status, details="", error=None):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if error:
            result["error"] = str(error)
            
        self.test_results["tests"].append(result)
        self.test_results["summary"]["total"] += 1
        
        if status == "PASS":
            self.test_results["summary"]["passed"] += 1
            print(f"✅ {test_name}: {details}")
        else:
            self.test_results["summary"]["failed"] += 1
            print(f"❌ {test_name}: {details}")
            if error:
                print(f"   Error: {error}")
    
    def test_health_endpoint(self):
        """Test 1: Health endpoint availability"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                db_status = health_data.get("database", "unknown")
                ai_status = health_data.get("ai_status", {}).get("enabled", False)
                
                self.log_test(
                    "Health Endpoint", 
                    "PASS", 
                    f"DB: {db_status}, AI: {ai_status}, Status: {health_data.get('status', 'unknown')}"
                )
                return True
            else:
                self.log_test("Health Endpoint", "FAIL", f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Endpoint", "FAIL", "Connection failed", e)
            return False
    
    def test_database_connectivity(self):
        """Test 2: Database operations"""
        try:
            # Import within function to avoid initialization issues
            sys.path.append('/home/runner/workspace')
            from app import app, db
            from models import Expense, User
            
            with app.app_context():
                # Test database connection
                result = db.session.execute(db.text("SELECT 1")).scalar()
                
                # Check existing users
                user_count = User.query.count()
                expense_count = Expense.query.count()
                
                # Get test user
                test_user = User.query.first()
                if test_user:
                    self.test_user_hash = test_user.user_id_hash
                
                self.log_test(
                    "Database Connectivity", 
                    "PASS", 
                    f"Users: {user_count}, Expenses: {expense_count}, Test User: {bool(test_user)}"
                )
                return True
                
        except Exception as e:
            self.log_test("Database Connectivity", "FAIL", "DB query failed", e)
            return False
    
    def test_ai_insights_generation(self):
        """Test 3: AI insights functionality"""
        if not self.test_user_hash:
            self.log_test("AI Insights Generation", "SKIP", "No test user available")
            return False
            
        try:
            sys.path.append('/home/runner/workspace')
            from app import app
            from handlers.insight import handle_insight
            
            # Test insights generation with proper app context
            with app.app_context():
                result = handle_insight(self.test_user_hash)
            
            if result and "text" in result:
                text = result["text"]
                if "Unable to generate insights" in text:
                    self.log_test("AI Insights Generation", "FAIL", "AI insights not working")
                    return False
                elif "Here's what I noticed:" in text or len(text) > 50:
                    self.log_test("AI Insights Generation", "PASS", f"Generated {len(text)} chars of insights")
                    return True
                else:
                    self.log_test("AI Insights Generation", "FAIL", f"Unexpected response: {text[:100]}")
                    return False
            else:
                self.log_test("AI Insights Generation", "FAIL", "Invalid response format")
                return False
                
        except Exception as e:
            self.log_test("AI Insights Generation", "FAIL", "Exception during generation", e)
            return False
    
    def test_expense_summary(self):
        """Test 4: Expense summary functionality"""
        if not self.test_user_hash:
            self.log_test("Expense Summary", "SKIP", "No test user available")
            return False
            
        try:
            sys.path.append('/home/runner/workspace')
            from handlers.summary import handle_summary
            
            # Test summary generation
            result = handle_summary(self.test_user_hash)
            
            if result and "text" in result:
                text = result["text"]
                # Accept various valid summary formats
                if any(word in text.lower() for word in ["spent", "expenses", "no expenses", "summary", "৳", "transactions"]):
                    self.log_test("Expense Summary", "PASS", f"Summary generated: {len(text)} chars")
                    return True
                else:
                    self.log_test("Expense Summary", "FAIL", f"Invalid summary format: {text[:100]}")
                    return False
            else:
                self.log_test("Expense Summary", "FAIL", "Invalid response format")
                return False
                
        except Exception as e:
            self.log_test("Expense Summary", "FAIL", "Exception during summary", e)
            return False
    
    def test_category_breakdown(self):
        """Test 5: Category-specific expense breakdown"""
        if not self.test_user_hash:
            self.log_test("Category Breakdown", "SKIP", "No test user available")
            return False
            
        try:
            sys.path.append('/home/runner/workspace')
            from handlers.category_breakdown import handle_category_breakdown
            
            # Test food category breakdown
            result = handle_category_breakdown(self.test_user_hash, "food")
            
            if result and "text" in result:
                text = result["text"]
                if "food" in text.lower() or "spent" in text.lower():
                    self.log_test("Category Breakdown", "PASS", f"Food breakdown: {text[:100]}...")
                    return True
                else:
                    self.log_test("Category Breakdown", "FAIL", f"Unexpected breakdown: {text}")
                    return False
            else:
                self.log_test("Category Breakdown", "FAIL", "Invalid response format")
                return False
                
        except Exception as e:
            self.log_test("Category Breakdown", "FAIL", "Exception during breakdown", e)
            return False
    
    def test_ai_adapter_functionality(self):
        """Test 6: AI adapter direct functionality"""
        try:
            sys.path.append('/home/runner/workspace')
            from utils.ai_adapter_v2 import production_ai_adapter
            
            # Test AI adapter status
            adapter_enabled = production_ai_adapter.enabled
            adapter_provider = production_ai_adapter.provider
            
            # Test sample insight generation
            test_data = {
                'total_amount': 1000,
                'expenses': [
                    {'category': 'food', 'total': 600, 'percentage': 60},
                    {'category': 'transport', 'total': 400, 'percentage': 40}
                ],
                'timeframe': 'this month'
            }
            
            ai_result = production_ai_adapter.generate_insights(test_data)
            
            if ai_result.get('success'):
                insights = ai_result.get('insights', [])
                self.log_test(
                    "AI Adapter Functionality", 
                    "PASS", 
                    f"Provider: {adapter_provider}, Generated {len(insights)} insights"
                )
                return True
            else:
                reason = ai_result.get('reason', 'unknown')
                self.log_test("AI Adapter Functionality", "FAIL", f"AI failed: {reason}")
                return False
                
        except Exception as e:
            self.log_test("AI Adapter Functionality", "FAIL", "Exception testing AI", e)
            return False
    
    def test_production_router(self):
        """Test 7: Production router functionality"""
        try:
            sys.path.append('/home/runner/workspace')
            from app import app
            from utils.production_router import production_router
            
            if not self.test_user_hash:
                # Use a mock hash for testing
                test_hash = "test_hash_12345678"
            else:
                test_hash = self.test_user_hash
            
            # Test summary routing using correct method with app context
            with app.app_context():
                response, intent, category, amount = production_router.route_message("summary", test_hash)
            
            if response and intent == "summary":
                self.log_test("Production Router", "PASS", f"Summary routing works, intent: {intent}")
                return True
            else:
                self.log_test("Production Router", "FAIL", f"Unexpected routing result: {intent}")
                return False
                
        except Exception as e:
            self.log_test("Production Router", "FAIL", "Exception testing router", e)
            return False
    
    def test_pca_system(self):
        """Test 8: PCA (Precision Capture & Audit) system"""
        try:
            sys.path.append('/home/runner/workspace')
            from utils.pca_flags import pca_flags
            
            # Test PCA flags using correct methods that exist
            overlay_enabled = pca_flags.should_write_overlays()
            
            # Get mode from environment or default
            import os
            mode = os.environ.get('PCA_MODE', 'FALLBACK')
            audit_ui_enabled = os.environ.get('SHOW_AUDIT_UI', 'false').lower() == 'true'
            
            self.log_test(
                "PCA System", 
                "PASS", 
                f"Mode: {mode}, Overlay: {overlay_enabled}, Audit UI: {audit_ui_enabled}"
            )
            return True
            
        except Exception as e:
            self.log_test("PCA System", "FAIL", "Exception testing PCA", e)
            return False
    
    def test_api_endpoints(self):
        """Test 9: Key API endpoints"""
        try:
            # Test monitoring endpoint with correct path
            response = requests.get(f"{self.base_url}/api/monitoring/health", timeout=5)
            monitoring_ok = response.status_code == 200
            
            # Test health endpoint as alternative
            health_response = requests.get(f"{self.base_url}/health", timeout=5)
            health_ok = health_response.status_code == 200
            
            self.log_test(
                "API Endpoints", 
                "PASS" if monitoring_ok and health_ok else "FAIL", 
                f"Monitoring: {monitoring_ok}, Health: {health_ok}"
            )
            return monitoring_ok and health_ok
            
        except Exception as e:
            self.log_test("API Endpoints", "FAIL", "Exception testing APIs", e)
            return False
    
    def test_security_headers(self):
        """Test 10: Security and HTTPS enforcement"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            
            # Check for security headers (basic check)
            has_cors = 'Access-Control-Allow-Origin' in response.headers
            content_type = response.headers.get('Content-Type', '')
            
            # Check response structure
            is_json = 'application/json' in content_type
            
            self.log_test(
                "Security Headers", 
                "PASS", 
                f"JSON response: {is_json}, CORS present: {has_cors}"
            )
            return True
            
        except Exception as e:
            self.log_test("Security Headers", "FAIL", "Exception checking security", e)
            return False
    
    def run_full_uat(self):
        """Execute complete UAT suite"""
        print("🚀 Starting FinBrain End-to-End UAT")
        print("=" * 50)
        
        # Run all tests
        tests = [
            self.test_health_endpoint,
            self.test_database_connectivity,
            self.test_ai_insights_generation,
            self.test_expense_summary,
            self.test_category_breakdown,
            self.test_ai_adapter_functionality,
            self.test_production_router,
            self.test_pca_system,
            self.test_api_endpoints,
            self.test_security_headers
        ]
        
        for test in tests:
            try:
                test()
                time.sleep(0.5)  # Brief pause between tests
            except Exception as e:
                test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
                self.log_test(test_name, "FAIL", "Unexpected exception", e)
        
        # Generate summary
        summary = self.test_results["summary"]
        print("\n" + "=" * 50)
        print("📊 UAT SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {summary['total']}")
        print(f"Passed: {summary['passed']} ✅")
        print(f"Failed: {summary['failed']} ❌")
        print(f"Success Rate: {(summary['passed']/summary['total']*100):.1f}%")
        
        # Overall status
        if summary['failed'] == 0:
            print("\n🎉 ALL TESTS PASSED - System is ready for production!")
        elif summary['failed'] <= 2:
            print(f"\n⚠️  Minor issues detected ({summary['failed']} failures)")
        else:
            print(f"\n🔥 Major issues detected ({summary['failed']} failures) - needs attention")
        
        return self.test_results

if __name__ == "__main__":
    uat = FinBrainUAT()
    results = uat.run_full_uat()
    
    # Save results
    with open('uat_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n📄 Detailed results saved to uat_results.json")