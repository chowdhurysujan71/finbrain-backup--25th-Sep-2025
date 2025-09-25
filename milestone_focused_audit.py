#!/usr/bin/env python3
"""
MILESTONE COACHING SYSTEM - FOCUSED AUDIT
Direct validation of milestone functionality for deployment readiness
"""

import json
import sys
import time
from datetime import UTC, date, datetime, timedelta, timezone

# Setup path
sys.path.append('/home/runner/workspace')

def focused_milestone_audit():
    """Execute focused audit of milestone system core functionality"""
    
    print("🎯 MILESTONE COACHING SYSTEM - FOCUSED AUDIT")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    audit_results = {
        "audit_meta": {
            "timestamp": datetime.now().isoformat(),
            "test_type": "focused_milestone_validation",
            "environment": "development"
        },
        "tests": {},
        "summary": {}
    }
    
    try:
        from app import app, db
        from handlers.milestones import (
            _calculate_streak_days,
            check_milestones_after_log,
        )
        from models import Expense, UserMilestone
        
        with app.app_context():
            
            # TEST 1: Core Milestone Detection Logic
            print("\n🧪 TEST 1: MILESTONE DETECTION LOGIC")
            print("-" * 40)
            
            test_user = f"focused_audit_{int(time.time())}"
            
            # Clean existing data
            db.session.query(Expense).filter_by(user_id_hash=test_user).delete()
            db.session.query(UserMilestone).filter_by(user_id_hash=test_user).delete()
            db.session.commit()
            
            # 1.1: Test streak calculation with known data
            print("  📊 1.1: Testing streak calculation...")
            
            # Create expenses for 3 consecutive days
            for days_back in [2, 1, 0]:
                expense = Expense()
                expense.user_id = test_user
                expense.user_id_hash = test_user
                expense.amount = 100 + days_back * 50
                expense.category = 'food'
                expense.description = f'Test expense day {days_back}'
                expense.original_message = f'Test expense day {days_back}'
                
                target_date = datetime.now(UTC) - timedelta(days=days_back)
                expense.created_at = target_date
                expense.date = target_date.date()
                expense.time = target_date.time()
                expense.month = target_date.strftime('%Y-%m')
                expense.platform = 'messenger'
                expense.unique_id = f'focused_test_{days_back}'
                expense.mid = f'focused_test_{days_back}_{int(time.time())}'
                
                db.session.add(expense)
            
            db.session.commit()
            
            # Test streak calculation
            calculated_streak = _calculate_streak_days(test_user)
            streak_correct = calculated_streak == 3
            
            print(f"     Expected streak: 3, Calculated: {calculated_streak}")
            print(f"     {'✅ PASS' if streak_correct else '❌ FAIL'} - Streak Calculation")
            
            audit_results["tests"]["streak_calculation"] = {
                "expected": 3,
                "calculated": calculated_streak,
                "status": "PASS" if streak_correct else "FAIL"
            }
            
            # 1.2: Test streak-3 milestone triggering
            print("  🎯 1.2: Testing streak-3 milestone triggering...")
            
            milestone_message = check_milestones_after_log(test_user)
            has_streak_milestone = milestone_message and "🔥 3-day streak" in milestone_message
            
            # Verify milestone stored in database
            streak_milestone_db = db.session.query(UserMilestone).filter_by(
                user_id_hash=test_user,
                milestone_type='streak-3'
            ).first()
            
            streak_milestone_valid = has_streak_milestone and streak_milestone_db is not None
            
            print(f"     Milestone message: {'Present' if has_streak_milestone else 'Missing'}")
            print(f"     Database record: {'Present' if streak_milestone_db else 'Missing'}")
            print(f"     {'✅ PASS' if streak_milestone_valid else '❌ FAIL'} - Streak-3 Milestone")
            
            audit_results["tests"]["streak_3_milestone"] = {
                "message_triggered": has_streak_milestone,
                "database_stored": streak_milestone_db is not None,
                "milestone_text": milestone_message,
                "status": "PASS" if streak_milestone_valid else "FAIL"
            }
            
            # TEST 2: 10-logs Milestone Logic
            print("\n🎯 TEST 2: 10-LOGS MILESTONE LOGIC")
            print("-" * 40)
            
            test_user_logs = f"logs_audit_{int(time.time())}"
            
            # Clean existing data
            db.session.query(Expense).filter_by(user_id_hash=test_user_logs).delete()
            db.session.query(UserMilestone).filter_by(user_id_hash=test_user_logs).delete()
            db.session.commit()
            
            print("  📊 2.1: Creating 10 expense logs...")
            
            # Create exactly 10 expenses
            for i in range(10):
                expense = Expense()
                expense.user_id = test_user_logs
                expense.user_id_hash = test_user_logs
                expense.amount = 100 + i * 10
                expense.category = 'test'
                expense.description = f'Log number {i+1}'
                expense.original_message = f'Log number {i+1}'
                expense.created_at = datetime.now(UTC) - timedelta(minutes=i)
                expense.date = datetime.now(UTC).date()
                expense.time = datetime.now(UTC).time()
                expense.month = datetime.now(UTC).strftime('%Y-%m')
                expense.platform = 'messenger'
                expense.unique_id = f'logs_test_{i}'
                expense.mid = f'logs_test_{i}_{int(time.time())}'
                
                db.session.add(expense)
            
            db.session.commit()
            
            # Verify we have exactly 10 logs
            total_logs = db.session.query(Expense).filter_by(user_id_hash=test_user_logs).count()
            logs_count_correct = total_logs == 10
            
            print(f"     Expected logs: 10, Actual: {total_logs}")
            print(f"     {'✅ PASS' if logs_count_correct else '❌ FAIL'} - Log Count")
            
            # Test 10-logs milestone
            print("  🎯 2.2: Testing 10-logs milestone...")
            
            milestone_message_logs = check_milestones_after_log(test_user_logs)
            has_logs_milestone = milestone_message_logs and "🎉 10th log" in milestone_message_logs
            
            # Verify milestone stored in database
            logs_milestone_db = db.session.query(UserMilestone).filter_by(
                user_id_hash=test_user_logs,
                milestone_type='10-logs'
            ).first()
            
            logs_milestone_valid = has_logs_milestone and logs_milestone_db is not None
            
            print(f"     Milestone message: {'Present' if has_logs_milestone else 'Missing'}")
            print(f"     Database record: {'Present' if logs_milestone_db else 'Missing'}")
            print(f"     {'✅ PASS' if logs_milestone_valid else '❌ FAIL'} - 10-logs Milestone")
            
            audit_results["tests"]["logs_10_milestone"] = {
                "total_logs": total_logs,
                "message_triggered": has_logs_milestone,
                "database_stored": logs_milestone_db is not None,
                "milestone_text": milestone_message_logs,
                "status": "PASS" if logs_milestone_valid else "FAIL"
            }
            
            # TEST 3: Daily Cap Enforcement
            print("\n🚫 TEST 3: DAILY CAP ENFORCEMENT")
            print("-" * 40)
            
            test_user_cap = f"cap_audit_{int(time.time())}"
            
            # Clean existing data
            db.session.query(Expense).filter_by(user_id_hash=test_user_cap).delete()
            db.session.query(UserMilestone).filter_by(user_id_hash=test_user_cap).delete()
            db.session.commit()
            
            # Set up streak scenario - need expenses for ALL 3 days including today
            for days_back in [2, 1, 0]:  # Include today (day 0)
                expense = Expense()
                expense.user_id = test_user_cap
                expense.user_id_hash = test_user_cap
                expense.amount = 200
                expense.category = 'test'
                expense.description = f'Setup day {days_back}'
                expense.original_message = f'Setup day {days_back}'
                
                target_date = datetime.now(UTC) - timedelta(days=days_back)
                expense.created_at = target_date
                expense.date = target_date.date()
                expense.time = target_date.time()
                expense.month = target_date.strftime('%Y-%m')
                expense.platform = 'messenger'
                expense.unique_id = f'cap_setup_{days_back}'
                expense.mid = f'cap_setup_{days_back}_{int(time.time())}'
                
                db.session.add(expense)
            
            db.session.commit()
            
            print("  🎯 3.1: First milestone trigger...")
            
            # First milestone should trigger (we have 3-day streak)
            first_milestone = check_milestones_after_log(test_user_cap)
            first_has_milestone = first_milestone and ("🔥" in first_milestone or "🎉" in first_milestone)
            
            print(f"     First trigger: {'Success' if first_has_milestone else 'Failed'}")
            
            print("  🚫 3.2: Second milestone (should be blocked)...")
            
            # Second milestone should be blocked by daily cap
            second_milestone = check_milestones_after_log(test_user_cap)
            second_has_milestone = second_milestone and ("🔥" in second_milestone or "🎉" in second_milestone)
            
            daily_cap_working = first_has_milestone and not second_has_milestone
            
            print(f"     Second trigger: {'Blocked' if not second_has_milestone else 'Failed to block'}")
            print(f"     {'✅ PASS' if daily_cap_working else '❌ FAIL'} - Daily Cap")
            
            audit_results["tests"]["daily_cap"] = {
                "first_milestone_fired": first_has_milestone,
                "second_milestone_blocked": not second_has_milestone,
                "daily_cap_working": daily_cap_working,
                "status": "PASS" if daily_cap_working else "FAIL"
            }
            
            # TEST 4: Database Constraints
            print("\n💾 TEST 4: DATABASE CONSTRAINTS")
            print("-" * 40)
            
            test_user_db = f"db_audit_{int(time.time())}"
            
            # Clean existing data
            db.session.query(UserMilestone).filter_by(user_id_hash=test_user_db).delete()
            db.session.commit()
            
            print("  🔒 4.1: Unique constraint enforcement...")
            
            # Create first milestone
            milestone1 = UserMilestone()
            milestone1.user_id_hash = test_user_db
            milestone1.milestone_type = 'streak-3'
            milestone1.fired_at = datetime.utcnow()
            milestone1.daily_count_date = date.today()
            
            db.session.add(milestone1)
            db.session.commit()
            
            # Attempt duplicate - should fail
            duplicate_blocked = False
            try:
                milestone2 = UserMilestone()
                milestone2.user_id_hash = test_user_db
                milestone2.milestone_type = 'streak-3'  # Same type
                milestone2.fired_at = datetime.utcnow()
                milestone2.daily_count_date = date.today()
                
                db.session.add(milestone2)
                db.session.commit()
                
            except Exception:
                duplicate_blocked = True
                db.session.rollback()
            
            print(f"     {'✅ PASS' if duplicate_blocked else '❌ FAIL'} - Unique Constraint")
            
            audit_results["tests"]["database_constraints"] = {
                "duplicate_prevented": duplicate_blocked,
                "status": "PASS" if duplicate_blocked else "FAIL"
            }
            
            # Clean up all test data
            print("\n🧹 CLEANING UP TEST DATA...")
            
            for user in [test_user, test_user_logs, test_user_cap, test_user_db]:
                db.session.query(Expense).filter_by(user_id_hash=user).delete()
                db.session.query(UserMilestone).filter_by(user_id_hash=user).delete()
            
            db.session.commit()
            print("     ✅ Test data cleaned")
            
            # GENERATE SUMMARY
            print("\n📋 GENERATING AUDIT SUMMARY")
            print("-" * 40)
            
            all_tests = list(audit_results["tests"].values())
            total_tests = len(all_tests)
            passed_tests = sum(1 for test in all_tests if test["status"] == "PASS")
            
            pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            if pass_rate == 100:
                overall_status = "PASS"
                deployment_ready = True
            elif pass_rate >= 80:
                overall_status = "CONDITIONAL_PASS"
                deployment_ready = False
            else:
                overall_status = "FAIL"
                deployment_ready = False
            
            audit_results["summary"] = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "pass_rate": pass_rate,
                "overall_status": overall_status,
                "deployment_ready": deployment_ready,
                "timestamp": datetime.now().isoformat()
            }
            
            return audit_results
            
    except Exception as e:
        print(f"\n❌ CRITICAL AUDIT ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        audit_results["critical_error"] = {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        audit_results["summary"] = {
            "overall_status": "ERROR",
            "deployment_ready": False
        }
        
        return audit_results

def print_focused_audit_report(results):
    """Print focused audit report"""
    
    print("\n" + "=" * 60)
    print("🎯 MILESTONE COACHING SYSTEM - FOCUSED AUDIT REPORT")
    print("=" * 60)
    
    summary = results.get("summary", {})
    
    print("\n📊 EXECUTIVE SUMMARY")
    print(f"Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
    print(f"Pass Rate: {summary.get('pass_rate', 0):.1f}% ({summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)} tests)")
    print(f"Deployment Ready: {'✅ YES' if summary.get('deployment_ready', False) else '❌ NO'}")
    
    print("\n🔍 DETAILED RESULTS")
    print("-" * 30)
    
    tests = results.get("tests", {})
    for test_name, test_result in tests.items():
        status = test_result.get("status", "UNKNOWN")
        emoji = "✅" if status == "PASS" else "❌"
        print(f"{emoji} {test_name.upper()}: {status}")
    
    # Critical error handling
    if "critical_error" in results:
        print("\n🚨 CRITICAL ERROR")
        print(f"Error: {results['critical_error']['error']}")
    
    # Deployment recommendation
    print("\n💡 DEPLOYMENT RECOMMENDATION")
    print("-" * 35)
    
    if summary.get("deployment_ready", False):
        print("✅ MILESTONE SYSTEM READY FOR DEPLOYMENT")
        print("   • All core functionality validated")
        print("   • Database constraints working")
        print("   • Daily caps enforced")
        print("   • Milestone detection accurate")
    else:
        print("❌ MILESTONE SYSTEM NOT READY FOR DEPLOYMENT")
        print("   • Fix failing tests before deployment")
        print("   • Re-run audit after fixes")
    
    print(f"\n🕐 AUDIT COMPLETED: {summary.get('timestamp', 'Unknown')}")
    print("=" * 60)

if __name__ == "__main__":
    # Execute focused audit
    results = focused_milestone_audit()
    
    # Print report
    print_focused_audit_report(results)
    
    # Save results
    with open('milestone_focused_audit.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n💾 Audit results saved to: milestone_focused_audit.json")
    
    # Exit with appropriate code
    if results.get("summary", {}).get("deployment_ready", False):
        print("\n🚀 MILESTONE SYSTEM: DEPLOYMENT APPROVED")
        exit(0)
    else:
        print("\n⚠️  MILESTONE SYSTEM: DEPLOYMENT PENDING")
        exit(1)