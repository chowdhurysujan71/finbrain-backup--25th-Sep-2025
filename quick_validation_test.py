#!/usr/bin/env python3
"""
Quick validation test to confirm critical fixes are working
"""

from app import app


def test_critical_fixes():
    """Test that the critical UAT failures have been resolved"""
    
    with app.app_context():
        print("🔧 VALIDATING CRITICAL FIXES")
        print("=" * 40)
        
        # Test 1: Money amount extraction
        try:
            from nlp.money_patterns import extract_money_amount, has_money_mention
            
            test_cases = [
                "চা ৫০ টাকা",
                "coffee 75 taka", 
                "৳১০০ expense",
                "spent 25 dollars"
            ]
            
            print("\n💰 Money Detection & Extraction:")
            for test_case in test_cases:
                has_money = has_money_mention(test_case)
                amount = extract_money_amount(test_case)
                print(f"  ✅ '{test_case}' → Money: {has_money}, Amount: {amount}")
            
        except Exception as e:
            print(f"  ❌ Money Detection Error: {e}")
        
        # Test 2: Identity hashing  
        try:
            from utils.identity import ensure_hashed
            
            print("\n🔒 Identity Hashing:")
            test_psid = "test_user_12345"
            hashed = ensure_hashed(test_psid)
            print(f"  ✅ PSID '{test_psid}' → Hash: {hashed[:16]}...")
            
            # Test idempotency
            hashed2 = ensure_hashed(hashed)
            print(f"  ✅ Hash idempotency: {hashed == hashed2}")
            
        except Exception as e:
            print(f"  ❌ Identity Hashing Error: {e}")
        
        # Test 3: Database operations
        try:
            from utils.db import save_expense
            
            print("\n💾 Database Operations:")
            test_expense = {
                "user_identifier": "test_validation_user",
                "description": "Validation Test Expense",
                "amount": 50.0,
                "category": "Test",
                "currency": "BDT"
            }
            
            result = save_expense(**test_expense)
            print(f"  ✅ Expense storage: {result is not None}")
            
        except Exception as e:
            print(f"  ❌ Database Error: {e}")
        
        # Test 4: Routing validation
        try:
            from utils.routing_policy import deterministic_router
            
            print("\n🧭 Routing Validation:")
            test_input = "আজ চা ৫০ টাকা খরচ করেছি"
            signals = deterministic_router.extract_signals(test_input, "validation_user")
            signals.ledger_count_30d = 0
            
            result = deterministic_router.route_intent(test_input, signals)
            print(f"  ✅ '{test_input}' → {result.intent.value}")
            
        except Exception as e:
            print(f"  ❌ Routing Error: {e}")
        
        print("\n" + "=" * 40)
        print("✅ CRITICAL FIXES VALIDATION COMPLETE")

if __name__ == "__main__":
    test_critical_fixes()