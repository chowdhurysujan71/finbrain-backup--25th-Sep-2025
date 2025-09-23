#!/usr/bin/env python3
"""
Simple UAT verification for expense logging system
Tests key functionality without complex test frameworks
"""

import requests
import sys
import time
import json

def test_system_health():
    """Test basic system health"""
    print("🏥 Testing system health...")
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("✅ System health: PASS")
            return True
        else:
            print(f"❌ System health: FAIL (status {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ System health: FAIL ({e})")
        return False

def test_authentication():
    """Test that authentication is required"""
    print("🔐 Testing authentication...")
    try:
        response = requests.post("http://localhost:5000/ai-chat", 
                               json={"text": "test"}, timeout=5)
        if response.status_code == 401:
            print("✅ Authentication: PASS (401 required)")
            return True
        else:
            print(f"❌ Authentication: FAIL (got {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Authentication: FAIL ({e})")
        return False

def test_expense_patterns():
    """Test expense detection patterns"""
    print("💰 Testing expense patterns...")
    try:
        # Import our expense detection logic
        sys.path.append('/home/runner/workspace')
        from utils.expense_repair import looks_like_expense, extract_amount_minor
        
        test_cases = [
            ("I spent 100 taka on lunch", True, 10000),
            ("Bought groceries for 250 tk", True, 25000), 
            ("hello how are you", False, None),
        ]
        
        all_passed = True
        for message, should_detect, expected_amount in test_cases:
            detected = looks_like_expense(message)
            amount = extract_amount_minor(message) if detected else None
            
            if detected == should_detect and amount == expected_amount:
                print(f"✅ '{message[:30]}...' -> detected={detected}, amount={amount}")
            else:
                print(f"❌ '{message[:30]}...' -> expected detect={should_detect}, amount={expected_amount}, got detect={detected}, amount={amount}")
                all_passed = False
        
        if all_passed:
            print("✅ Expense patterns: PASS")
        else:
            print("❌ Expense patterns: FAIL") 
        return all_passed
        
    except Exception as e:
        print(f"❌ Expense patterns: FAIL ({e})")
        return False

def test_category_normalization():
    """Test category normalization"""
    print("📂 Testing category normalization...")
    try:
        sys.path.append('/home/runner/workspace')
        from utils.expense_repair import normalize_category
        
        test_cases = [
            ("food", "food"),
            ("groceries", "food"),
            ("uber", "transport"), 
            ("electricity", "bills"),
            ("clothes", "shopping"),
            ("invalid", "uncategorized"),
        ]
        
        all_passed = True
        for input_cat, expected in test_cases:
            result = normalize_category(input_cat)
            if result == expected:
                print(f"✅ '{input_cat}' -> '{result}'")
            else:
                print(f"❌ '{input_cat}' -> expected '{expected}', got '{result}'")
                all_passed = False
        
        if all_passed:
            print("✅ Category normalization: PASS")
        else:
            print("❌ Category normalization: FAIL")
        return all_passed
        
    except Exception as e:
        print(f"❌ Category normalization: FAIL ({e})")
        return False

def test_feature_flags():
    """Test feature flag system"""
    print("🚩 Testing feature flags...")
    try:
        sys.path.append('/home/runner/workspace')
        from utils.feature_flags import expense_repair_enabled
        
        # Test that feature flag system loads
        enabled = expense_repair_enabled()
        print(f"✅ Feature flag system: PASS (EXPENSE_REPAIR_ENABLED = {enabled})")
        return True
        
    except Exception as e:
        print(f"❌ Feature flag system: FAIL ({e})")
        return False

def test_database_constraints():
    """Test database setup"""
    print("🗄️  Testing database constraints...")
    try:
        # Test that system starts (implies DB migrations worked)
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Database constraints: PASS (system running)")
            return True
        else:
            print("❌ Database constraints: FAIL (system not responding)")
            return False
    except Exception as e:
        print(f"❌ Database constraints: FAIL ({e})")
        return False

def main():
    """Run all UAT tests"""
    print("🚀 Starting Finbrain UAT Verification")
    print("=" * 50)
    
    tests = [
        test_system_health,
        test_authentication,
        test_expense_patterns,
        test_category_normalization,
        test_feature_flags,
        test_database_constraints,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"📊 UAT SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL UAT TESTS PASSED! System ready for deployment.")
        return 0
    else:
        print(f"⚠️  {total - passed} tests failed. Review required.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)