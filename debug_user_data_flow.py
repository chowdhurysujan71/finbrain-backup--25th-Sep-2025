#!/usr/bin/env python3
"""
Debug the complete user data flow to understand why summaries fail
"""

import logging
import sys
sys.path.insert(0, '.')

def debug_complete_flow():
    """Debug the complete data flow from Facebook PSID to database lookup"""
    from app import app
    from utils.security import hash_psid
    from utils.conversational_ai import conversational_ai
    from utils.production_router import ProductionRouter
    
    with app.app_context():
        print("🔍 DEBUGGING COMPLETE USER DATA FLOW")
        print("=" * 60)
        
        # Step 1: Check recent expenses in database
        from models import db
        from sqlalchemy import text
        
        print("\n1. Recent expenses in database:")
        result = db.session.execute(text("SELECT user_id, description, amount, category, created_at FROM expenses ORDER BY created_at DESC LIMIT 10"))
        expenses = result.fetchall()
        
        user_hashes = set()
        for expense in expenses:
            user_id, desc, amount, cat, created = expense
            user_hashes.add(user_id)
            print(f"   {user_id[:16]}... | {desc} | {amount} | {cat} | {created}")
            
        print(f"\n   Found {len(user_hashes)} unique user hashes")
        
        # Step 2: Test with the most recent user
        if user_hashes:
            test_hash = list(user_hashes)[0]
            print(f"\n2. Testing with user hash: {test_hash[:16]}...")
            
            # Direct conversational AI test
            context = conversational_ai.get_user_expense_context_direct(test_hash, days=30)
            print(f"   Direct context access:")
            print(f"   - Has data: {context['has_data']}")
            print(f"   - Total expenses: {context['total_expenses']}")
            print(f"   - Total amount: {context['total_amount']}")
            
            if context['has_data']:
                # Test conversational response
                print(f"\n3. Testing conversational AI with this hash:")
                response, intent = conversational_ai.handle_conversational_query(test_hash, "Give me a summary")
                print(f"   Response: {response}")
                print(f"   Intent: {intent}")
                
                # Test production router
                print(f"\n4. Testing production router:")
                router = ProductionRouter()
                
                # Router expects original PSID, but we need to find what PSID creates this hash
                # For now, test with the hash itself (this should work with our fixes)
                try:
                    response, intent, cat, amt = router.route_message(
                        text="Give me a summary", 
                        psid=test_hash,  # Use hash as PSID for testing
                        rid="debug_test"
                    )
                    print(f"   Router response: {response}")
                    print(f"   Router intent: {intent}")
                    
                    if "no data" in response.lower() or "start logging" in response.lower():
                        print("   ❌ ROUTER STILL FAILING - NEEDS INVESTIGATION")
                    else:
                        print("   ✅ ROUTER WORKING")
                        
                except Exception as e:
                    print(f"   ❌ Router error: {e}")
            else:
                print("   ❌ No data found for recent user")

if __name__ == "__main__":
    debug_complete_flow()