#!/usr/bin/env python3
"""
Debug why the system gives inconsistent responses about user data
"""

import sys
sys.path.insert(0, '.')

def debug_inconsistent_responses():
    """Debug the inconsistent response issue"""
    from app import app
    from utils.production_router import ProductionRouter
    from utils.security import hash_psid
    from models import db
    from sqlalchemy import text
    
    with app.app_context():
        print("🔍 DEBUGGING INCONSISTENT RESPONSES")
        print("=" * 50)
        
        # Check recent user activity to find who might be getting these responses
        print("\n1. CHECKING RECENT USER ACTIVITY")
        result = db.session.execute(text("""
            SELECT user_id, COUNT(*) as count, SUM(amount) as total, 
                   MAX(created_at) as last_expense,
                   STRING_AGG(DISTINCT description, ', ') as descriptions
            FROM expenses 
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY user_id 
            ORDER BY last_expense DESC
            LIMIT 5
        """))
        
        users = result.fetchall()
        for user_id, count, total, last, descriptions in users:
            print(f"   User: {user_id[:16]}... | {count} expenses | ${total} | Last: {last}")
            print(f"   Recent items: {descriptions[:100]}...")
            print()
        
        if not users:
            print("   No recent users found")
            return
            
        # Test with the most active user
        test_user = users[0][0]
        print(f"\n2. TESTING WITH MOST ACTIVE USER: {test_user[:16]}...")
        
        router = ProductionRouter()
        
        # Test the exact sequence from screenshots
        test_sequence = [
            "Do you know all my expenses so far?",
            "What about gambling"
        ]
        
        for i, message in enumerate(test_sequence, 1):
            print(f"\n   Test {i}: '{message}'")
            
            try:
                # Test with the user hash directly (since they store data with hash)
                response, intent, category, amount = router.route_message(
                    text=message,
                    psid=test_user,  # Use stored hash
                    rid=f"debug_test_{i}"
                )
                
                print(f"   Response: {response}")
                print(f"   Intent: {intent}")
                
                # Check if response contains data
                has_data = any(word in response.lower() for word in ['spent', '$', 'groceries', 'coffee', 'gambling'])
                no_data = any(phrase in response.lower() for phrase in ['no data', "don't see", 'start logging'])
                
                if has_data and no_data:
                    print(f"   ⚠️  INCONSISTENT: Contains both 'no data' and specific spending info")
                elif has_data:
                    print(f"   ✅ GOOD: Contains spending data")
                elif no_data:
                    print(f"   ❌ BAD: Says no data available")
                else:
                    print(f"   ⚠️  UNCLEAR: Response type unknown")
                    
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
        
        # Test different ways the PSID might come in
        print(f"\n3. TESTING DIFFERENT PSID FORMATS")
        
        # Simulate what happens if we get an actual Facebook PSID
        fake_psid = "1234567890123456"  # 16-digit Facebook PSID
        actual_hash = hash_psid(fake_psid)
        
        print(f"   Facebook PSID: {fake_psid}")
        print(f"   Computed hash: {actual_hash[:16]}...")
        
        # Test if there are expenses for this computed hash
        result = db.session.execute(text("SELECT COUNT(*) FROM expenses WHERE user_id = %s"), (actual_hash,))
        count = result.fetchone()[0]
        print(f"   Expenses for computed hash: {count}")
        
        # Now test routing with the fake PSID
        try:
            response, intent, category, amount = router.route_message(
                text="Do you know all my expenses so far?",
                psid=fake_psid,  # Real PSID format
                rid="debug_psid_test"
            )
            print(f"   PSID Response: {response[:100]}...")
            
            if "no data" in response.lower():
                print(f"   ✅ EXPECTED: No data for new PSID")
            else:
                print(f"   ⚠️  UNEXPECTED: Found data for new PSID")
                
        except Exception as e:
            print(f"   ❌ PSID test error: {e}")

if __name__ == "__main__":
    debug_inconsistent_responses()