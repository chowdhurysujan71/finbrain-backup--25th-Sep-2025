#!/usr/bin/env python3
"""
CI Hash Consistency Check - Standalone Script

This script can be run in CI/CD pipelines to detect hash inconsistencies
that would break reconciliation after deploy restarts.

Exit codes:
- 0: All hash methods are consistent (PASS)
- 1: Hash inconsistency detected (FAIL - will break reconciliation)
- 2: Script execution error
"""

import hashlib
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def ensure_required_env_vars():
    """Ensure required environment variables are set"""
    required_vars = ['ID_SALT']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        # Set default for testing if not provided
        for var in missing_vars:
            if var == 'ID_SALT':
                os.environ[var] = 'default_test_salt_for_ci'
                logger.warning(f"Using default value for {var}")

def psid_hash_with_salt(psid: str) -> str:
    """Hash implementation from utils/identity.py - uses salt"""
    id_salt = os.getenv("ID_SALT")
    if not id_salt:
        raise RuntimeError("ID_SALT missing")
    return hashlib.sha256(f"{id_salt}|{psid}".encode()).hexdigest()

def ensure_hashed_no_salt(psid_or_hash: str) -> str:
    """Hash implementation from utils/crypto.py - no salt"""
    if not psid_or_hash:
        raise ValueError("psid_or_hash cannot be empty")
    
    # If it's already a 64-character hex string, return as-is
    if len(psid_or_hash) == 64 and all(c in '0123456789abcdef' for c in psid_or_hash.lower()):
        return psid_or_hash.lower()
    
    # Otherwise, hash it without salt
    return hashlib.sha256(psid_or_hash.encode('utf-8')).hexdigest()

def test_hash_consistency():
    """Test if both hash methods produce the same result"""
    test_psid = "ci_test_user_12345"
    
    logger.info("Testing hash consistency between utils/identity.py and utils/crypto.py")
    logger.info(f"Test PSID: {test_psid}")
    
    # Method 1: utils/identity.py with salt
    identity_hash = psid_hash_with_salt(test_psid)
    logger.info(f"utils/identity.py hash: {identity_hash}")
    
    # Method 2: utils/crypto.py without salt
    crypto_hash = ensure_hashed_no_salt(test_psid)
    logger.info(f"utils/crypto.py hash:    {crypto_hash}")
    
    # Check consistency
    hashes_match = identity_hash == crypto_hash
    logger.info(f"Hashes match: {hashes_match}")
    
    return hashes_match, identity_hash, crypto_hash

def main():
    """Main execution function"""
    print("=" * 60)
    print("CI HASH CONSISTENCY CHECK")
    print("=" * 60)
    
    try:
        # Ensure environment is set up
        ensure_required_env_vars()
        
        # Run hash consistency test
        hashes_match, identity_hash, crypto_hash = test_hash_consistency()
        
        print("\n" + "=" * 60)
        print("RESULTS:")
        
        if hashes_match:
            print("✅ PASS: Hash methods are consistent")
            print("   Both utils/identity.py and utils/crypto.py produce the same hash")
            print("   Reconciliation will work correctly after restarts")
            return 0
        else:
            print("❌ FAIL: Hash methods are inconsistent")
            print(f"   utils/identity.py: {identity_hash}")
            print(f"   utils/crypto.py:   {crypto_hash}")
            print("")
            print("IMPACT:")
            print("- Users will lose access to their expense data after restarts")
            print("- Reconciliation will fail when hash method changes")
            print("- Database queries will return empty results for existing users")
            print("")
            print("FIX REQUIRED:")
            print("- Unify all hash methods to use the same implementation")
            print("- Ensure consistent salt usage across all modules")
            print("- Test with this script before deploying")
            return 1
            
    except Exception as e:
        print(f"❌ SCRIPT EXECUTION ERROR: {str(e)}")
        print("This indicates a serious issue with the environment or codebase.")
        logger.exception("Unexpected error during execution")
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)