#!/usr/bin/env python3
"""
Test script to verify Bengali food categorization is working correctly
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

from parsers.expense import extract_all_expenses, infer_category_with_strength


def test_categorization():
    """Test that Bengali food terms are properly categorized"""
    
    test_cases = [
        # Original issue cases
        "tarmujer rosh 250",
        "jaali kabab 180", 
        
        # Other Bengali foods that should be categorized as food
        "fuchka 50",
        "chotpoti 70", 
        "roshogolla 120",
        "kacchi biriyani 380",
        "hilsa fish 450",
        "mishti doi 80",
        "cha 25",
        "bharta 60"
    ]
    
    print("🧪 Testing Bengali Food Categorization")
    print("=" * 50)
    
    now = datetime.now()
    all_passed = True
    
    for test_text in test_cases:
        print(f"\nTesting: '{test_text}'")
        
        # Test the expense parsing
        expenses = extract_all_expenses(test_text, now)
        
        if expenses:
            expense = expenses[0]
            category = expense['category']
            print(f"  → Amount: {expense['amount']} {expense['currency']}")
            print(f"  → Category: {category}")
            
            if category == 'food':
                print("  ✅ PASS - Correctly categorized as food")
            else:
                print(f"  ❌ FAIL - Incorrectly categorized as '{category}' instead of 'food'")
                all_passed = False
        else:
            print("  ❌ FAIL - No expense found")
            all_passed = False
        
        # Also test direct category inference
        direct_category = infer_category_with_strength(test_text)
        print(f"  → Direct category inference: {direct_category}")
        
        if direct_category != 'food':
            print(f"  ⚠️  Warning: Direct inference gave '{direct_category}' instead of 'food'")
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests PASSED! Bengali food terms are properly categorized.")
    else:
        print("❌ Some tests FAILED. Check the category mapping.")
    
    return all_passed

if __name__ == "__main__":
    test_categorization()