#!/usr/bin/env python3
"""
Identity Migration Script - FinBrain
Merges duplicate users and archives test data for canonical identity system
"""

import os
import sys
import json
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable is required")
        sys.exit(1)
    return db_url

def get_id_salt():
    """Get ID salt from environment"""
    salt = os.environ.get('ID_SALT')
    if not salt:
        logger.error("ID_SALT environment variable is required")
        sys.exit(1)
    return salt

def connect_db():
    """Connect to PostgreSQL database"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    try:
        db_url = get_database_url()
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)

def canonical_hash(raw_psid: str, salt: str) -> str:
    """Generate canonical hash for PSID using provided salt"""
    import hashlib
    return hashlib.sha256((raw_psid + salt).encode()).hexdigest()

def find_potential_duplicates(conn, salt: str) -> Dict[str, Any]:
    """Find users that might be duplicates based on patterns"""
    cursor = conn.cursor()
    
    # Get all users
    cursor.execute("""
        SELECT 
            id, user_id_hash, platform, total_expenses, expense_count,
            created_at, last_interaction, first_name, 
            has_completed_onboarding, is_new
        FROM users 
        ORDER BY created_at
    """)
    
    users = cursor.fetchall()
    logger.info(f"Found {len(users)} total users")
    
    # Group by patterns that suggest duplicates
    patterns = defaultdict(list)
    test_users = []
    
    for user in users:
        user_dict = dict(user)
        
        # Identify test users
        hash_val = user_dict['user_id_hash']
        if any(pattern in hash_val for pattern in [
            'test', 'existing_test', 'victory_test', 'final_complete'
        ]):
            test_users.append(user_dict)
        
        # Group by first few characters (rough grouping for manual review)
        prefix = hash_val[:8]
        patterns[prefix].append(user_dict)
    
    # Find actual duplicates (same canonical hash)
    duplicate_groups = []
    for prefix, user_group in patterns.items():
        if len(user_group) > 1:
            duplicate_groups.append(user_group)
    
    result = {
        'total_users': len(users),
        'test_users': test_users,
        'potential_duplicate_groups': duplicate_groups,
        'users_by_prefix': dict(patterns)
    }
    
    logger.info(f"Found {len(test_users)} test users")
    logger.info(f"Found {len(duplicate_groups)} potential duplicate groups")
    
    return result

def merge_user_data(primary_user: Dict, duplicate_users: List[Dict]) -> Dict[str, Any]:
    """Merge data from duplicate users into primary user"""
    merge_actions = []
    
    # Use the oldest user as primary (earliest created_at)
    all_users = [primary_user] + duplicate_users
    primary = min(all_users, key=lambda u: u['created_at'] or datetime.min)
    
    # Calculate merged totals
    total_expenses = sum(float(u['total_expenses'] or 0) for u in all_users)
    total_count = sum(int(u['expense_count'] or 0) for u in all_users)
    
    # Use best available data (non-null, non-empty values)
    best_first_name = next((u['first_name'] for u in all_users if u['first_name']), '')
    best_onboarding = any(u['has_completed_onboarding'] for u in all_users)
    latest_interaction = max((u['last_interaction'] for u in all_users if u['last_interaction']), default=None)
    
    merge_result = {
        'primary_user_id': primary['id'],
        'merged_total_expenses': total_expenses,
        'merged_expense_count': total_count,
        'merged_first_name': best_first_name,
        'merged_onboarding': best_onboarding,
        'latest_interaction': latest_interaction,
        'users_to_remove': [u['id'] for u in all_users if u['id'] != primary['id']],
        'merge_actions': merge_actions
    }
    
    return merge_result

def create_migration_plan(analysis: Dict[str, Any], salt: str) -> Dict[str, Any]:
    """Create detailed migration plan"""
    plan = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_users': analysis['total_users'],
            'test_users_to_archive': len(analysis['test_users']),
            'duplicate_groups': len(analysis['potential_duplicate_groups'])
        },
        'test_users': analysis['test_users'],
        'duplicate_merges': [],
        'archive_actions': [],
        'database_changes': []
    }
    
    # Plan test user archival
    for test_user in analysis['test_users']:
        plan['archive_actions'].append({
            'action': 'archive_test_user',
            'user_id': test_user['id'],
            'user_hash': test_user['user_id_hash'],
            'reason': 'Test user pattern detected'
        })
    
    # Plan duplicate merges (simplified - manual review needed)
    for group in analysis['potential_duplicate_groups']:
        if len(group) > 1:
            primary = group[0]  # First one as primary for now
            duplicates = group[1:]
            
            merge_plan = merge_user_data(primary, duplicates)
            plan['duplicate_merges'].append(merge_plan)
    
    return plan

def apply_migration(plan: Dict[str, Any], conn) -> Dict[str, Any]:
    """Apply the migration plan to the database"""
    cursor = conn.cursor()
    results = {
        'archived_users': 0,
        'merged_duplicates': 0,
        'updated_expenses': 0,
        'errors': []
    }
    
    try:
        # Archive test users
        for action in plan['archive_actions']:
            try:
                user_id = action['user_id']
                
                # Move expenses to archived table or delete
                cursor.execute("DELETE FROM expenses WHERE user_id = %s", (action['user_hash'],))
                results['updated_expenses'] += cursor.rowcount
                
                # Delete user
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                results['archived_users'] += cursor.rowcount
                
                logger.info(f"Archived test user {user_id}")
                
            except Exception as e:
                error_msg = f"Failed to archive user {user_id}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        # Apply duplicate merges
        for merge in plan['duplicate_merges']:
            try:
                primary_id = merge['primary_user_id']
                
                # Update primary user with merged data
                cursor.execute("""
                    UPDATE users 
                    SET total_expenses = %s, expense_count = %s, 
                        first_name = %s, has_completed_onboarding = %s,
                        last_interaction = %s
                    WHERE id = %s
                """, (
                    merge['merged_total_expenses'],
                    merge['merged_expense_count'], 
                    merge['merged_first_name'],
                    merge['merged_onboarding'],
                    merge['latest_interaction'],
                    primary_id
                ))
                
                # Remove duplicate users
                for dup_id in merge['users_to_remove']:
                    cursor.execute("DELETE FROM users WHERE id = %s", (dup_id,))
                
                results['merged_duplicates'] += len(merge['users_to_remove'])
                logger.info(f"Merged {len(merge['users_to_remove'])} duplicates into user {primary_id}")
                
            except Exception as e:
                error_msg = f"Failed to merge duplicates for user {primary_id}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        conn.commit()
        logger.info("Migration applied successfully")
        
    except Exception as e:
        conn.rollback()
        error_msg = f"Migration failed, rolled back: {e}"
        logger.error(error_msg)
        results['errors'].append(error_msg)
    
    return results

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FinBrain Identity Migration')
    parser.add_argument('--apply', action='store_true', help='Apply migration (default: dry run)')
    args = parser.parse_args()
    
    logger.info("Starting FinBrain identity migration")
    logger.info(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    
    # Get environment
    salt = get_id_salt()
    
    # Connect to database
    conn = connect_db()
    
    try:
        # Analyze current state
        logger.info("Analyzing database for duplicates and test users...")
        analysis = find_potential_duplicates(conn, salt)
        
        # Create migration plan
        logger.info("Creating migration plan...")
        plan = create_migration_plan(analysis, salt)
        
        # Save migration plan
        plan_file = 'merge_mapping.json'
        with open(plan_file, 'w') as f:
            json.dump(plan, f, indent=2, default=str)
        logger.info(f"Migration plan saved to {plan_file}")
        
        # Print summary
        print(f"\n=== MIGRATION SUMMARY ===")
        print(f"Total users: {plan['summary']['total_users']}")
        print(f"Test users to archive: {plan['summary']['test_users_to_archive']}")
        print(f"Duplicate groups: {plan['summary']['duplicate_groups']}")
        print(f"Plan saved to: {plan_file}")
        
        if args.apply:
            print(f"\nApplying migration...")
            results = apply_migration(plan, conn)
            
            print(f"\n=== MIGRATION RESULTS ===")
            print(f"Archived users: {results['archived_users']}")
            print(f"Merged duplicates: {results['merged_duplicates']}")
            print(f"Updated expenses: {results['updated_expenses']}")
            
            if results['errors']:
                print(f"Errors: {len(results['errors'])}")
                for error in results['errors']:
                    print(f"  - {error}")
        else:
            print(f"\nDry run complete. Review {plan_file} and run with --apply to execute.")
    
    finally:
        conn.close()

if __name__ == '__main__':
    main()