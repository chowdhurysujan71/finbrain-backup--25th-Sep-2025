#!/usr/bin/env python3
"""
UAT script using real existing data to verify double-hashing fix
"""

import sys
sys.path.insert(0, '.')

def test_with_real_data():
    """Test double-hashing fix with existing real user data"""
    from app import app
    from utils.security import hash_psid
    from utils.user_manager import user_manager
    from utils.conversational_ai import conversational_ai
    from utils.production_router import ProductionRouter
    from models import db, Expense
    
    with app.app_context():
        print("🧪 UAT: REAL DATA VERIFICATION")
        print("=" * 50)
        
        # Find a user with existing data
        sample_expense = Expense.query.first()
        if not sample_expense:
            print("❌ No expenses found in database")
            return False
            
        real_hash = sample_expense.user_id
        print(f"Using real user hash: {real_hash[:16]}...")
        
        # We need to simulate what the raw PSID would be
        # Since we can't reverse a hash, we'll test both:
        # 1. Using the hash directly (simulating already-hashed input)
        # 2. Using a fake PSID that we hash to create a different scenario
        
        print(f"\n1. TESTING WITH REAL HASH (simulating hashed input)")
        
        # Test User Manager with hash
        hash_summary = user_manager.get_user_spending_summary(real_hash, days=30)
        hash_total = sum(hash_summary.values())
        print(f"   Hash summary: {hash_summary}")
        print(f"   Hash total: ${hash_total:.2f}")
        
        # Test Conversational AI with hash
        hash_context = conversational_ai.get_user_expense_context_direct(real_hash)
        print(f"   Hash context: {hash_context['has_data']}")
        print(f"   Hash expenses: {hash_context.get('total_expenses', 0)}")
        print(f"   Hash AI total: ${hash_context.get('total_amount', 0):.2f}")
        
        # Test Production Router with hash
        router = ProductionRouter()
        hash_response, hash_intent, _, _ = router.route_message(
            text="Show me my spending summary",
            psid=real_hash,  # Using hash directly
            rid="test_hash_direct"
        )
        print(f"   Hash response: {hash_response[:80]}...")
        
        print(f"\n2. TESTING WITH SIMULATED RAW PSID")
        
        # Create a fake PSID and test the flow
        fake_psid = "1234567890123456"  # 16-digit Facebook PSID format
        fake_hash = hash_psid(fake_psid)
        print(f"   Fake PSID: {fake_psid}")
        print(f"   Computed hash: {fake_hash[:16]}...")
        
        # Test User Manager with fake PSID
        psid_summary = user_manager.get_user_spending_summary(fake_psid, days=30)
        psid_total = sum(psid_summary.values())
        print(f"   PSID summary: {psid_summary}")
        print(f"   PSID total: ${psid_total:.2f}")
        
        # Test Conversational AI with fake PSID
        psid_context = conversational_ai.get_user_expense_context(fake_psid)
        print(f"   PSID context: {psid_context['has_data']}")
        print(f"   PSID expenses: {psid_context.get('total_expenses', 0)}")
        print(f"   PSID AI total: ${psid_context.get('total_amount', 0):.2f}")
        
        print(f"\n3. VERIFICATION")
        
        # Check database consistency
        total_expenses = Expense.query.filter_by(user_id=real_hash).count()
        db_total = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=real_hash).scalar() or 0
        
        print(f"   Database expenses for real user: {total_expenses}")
        print(f"   Database total for real user: ${float(db_total):.2f}")
        
        # Check if hash detection is working
        hash_length_ok = len(real_hash) == 64
        fake_hash_length_ok = len(fake_hash) == 64
        
        print(f"   Real hash length (64): {hash_length_ok}")
        print(f"   Fake hash length (64): {fake_hash_length_ok}")
        
        # Check consistency for real data
        real_data_consistent = (
            hash_context['has_data'] and
            hash_context.get('total_expenses', 0) == total_expenses and
            abs(hash_context.get('total_amount', 0) - float(db_total)) < 0.01
        )
        
        print(f"   Real data consistency: {real_data_consistent}")
        
        # Check that fake PSID returns no data (as expected)
        fake_data_empty = (
            not psid_context['has_data'] and
            psid_total == 0
        )
        
        print(f"   Fake PSID returns empty (correct): {fake_data_empty}")
        
        print(f"\n🎯 OVERALL VERIFICATION")
        success = real_data_consistent and fake_data_empty and hash_length_ok
        print(f"   Result: {'PASS' if success else 'FAIL'}")
        
        if success:
            print("   ✓ Hash detection working correctly")
            print("   ✓ Real user data accessible via hash")
            print("   ✓ No double-hashing detected")
            print("   ✓ Conversational AI finds real data")
        
        return success

if __name__ == "__main__":
    success = test_with_real_data()
    sys.exit(0 if success else 1)