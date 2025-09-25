#!/usr/bin/env python3
"""
UAT script for ensure_hashed user ID normalization
Tests that raw PSID and hash parameters produce identical results
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from utils.db import get_user_spending_summary, record_expense
from utils.security import hash_psid


def main():
    """Test ensure_hashed normalization end-to-end"""
    print("=== UAT: ensure_hashed User ID Normalization ===\n")
    
    # Test canary PSID
    raw_psid = "PSID_DEMO_CANARY"
    hashed_psid = hash_psid(raw_psid)
    
    print(f"Test PSID: {raw_psid}")
    print(f"SHA-256 Hash: {hashed_psid}")
    print()
    
    with app.app_context():
        try:
            # Test 1: Record expenses with raw PSID and hash
            print("1. Recording expenses...")
            result1 = record_expense(120, "groceries", psid=raw_psid)
            print(f"   Raw PSID expense: {result1}")
            
            result2 = record_expense(100, "uber", psid_hash=hashed_psid)
            print(f"   Hashed PSID expense: {result2}")
            print()
            
            # Test 2: Retrieve summaries with both parameters
            print("2. Retrieving spending summaries...")
            summary_raw = get_user_spending_summary(psid=raw_psid)
            print(f"   Raw PSID summary: {summary_raw}")
            
            summary_hash = get_user_spending_summary(psid_hash=hashed_psid)
            print(f"   Hashed PSID summary: {summary_hash}")
            print()
            
            # Test 3: Verify consistency
            print("3. Consistency validation...")
            totals_match = summary_raw.get('total', 0) == summary_hash.get('total', 0)
            counts_match = summary_raw.get('total_transactions', 0) == summary_hash.get('total_transactions', 0)
            expected_total = 220  # 120 + 100
            
            print(f"   Totals match: {totals_match}")
            print(f"   Counts match: {counts_match}")
            print(f"   Expected total: {expected_total}")
            print(f"   Actual total: {summary_raw.get('total', 0)}")
            
            # Test 4: Final assertion
            success = (
                totals_match and 
                counts_match and 
                summary_raw.get('total', 0) >= expected_total
            )
            
            print(f"\n✅ UAT Result: {'PASS' if success else 'FAIL'}")
            
            if success:
                print("✓ Both raw PSID and hash parameter produce identical results")
                print(f"✓ Total expenses: ${summary_raw.get('total', 0)}")
                print(f"✓ Transaction count: {summary_raw.get('total_transactions', 0)}")
            else:
                print("✗ Inconsistency detected in user ID normalization")
                return 1
                
        except Exception as e:
            print(f"✗ UAT Failed with error: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    return 0

if __name__ == "__main__":
    exit(main())