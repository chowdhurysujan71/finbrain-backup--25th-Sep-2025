#!/usr/bin/env python3
"""
Test the evolved AI expense parser to verify multi-item parsing
Tests the exact scenario from the screenshot: "coffee 100, burger 300 and watermelon juice 300"
"""

import logging
import sys
sys.path.insert(0, '.')

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_multi_item_parsing():
    """Test the AI expense parser with the exact message from the screenshot"""
    from utils.ai_expense_parser import ai_expense_parser
    
    # Test message from the screenshot
    test_message = "Logging today's expenses - coffee 100, burger 300 and watermelon juice 300"
    
    print(f"🧪 Testing AI Expense Parser Evolution")
    print(f"📝 Message: {test_message}")
    print(f"🎯 Expected: 3 expenses totaling 700")
    print("=" * 60)
    
    try:
        # Parse the message using evolved AI system
        result = ai_expense_parser.parse_message(test_message)
        
        print(f"✅ Parsing Success: {result['success']}")
        print(f"📊 Items Found: {result['item_count']}")
        print(f"💰 Total Amount: {result['total_amount']}")
        print(f"🎯 Intent: {result['intent']}")
        print(f"🔥 Confidence: {result['confidence']}")
        
        if result['success'] and result['expenses']:
            print(f"\n📋 Expense Breakdown:")
            for i, expense in enumerate(result['expenses'], 1):
                print(f"  {i}. {expense['amount']} - {expense['description']} ({expense['category']})")
        
        # Verify expected results
        expected_total = 700
        expected_count = 3
        
        if result['success']:
            if result['total_amount'] == expected_total:
                print(f"✅ Total amount matches expected: {expected_total}")
            else:
                print(f"❌ Total amount mismatch: got {result['total_amount']}, expected {expected_total}")
            
            if result['item_count'] == expected_count:
                print(f"✅ Item count matches expected: {expected_count}")
            else:
                print(f"❌ Item count mismatch: got {result['item_count']}, expected {expected_count}")
        else:
            print(f"❌ Parsing failed - the evolution didn't work as expected")
        
        return result
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return None

def test_simple_cases():
    """Test some simpler cases to ensure basic functionality works"""
    from utils.ai_expense_parser import ai_expense_parser
    
    test_cases = [
        "coffee 100",
        "spent 250 on lunch",
        "taxi 120, coffee 80",
        "grocery shopping 450"
    ]
    
    print(f"\n🧪 Testing Simple Cases")
    print("=" * 60)
    
    for i, message in enumerate(test_cases, 1):
        print(f"\nTest {i}: {message}")
        try:
            result = ai_expense_parser.parse_message(message)
            print(f"  Success: {result['success']}, Items: {result['item_count']}, Total: {result['total_amount']}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    # Test the main evolution scenario
    result = test_multi_item_parsing()
    
    # Test simpler cases
    test_simple_cases()
    
    # Summary
    print(f"\n🎯 EVOLUTION TEST SUMMARY")
    print("=" * 60)
    
    if result and result['success'] and result['item_count'] == 3 and result['total_amount'] == 700:
        print("✅ AI EXPENSE PARSER EVOLUTION SUCCESSFUL!")
        print("✅ Multi-item parsing now works correctly") 
        print("✅ System can handle: 'coffee 100, burger 300 and watermelon juice 300'")
        print("✅ Context awareness will now receive proper spending data")
    else:
        print("❌ Evolution needs more work")
        print("❌ Multi-item parsing not fully functional yet")