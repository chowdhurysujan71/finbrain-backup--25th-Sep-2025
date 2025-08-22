#!/usr/bin/env python3
"""
Developer CLI for simulating new user expense logging
Tests the money detection and routing logic
"""

import sys
import os
import json
import hashlib
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def simulate_new_user_message(text: str, debug: bool = False):
    """
    Simulate a new user sending a message to test money detection and routing
    
    Args:
        text: The message text to test
        debug: Whether to print debug information
        
    Returns:
        Dict with routing results and database writes
    """
    try:
        # Import required components
        from finbrain.router import contains_money
        from parsers.expense import parse_amount_currency_category
        from utils.production_router import ProductionRouter
        from utils.identity import psid_hash
        
        # Generate fresh test user
        test_psid = f"test_user_{int(time.time())}"
        user_hash = psid_hash(test_psid)
        rid = f"dev_sim_{int(time.time() * 1000)}"
        
        print(f"🧪 Simulating new user message:")
        print(f"   Text: '{text}'")
        print(f"   PSID: {test_psid}")
        print(f"   Hash: {user_hash[:8]}...")
        print(f"   MID:  {rid}")
        print()
        
        # Step 1: Test money detection
        money_detected = contains_money(text)
        print(f"💰 Money Detection: {money_detected}")
        
        if money_detected:
            # Step 2: Test unified parser
            parsed_data = parse_amount_currency_category(text)
            print(f"📊 Parsed Data: {parsed_data}")
        else:
            parsed_data = {}
            print(f"📊 Parsed Data: (no money detected)")
        
        # Step 3: Test router
        router = ProductionRouter()
        
        # Mock the database save to prevent actual writes during testing
        from unittest.mock import patch
        with patch('utils.db.save_expense_idempotent') as mock_save:
            mock_save.return_value = {
                'duplicate': False,
                'success': True,
                'expense_id': 999,
                'monthly_total': float(parsed_data.get('amount', 0)),
                'expense_count': 1
            }
            
            response, intent, category, amount = router.route_message(text, test_psid, rid)
        
        print(f"🎯 Router Result:")
        print(f"   Intent:   {intent}")
        print(f"   Category: {category}")
        print(f"   Amount:   {amount}")
        print(f"   Response: {response}")
        print()
        
        # Check if structured telemetry would be emitted
        if money_detected and parsed_data:
            telemetry_data = {
                'intent': 'LOG',
                'amount': float(parsed_data['amount']),
                'currency': parsed_data['currency'],
                'category': parsed_data['category'],
                'psid_hash': user_hash,
                'mid': rid
            }
            print(f"📈 Telemetry Data: {json.dumps(telemetry_data, indent=2)}")
        
        # Summary
        result = {
            'money_detected': money_detected,
            'parsed_data': parsed_data,
            'router_intent': intent,
            'router_category': category,
            'router_amount': amount,
            'router_response': response,
            'test_passed': True
        }
        
        # Validate expectations for expense logging
        if money_detected:
            if intent not in ['log', 'log_duplicate']:
                result['test_passed'] = False
                print(f"❌ FAIL: Expected LOG intent but got {intent}")
            elif parsed_data and amount != float(parsed_data['amount']):
                result['test_passed'] = False
                print(f"❌ FAIL: Amount mismatch: expected {parsed_data['amount']}, got {amount}")
            else:
                print(f"✅ PASS: Money detection → LOG intent working correctly")
        else:
            if intent == 'log':
                result['test_passed'] = False
                print(f"❌ FAIL: No money detected but got LOG intent")
            else:
                print(f"✅ PASS: No money → {intent} intent (correct)")
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'test_passed': False}

def run_test_suite():
    """Run a comprehensive test suite"""
    test_cases = [
        "Spent 100 on lunch",
        "৳100 coffee", 
        "paid $25",
        "100 tk for transport",
        "bought €30 groceries",
        "summary",
        "hello",
        "show me my expenses"
    ]
    
    print("🧪 Running New User Logging Test Suite")
    print("=" * 50)
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}]")
        result = simulate_new_user_message(test_case)
        results.append({'test_case': test_case, **result})
        print("-" * 30)
    
    # Summary
    passed = sum(1 for r in results if r.get('test_passed', False))
    total = len(results)
    
    print(f"\n📋 Test Summary: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed:")
        for r in results:
            if not r.get('test_passed', False):
                print(f"   - {r['test_case']}: {r.get('error', 'failed validation')}")
    
    return results

def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {sys.argv[0]} '<message text>'     # Test single message")
        print(f"  python {sys.argv[0]} --test-suite         # Run full test suite")
        print(f"  python {sys.argv[0]} --help               # Show this help")
        print()
        print("Examples:")
        print(f"  python {sys.argv[0]} 'Spent 100 on lunch'")
        print(f"  python {sys.argv[0]} '৳100 coffee'")
        print(f"  python {sys.argv[0]} 'summary'")
        return
    
    if sys.argv[1] == '--help':
        main()
        return
    elif sys.argv[1] == '--test-suite':
        run_test_suite()
        return
    
    # Single message test
    message_text = sys.argv[1]
    result = simulate_new_user_message(message_text, debug=True)
    
    if result.get('test_passed'):
        print(f"\n🎉 Simulation completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Simulation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()