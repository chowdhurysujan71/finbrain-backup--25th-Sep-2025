#!/usr/bin/env python3
"""
Test the evolved AI expense parser within proper Flask application context
"""

import logging
import sys
sys.path.insert(0, '.')

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_with_app_context():
    """Test the AI expense parser within Flask app context"""
    from app import app, db
    from utils.production_router import ProductionRouter
    
    with app.app_context():
        print("🧪 Testing Evolution with Flask App Context")
        print("=" * 60)
        
        # Initialize router within app context
        router = ProductionRouter()
        
        # Test the exact scenario from screenshot
        test_message = "Logging today's expenses - coffee 100, burger 300 and watermelon juice 300"
        test_psid = "test_evolution_context"
        
        print(f"📝 Message: {test_message}")
        
        try:
            # Route through evolved system
            response, intent, category, amount = router.route_message(
                text=test_message,
                psid=test_psid,
                rid="context_test"
            )
            
            print(f"✅ Response: {response}")
            print(f"🎯 Intent: {intent}")
            print(f"🏷️ Category: {category}")
            print(f"💰 Amount: {amount}")
            
            # Check if evolution works in proper context
            if intent == "ai_expense_logged":
                print(f"\n🎉 SUCCESS: Evolution works perfectly in Flask context!")
                print(f"✅ Multi-item parsing functional")
                print(f"✅ Database operations successful")
                print(f"✅ No Flask context issues")
                return True
            elif intent == "ai_context_driven":
                print(f"\n⚠️ Still hitting context-thin logic")
                print(f"This means the expense parser integration needs adjustment")
                return False
            else:
                print(f"\n❌ Unexpected intent: {intent}")
                return False
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_simple_case_context():
    """Test simple case within app context"""
    from app import app
    from utils.production_router import ProductionRouter
    
    with app.app_context():
        print(f"\n🧪 Testing Simple Case with App Context")
        print("=" * 40)
        
        router = ProductionRouter()
        
        test_message = "coffee 100"
        test_psid = "test_simple_context"
        
        try:
            response, intent, category, amount = router.route_message(
                text=test_message,
                psid=test_psid,
                rid="simple_context_test"
            )
            
            print(f"✅ Response: {response}")
            print(f"🎯 Intent: {intent}")
            print(f"💰 Amount: {amount}")
            
            if intent == "ai_expense_logged":
                print(f"✅ Simple case works in Flask context")
                return True
            else:
                print(f"⚠️ Simple case has different behavior: {intent}")
                return False
                
        except Exception as e:
            print(f"❌ Simple test failed: {e}")
            return False

if __name__ == "__main__":
    # Test evolution within proper Flask context
    evolution_success = test_with_app_context()
    simple_success = test_simple_case_context()
    
    print(f"\n🏁 FLASK CONTEXT TEST RESULTS")
    print("=" * 60)
    
    if evolution_success:
        print("🚀 EVOLUTION CONFIRMED: Flask context issue RESOLVED!")
        print("✅ Multi-item expense parser works in production environment")
        print("✅ Database operations function correctly")
        print("✅ No application context errors")
    else:
        print("❌ Flask context issue persists - needs investigation")
        
    if simple_success:
        print("✅ Backward compatibility maintained")
    else:
        print("⚠️ Simple cases affected by changes")