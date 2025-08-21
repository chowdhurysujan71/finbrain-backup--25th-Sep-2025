#!/usr/bin/env python3
"""
Test direct data access to prove the conversational AI can work
"""

import logging
import sys
sys.path.insert(0, '.')

def test_direct_access():
    """Test direct database access with the actual hash"""
    from app import app
    from utils.conversational_ai import conversational_ai
    
    with app.app_context():
        print("🔍 TESTING DIRECT DATA ACCESS")
        print("=" * 50)
        
        # Use the actual hash from database (no double hashing)
        user_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        print(f"Testing direct access with hash: {user_hash[:16]}...")
        
        # Test the new direct method
        context = conversational_ai.get_user_expense_context_direct(user_hash, days=30)
        
        print(f"📊 Context retrieved:")
        print(f"  - Has data: {context['has_data']}")
        print(f"  - Total expenses: {context['total_expenses']}")
        print(f"  - Total amount: {context['total_amount']}")
        
        if context['has_data']:
            print(f"  - Categories: {list(context['categories'].keys())}")
            print(f"  - Recent expenses: {len(context['recent_expenses'])}")
            
            # Generate summary using this context
            if context['total_amount'] > 0:
                summary = f"Your spending summary: {context['total_expenses']} expenses totaling {context['total_amount']:.0f}. Top category is {context['top_category'][0]} at {context['top_category'][1]['amount']:.0f}."
                
                print(f"✅ GENERATED SUMMARY: {summary}")
                return True
            else:
                print("❌ Total amount is 0")
                return False
        else:
            print("❌ No data found")
            return False

if __name__ == "__main__":
    test_direct_access()