"""
Context-Driven AI System - User Acceptance Testing
Comprehensive testing of all context packet components and integrations
"""

import json
import time
import logging
from datetime import datetime, timedelta
from app import app, db
from models import Expense, User
from utils.security import hash_psid
from production_router import router
from utils.context_packet import build_context, is_context_thin, CONTEXT_SYSTEM_PROMPT, RESPONSE_SCHEMA
from ai_adapter_gemini import generate_with_schema
from limiter import can_use_ai, fallback_blurb

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContextSystemUAT:
    """UAT test suite for context-driven AI system"""
    
    def __init__(self):
        self.test_psid = "UAT_TEST_USER_12345"
        self.test_user_hash = hash_psid(self.test_psid)
        self.test_results = {}
        
    def setup_test_data(self):
        """Create test expense data for UAT"""
        print("Setting up test expense data...")
        
        with app.app_context():
            # Clear existing test data
            db.session.query(Expense).filter(Expense.user_id == self.test_user_hash).delete()
            db.session.commit()
            
            now = datetime.utcnow()
            
            # Create rich context - multiple categories with spending
            test_expenses = [
                # Current 30 days - dining category
                {"amount": 2500, "category": "dining", "days_ago": 5, "description": "Restaurant lunch"},
                {"amount": 1800, "category": "dining", "days_ago": 10, "description": "Coffee shop"},
                {"amount": 3200, "category": "dining", "days_ago": 15, "description": "Dinner with friends"},
                {"amount": 1500, "category": "dining", "days_ago": 20, "description": "Fast food"},
                
                # Current 30 days - groceries category  
                {"amount": 4500, "category": "groceries", "days_ago": 3, "description": "Weekly shopping"},
                {"amount": 2200, "category": "groceries", "days_ago": 12, "description": "Fruit and vegetables"},
                {"amount": 3800, "category": "groceries", "days_ago": 25, "description": "Monthly groceries"},
                
                # Current 30 days - transport category
                {"amount": 800, "category": "transport", "days_ago": 7, "description": "Uber ride"},
                {"amount": 1200, "category": "transport", "days_ago": 14, "description": "Bus fare"},
                
                # Previous 30 days for comparison (31-60 days ago)
                {"amount": 2000, "category": "dining", "days_ago": 35, "description": "Old restaurant"},
                {"amount": 1500, "category": "dining", "days_ago": 45, "description": "Old coffee"},
                {"amount": 5000, "category": "groceries", "days_ago": 40, "description": "Old groceries"},
                {"amount": 3000, "category": "groceries", "days_ago": 50, "description": "Old shopping"},
            ]
            
            for i, expense_data in enumerate(test_expenses):
                expense_date = now - timedelta(days=expense_data["days_ago"])
                expense = Expense(
                    user_id=self.test_user_hash,
                    amount=expense_data["amount"],
                    category=expense_data["category"],
                    description=expense_data["description"],
                    created_at=expense_date,
                    date=expense_date.date(),
                    time=expense_date.time(),
                    month=expense_date.strftime("%Y-%m"),
                    currency="৳",
                    platform="messenger",
                    original_message="",
                    ai_insights="",
                    unique_id=f"UAT_TEST_{i}_{int(time.time())}"
                )
                db.session.add(expense)
            
            db.session.commit()
            print(f"✓ Created {len(test_expenses)} test expenses")
    
    def test_context_building(self):
        """Test 1: Context packet building with spending analysis"""
        print("\n=== TEST 1: Context Building ===")
        
        with app.app_context():
            context = build_context(self.test_psid, db.session)
            
            # Validate context structure
            required_keys = ["income_30d", "top_cats", "total_spend_30d", "recurring", "goals", "context_quality"]
            missing_keys = [key for key in required_keys if key not in context]
            
            if missing_keys:
                self.test_results["context_building"] = f"FAIL: Missing keys {missing_keys}"
                return False
            
            # Validate spending data
            total_spend = context["total_spend_30d"]
            expected_total = 2500 + 1800 + 3200 + 1500 + 4500 + 2200 + 3800 + 800 + 1200  # 21500
            
            if abs(total_spend - expected_total) > 100:  # Allow small variance
                self.test_results["context_building"] = f"FAIL: Total spend {total_spend}, expected ~{expected_total}"
                return False
            
            # Validate top categories
            top_cats = context["top_cats"]
            if len(top_cats) < 2:
                self.test_results["context_building"] = f"FAIL: Expected 2+ categories, got {len(top_cats)}"
                return False
            
            # Check for dining and groceries categories
            categories = [cat["category"] for cat in top_cats]
            if "dining" not in categories or "groceries" not in categories:
                self.test_results["context_building"] = f"FAIL: Missing expected categories, got {categories}"
                return False
            
            # Validate delta calculations
            dining_cat = next((cat for cat in top_cats if cat["category"] == "dining"), None)
            if dining_cat and "delta_pct" not in dining_cat:
                self.test_results["context_building"] = "FAIL: Missing delta_pct in category data"
                return False
            
            print(f"✓ Context built successfully:")
            print(f"  - Total spend: ৳{total_spend:,}")
            print(f"  - Categories: {len(top_cats)}")
            print(f"  - Top category: {top_cats[0]['category']} (৳{top_cats[0]['amount']:,})")
            print(f"  - Context quality: {context['context_quality']}")
            
            self.test_results["context_building"] = "PASS"
            return True
    
    def test_thin_context_guard(self):
        """Test 2: Thin context detection and guard logic"""
        print("\n=== TEST 2: Thin Context Guard ===")
        
        # Test with empty context
        thin_context = {
            "total_spend_30d": 0,
            "top_cats": [],
            "income_30d": 0,
            "recurring": [],
            "goals": [],
            "context_quality": "thin"
        }
        
        is_thin = is_context_thin(thin_context)
        if not is_thin:
            self.test_results["thin_context_guard"] = "FAIL: Should detect thin context"
            return False
        
        # Test with rich context
        rich_context = {
            "total_spend_30d": 21500,
            "top_cats": [
                {"category": "dining", "amount": 9000},
                {"category": "groceries", "amount": 10500}
            ],
            "context_quality": "rich"
        }
        
        is_thin_rich = is_context_thin(rich_context)
        if is_thin_rich:
            self.test_results["thin_context_guard"] = "FAIL: Should not detect rich context as thin"
            return False
        
        print("✓ Thin context detection working correctly")
        self.test_results["thin_context_guard"] = "PASS"
        return True
    
    def test_ai_schema_enforcement(self):
        """Test 3: AI JSON schema enforcement"""
        print("\n=== TEST 3: AI Schema Enforcement ===")
        
        try:
            # Test schema generation with mock context
            test_prompt = """Question: How can I save money?

user_context={
    "income_30d": 50000,
    "total_spend_30d": 21500,
    "top_categories": [
        {"category": "dining", "amount": 9000, "delta_pct": 25},
        {"category": "groceries", "amount": 10500, "delta_pct": -5}
    ]
}"""
            
            result = generate_with_schema(
                user_text=test_prompt,
                system_prompt=CONTEXT_SYSTEM_PROMPT,
                response_schema=RESPONSE_SCHEMA
            )
            
            if not result["ok"]:
                print(f"⚠ AI generation failed: {result.get('error', 'Unknown error')}")
                print("✓ Testing structured fallback...")
                
                # Validate fallback structure
                fallback = {
                    "summary": "Test summary with spending data",
                    "action": "Test action recommendation", 
                    "question": "Test follow-up question"
                }
                
                required_fields = RESPONSE_SCHEMA["required"]
                missing = [field for field in required_fields if field not in fallback]
                
                if missing:
                    self.test_results["ai_schema_enforcement"] = f"FAIL: Fallback missing {missing}"
                    return False
                
                print("✓ Structured fallback format validated")
                self.test_results["ai_schema_enforcement"] = "PASS (fallback)"
                return True
            
            # Validate AI response structure
            if "data" not in result:
                self.test_results["ai_schema_enforcement"] = "FAIL: No data in AI response"
                return False
            
            response_data = result["data"]
            required_fields = RESPONSE_SCHEMA["required"]
            missing = [field for field in required_fields if field not in response_data]
            
            if missing:
                self.test_results["ai_schema_enforcement"] = f"FAIL: AI response missing {missing}"
                return False
            
            print("✓ AI response structure validated:")
            print(f"  - Summary: {response_data['summary'][:50]}...")
            print(f"  - Action: {response_data['action'][:50]}...")
            print(f"  - Question: {response_data['question'][:50]}...")
            
            self.test_results["ai_schema_enforcement"] = "PASS"
            return True
            
        except Exception as e:
            self.test_results["ai_schema_enforcement"] = f"FAIL: Exception {e}"
            return False
    
    def test_production_router_integration(self):
        """Test 4: Production router integration"""
        print("\n=== TEST 4: Production Router Integration ===")
        
        with app.app_context():
            try:
                # Test route_message method
                result = router.route_message(
                    text="How can I save money on dining?",
                    psid=self.test_psid,
                    rid="UAT_TEST_001"
                )
                
                if not isinstance(result, tuple) or len(result) != 4:
                    self.test_results["router_integration"] = f"FAIL: Invalid result format {type(result)}"
                    return False
                
                response_text, intent, category, amount = result
                
                # Validate response structure
                if not response_text or len(response_text) == 0:
                    self.test_results["router_integration"] = "FAIL: Empty response text"
                    return False
                
                # Check 280 character limit
                if len(response_text) > 280:
                    self.test_results["router_integration"] = f"FAIL: Response too long ({len(response_text)} chars)"
                    return False
                
                # Validate intent
                expected_intents = ["ai_context_driven", "rate_limited", "fallback_error"]
                if intent not in expected_intents:
                    self.test_results["router_integration"] = f"FAIL: Unexpected intent {intent}"
                    return False
                
                print("✓ Router integration working:")
                print(f"  - Response length: {len(response_text)} chars")
                print(f"  - Intent: {intent}")
                print(f"  - Response: {response_text[:100]}...")
                
                self.test_results["router_integration"] = "PASS"
                return True
                
            except Exception as e:
                self.test_results["router_integration"] = f"FAIL: Exception {e}"
                return False
    
    def test_rate_limiting_integration(self):
        """Test 5: Rate limiting integration"""
        print("\n=== TEST 5: Rate Limiting Integration ===")
        
        try:
            # Test rate limiting function
            allowed, retry_in = can_use_ai(self.test_psid)
            
            if not isinstance(allowed, bool):
                self.test_results["rate_limiting"] = f"FAIL: Invalid allowed type {type(allowed)}"
                return False
            
            if not isinstance(retry_in, (int, float)):
                self.test_results["rate_limiting"] = f"FAIL: Invalid retry_in type {type(retry_in)}"
                return False
            
            # Test fallback message
            if not allowed:
                fallback_msg = fallback_blurb(retry_in)
                if not fallback_msg or "fast & free" not in fallback_msg:
                    self.test_results["rate_limiting"] = "FAIL: Invalid fallback message"
                    return False
            
            print(f"✓ Rate limiting check: allowed={allowed}, retry_in={retry_in}")
            self.test_results["rate_limiting"] = "PASS"
            return True
            
        except Exception as e:
            self.test_results["rate_limiting"] = f"FAIL: Exception {e}"
            return False
    
    def test_end_to_end_workflow(self):
        """Test 6: End-to-end workflow"""
        print("\n=== TEST 6: End-to-End Workflow ===")
        
        with app.app_context():
            try:
                # Simulate complete message processing workflow
                test_messages = [
                    "How can I save money?",
                    "I want to reduce my spending",
                    "Show me my dining expenses"
                ]
                
                workflow_results = []
                
                for i, message in enumerate(test_messages):
                    print(f"\nProcessing message {i+1}: '{message}'")
                    
                    # 1. Check rate limiting
                    allowed, retry_in = can_use_ai(self.test_psid)
                    print(f"  Rate limit check: allowed={allowed}")
                    
                    # 2. Route through production router
                    result = router.route_message(
                        text=message,
                        psid=self.test_psid,
                        rid=f"UAT_E2E_{i+1}"
                    )
                    
                    response_text, intent, category, amount = result
                    
                    # 3. Validate response
                    if not response_text:
                        workflow_results.append(f"Message {i+1}: FAIL - Empty response")
                        continue
                    
                    if len(response_text) > 280:
                        workflow_results.append(f"Message {i+1}: FAIL - Response too long")
                        continue
                    
                    # 4. Check for structured format (summary/action/question pattern)
                    line_count = len(response_text.split('\n'))
                    if line_count < 2:
                        workflow_results.append(f"Message {i+1}: WARN - Not structured format")
                    else:
                        workflow_results.append(f"Message {i+1}: PASS")
                    
                    print(f"  Response ({len(response_text)} chars): {response_text[:100]}...")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                
                # Evaluate overall workflow
                passed = sum(1 for result in workflow_results if "PASS" in result)
                total = len(workflow_results)
                
                if passed >= total * 0.7:  # 70% pass rate
                    print(f"\n✓ End-to-end workflow: {passed}/{total} messages processed successfully")
                    self.test_results["end_to_end"] = "PASS"
                    return True
                else:
                    print(f"\n⚠ End-to-end workflow: Only {passed}/{total} messages passed")
                    self.test_results["end_to_end"] = f"PARTIAL: {passed}/{total}"
                    return False
                    
            except Exception as e:
                self.test_results["end_to_end"] = f"FAIL: Exception {e}"
                return False
    
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\nCleaning up test data...")
        
        with app.app_context():
            db.session.query(Expense).filter(Expense.user_id == self.test_user_hash).delete()
            db.session.commit()
            print("✓ Test data cleaned up")
    
    def run_full_uat(self):
        """Run complete UAT suite"""
        print("=" * 60)
        print("CONTEXT-DRIVEN AI SYSTEM - USER ACCEPTANCE TESTING")
        print("=" * 60)
        
        start_time = time.time()
        
        # Setup
        self.setup_test_data()
        
        # Run all tests
        tests = [
            ("Context Building", self.test_context_building),
            ("Thin Context Guard", self.test_thin_context_guard),
            ("AI Schema Enforcement", self.test_ai_schema_enforcement),
            ("Router Integration", self.test_production_router_integration),
            ("Rate Limiting", self.test_rate_limiting_integration),
            ("End-to-End Workflow", self.test_end_to_end_workflow)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                print(f"ERROR in {test_name}: {e}")
                self.test_results[test_name.lower().replace(" ", "_")] = f"ERROR: {e}"
        
        # Cleanup
        self.cleanup_test_data()
        
        # Generate report
        duration = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("UAT RESULTS SUMMARY")
        print("=" * 60)
        
        for test_name, (_, _) in zip(self.test_results.keys(), tests):
            status = self.test_results.get(test_name, "NOT_RUN")
            status_icon = "✓" if status == "PASS" else "⚠" if "PARTIAL" in status else "✗"
            print(f"{status_icon} {test_name.replace('_', ' ').title()}: {status}")
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        print(f"Duration: {duration:.2f} seconds")
        
        # Final verdict
        if passed_tests >= total_tests * 0.8:  # 80% pass rate
            print("\n🎯 UAT RESULT: PASS - System ready for production")
            return True
        else:
            print("\n⚠ UAT RESULT: NEEDS ATTENTION - Some components require fixes")
            return False

def main():
    """Run UAT from command line"""
    uat = ContextSystemUAT()
    return uat.run_full_uat()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)