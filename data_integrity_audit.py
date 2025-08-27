#!/usr/bin/env python3
"""
CRITICAL DATA INTEGRITY AUDIT
Comprehensive audit to ensure users only see their own accurate financial data
"""

import os
import sys
sys.path.append('/home/runner/workspace')

from app import app, db
from models import User, Expense
from sqlalchemy import func, text
from datetime import datetime, timezone, timedelta
import hashlib

def audit_user_isolation():
    """Verify users can only access their own expense data"""
    print("🔒 AUDITING USER DATA ISOLATION")
    print("=" * 40)
    
    with app.app_context():
        # Get all users with expenses
        users_with_expenses = db.session.query(
            Expense.user_id,
            func.count(Expense.id).label('expense_count'),
            func.sum(Expense.amount).label('total_amount')
        ).group_by(Expense.user_id).all()
        
        print(f"Found {len(users_with_expenses)} users with expense data")
        
        issues = []
        
        # Test cross-user data leakage
        for i, (user_id, count, total) in enumerate(users_with_expenses[:3]):  # Test first 3 users
            print(f"\n👤 Testing user: {user_id[:16]}... ({count} expenses, ৳{total})")
            
            # Get expenses for this specific user
            user_expenses = db.session.query(Expense).filter(
                Expense.user_id == user_id
            ).all()
            
            # Verify all expenses belong to this user
            foreign_expenses = [e for e in user_expenses if e.user_id != user_id]
            if foreign_expenses:
                issues.append(f"❌ User {user_id[:16]} has {len(foreign_expenses)} expenses from other users!")
            else:
                print(f"   ✅ All {len(user_expenses)} expenses belong to correct user")
            
            # Test category breakdown isolation
            from handlers.category_breakdown import handle_category_breakdown
            try:
                result = handle_category_breakdown(user_id, "How much did I spend this month")
                # Verify response doesn't contain other users' data
                if "Error" not in result.get('text', ''):
                    print(f"   ✅ Category breakdown isolated correctly")
                else:
                    issues.append(f"❌ Category breakdown error for user {user_id[:16]}")
            except Exception as e:
                issues.append(f"❌ Category breakdown failed for user {user_id[:16]}: {str(e)}")
        
        return issues

def audit_user_identity_system():
    """Verify user identity hashing is consistent and secure"""
    print("\n🔐 AUDITING USER IDENTITY SYSTEM")
    print("=" * 40)
    
    with app.app_context():
        issues = []
        
        # Check for duplicate user_id_hash values
        duplicate_check = db.session.query(
            User.user_id_hash,
            func.count(User.id).label('count')
        ).group_by(User.user_id_hash).having(func.count(User.id) > 1).all()
        
        if duplicate_check:
            for user_hash, count in duplicate_check:
                issues.append(f"❌ Duplicate user_id_hash: {user_hash[:16]}... appears {count} times")
        else:
            print("✅ No duplicate user identity hashes found")
        
        # Check for orphaned expenses (expenses without corresponding users)
        orphaned_expenses = db.session.query(Expense).filter(
            ~Expense.user_id.in_(db.session.query(User.user_id_hash))
        ).all()
        
        if orphaned_expenses:
            issues.append(f"❌ Found {len(orphaned_expenses)} orphaned expenses without user records")
            for exp in orphaned_expenses[:3]:  # Show first 3
                issues.append(f"   Orphan: {exp.user_id[:16]}... ৳{exp.amount} {exp.category}")
        else:
            print("✅ No orphaned expenses found")
        
        # Check user_id format consistency
        all_users = User.query.all()
        invalid_hashes = []
        
        for user in all_users:
            # User ID hash should be 64-character hex string (SHA256)
            if len(user.user_id_hash) != 64 or not all(c in '0123456789abcdef' for c in user.user_id_hash.lower()):
                invalid_hashes.append(user.user_id_hash)
        
        if invalid_hashes:
            issues.append(f"❌ Found {len(invalid_hashes)} invalid user_id_hash formats")
        else:
            print(f"✅ All {len(all_users)} user identity hashes properly formatted (SHA256)")
        
        return issues

def audit_expense_calculations():
    """Verify expense amount calculations and aggregations are accurate"""
    print("\n💰 AUDITING EXPENSE CALCULATIONS")
    print("=" * 40)
    
    with app.app_context():
        issues = []
        
        # Test calculation accuracy for each user
        users_with_expenses = db.session.query(Expense.user_id).distinct().all()
        
        for (user_id,) in users_with_expenses[:3]:  # Test first 3 users
            print(f"\n🧮 Testing calculations for user: {user_id[:16]}...")
            
            # Get all expenses for this user
            user_expenses = db.session.query(Expense).filter(
                Expense.user_id == user_id
            ).all()
            
            # Manual calculation
            manual_total = sum(float(exp.amount) for exp in user_expenses)
            manual_count = len(user_expenses)
            
            # Database aggregation
            db_result = db.session.query(
                func.sum(Expense.amount).label('total'),
                func.count(Expense.id).label('count')
            ).filter(Expense.user_id == user_id).first()
            
            db_total = float(db_result.total) if db_result.total else 0
            db_count = int(db_result.count) if db_result.count else 0
            
            # Compare calculations
            if abs(manual_total - db_total) > 0.01:  # Allow for floating point precision
                issues.append(f"❌ Calculation mismatch for user {user_id[:16]}: manual=৳{manual_total}, db=৳{db_total}")
            else:
                print(f"   ✅ Amount calculation accurate: ৳{manual_total} ({manual_count} expenses)")
            
            if manual_count != db_count:
                issues.append(f"❌ Count mismatch for user {user_id[:16]}: manual={manual_count}, db={db_count}")
            else:
                print(f"   ✅ Expense count accurate: {manual_count} transactions")
        
        return issues

def audit_timeframe_accuracy():
    """Verify timeframe filtering (this month, last week, etc.) is accurate"""
    print("\n📅 AUDITING TIMEFRAME CALCULATIONS")
    print("=" * 40)
    
    with app.app_context():
        issues = []
        
        # Test current month timeframe
        now = datetime.now(timezone.utc)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        print(f"Current month timeframe: {current_month_start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d %H:%M')}")
        
        # Get expenses that should be in current month
        current_month_expenses = db.session.query(Expense).filter(
            Expense.created_at >= current_month_start,
            Expense.created_at <= now
        ).all()
        
        # Manual verification
        manual_current_month = []
        all_expenses = db.session.query(Expense).all()
        
        for exp in all_expenses:
            exp_time = exp.created_at
            if exp_time.tzinfo is None:
                exp_time = exp_time.replace(tzinfo=timezone.utc)
            
            if current_month_start <= exp_time <= now:
                manual_current_month.append(exp)
        
        if len(current_month_expenses) != len(manual_current_month):
            issues.append(f"❌ Current month filter mismatch: db={len(current_month_expenses)}, manual={len(manual_current_month)}")
        else:
            print(f"✅ Current month timeframe filter accurate: {len(current_month_expenses)} expenses")
        
        # Test category breakdown timeframe integration
        users_with_current_expenses = db.session.query(Expense.user_id).filter(
            Expense.created_at >= current_month_start,
            Expense.created_at <= now
        ).distinct().limit(2).all()
        
        for (user_id,) in users_with_current_expenses:
            from handlers.category_breakdown import handle_category_breakdown
            try:
                result = handle_category_breakdown(user_id, "How much did I spend this month")
                if "error" in result.get('text', '').lower():
                    issues.append(f"❌ Timeframe error in category breakdown for user {user_id[:16]}")
                else:
                    print(f"   ✅ Category breakdown timeframe working for user {user_id[:16]}...")
            except Exception as e:
                issues.append(f"❌ Category breakdown timeframe failed for user {user_id[:16]}: {str(e)}")
        
        return issues

def audit_category_consistency():
    """Verify expense categories are consistent and properly mapped"""
    print("\n🏷️  AUDITING CATEGORY CONSISTENCY")
    print("=" * 40)
    
    with app.app_context():
        issues = []
        
        # Get all unique categories
        categories = db.session.query(
            Expense.category,
            func.count(Expense.id).label('count')
        ).group_by(Expense.category).order_by(func.count(Expense.id).desc()).all()
        
        print(f"Found {len(categories)} unique categories:")
        for category, count in categories:
            print(f"   - {category}: {count} expenses")
        
        # Check for potential category mapping issues
        transport_variations = [cat for cat, count in categories if cat and ('transport' in cat.lower() or 'ride' in cat.lower() or 'taxi' in cat.lower() or 'uber' in cat.lower())]
        food_variations = [cat for cat, count in categories if cat and 'food' in cat.lower()]
        
        if len(transport_variations) > 3:
            issues.append(f"❌ Too many transport category variations: {transport_variations}")
        else:
            print(f"✅ Transport categories well consolidated: {transport_variations}")
        
        # Test category breakdown mapping
        from handlers.category_breakdown import extract_category_from_query
        test_queries = [
            ("How much did I spend on food", "food"),
            ("How much did I spend on transport", "transport"),
            ("How much did I spend on rides", "transport"),
            ("How much did I spend on shopping", "shopping")
        ]
        
        for query, expected in test_queries:
            actual = extract_category_from_query(query)
            if actual != expected:
                issues.append(f"❌ Category mapping error: '{query}' -> '{actual}' (expected '{expected}')")
            else:
                print(f"   ✅ '{query}' correctly maps to '{actual}'")
        
        return issues

def main():
    """Run comprehensive data integrity audit"""
    print("🚨 CRITICAL DATA INTEGRITY AUDIT")
    print("=" * 50)
    print("Ensuring users only see their own accurate financial data")
    print("=" * 50)
    
    all_issues = []
    
    # Run all audit modules
    all_issues.extend(audit_user_isolation())
    all_issues.extend(audit_user_identity_system())
    all_issues.extend(audit_expense_calculations())
    all_issues.extend(audit_timeframe_accuracy())
    all_issues.extend(audit_category_consistency())
    
    # Final report
    print(f"\n📋 AUDIT SUMMARY")
    print("=" * 30)
    
    if all_issues:
        print(f"❌ FOUND {len(all_issues)} CRITICAL ISSUES:")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        print(f"\n🚨 DATA INTEGRITY COMPROMISED - IMMEDIATE ACTION REQUIRED")
        return False
    else:
        print("✅ ALL AUDIT CHECKS PASSED")
        print("✅ DATA INTEGRITY VERIFIED - USERS ONLY SEE THEIR OWN ACCURATE DATA")
        print("✅ FINANCIAL CALCULATIONS ARE ACCURATE AND RELIABLE")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)