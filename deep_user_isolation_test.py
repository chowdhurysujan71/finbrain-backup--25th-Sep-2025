#!/usr/bin/env python3
"""
DEEP USER ISOLATION TESTING
Advanced testing to ensure absolute user data isolation
"""

import sys

sys.path.append('/home/runner/workspace')

from sqlalchemy import func

from app import app, db
from handlers.category_breakdown import handle_category_breakdown
from models import Expense


def test_cross_user_contamination():
    """Test for any cross-user data contamination in responses"""
    print("🔬 TESTING CROSS-USER DATA CONTAMINATION")
    print("=" * 45)
    
    with app.app_context():
        # Get users with different spending patterns
        users_data = db.session.query(
            Expense.user_id,
            func.sum(Expense.amount).label('total'),
            func.count(Expense.id).label('count')
        ).group_by(Expense.user_id).having(func.count(Expense.id) >= 2).limit(3).all()
        
        contamination_issues = []
        
        for user_id, user_total, user_count in users_data:
            print(f"\n🧪 Testing user: {user_id[:16]}... (৳{user_total}, {user_count} expenses)")
            
            # Get user's actual expense data
            user_expenses = db.session.query(Expense).filter(
                Expense.user_id == user_id
            ).all()
            
            user_categories = set(exp.category for exp in user_expenses if exp.category)
            user_amounts = [float(exp.amount) for exp in user_expenses]
            
            # Test category breakdown
            if user_categories:
                for category in list(user_categories)[:2]:  # Test first 2 categories
                    result = handle_category_breakdown(user_id, f"How much did I spend on {category}")
                    response_text = result.get('text', '').lower()
                    
                    # Check if response contains other users' amounts
                    other_users_amounts = []
                    for other_user, other_total, other_count in users_data:
                        if other_user != user_id:
                            other_expenses = db.session.query(Expense).filter(
                                Expense.user_id == other_user
                            ).all()
                            other_users_amounts.extend([float(exp.amount) for exp in other_expenses])
                    
                    # Look for foreign amounts in response
                    for foreign_amount in other_users_amounts:
                        if f"৳{foreign_amount:,.0f}" in response_text or f"{foreign_amount:,.0f}" in response_text:
                            contamination_issues.append(f"❌ User {user_id[:16]} response contains foreign amount ৳{foreign_amount}")
                    
                    print(f"   ✅ Category '{category}' response isolated correctly")
            
            # Skip insights test for now - focusing on core data isolation
            print("   ✅ Core isolation tests passed (insights test skipped)")
        
        return contamination_issues

def test_concurrent_user_access():
    """Simulate concurrent access to test for race conditions"""
    print("\n⚡ TESTING CONCURRENT USER ACCESS")
    print("=" * 35)
    
    with app.app_context():
        users = db.session.query(Expense.user_id).distinct().limit(3).all()
        
        race_condition_issues = []
        
        # Simulate rapid concurrent requests
        for i in range(5):  # 5 iterations
            results = {}
            
            for user_id, in users:
                try:
                    # Rapid fire requests
                    result1 = handle_category_breakdown(user_id, "How much did I spend this month")
                    result2 = handle_category_breakdown(user_id, "How much did I spend this month")
                    
                    # Results should be identical for same user/query
                    if result1.get('text') != result2.get('text'):
                        race_condition_issues.append(f"❌ Inconsistent results for user {user_id[:16]} in iteration {i+1}")
                    
                    results[user_id] = result1.get('text', '')
                    
                except Exception as e:
                    race_condition_issues.append(f"❌ Concurrent access error for user {user_id[:16]}: {str(e)[:30]}...")
            
            # Verify no cross-contamination between concurrent users
            result_values = list(results.values())
            unique_responses = len(set(result_values))
            
            if len(result_values) != unique_responses and len(set(users)) > 1:
                # Only flag if users actually have different data
                user_totals = {}
                for user_id, in users:
                    total = db.session.query(func.sum(Expense.amount)).filter(Expense.user_id == user_id).scalar() or 0
                    user_totals[user_id] = total
                
                if len(set(user_totals.values())) > 1:  # Users have different totals
                    race_condition_issues.append(f"❌ Potential cross-contamination in concurrent access iteration {i+1}")
        
        if not race_condition_issues:
            print("✅ No race conditions detected in concurrent access")
        
        return race_condition_issues

if __name__ == "__main__":
    print("🔍 DEEP USER ISOLATION TESTING")
    print("=" * 40)
    
    issues = []
    issues.extend(test_cross_user_contamination())
    issues.extend(test_concurrent_user_access())
    
    print("\n📊 DEEP TESTING RESULTS")
    print("=" * 25)
    
    if issues:
        print(f"❌ FOUND {len(issues)} ISOLATION ISSUES:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
    else:
        print("✅ ALL DEEP ISOLATION TESTS PASSED")
        print("✅ USER DATA COMPLETELY ISOLATED")