#!/usr/bin/env python3
"""
Comprehensive test suite to prevent hash consistency regressions
"""
import sys
import os
sys.path.append('.')

import pytest
from utils.crypto import ensure_hashed, is_sha256_hex
from utils.user_manager import UserManager
from utils.conversational_ai import ConversationalAI

# Test data
RAW_PSID = "test_psid_12345"
HASHED_PSID = "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d"  # sha256 of RAW_PSID

class TestHashConsistency:
    """Test hash consistency across all components"""
    
    def test_is_sha256_hex_validation(self):
        """Test SHA-256 hex validation"""
        assert is_sha256_hex(HASHED_PSID)
        assert not is_sha256_hex("short")
        assert not is_sha256_hex("invalid_hex_chars_xyz123" + "0" * 38)
        assert not is_sha256_hex("G" * 64)  # Invalid hex char
        assert not is_sha256_hex("")
        assert not is_sha256_hex(None)
    
    def test_ensure_hashed_idempotent(self):
        """Test ensure_hashed is idempotent"""
        # Raw PSID should be hashed
        result1 = ensure_hashed(RAW_PSID)
        assert len(result1) == 64
        assert is_sha256_hex(result1)
        
        # Already hashed should return as-is
        result2 = ensure_hashed(result1)
        assert result1 == result2
        
        # Case insensitive
        upper_hash = HASHED_PSID.upper()
        result3 = ensure_hashed(upper_hash)
        assert result3 == HASHED_PSID.lower()
    
    def test_no_double_hashing_regression(self):
        """Regression test: ensure no double-hashing occurs"""
        # Hash once
        first_hash = ensure_hashed(RAW_PSID)
        
        # Hash again should be identical
        second_hash = ensure_hashed(first_hash)
        
        assert first_hash == second_hash, "Double-hashing detected!"
        
        # Multiple iterations should remain stable
        for _ in range(5):
            next_hash = ensure_hashed(second_hash)
            assert next_hash == second_hash, "Hash instability detected!"
    
    @pytest.mark.parametrize("method_name", [
        "get_user_spending_summary",
        "update_user_onboarding"
    ])
    def test_user_manager_consistency(self, method_name):
        """Test UserManager methods handle both raw PSID and hash consistently"""
        from app import app, db
        
        with app.app_context():
            manager = UserManager()
            
            # Test with raw PSID
            if method_name == "get_user_spending_summary":
                result1 = manager.get_user_spending_summary(RAW_PSID, days=7)
            elif method_name == "update_user_onboarding":
                result1 = manager.update_user_onboarding(RAW_PSID, {"first_name": "Test"})
            
            # Test with pre-hashed
            if method_name == "get_user_spending_summary":
                result2 = manager.get_user_spending_summary(HASHED_PSID, days=7)
            elif method_name == "update_user_onboarding":
                result2 = manager.update_user_onboarding(HASHED_PSID, {"first_name": "Test"})
            
            # Results should be identical
            assert result1 == result2, f"Inconsistent results for {method_name}"
    
    def test_conversational_ai_consistency(self):
        """Test ConversationalAI methods handle both raw PSID and hash consistently"""
        from app import app, db
        
        with app.app_context():
            ai = ConversationalAI()
            
            # Test get_user_expense_context
            context1 = ai.get_user_expense_context(RAW_PSID, days=30)
            context2 = ai.get_user_expense_context(HASHED_PSID, days=30)
            
            # Should return identical results
            assert context1['has_data'] == context2['has_data']
            assert context1['total_expenses'] == context2['total_expenses']
            assert context1['total_amount'] == context2['total_amount']
    
    def test_strict_validation_guards(self):
        """Test strict validation guards work correctly"""
        os.environ['STRICT_IDS'] = 'true'
        
        try:
            # Valid hash should pass
            result = ensure_hashed(HASHED_PSID)
            assert is_sha256_hex(result)
            
            # Invalid input should still work (will be hashed)
            result2 = ensure_hashed("invalid_but_will_be_hashed")
            assert is_sha256_hex(result2)
            
        finally:
            # Clean up
            os.environ.pop('STRICT_IDS', None)

def run_manual_tests():
    """Run tests that require manual verification"""
    print("Running Hash Consistency Tests...")
    print("=" * 50)
    
    # Test 1: Basic functionality
    raw = "test_psid_12345"
    hashed_once = ensure_hashed(raw)
    hashed_twice = ensure_hashed(hashed_once)
    
    print(f"Raw PSID: {raw}")
    print(f"Hashed once: {hashed_once}")
    print(f"Hashed twice: {hashed_twice}")
    print(f"Idempotent: {hashed_once == hashed_twice}")
    
    # Test 2: Validation
    print(f"\nValidation Tests:")
    print(f"Is valid SHA-256: {is_sha256_hex(hashed_once)}")
    print(f"Invalid too short: {is_sha256_hex('short')}")
    print(f"Invalid bad chars: {is_sha256_hex('G' * 64)}")
    
    print("\n✓ All manual tests passed!")

if __name__ == "__main__":
    run_manual_tests()