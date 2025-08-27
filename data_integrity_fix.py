#!/usr/bin/env python3
"""
CRITICAL DATA INTEGRITY FIX
Fixes orphaned expenses and invalid user hashes while preserving data
"""

import sys
sys.path.append('/home/runner/workspace')

from app import app, db
from models import User, Expense
import hashlib
from datetime import datetime, timezone
from sqlalchemy import text

def fix_orphaned_expenses():
    """Create missing user records for orphaned expenses"""
    print("🔧 FIXING ORPHANED EXPENSES")
    print("=" * 30)
    
    with app.app_context():
        # Find orphaned expenses
        orphaned_query = '''
        SELECT DISTINCT e.user_id
        FROM expenses e
        LEFT JOIN users u ON e.user_id = u.user_id_hash
        WHERE u.user_id_hash IS NULL
        '''
        
        orphaned_user_ids = [row[0] for row in db.session.execute(text(orphaned_query)).fetchall()]
        
        print(f"Found {len(orphaned_user_ids)} user IDs with orphaned expenses")
        
        fixes_applied = 0
        for user_id_hash in orphaned_user_ids:
            # Check if this is a valid hash format
            if len(user_id_hash) == 64 and all(c in '0123456789abcdef' for c in user_id_hash.lower()):
                # Create missing user record
                new_user = User(
                    user_id_hash=user_id_hash,
                    created_at=datetime.now(timezone.utc),
                    last_interaction=datetime.now(timezone.utc),
                    total_expenses=0
                )
                
                db.session.add(new_user)
                fixes_applied += 1
                print(f"   ✅ Created user record for {user_id_hash[:16]}...")
                
                # Update total_expenses for the new user
                total = db.session.query(db.func.sum(Expense.amount)).filter(
                    Expense.user_id == user_id_hash
                ).scalar() or 0
                
                new_user.total_expenses = float(total)
                print(f"      Set total_expenses to ৳{total}")
                
            else:
                print(f"   ❌ Invalid hash format, cannot fix: {user_id_hash}")
        
        if fixes_applied > 0:
            db.session.commit()
            print(f"✅ Fixed {fixes_applied} orphaned expense user records")
        
        return fixes_applied

def fix_invalid_user_hashes():
    """Fix invalid user hash formats"""
    print("\\n🔧 FIXING INVALID USER HASHES")
    print("=" * 35)
    
    with app.app_context():
        all_users = db.session.query(User).all()
        fixes_applied = 0
        
        for user in all_users:
            hash_len = len(user.user_id_hash) if user.user_id_hash else 0
            is_hex = all(c in '0123456789abcdef' for c in user.user_id_hash.lower()) if user.user_id_hash else False
            
            if hash_len != 64 or not is_hex:
                print(f"   ❌ Invalid hash found: ID={user.id}, Hash='{user.user_id_hash}', Length={hash_len}")
                
                # Check if this user has expenses
                expense_count = db.session.query(Expense).filter(Expense.user_id == user.user_id_hash).count()
                
                if expense_count > 0:
                    print(f"      User has {expense_count} expenses - CANNOT DELETE")
                    print(f"      Manual intervention required for user ID {user.id}")
                else:
                    # Safe to remove unused invalid user record
                    db.session.delete(user)
                    fixes_applied += 1
                    print(f"      ✅ Removed invalid unused user record")
        
        if fixes_applied > 0:
            db.session.commit()
            print(f"✅ Cleaned up {fixes_applied} invalid user records")
        
        return fixes_applied

def validate_fixes():
    """Validate that all fixes worked correctly"""
    print("\\n🧪 VALIDATING DATA INTEGRITY FIXES")
    print("=" * 40)
    
    with app.app_context():
        # Check for remaining orphaned expenses
        orphaned_query = '''
        SELECT COUNT(*)
        FROM expenses e
        LEFT JOIN users u ON e.user_id = u.user_id_hash
        WHERE u.user_id_hash IS NULL
        '''
        
        orphaned_count = db.session.execute(text(orphaned_query)).scalar()
        
        if orphaned_count == 0:
            print("✅ No orphaned expenses remaining")
        else:
            print(f"❌ Still have {orphaned_count} orphaned expenses")
        
        # Check for invalid hashes
        all_users = db.session.query(User).all()
        invalid_count = 0
        
        for user in all_users:
            hash_len = len(user.user_id_hash) if user.user_id_hash else 0
            is_hex = all(c in '0123456789abcdef' for c in user.user_id_hash.lower()) if user.user_id_hash else False
            
            if hash_len != 64 or not is_hex:
                invalid_count += 1
        
        if invalid_count == 0:
            print("✅ All user hashes properly formatted")
        else:
            print(f"❌ Still have {invalid_count} invalid user hashes")
        
        # Check user-expense relationship integrity
        expense_users = set(db.session.query(Expense.user_id).distinct().all())
        user_hashes = set((u.user_id_hash,) for u in all_users)
        missing = expense_users - user_hashes
        
        if len(missing) == 0:
            print("✅ All expenses have corresponding user records")
        else:
            print(f"❌ {len(missing)} expenses still missing user records")
        
        return orphaned_count == 0 and invalid_count == 0 and len(missing) == 0

def main():
    """Execute all data integrity fixes"""
    print("🚨 EXECUTING CRITICAL DATA INTEGRITY FIXES")
    print("=" * 50)
    
    try:
        fixes_1 = fix_orphaned_expenses()
        fixes_2 = fix_invalid_user_hashes()
        
        total_fixes = fixes_1 + fixes_2
        
        if validate_fixes():
            print(f"\\n✅ ALL DATA INTEGRITY ISSUES RESOLVED")
            print(f"✅ Applied {total_fixes} fixes successfully")
            print("✅ Financial data integrity restored")
            return True
        else:
            print(f"\\n❌ Some issues remain after fixes")
            return False
            
    except Exception as e:
        print(f"\\n❌ Error during fixes: {str(e)}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)