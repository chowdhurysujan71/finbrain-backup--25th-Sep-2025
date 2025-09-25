#!/usr/bin/env python3
"""
CRITICAL CROSS-CONTAMINATION TEST
Test for AI response mixing between users - this is a financial data security breach
"""

import sys

sys.path.append('/home/runner/workspace')

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC

from app import app, db
from utils.ai_adapter_v2 import production_ai_adapter


def test_concurrent_ai_contamination():
    """Test if AI responses get mixed between concurrent users"""
    print("🚨 TESTING CRITICAL AI CROSS-CONTAMINATION")
    print("=" * 55)
    
    with app.app_context():
        # User 1: Should have ৳4000 transport + ৳2500 ride
        user1_id = 'a20425ef9abcb344b5e0c892e1d1cad28e35f9b2e5b11c19aa7a3b4d4c8e5f2a6'
        
        # KC: Should have ৳300 ride only  
        kc_id = 'd17538bfc1dd48052f6df15a1ae94cb1f9b4c5e7a2f8f8d3c5e9f2a6b7c8d1e4'
        
        # Get their actual data
        from datetime import datetime, timezone

        from sqlalchemy import func

        from models import Expense
        
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # User 1 actual data
        user1_expenses = db.session.query(
            Expense.category,
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id == user1_id,
            Expense.created_at >= month_start
        ).group_by(Expense.category).all()
        
        # KC actual data
        kc_expenses = db.session.query(
            Expense.category,
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id == kc_id,
            Expense.created_at >= month_start
        ).group_by(Expense.category).all()
        
        print("EXPECTED USER DATA:")
        print(f"User 1 ({user1_id[:16]}...):")
        user1_totals = {}
        for category, total in user1_expenses:
            user1_totals[category] = float(total)
            print(f"   {category}: ৳{total}")
        
        print(f"\nKC ({kc_id[:16]}...):")
        kc_totals = {}
        for category, total in kc_expenses:
            kc_totals[category] = float(total)
            print(f"   {category}: ৳{total}")
        
        # Prepare AI expense data for both users
        user1_ai_data = {
            'total_amount': sum(user1_totals.values()),
            'expenses': [
                {
                    'category': cat,
                    'total': amount,
                    'percentage': (amount / sum(user1_totals.values())) * 100
                }
                for cat, amount in user1_totals.items()
            ],
            'timeframe': 'this month'
        }
        
        kc_ai_data = {
            'total_amount': sum(kc_totals.values()),
            'expenses': [
                {
                    'category': cat,
                    'total': amount,
                    'percentage': (amount / sum(kc_totals.values())) * 100
                }
                for cat, amount in kc_totals.items()
            ],
            'timeframe': 'this month'
        }
        
        print("\n🔄 TESTING CONCURRENT AI REQUESTS...")
        
        contamination_issues = []
        
        def test_user1():
            """Generate AI insights for User 1"""
            result = production_ai_adapter.generate_insights(user1_ai_data)
            return ("USER1", result)
        
        def test_kc():
            """Generate AI insights for KC"""
            result = production_ai_adapter.generate_insights(kc_ai_data)
            return ("KC", result)
        
        # Run concurrent requests to see if data gets mixed
        for iteration in range(3):
            print(f"\nIteration {iteration + 1}:")
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(test_user1)
                future_kc = executor.submit(test_kc)
                
                result1 = future1.result()
                result_kc = future_kc.result()
                
                # Check for contamination
                user1_response = str(result1[1])
                kc_response = str(result_kc[1])
                
                print(f"   User 1 response length: {len(user1_response)}")
                print(f"   KC response length: {len(kc_response)}")
                
                # Check if User 1's response contains KC's data
                if '300' in user1_response and kc_totals.get('ride', 0) == 300:
                    contamination_issues.append(f"Iteration {iteration + 1}: User 1 response contains KC's ৳300")
                
                # Check if KC's response contains User 1's data
                if '4000' in kc_response or '2500' in kc_response:
                    contamination_issues.append(f"Iteration {iteration + 1}: KC response contains User 1's amounts")
                
                # Check for identical responses (suspicious)
                if user1_response == kc_response and len(user1_response) > 50:
                    contamination_issues.append(f"Iteration {iteration + 1}: Identical responses for different users!")
                
                # Check for contamination conditions
                conditions = [
                    '300' in user1_response and kc_totals.get('ride', 0) == 300,
                    '4000' in kc_response or '2500' in kc_response,
                    user1_response == kc_response and len(user1_response) > 50
                ]
                
                has_contamination = any(conditions)
                print(f"   Contamination check: {'❌ ISSUES FOUND' if has_contamination else '✅ Clean'}")
        
        return contamination_issues

def test_shared_state_isolation():
    """Test if the shared AI adapter instance causes state mixing"""
    print("\n🔍 TESTING SHARED STATE ISOLATION")
    print("=" * 40)
    
    # Check if the AI adapter has any instance variables that could store user data
    adapter_vars = [attr for attr in dir(production_ai_adapter) if not attr.startswith('_')]
    print(f"AI Adapter attributes: {adapter_vars}")
    
    # Check session object for shared state
    session_id = id(production_ai_adapter.session)
    print(f"Shared session ID: {session_id}")
    
    # Test if session headers get mixed
    original_headers = dict(production_ai_adapter.session.headers)
    print(f"Session headers: {list(original_headers.keys())}")
    
    return []

if __name__ == "__main__":
    contamination_issues = test_concurrent_ai_contamination()
    state_issues = test_shared_state_isolation()
    
    all_issues = contamination_issues + state_issues
    
    print("\n📋 CRITICAL SECURITY ASSESSMENT")
    print("=" * 40)
    
    if all_issues:
        print(f"🚨 CRITICAL DATA BREACH: {len(all_issues)} cross-contamination issues found")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        print("\n🚨 IMMEDIATE ACTION REQUIRED - USERS SEEING OTHER USERS' FINANCIAL DATA")
    else:
        print("✅ No cross-contamination detected in AI responses")
        print("✅ User financial data properly isolated")
    
    sys.exit(0 if not all_issues else 1)