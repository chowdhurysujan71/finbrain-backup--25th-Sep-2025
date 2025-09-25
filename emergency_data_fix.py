#!/usr/bin/env python3
"""
EMERGENCY DATA INTEGRITY FIX
Direct SQL approach to fix orphaned expenses and invalid user hashes
"""

import sys

sys.path.append('/home/runner/workspace')

from datetime import UTC, datetime, timezone

from sqlalchemy import text

from app import app, db


def emergency_fix():
    """Execute emergency SQL fixes for data integrity"""
    print("🚨 EMERGENCY DATA INTEGRITY FIX")
    print("=" * 40)
    
    with app.app_context():
        try:
            # 1. Create minimal user records for orphaned expenses
            print("1. Creating user records for orphaned expenses...")
            
            orphaned_users_sql = """
            SELECT DISTINCT e.user_id
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.user_id_hash
            WHERE u.user_id_hash IS NULL
            """
            
            orphaned_users = db.session.execute(text(orphaned_users_sql)).fetchall()
            
            for (user_id,) in orphaned_users:
                if len(user_id) == 64 and all(c in '0123456789abcdef' for c in user_id.lower()):
                    # Get total expenses for this user
                    total_sql = "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = :user_id"
                    total_result = db.session.execute(text(total_sql), {"user_id": user_id}).first()
                    total_amount, expense_count = total_result
                    
                    # Insert minimal user record
                    insert_user_sql = """
                    INSERT INTO users (
                        user_id_hash, platform, total_expenses, expense_count,
                        created_at, last_interaction, is_new, has_completed_onboarding,
                        onboarding_step, interaction_count, daily_message_count,
                        hourly_message_count, last_daily_reset, last_hourly_reset,
                        reminder_preference, privacy_consent_given, terms_accepted
                    ) VALUES (
                        :user_id, 'messenger', :total, :count,
                        :now, :now, false, true,
                        0, 1, 0,
                        0, :today, :now,
                        'none', true, true
                    )
                    """
                    
                    now = datetime.now(UTC)
                    today = now.date()
                    
                    db.session.execute(text(insert_user_sql), {
                        "user_id": user_id,
                        "total": float(total_amount),
                        "count": expense_count,
                        "now": now,
                        "today": today
                    })
                    
                    print(f"   ✅ Created user record: {user_id[:16]}... (৳{total_amount}, {expense_count} expenses)")
            
            # 2. Remove invalid user hash records (if they have no expenses)
            print("\n2. Cleaning invalid user hash records...")
            
            invalid_users_sql = """
            SELECT id, user_id_hash 
            FROM users 
            WHERE LENGTH(user_id_hash) != 64 
               OR user_id_hash !~ '^[0-9a-f]+$'
            """
            
            invalid_users = db.session.execute(text(invalid_users_sql)).fetchall()
            
            for user_id, user_hash in invalid_users:
                # Check if user has expenses
                expense_check_sql = "SELECT COUNT(*) FROM expenses WHERE user_id = :user_hash"
                expense_count = db.session.execute(text(expense_check_sql), {"user_hash": user_hash}).scalar()
                
                if expense_count == 0:
                    # Safe to delete
                    delete_sql = "DELETE FROM users WHERE id = :user_id"
                    db.session.execute(text(delete_sql), {"user_id": user_id})
                    print(f"   ✅ Removed invalid user record: ID={user_id}, Hash='{user_hash}'")
                else:
                    print(f"   ⚠️ Cannot remove invalid user with expenses: ID={user_id} ({expense_count} expenses)")
            
            # Commit all fixes
            db.session.commit()
            print("\n✅ All fixes committed to database")
            
            # 3. Validation
            print("\n3. Validating fixes...")
            
            # Check orphaned expenses
            remaining_orphans = db.session.execute(text("""
                SELECT COUNT(*)
                FROM expenses e
                LEFT JOIN users u ON e.user_id = u.user_id_hash
                WHERE u.user_id_hash IS NULL
            """)).scalar()
            
            # Check invalid hashes
            remaining_invalid = db.session.execute(text("""
                SELECT COUNT(*)
                FROM users
                WHERE LENGTH(user_id_hash) != 64 
                   OR user_id_hash !~ '^[0-9a-f]+$'
            """)).scalar()
            
            if remaining_orphans == 0 and remaining_invalid == 0:
                print("✅ ALL DATA INTEGRITY ISSUES RESOLVED")
                return True
            else:
                print(f"❌ Issues remain: {remaining_orphans} orphans, {remaining_invalid} invalid hashes")
                return False
                
        except Exception as e:
            print(f"❌ Error during emergency fix: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = emergency_fix()
    sys.exit(0 if success else 1)