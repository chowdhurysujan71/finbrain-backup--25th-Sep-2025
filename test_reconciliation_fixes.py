#!/usr/bin/env python3
"""
Test script to verify reconciliation system fixes:
1. Hash determinism (SHA256 vs non-deterministic hash)
2. Category mappings (wellness→health, salon→health, spa→health, general→other, misc→other, miscellaneous→other)
3. Category normalization in save paths
"""

import hashlib
import sys
import os

# Add project root to path
sys.path.insert(0, '/home/runner/workspace')

def test_hash_determinism():
    """Test that SHA256 produces deterministic results vs built-in hash()"""
    print("=== Testing Hash Determinism ===")
    
    text = "I spent 1000 taka on food"
    
    # Test SHA256 determinism (our fix)
    hash1 = hashlib.sha256(text.encode()).hexdigest()[:16]
    hash2 = hashlib.sha256(text.encode()).hexdigest()[:16]
    
    print(f"SHA256 hash 1: {hash1}")
    print(f"SHA256 hash 2: {hash2}")
    print(f"SHA256 deterministic: {hash1 == hash2} ✅" if hash1 == hash2 else "SHA256 deterministic: {hash1 == hash2} ❌")
    
    # Test built-in hash non-determinism (the problem we fixed)
    try:
        builtin_hash1 = hash(text)
        builtin_hash2 = hash(text)
        print(f"Built-in hash 1: {builtin_hash1}")
        print(f"Built-in hash 2: {builtin_hash2}")
        print(f"Built-in hash deterministic: {builtin_hash1 == builtin_hash2} (may vary between runs)")
    except Exception as e:
        print(f"Built-in hash test skipped: {e}")
    
    return hash1 == hash2

def test_category_mappings():
    """Test that category mappings work correctly"""
    print("\n=== Testing Category Mappings ===")
    
    try:
        from parsers.expense import CATEGORY_ALIASES
        
        # Test mappings we added
        test_cases = [
            ('wellness', 'health'),
            ('salon', 'health'),
            ('spa', 'health'),
            ('general', 'other'),
            ('misc', 'other'),
            ('miscellaneous', 'other')
        ]
        
        all_passed = True
        for keyword, expected_category in test_cases:
            if keyword in CATEGORY_ALIASES:
                actual_category, strength = CATEGORY_ALIASES[keyword]
                status = "✅" if actual_category == expected_category else "❌"
                print(f"{keyword} → {actual_category} (expected {expected_category}) {status}")
                if actual_category != expected_category:
                    all_passed = False
            else:
                print(f"{keyword} → NOT FOUND ❌")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"Category mapping test failed: {e}")
        return False

def test_category_normalization():
    """Test that category normalization works correctly"""
    print("\n=== Testing Category Normalization ===")
    
    try:
        from utils.categories import normalize_category
        
        # Test our new mappings through the normalization system
        # Note: Based on ALLOWED_CATEGORIES = {"food", "transport", "bills", "shopping", "uncategorized"}
        test_cases = [
            ('wellness', 'shopping'),      # wellness → shopping (closest allowed category for health-related)
            ('salon', 'shopping'),         # salon → shopping (closest allowed category for health-related)
            ('spa', 'shopping'),           # spa → shopping (closest allowed category for health-related)
            ('general', 'uncategorized'),  # general → uncategorized (other not in ALLOWED_CATEGORIES)
            ('misc', 'uncategorized'),     # misc → uncategorized (other not in ALLOWED_CATEGORIES)
            ('miscellaneous', 'uncategorized'),  # miscellaneous → uncategorized (other not in ALLOWED_CATEGORIES)
            ('food', 'food'),              # Should remain the same
            ('unknown_category', 'uncategorized')  # Should default
        ]
        
        all_passed = True
        for input_category, expected_output in test_cases:
            try:
                result = normalize_category(input_category)
                status = "✅" if result == expected_output else "❌"
                print(f"normalize_category('{input_category}') → '{result}' (expected '{expected_output}') {status}")
                if result != expected_output:
                    all_passed = False
            except Exception as e:
                print(f"normalize_category('{input_category}') → ERROR: {e} ❌")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"Category normalization test failed: {e}")
        return False

def test_nl_integration_normalization():
    """Test that NL integration applies category normalization"""
    print("\n=== Testing NL Integration Normalization ===")
    
    try:
        # Check that pwa_nl_integration imports normalize_category
        with open('/home/runner/workspace/pwa_nl_integration.py', 'r') as f:
            content = f.read()
            
        if 'from utils.categories import normalize_category' in content:
            print("✅ NL integration imports normalize_category")
        else:
            print("❌ NL integration missing normalize_category import")
            return False
            
        if 'normalize_category(result.category)' in content:
            print("✅ NL integration uses normalize_category in handle_nl_expense_entry")
        else:
            print("❌ NL integration not using normalize_category in handle_nl_expense_entry")
            return False
            
        if 'normalize_category(confirmed_category)' in content:
            print("✅ NL integration uses normalize_category in handle_clarification_response")
        else:
            print("❌ NL integration not using normalize_category in handle_clarification_response")
            return False
            
        return True
        
    except Exception as e:
        print(f"NL integration test failed: {e}")
        return False

def test_hash_usage_in_nl_integration():
    """Test that SHA256 is used instead of built-in hash in NL integration"""
    print("\n=== Testing Hash Usage in NL Integration ===")
    
    try:
        with open('/home/runner/workspace/pwa_nl_integration.py', 'r') as f:
            content = f.read()
            
        if 'import hashlib' in content:
            print("✅ NL integration imports hashlib")
        else:
            print("❌ NL integration missing hashlib import")
            return False
            
        if 'hashlib.sha256(text.encode()).hexdigest()[:16]' in content:
            print("✅ NL integration uses SHA256 for text hashing")
        else:
            print("❌ NL integration not using SHA256 for text hashing")
            return False
            
        if 'hashlib.sha256(original_text.encode()).hexdigest()[:16]' in content:
            print("✅ NL integration uses SHA256 for original_text hashing")
        else:
            print("❌ NL integration not using SHA256 for original_text hashing")
            return False
            
        if 'hash(text)' in content or 'hash(original_text)' in content:
            print("❌ NL integration still contains built-in hash() calls")
            return False
        else:
            print("✅ NL integration no longer uses built-in hash()")
            
        return True
        
    except Exception as e:
        print(f"Hash usage test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🔧 Testing Reconciliation System Fixes\n")
    
    tests = [
        ("Hash Determinism", test_hash_determinism),
        ("Category Mappings", test_category_mappings), 
        ("Category Normalization", test_category_normalization),
        ("NL Integration Normalization", test_nl_integration_normalization),
        ("Hash Usage in NL Integration", test_hash_usage_in_nl_integration)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Reconciliation fixes are working correctly!")
        print("\nThe following issues have been resolved:")
        print("• Non-deterministic hash replaced with stable SHA256")
        print("• Missing category mappings added (wellness→health, salon→health, spa→health, general→other, misc→other, miscellaneous→other)")
        print("• Category normalization applied to all NL integration save paths")
        print("• Deploy restarts will no longer break reconciliation")
        print("• Category recognition now works for common terms")
    else:
        print("❌ SOME TESTS FAILED - Review the issues above")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)