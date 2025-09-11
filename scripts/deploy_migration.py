#!/usr/bin/env python3
"""
Database Migration Script for Deployment Schema Conflicts
Handles schema conflicts during deployment by resolving duplicate indexes and table issues
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_connection():
    """Get database connection using environment DATABASE_URL"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable is required")
        return None
    
    try:
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

def check_index_exists(cursor, index_name):
    """Check if an index exists in the database"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE schemaname = 'public' AND indexname = %s
        )
    """, (index_name,))
    return cursor.fetchone()[0]

def drop_problematic_indexes(cursor):
    """Drop problematic indexes that are causing deployment conflicts"""
    
    problematic_indexes = [
        'idx_user_corrections_corr_id',
        'idx_user_corrections_user_created',
        'idx_user_corrections_tx_id',
        'idx_transactions_effective_user_date',
        'idx_transactions_effective_tx_id',
        'idx_transactions_effective_raw_expense',
        'idx_user_rules_user_active',
        'idx_user_rules_rule_id',
        'idx_inference_snapshots_user_created',
        'idx_inference_snapshots_intent_decision',
        'idx_inference_snapshots_cc_id',
        'idx_inference_snapshots_confidence'
    ]
    
    dropped_count = 0
    for index_name in problematic_indexes:
        try:
            if check_index_exists(cursor, index_name):
                cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
                logger.info(f"✓ Dropped problematic index: {index_name}")
                dropped_count += 1
            else:
                logger.debug(f"Index {index_name} does not exist, skipping")
        except Exception as e:
            logger.error(f"✗ Failed to drop index {index_name}: {e}")
    
    return dropped_count

def recreate_indexes_safely(cursor):
    """Recreate indexes with IF NOT EXISTS to prevent conflicts"""
    
    safe_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_user_corrections_user_created ON user_corrections (user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_user_corrections_tx_id ON user_corrections (tx_id);", 
        "CREATE INDEX IF NOT EXISTS idx_user_corrections_corr_id ON user_corrections (corr_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_effective_user_date ON transactions_effective (user_id, transaction_date);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_effective_tx_id ON transactions_effective (tx_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_effective_raw_expense ON transactions_effective (raw_expense_id);",
        "CREATE INDEX IF NOT EXISTS idx_user_rules_user_active ON user_rules (user_id, is_active);",
        "CREATE INDEX IF NOT EXISTS idx_user_rules_rule_id ON user_rules (rule_id);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_user_created ON inference_snapshots (user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_intent_decision ON inference_snapshots (intent, decision);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_cc_id ON inference_snapshots (cc_id);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_confidence ON inference_snapshots (confidence);"
    ]
    
    created_count = 0
    for sql in safe_indexes:
        try:
            cursor.execute(sql)
            logger.info(f"✓ Created/verified index: {sql.split('idx_')[1].split(' ')[0]}")
            created_count += 1
        except Exception as e:
            logger.error(f"✗ Failed to create index: {sql} - {e}")
    
    return created_count

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        )
    """, (table_name,))
    return cursor.fetchone()[0]

def verify_required_tables(cursor):
    """Verify that all required tables exist"""
    
    required_tables = [
        'expenses', 'users', 'monthly_summaries', 
        'user_corrections', 'transactions_effective', 
        'user_rules', 'inference_snapshots'
    ]
    
    missing_tables = []
    for table_name in required_tables:
        if not check_table_exists(cursor, table_name):
            missing_tables.append(table_name)
        else:
            logger.info(f"✓ Table exists: {table_name}")
    
    if missing_tables:
        logger.error(f"✗ Missing required tables: {missing_tables}")
        return False
    
    logger.info("✓ All required tables exist")
    return True

def run_migration():
    """Run the complete migration to fix deployment schema conflicts"""
    
    logger.info("=== DEPLOYMENT MIGRATION STARTING ===")
    
    # Connect to database
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Step 1: Verify required tables exist
        if not verify_required_tables(cursor):
            logger.error("✗ Cannot proceed - missing required tables")
            return False
        
        # Step 2: Drop problematic indexes
        logger.info("Step 1: Dropping problematic duplicate indexes...")
        dropped_count = drop_problematic_indexes(cursor)
        logger.info(f"✓ Dropped {dropped_count} problematic indexes")
        
        # Step 3: Recreate indexes safely
        logger.info("Step 2: Recreating indexes with IF NOT EXISTS...")
        created_count = recreate_indexes_safely(cursor)
        logger.info(f"✓ Created/verified {created_count} indexes")
        
        logger.info("=== DEPLOYMENT MIGRATION COMPLETED SUCCESSFULLY ===")
        return True
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

def rollback_migration():
    """Emergency rollback function to undo migration changes"""
    
    logger.warning("=== EMERGENCY ROLLBACK STARTING ===")
    
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # This is a safe rollback - we only drop indexes we created
        # Tables and data remain untouched
        all_indexes = [
            'idx_user_corrections_user_created',
            'idx_user_corrections_tx_id', 
            'idx_user_corrections_corr_id',
            'idx_transactions_effective_user_date',
            'idx_transactions_effective_tx_id',
            'idx_transactions_effective_raw_expense',
            'idx_user_rules_user_active',
            'idx_user_rules_rule_id',
            'idx_inference_snapshots_user_created',
            'idx_inference_snapshots_intent_decision',
            'idx_inference_snapshots_cc_id',
            'idx_inference_snapshots_confidence'
        ]
        
        for index_name in all_indexes:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
                logger.info(f"✓ Rolled back index: {index_name}")
            except Exception as e:
                logger.error(f"✗ Failed to rollback index {index_name}: {e}")
        
        logger.warning("=== ROLLBACK COMPLETED ===")
        return True
        
    except Exception as e:
        logger.error(f"✗ Rollback failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        success = rollback_migration()
    else:
        success = run_migration()
    
    sys.exit(0 if success else 1)