#!/usr/bin/env python3
"""
Test with the actual PSID that should have the expenses
"""

import logging
import sys
sys.path.insert(0, '.')

def find_real_psid():
    """Find the original PSID that creates the hash in the database"""
    from app import app
    from utils.security import hash_psid
    from models import Expense
    
    with app.app_context():
        # Get the user_id from database
        user_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        print(f"🔍 Looking for PSID that hashes to: {user_hash[:16]}...")
        
        # The hash in database corresponds to the actual Facebook PSID
        # Let's check recent expenses and try different PSIDs
        
        # Check if this hash already exists as expenses
        expenses = Expense.query.filter_by(user_id=user_hash).all()
        print(f"📊 Found {len(expenses)} expenses for this hash")
        
        # Try to reverse engineer or use actual production PSID
        # Based on the screenshots, this should be a real Facebook PSID
        
        # Test the conversational AI with a simulated production scenario
        from utils.production_router import ProductionRouter
        
        router = ProductionRouter()
        
        # Use the hash as if it were the original PSID (for testing)
        response, intent, category, amount = router.route_message(
            text="Give me a summary report now",
            psid=user_hash,  # Use the hash directly
            rid="debug_test"
        )
        
        print(f"✅ Response: {response}")
        print(f"🎯 Intent: {intent}")

if __name__ == "__main__":
    find_real_psid()