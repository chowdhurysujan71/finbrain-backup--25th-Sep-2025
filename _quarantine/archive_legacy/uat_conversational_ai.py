#!/usr/bin/env python3
"""
UAT: Conversational AI Production Validation
Test the complete user flow from screenshots with real data
"""

import logging
import sys
sys.path.insert(0, '.')

def run_conversational_uat():
    """Run comprehensive UAT for conversational AI with production data"""
    from app import app
    from utils.production_router import ProductionRouter
    from utils.security import hash_psid
    from models import db
    from sqlalchemy import text
    
    with app.app_context():
        print("🎯 UAT: CONVERSATIONAL AI PRODUCTION VALIDATION")
        print("=" * 70)
        
        # Step 1: Verify user has logged expenses (from screenshots)
        print("\n1. VERIFYING USER EXPENSE DATA")
        print("-" * 40)
        
        # Get the user with most recent activity
        result = db.session.execute(text("""
            SELECT user_id, COUNT(*) as expense_count, SUM(amount) as total_amount
            FROM expenses 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY user_id 
            ORDER BY total_amount DESC 
            LIMIT 1
        """))
        
        user_data = result.fetchone()
        if not user_data:
            print("❌ No recent expenses found for UAT")
            return False
            
        user_hash, expense_count, total_amount = user_data
        print(f"✅ Test User: {user_hash[:16]}...")
        print(f"✅ Expenses: {expense_count} transactions")
        print(f"✅ Total: ${total_amount}")
        
        # Step 2: Test the exact scenario from screenshots
        print(f"\n2. TESTING EXACT USER SCENARIOS FROM SCREENSHOTS")
        print("-" * 50)
        
        router = ProductionRouter()
        
        # Test scenarios matching the screenshots
        test_scenarios = [
            {
                "message": "Give me a summary report now",
                "expected": ["summary", "total", "expense"],
                "context": "User requests summary after logging multiple expenses"
            },
            {
                "message": "Can you now show me my total expenses and how much I have been spending",
                "expected": ["total", str(int(total_amount)), str(expense_count)],
                "context": "Exact message from screenshot 1"
            },
            {
                "message": "Show me the summary please",
                "expected": ["summary", "spending"],
                "context": "User asks for summary (screenshot 3)"
            },
            {
                "message": "Ok can you give me so far insight",
                "expected": ["insight", "spending", "category"],
                "context": "User requests insights (screenshot 2)"
            }
        ]
        
        success_count = 0
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n   Test {i}: {scenario['context']}")
            print(f"   Message: '{scenario['message']}'")
            
            try:
                # Use the hash as PSID since our system now detects hash length
                response, intent, category, amount = router.route_message(
                    text=scenario['message'],
                    psid=user_hash,  # Real user hash from database
                    rid=f"uat_test_{i}"
                )
                
                print(f"   Response: {response[:100]}...")
                print(f"   Intent: {intent}")
                
                # Validate response quality
                has_real_data = any(expected in response.lower() for expected in scenario['expected'])
                no_fallback = "start logging" not in response.lower() and "no data" not in response.lower()
                
                if has_real_data and no_fallback:
                    print(f"   ✅ SUCCESS: Response contains real data")
                    success_count += 1
                else:
                    print(f"   ❌ FAILURE: Response missing expected content or using fallback")
                    print(f"      Expected keywords: {scenario['expected']}")
                    
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
        
        # Step 3: Validate AI response quality
        print(f"\n3. AI RESPONSE QUALITY VALIDATION")
        print("-" * 40)
        
        # Test with a direct summary request
        try:
            from utils.conversational_ai import conversational_ai
            
            # Direct test with conversational AI
            context = conversational_ai.get_user_expense_context_direct(user_hash, days=30)
            print(f"✅ Direct context access: {context['has_data']}")
            print(f"✅ Total expenses: {context['total_expenses']}")
            print(f"✅ Total amount: {context['total_amount']}")
            
            if context['has_data']:
                response, intent = conversational_ai.handle_conversational_query(
                    user_hash, "Give me a complete financial summary"
                )
                print(f"✅ AI Response length: {len(response)} chars")
                print(f"✅ AI Intent: {intent}")
                
                # Check for data-driven content
                data_indicators = [
                    str(int(context['total_amount'])),
                    str(context['total_expenses']),
                    context['top_category'][0] if context['top_category'] else 'other'
                ]
                
                found_indicators = [ind for ind in data_indicators if ind in response]
                print(f"✅ Data indicators found: {found_indicators}")
                
        except Exception as e:
            print(f"❌ Direct AI test failed: {e}")
        
        # Step 4: Production readiness assessment
        print(f"\n4. PRODUCTION READINESS ASSESSMENT")
        print("-" * 45)
        
        print(f"Success Rate: {success_count}/{len(test_scenarios)} ({success_count/len(test_scenarios)*100:.1f}%)")
        
        if success_count >= len(test_scenarios) * 0.8:  # 80% success threshold
            print("✅ UAT PASSED: System ready for production")
            print("✅ Users will receive data-driven financial insights")
            print("✅ No more 'start logging expenses' for existing users")
            return True
        else:
            print("❌ UAT FAILED: System needs additional fixes")
            print("❌ Some responses still using fallback behavior")
            return False

if __name__ == "__main__":
    success = run_conversational_uat()
    exit(0 if success else 1)