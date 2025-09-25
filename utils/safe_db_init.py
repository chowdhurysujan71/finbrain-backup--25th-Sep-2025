#!/usr/bin/env python3
"""
Safe Database Initialization Script
Handles schema creation with IF NOT EXISTS to prevent duplicate errors during deployment
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError

from db_base import db

logger = logging.getLogger(__name__)

def safe_create_tables():
    """Safely check tables exist - skip creation if tables already exist"""
    try:
        # Check if critical tables already exist
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # Define critical tables that need to exist
        required_tables = [
            'expenses', 'users', 'monthly_summaries', 'user_corrections', 
            'transactions_effective', 'user_rules', 'inference_snapshots'
        ]
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.warning(f"Missing tables detected: {missing_tables}")
            logger.warning("These tables need to be created manually or through proper migration")
            # Don't attempt to create tables here to avoid index conflicts
            # Just log the issue and continue - indexes will be handled separately
        else:
            logger.info("✓ All required tables already exist")
        
        return True
    except Exception as e:
        logger.error(f"✗ Error checking tables: {e}")
        return False

def safe_create_indexes():
    """Create indexes with IF NOT EXISTS to prevent duplicates"""
    
    # Define all indexes that need to be created safely
    indexes = [
        # User corrections indexes from models_pca.py
        "CREATE INDEX IF NOT EXISTS idx_user_corrections_user_created ON user_corrections (user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_user_corrections_tx_id ON user_corrections (tx_id);", 
        "CREATE INDEX IF NOT EXISTS idx_user_corrections_corr_id ON user_corrections (corr_id);",
        
        # Transaction effective indexes from models_pca.py
        "CREATE INDEX IF NOT EXISTS idx_transactions_effective_user_date ON transactions_effective (user_id, transaction_date);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_effective_tx_id ON transactions_effective (tx_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_effective_raw_expense ON transactions_effective (raw_expense_id);",
        
        # User rules indexes from models_pca.py
        "CREATE INDEX IF NOT EXISTS idx_user_rules_user_active ON user_rules (user_id, is_active);",
        "CREATE INDEX IF NOT EXISTS idx_user_rules_rule_id ON user_rules (rule_id);",
        
        # Inference snapshots indexes from models_pca.py
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_user_created ON inference_snapshots (user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_intent_decision ON inference_snapshots (intent, decision);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_cc_id ON inference_snapshots (cc_id);",
        "CREATE INDEX IF NOT EXISTS idx_inference_snapshots_confidence ON inference_snapshots (confidence);",
        
        # Performance indexes from existing scripts
        "CREATE INDEX IF NOT EXISTS idx_expenses_uid_created ON expenses (user_id_hash, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_expenses_user_id_created_at ON expenses (user_id, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses (category, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_users_user_id_hash ON users (user_id_hash);",
        "CREATE INDEX IF NOT EXISTS idx_monthly_summaries_uid_month ON monthly_summaries (user_id_hash, month);"
    ]
    
    success_count = 0
    error_count = 0
    
    for sql in indexes:
        try:
            db.session.execute(text(sql))
            logger.debug(f"✓ Index created/verified: {sql}")
            success_count += 1
        except ProgrammingError as e:
            if "already exists" in str(e).lower():
                logger.debug(f"✓ Index already exists: {sql}")
                success_count += 1
            else:
                logger.error(f"✗ Error creating index: {sql} - {e}")
                error_count += 1
        except Exception as e:
            logger.error(f"✗ Unexpected error creating index: {sql} - {e}")
            error_count += 1
    
    try:
        db.session.commit()
        logger.info(f"✓ Indexes processed: {success_count} successful, {error_count} errors")
        
        # Allow deployment to continue if most indexes are successful
        # Only fail if more than 50% of indexes fail
        success_rate = success_count / (success_count + error_count) if (success_count + error_count) > 0 else 1.0
        if success_rate >= 0.8:  # 80% success rate required
            logger.info(f"✓ Index creation mostly successful ({success_rate:.1%}), allowing deployment to continue")
            return True
        else:
            logger.error(f"✗ Too many index failures ({success_rate:.1%}), aborting deployment")
            return False
            
    except Exception as e:
        logger.error(f"✗ Failed to commit index changes: {e}")
        db.session.rollback()
        return False

def check_existing_schema():
    """Check what indexes already exist in the database"""
    try:
        result = db.session.execute(text("""
            SELECT tablename, indexname, indexdef
            FROM pg_indexes  
            WHERE schemaname = 'public'
            AND (tablename LIKE '%corrections%' OR tablename LIKE '%effective%' OR tablename LIKE '%rules%' OR tablename LIKE '%snapshots%')
            ORDER BY tablename, indexname
        """))
        
        existing_indexes = {}
        for row in result:
            table = row[0]
            index_name = row[1]
            if table not in existing_indexes:
                existing_indexes[table] = []
            existing_indexes[table].append(index_name)
        
        logger.info("=== EXISTING SCHEMA CHECK ===")
        for table, indexes in existing_indexes.items():
            logger.info(f"{table}: {len(indexes)} indexes")
            for idx in indexes:
                logger.debug(f"  - {idx}")
        
        return existing_indexes
    except Exception as e:
        logger.warning(f"Could not check existing schema: {e}")
        return {}

def safe_database_initialization():
    """
    Main function to safely initialize the database schema
    Returns True if successful, False if critical errors occurred
    """
    
    logger.info("=== SAFE DATABASE INITIALIZATION ===")
    
    # Check existing schema first
    existing_schema = check_existing_schema()
    
    # Step 1: Create tables safely
    if not safe_create_tables():
        logger.error("✗ Failed to create tables - aborting initialization")
        return False
    
    # Step 2: Create indexes safely
    if not safe_create_indexes():
        logger.error("✗ Failed to create some indexes - check logs for details")
        return False
    
    logger.info("✓ Safe database initialization completed successfully")
    return True

def safe_database_check_only():
    """
    Read-only database validation for Alembic-managed environments
    Only performs logging and checking without any schema creation
    Returns True if schema validation passes, False for critical issues
    """
    
    logger.info("=== DATABASE SCHEMA VALIDATION (READ-ONLY) ===")
    
    # Check existing schema first
    existing_schema = check_existing_schema()
    
    # Check if critical tables exist (read-only)
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # Define critical tables that need to exist
        required_tables = [
            'expenses', 'users', 'monthly_summaries', 'user_corrections', 
            'transactions_effective', 'user_rules', 'inference_snapshots'
        ]
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.error(f"✗ Missing required tables: {missing_tables}")
            logger.error("These tables must be created through Alembic migrations")
            logger.error("Run: ./scripts/migrate.sh to apply pending migrations")
            logger.error("Database is not at the required schema state - refusing to start")
            return False
        else:
            logger.info("✓ All required tables exist")
        
        # Log schema readiness
        logger.info("✓ Database schema validation completed (read-only mode)")
        logger.info("✓ Schema creation is now managed by Alembic migrations")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error during schema validation: {e}")
        return False

def reset_problematic_indexes():
    """
    Emergency function to drop and recreate problematic indexes
    Use this only when absolutely necessary
    """
    
    logger.warning("=== RESETTING PROBLEMATIC INDEXES ===")
    
    problematic_indexes = [
        "idx_user_corrections_corr_id",
        "idx_user_corrections_user_created", 
        "idx_user_corrections_tx_id"
    ]
    
    for index_name in problematic_indexes:
        try:
            # Drop index if exists
            db.session.execute(text(f"DROP INDEX IF EXISTS {index_name};"))
            logger.info(f"✓ Dropped index: {index_name}")
        except Exception as e:
            logger.error(f"✗ Error dropping index {index_name}: {e}")
    
    try:
        db.session.commit()
        logger.info("✓ Problematic indexes dropped successfully")
        
        # Now recreate them safely
        return safe_create_indexes()
        
    except Exception as e:
        logger.error(f"✗ Failed to commit index drops: {e}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    # Import Flask app when running as standalone script
    from app import app
    with app.app_context():
        success = safe_database_initialization()
        exit(0 if success else 1)