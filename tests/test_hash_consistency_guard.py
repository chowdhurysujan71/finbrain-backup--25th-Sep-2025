"""
CI Guard: Hash Consistency Enforcement

This test ensures that ALL hashing methods produce identical outputs,
preventing the hash inconsistency bug that breaks reconciliation.

CRITICAL: This test MUST pass in CI/CD to prevent deployment of 
hash inconsistencies that break user data reconciliation.
"""

import hashlib
import os

import pytest

from utils.crypto import ensure_hashed as crypto_ensure_hashed
from utils.identity import ensure_hashed as identity_ensure_hashed
from utils.identity import psid_hash


class TestHashConsistencyGuard:
    """CI guard tests to prevent hash method divergence"""
    
    def test_crypto_delegates_to_identity(self):
        """Ensure utils.crypto.ensure_hashed() delegates to utils.identity.ensure_hashed()"""
        test_values = [
            "test_user_12345",
            "1234567890",
            "messenger_psid_abc123",
            "web_session_user_xyz789"
        ]
        
        for test_value in test_values:
            identity_result = identity_ensure_hashed(test_value)
            crypto_result = crypto_ensure_hashed(test_value)
            
            assert identity_result == crypto_result, (
                f"Hash inconsistency detected!\n"
                f"Input: {test_value}\n"
                f"identity.ensure_hashed(): {identity_result}\n"
                f"crypto.ensure_hashed():   {crypto_result}\n"
                f"This would break user data reconciliation!"
            )
    
    def test_all_methods_use_salted_hashing(self):
        """Ensure all hashing methods use the salted approach"""
        test_psid = "test_consistency_psid"
        
        # All these should produce the same salted hash
        identity_hash = identity_ensure_hashed(test_psid)
        crypto_hash = crypto_ensure_hashed(test_psid)
        direct_psid_hash = psid_hash(test_psid)
        
        assert identity_hash == crypto_hash == direct_psid_hash, (
            f"Salted hash inconsistency!\n"
            f"identity.ensure_hashed(): {identity_hash}\n"
            f"crypto.ensure_hashed():   {crypto_hash}\n"
            f"psid_hash():              {direct_psid_hash}\n"
            f"All methods must use the same salted hashing approach!"
        )
    
    def test_no_direct_unsalted_hashing_allowed(self):
        """Prevent direct usage of hashlib.sha256 without salt"""
        test_psid = "test_unsalted_prevention"
        
        # Get the correct salted hash
        correct_hash = psid_hash(test_psid)
        
        # This is what the old broken method would produce
        broken_hash = hashlib.sha256(test_psid.encode('utf-8')).hexdigest()
        
        # They MUST be different - if they're the same, someone removed the salt!
        assert correct_hash != broken_hash, (
            f"CRITICAL: Salting has been removed from hash functions!\n"
            f"Salted hash:   {correct_hash}\n"
            f"Unsalted hash: {broken_hash}\n"
            f"These must be different to prevent the reconciliation bug!"
        )
    
    def test_id_salt_is_mandatory(self):
        """Ensure ID_SALT environment variable is present and non-empty"""
        id_salt = os.getenv("ID_SALT")
        assert id_salt is not None, "ID_SALT environment variable is missing!"
        assert len(id_salt) > 0, "ID_SALT cannot be empty!"
        assert len(id_salt) >= 8, "ID_SALT must be at least 8 characters for security!"
    
    def test_hash_format_validation(self):
        """Ensure all hashes are 64-character hex strings"""
        test_values = ["test1", "test2", "test3"]
        
        for test_value in test_values:
            result = identity_ensure_hashed(test_value)
            
            assert isinstance(result, str), f"Hash must be string, got {type(result)}"
            assert len(result) == 64, f"Hash must be 64 chars, got {len(result)}"
            assert all(c in '0123456789abcdef' for c in result.lower()), (
                f"Hash must be hex, got {result}"
            )
    
    def test_prevent_reconciliation_failure_scenario(self):
        """Test the exact scenario that caused reconciliation failures"""
        # This simulates a user PSID that would cause reconciliation failure
        test_psid = "reconciliation_test_user"
        
        # Step 1: Hash during expense creation (should use salted method)
        expense_hash = identity_ensure_hashed(test_psid)
        
        # Step 2: Hash during data retrieval (must be identical)
        retrieval_hash = crypto_ensure_hashed(test_psid)
        
        # Step 3: These MUST match or user data becomes inaccessible
        assert expense_hash == retrieval_hash, (
            f"RECONCILIATION FAILURE DETECTED!\n"
            f"Expense creation hash: {expense_hash}\n"
            f"Data retrieval hash:   {retrieval_hash}\n"
            f"User data would be inaccessible after restart!"
        )
        
        print(f"✅ Reconciliation test passed - hashes match: {expense_hash}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])