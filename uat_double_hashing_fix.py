#!/usr/bin/env python3
"""
UAT script to verify double-hashing fix
Tests that raw PSID and hashed PSID return identical results
"""

import sys
sys.path.insert(0, '.')

def test_double_hashing_fix():
    """Comprehensive test of double-hashing fix"""
    from app import app
    from utils.security import hash_psid
    from utils.user_manager import user_manager
    from utils.conversational_ai import conversational_ai
    from utils.production_router import ProductionRouter
    from models import db, Expense
    from datetime import datetime
    import json
    
    with app.app_context():
        print("🧪 UAT: DOUBLE-HASHING FIX VERIFICATION")
        print("=" * 60)
        
        # Demo PSID for testing
        demo_psid = "PSID_DEMO_001"
        demo_hash = hash_psid(demo_psid)
        
        print(f"Demo PSID: {demo_psid}")
        print(f"Computed Hash: {demo_hash}")
        print()
        
        # Clean up any existing test data first
        existing_expenses = Expense.query.filter_by(user_id=demo_hash).all()
        for expense in existing_expenses:
            db.session.delete(expense)
        db.session.commit()
        print(f"Cleaned up {len(existing_expenses)} existing test expenses")
        
        # Step 1: Create test expenses using RAW PSID
        print("\n1. CREATING TEST EXPENSES (via RAW PSID)")
        test_expenses = [
            {"amount": 500.0, "description": "Groceries", "category": "food"},
            {"amount": 150.0, "description": "Coffee", "category": "food"},
            {"amount": 300.0, "description": "Uber ride", "category": "transport"},
            {"amount": 1000.0, "description": "Shopping", "category": "shopping"}
        ]
        
        router = ProductionRouter()
        created_expenses = []
        
        for expense_data in test_expenses:
            # Simulate expense logging message
            message = f"{expense_data['description']} {expense_data['amount']}"
            response, intent, category, amount = router.route_message(
                text=message,
                psid=demo_psid,  # Using RAW PSID
                rid=f"test_{len(created_expenses)}"
            )
            created_expenses.append({
                "message": message,
                "response": response,
                "intent": intent,
                "amount": amount
            })
            print(f"   {message} → {response[:50]}...")
        
        print(f"\nCreated {len(created_expenses)} expenses via RAW PSID")
        
        # Step 2: Verify expenses were stored correctly
        print("\n2. VERIFYING STORED EXPENSES")
        stored_expenses = Expense.query.filter_by(user_id=demo_hash).all()
        total_stored = sum(float(e.amount) for e in stored_expenses)
        
        print(f"   Expenses in database: {len(stored_expenses)}")
        print(f"   Total amount stored: ${total_stored:.2f}")
        for expense in stored_expenses:
            print(f"     - {expense.description}: ${expense.amount} ({expense.category})")
        
        # Step 3: Test User Manager with RAW PSID
        print("\n3. TESTING USER MANAGER (RAW PSID)")
        raw_psid_summary = user_manager.get_user_spending_summary(demo_psid, days=7)
        raw_psid_total = sum(raw_psid_summary.values())
        
        print(f"   Raw PSID summary: {raw_psid_summary}")
        print(f"   Raw PSID total: ${raw_psid_total:.2f}")
        
        # Step 4: Test User Manager with HASHED PSID
        print("\n4. TESTING USER MANAGER (HASHED PSID)")
        hashed_psid_summary = user_manager.get_user_spending_summary(demo_hash, days=7)
        hashed_psid_total = sum(hashed_psid_summary.values())
        
        print(f"   Hashed PSID summary: {hashed_psid_summary}")
        print(f"   Hashed PSID total: ${hashed_psid_total:.2f}")
        
        # Step 5: Test Conversational AI with RAW PSID
        print("\n5. TESTING CONVERSATIONAL AI (RAW PSID)")
        raw_context = conversational_ai.get_user_expense_context(demo_psid)
        
        print(f"   Raw PSID context: has_data={raw_context['has_data']}")
        print(f"   Raw PSID expenses: {raw_context.get('total_expenses', 0)}")
        print(f"   Raw PSID total: ${raw_context.get('total_amount', 0):.2f}")
        
        # Step 6: Test Conversational AI with HASHED PSID (direct)
        print("\n6. TESTING CONVERSATIONAL AI (HASHED PSID)")
        hashed_context = conversational_ai.get_user_expense_context_direct(demo_hash)
        
        print(f"   Hashed PSID context: has_data={hashed_context['has_data']}")
        print(f"   Hashed PSID expenses: {hashed_context.get('total_expenses', 0)}")
        print(f"   Hashed PSID total: ${hashed_context.get('total_amount', 0):.2f}")
        
        # Step 7: Test Production Router with both formats
        print("\n7. TESTING PRODUCTION ROUTER")
        
        # Test with RAW PSID
        raw_response, raw_intent, _, _ = router.route_message(
            text="Show me my spending summary",
            psid=demo_psid,  # RAW PSID
            rid="test_raw_summary"
        )
        
        # Test with HASHED PSID
        hashed_response, hashed_intent, _, _ = router.route_message(
            text="Show me my spending summary", 
            psid=demo_hash,  # HASHED PSID
            rid="test_hashed_summary"
        )
        
        print(f"   Raw PSID response: {raw_response[:80]}...")
        print(f"   Hashed PSID response: {hashed_response[:80]}...")
        
        # Step 8: VERIFICATION AND RESULTS
        print("\n" + "=" * 60)
        print("🎯 VERIFICATION RESULTS")
        print("=" * 60)
        
        # Check if summaries are identical
        summaries_match = raw_psid_summary == hashed_psid_summary
        totals_match = abs(raw_psid_total - hashed_psid_total) < 0.01
        stored_total_matches = abs(total_stored - raw_psid_total) < 0.01
        
        # Check conversational AI consistency
        ai_raw_total = raw_context.get('total_amount', 0)
        ai_hashed_total = hashed_context.get('total_amount', 0)
        ai_totals_match = abs(ai_raw_total - ai_hashed_total) < 0.01
        
        print(f"✓ Database has {len(stored_expenses)} expenses totaling ${total_stored:.2f}")
        print(f"{'✓' if summaries_match else '✗'} User Manager summaries match: {summaries_match}")
        print(f"{'✓' if totals_match else '✗'} User Manager totals match: RAW=${raw_psid_total:.2f}, HASH=${hashed_psid_total:.2f}")
        print(f"{'✓' if stored_total_matches else '✗'} Stored total matches summaries: {stored_total_matches}")
        print(f"{'✓' if ai_totals_match else '✗'} Conversational AI totals match: RAW=${ai_raw_total:.2f}, HASH=${ai_hashed_total:.2f}")
        
        # Check for no double-hashing
        no_double_hashing = (
            len(demo_hash) == 64 and  # Hash is 64 chars
            summaries_match and       # Both paths find same data
            totals_match and         # Both paths sum same total
            ai_totals_match          # AI paths consistent
        )
        
        print(f"{'✓' if no_double_hashing else '✗'} No double-hashing detected: {no_double_hashing}")
        
        # Overall result
        all_tests_pass = summaries_match and totals_match and stored_total_matches and ai_totals_match
        
        print(f"\n🎉 OVERALL RESULT: {'PASS' if all_tests_pass else 'FAIL'}")
        
        if all_tests_pass:
            print("   All data access paths return identical results")
            print("   Double-hashing bug has been eliminated")
            print("   Raw PSID and hashed PSID produce consistent data")
        else:
            print("   ❌ Inconsistencies still exist")
            print("   Further debugging required")
        
        # Step 9: Cleanup
        print(f"\n9. CLEANING UP TEST DATA")
        cleanup_expenses = Expense.query.filter_by(user_id=demo_hash).all()
        for expense in cleanup_expenses:
            db.session.delete(expense)
        db.session.commit()
        print(f"   Cleaned up {len(cleanup_expenses)} test expenses")
        
        return all_tests_pass

if __name__ == "__main__":
    success = test_double_hashing_fix()
    sys.exit(0 if success else 1)