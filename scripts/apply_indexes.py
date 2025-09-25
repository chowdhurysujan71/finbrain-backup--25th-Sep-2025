#!/usr/bin/env python3
"""
Apply critical database indexes for FinBrain performance
Idempotent - safe to run multiple times
"""
import os
import sys

import psycopg2


def apply_indexes():
    """Apply performance indexes idempotently"""
    indexes = [
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_uid_created ON expenses (user_id_hash, created_at DESC);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pca_expenses_uid_date ON pca_expenses (user_id, transaction_date DESC);", 
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monthly_summaries_uid_month ON monthly_summaries (user_id_hash, month, year);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_category ON expenses (category, created_at DESC);"
    ]
    
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.autocommit = True
        cursor = conn.cursor()
        
        for sql in indexes:
            print(f"Applying: {sql}")
            try:
                cursor.execute(sql)
                print("✓ Applied successfully")
            except Exception as e:
                if "already exists" in str(e):
                    print("✓ Index already exists")
                else:
                    print(f"✗ Error: {e}")
                    
        cursor.close()
        conn.close()
        print("\n✓ All indexes processed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    success = apply_indexes()
    sys.exit(0 if success else 1)