#!/usr/bin/env python3
"""
Test both data access paths to understand the inconsistency
"""

import sys
sys.path.insert(0, '.')

def test_both_paths():
    """Test both data access paths"""
    from app import app
    from utils.security import hash_psid
    from utils.user_manager import user_manager
    from utils.conversational_ai import conversational_ai
    
    with app.app_context():
        print("🔍 TESTING BOTH DATA ACCESS PATHS")
        print("=" * 50)
        
        # Use the user hash we know has data
        user_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        print(f"Testing with hash: {user_hash[:16]}...")
        
        # Test Path A: Conversational AI direct access
        print("\n1. PATH A: Conversational AI Direct Access")
        context = conversational_ai.get_user_expense_context_direct(user_hash)
        print(f"   Has data: {context['has_data']}")
        print(f"   Total expenses: {context.get('total_expenses', 0)}")
        print(f"   Total amount: {context.get('total_amount', 0)}")
        
        # Test Path B: User Manager spending summary
        print("\n2. PATH B: User Manager Spending Summary")
        # This expects a PSID, not a hash, but let's test what happens
        
        # First, let's see what PSID would create this hash
        # We'll reverse-engineer or test with the hash directly
        
        # For now, let's test what the engagement system would see
        from utils.engagement import engagement_engine
        
        # Create mock user data
        mock_user_data = {
            'is_new': False,
            'has_completed_onboarding': True,
            'first_name': 'Test'
        }
        
        # Test if user manager can find data with the hash as PSID
        spend_data = user_manager.get_user_spending_summary(user_hash, days=7)
        print(f"   Spending summary: {spend_data}")
        
        # Test what engagement engine generates
        ai_prompt = engagement_engine.get_ai_prompt(mock_user_data, "test message", spend_data)
        print(f"   AI prompt preview: {ai_prompt[:150]}...")
        
        # Now test what happens if we use the hash differently
        print("\n3. PATH COMPARISON")
        
        # Check if user_manager is handling the hash correctly
        print(f"   User manager uses hash_psid() internally")
        print(f"   Conversational AI uses hash directly")
        print(f"   This might cause the discrepancy!")

if __name__ == "__main__":
    test_both_paths()