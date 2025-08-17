#!/usr/bin/env python3
"""
Test script to verify conversational AI read path after fixes
"""
import sys
import os
sys.path.append('.')

from utils.conversational_ai import ConversationalAI
from utils.crypto import ensure_hashed

def test_conversational_ai_fix():
    """Test the fixed conversational AI data access"""
    from app import app, db
    
    # Real user hashes from database
    test_users = [
        "9406d3902955fd67c5bb9bdaa24bb580cf38f5821d8e6b7678ff6950156ba0ec",  # 3 expenses, 700 total
        "fe9853b6f04f5ebcff7f52edab15c11b2f1cde64fa3544c7afdff6fc16ccffc5",  # 1 expense, 100 total
    ]
    
    with app.app_context():
        ai = ConversationalAI()
    
        print("Testing Conversational AI Data Access After Field Fixes")
        print("=" * 60)
        
        for user_hash in test_users:
            print(f"\nTesting User: {user_hash[:16]}...")
            
            # Test the original method (should be fixed now)
            context = ai.get_user_expense_context(user_hash, days=30)
            
            print(f"Has Data: {context['has_data']}")
            print(f"Total Expenses: {context['total_expenses']}")
            print(f"Total Amount: {context['total_amount']}")
            print(f"Categories: {list(context['categories'].keys())}")
            print(f"Recent Expenses: {len(context['recent_expenses'])}")
            
            # Test summary generation
            try:
                summary, intent = ai.generate_summary_response_direct(user_hash, "give me a summary")
                print(f"Summary Response: {summary[:100]}...")
                print(f"Intent: {intent}")
            except Exception as e:
                print(f"Summary Error: {e}")
            
            print("-" * 40)

if __name__ == "__main__":
    test_conversational_ai_fix()