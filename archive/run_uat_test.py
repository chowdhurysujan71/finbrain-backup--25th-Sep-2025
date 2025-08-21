#!/usr/bin/env python3
"""
FinBrain UAT Test Suite
Tests all critical message routing paths
"""
import time
import json
import hashlib
from datetime import datetime

def test_production_router():
    """Run comprehensive UAT tests on the production router"""
    from utils.production_router import production_router
    from utils.user_manager import resolve_user_id
    from app import app, db
    from models import User, Expense
    
    # Test PSID
    test_psid = "UAT_TEST_USER_" + str(int(time.time()))
    test_hash = hashlib.sha256(test_psid.encode()).hexdigest()
    
    print("=" * 60)
    print("FINBRAIN UAT TEST SUITE")
    print("=" * 60)
    print(f"Test PSID: {test_psid[:20]}...")
    print(f"Test Hash: {test_hash[:16]}...")
    print()
    
    test_cases = [
        # Core commands
        ("summary", "SUMMARY", "Should return spending summary"),
        ("Summary", "SUMMARY", "Case-insensitive summary"),
        ("give me insights", "INSIGHT", "Should provide insights"),
        ("coffee 100", "LOG_EXPENSE", "Should log single expense"),
        ("100 on uber and 500 on shoes", "LOG_EXPENSE", "Should log multiple expenses"),
        ("undo last", "UNDO", "Should undo last expense"),
        
        # Edge cases
        ("SUMMARY", "SUMMARY", "All caps summary"),
        ("can you show my summary?", "SUMMARY", "Natural language summary"),
        ("spent 50 on lunch", "LOG_EXPENSE", "Natural expense logging"),
        ("I need some insights", "INSIGHT", "Natural insights request"),
    ]
    
    results = []
    
    with app.app_context():
        # Ensure test user exists - using correct field names from model
        existing = db.session.query(User).filter_by(user_id_hash=test_hash).first()
        if not existing:
            test_user = User(
                user_id_hash=test_hash,
                platform="messenger",
                first_name="UAT",
                created_at=datetime.utcnow()
            )
            db.session.add(test_user)
            db.session.commit()
            print(f"✓ Created test user")
        else:
            print(f"✓ Using existing test user")
        
        # Add some test expenses for summary
        test_expense = Expense(
            user_id=test_hash,
            amount=100.0,
            category="food",
            description="UAT test expense",
            month=datetime.utcnow().strftime("%Y-%m"),
            unique_id=f"UAT_{int(time.time())}",
            created_at=datetime.utcnow()
        )
        db.session.add(test_expense)
        db.session.commit()
        print(f"✓ Added test expense")
        print()
        
        print("Running Test Cases:")
        print("-" * 60)
        
        for i, (message, expected_intent, description) in enumerate(test_cases, 1):
            try:
                # Test the routing
                response, intent, category, amount = production_router.route_message(
                    text=message,
                    psid=test_psid,
                    rid=f"UAT_{i}"
                )
                
                # Check if intent matches expected
                success = expected_intent.lower() in intent.lower()
                
                # Check response quality
                has_fallback = "Got it. Try 'summary'" in response
                is_error = "error" in intent.lower() or "fallback" in intent.lower()
                
                result = {
                    "test": f"Test {i}: {description}",
                    "message": message,
                    "expected_intent": expected_intent,
                    "actual_intent": intent,
                    "response_preview": response[:100] + "..." if len(response) > 100 else response,
                    "success": success and not has_fallback and not is_error,
                    "has_fallback": has_fallback,
                    "is_error": is_error
                }
                
                results.append(result)
                
                # Print result
                status = "✅ PASS" if result["success"] else "❌ FAIL"
                print(f"{status} Test {i}: {description}")
                print(f"   Message: '{message}'")
                print(f"   Intent: {intent} (expected: {expected_intent})")
                if not result["success"]:
                    print(f"   Response: {response[:150]}")
                    if has_fallback:
                        print(f"   ⚠️  Generic fallback detected")
                    if is_error:
                        print(f"   ⚠️  Error/fallback intent")
                print()
                
            except Exception as e:
                result = {
                    "test": f"Test {i}: {description}",
                    "message": message,
                    "error": str(e),
                    "success": False
                }
                results.append(result)
                print(f"❌ FAIL Test {i}: {description}")
                print(f"   Error: {e}")
                print()
        
        # Clean up test data
        db.session.query(Expense).filter_by(user_id=test_hash).delete()
        db.session.query(User).filter_by(user_id_hash=test_hash).delete()
        db.session.commit()
        print("✓ Cleaned up test data")
    
    # Summary
    print("=" * 60)
    print("UAT TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r.get("success", False))
    failed = len(results) - passed
    
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")
    print()
    
    if failed > 0:
        print("Failed Tests:")
        for r in results:
            if not r.get("success", False):
                print(f"  - {r['test']}")
                if "error" in r:
                    print(f"    Error: {r['error']}")
                elif r.get("has_fallback"):
                    print(f"    Issue: Generic fallback response")
                elif r.get("is_error"):
                    print(f"    Issue: Error/fallback intent ({r.get('actual_intent')})")
    
    # Save detailed results
    with open("uat_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": failed,
                "success_rate": passed/len(results)*100
            },
            "results": results
        }, f, indent=2)
    
    print("\nDetailed results saved to uat_results.json")
    
    return passed == len(results)

if __name__ == "__main__":
    success = test_production_router()
    exit(0 if success else 1)