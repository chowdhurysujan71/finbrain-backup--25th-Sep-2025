#!/usr/bin/env python3
"""
Check and create database indexes for performance optimization
"""
from app import app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_and_create_indexes():
    """Ensure proper indexes exist on critical fields"""
    
    with app.app_context():
        # Check for existing indexes
        result = db.session.execute(text("""
            SELECT tablename, indexname, indexdef
            FROM pg_indexes  
            WHERE schemaname = 'public'
            AND (tablename = 'expenses' OR tablename = 'users')
            ORDER BY tablename, indexname
        """))
        
        existing_indexes = {}
        for row in result:
            table = row[0]
            index_name = row[1]
            index_def = row[2]
            if table not in existing_indexes:
                existing_indexes[table] = []
            existing_indexes[table].append((index_name, index_def))
        
        print("=" * 60)
        print("DATABASE INDEX CHECK")
        print("=" * 60)
        
        # Display existing indexes
        for table, indexes in existing_indexes.items():
            print(f"\n{table} table indexes:")
            for idx_name, idx_def in indexes:
                print(f"  - {idx_name}")
                if "user_id" in idx_def:
                    print(f"    ✓ Has user_id index")
        
        # Create missing indexes
        try:
            # Critical performance index for expenses table
            logger.info("Creating index on expenses(user_id, created_at) if not exists...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_expenses_user_id_created_at 
                ON expenses(user_id, created_at DESC)
            """))
            
            # Index for user lookups
            logger.info("Creating unique index on users(user_id_hash) if not exists...")
            db.session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_id_hash 
                ON users(user_id_hash)
            """))
            
            db.session.commit()
            print("\n✅ All critical indexes ensured")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            db.session.rollback()
            print(f"\n❌ Failed to create indexes: {e}")
        
        # Verify indexes after creation
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        
        # Check query performance
        test_queries = [
            ("SELECT COUNT(*) FROM expenses WHERE user_id = 'test_hash'", "expenses by user_id"),
            ("SELECT * FROM users WHERE user_id_hash = 'test_hash'", "users by user_id_hash")
        ]
        
        for query, description in test_queries:
            try:
                explain_result = db.session.execute(text(f"EXPLAIN {query}"))
                plan = [row[0] for row in explain_result]
                uses_index = any("Index" in line or "index" in line.lower() for line in plan)
                
                if uses_index:
                    print(f"✅ {description}: Uses index")
                else:
                    print(f"⚠️  {description}: May not use index (check with real data)")
                    
            except Exception as e:
                print(f"❌ {description}: Query failed - {e}")
        
        print("\n" + "=" * 60)
        print("RECOMMENDATION")
        print("=" * 60)
        print("Consider running ANALYZE to update statistics:")
        print("  ANALYZE expenses;")
        print("  ANALYZE users;")

if __name__ == "__main__":
    check_and_create_indexes()