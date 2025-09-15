#!/usr/bin/env python3
"""
Debug the conversational AI to see why it's not accessing real user data
"""

import logging
import sys
sys.path.insert(0, '.')

def debug_user_data():
    """Debug user expense data access"""
    from app import app, db
    from models import Expense
    from utils.conversational_ai import conversational_ai
    from utils.security import hash_psid
    
    with app.app_context():
        # Check the actual user PSID from recent expenses
        print("🔍 DEBUGGING CONVERSATIONAL AI DATA ACCESS")
        print("=" * 60)
        
        # Get recent expenses to find actual user PSID
        recent_expenses = Expense.query.order_by(Expense.created_at.desc()).limit(10).all()
        
        if recent_expenses:
            user_id = recent_expenses[0].user_id
            print(f"📊 Found user_id: {user_id[:16]}...")
            
            # Count expenses for this user
            user_expenses = Expense.query.filter_by(user_id=user_id).all()
            print(f"📈 Total expenses for user: {len(user_expenses)}")
            
            for exp in user_expenses[-5:]:  # Last 5
                print(f"  - {exp.amount}: {exp.description} ({exp.category})")
            
            # Now test conversational AI with a reverse-engineered PSID
            # We need to find the original PSID that hashes to this user_id
            print(f"\n🧪 Testing conversational AI with hashed user_id...")
            
            # Test the conversational AI context directly
            context = conversational_ai.get_user_expense_context(user_id, days=30)  # Pass hash directly
            
            print(f"Context retrieved: {context}")
            
            if context['has_data']:
                print(f"✅ Data found: {context['total_expenses']} expenses, total: {context['total_amount']}")
            else:
                print(f"❌ No data found in context")
                
        else:
            print("❌ No expenses found in database")

def test_with_known_psid():
    """Test with the PSID from the production scenario"""
    from app import app
    from utils.conversational_ai import conversational_ai
    from utils.security import hash_psid
    
    with app.app_context():
        # This is the test PSID that should have the clothes/uber expenses
        test_psid = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        print(f"\n🎯 Testing with known user hash: {test_psid[:16]}...")
        
        # Test conversational AI
        response, intent = conversational_ai.generate_summary_response(test_psid, "Give me a summary of my expenses")
        
        print(f"Response: {response}")
        print(f"Intent: {intent}")

if __name__ == "__main__":
    debug_user_data()
    test_with_known_psid()