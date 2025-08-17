#!/usr/bin/env python3
"""
Test the FIXED conversational AI with user data access
"""

import logging
import sys
sys.path.insert(0, '.')

def test_fixed_system():
    """Test the fixed conversational AI system"""
    from app import app
    from utils.production_router import ProductionRouter
    from utils.conversational_ai import conversational_ai
    
    with app.app_context():
        print("🎯 TESTING FIXED CONVERSATIONAL AI SYSTEM")
        print("=" * 60)
        
        # Use the actual hash that has expense data
        user_hash = "dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc"
        
        # Test 1: Direct conversational AI with hash
        print("\n1. Testing direct conversational AI with hash:")
        response, intent = conversational_ai.handle_conversational_query(user_hash, "Give me a summary report now")
        print(f"   Response: {response}")
        print(f"   Intent: {intent}")
        
        # Check for real data
        if any(str(amt) in response for amt in ['2915', '8', '1815', '1000']):
            print("   ✅ USING REAL USER DATA!")
        else:
            print("   ❌ Still using arbitrary data")
            
        # Test 2: Complete production flow with hash
        print("\n2. Testing production router with hash:")
        router = ProductionRouter()
        
        # Simulate message from existing user
        response, intent, category, amount = router.route_message(
            text="Give me a summary report now",
            psid=user_hash,  # Pass the hash as PSID
            rid="test_fixed"
        )
        
        print(f"   Response: {response}")
        print(f"   Intent: {intent}")
        
        # Check for real data
        if any(str(amt) in response for amt in ['2915', '8', '1815', '1000']):
            print("   ✅ PRODUCTION ROUTER USING REAL DATA!")
        else:
            print("   ❌ Production router still has issues")
            
        # Test 3: Different query types
        print("\n3. Testing different query types:")
        test_queries = [
            "How much did I spend this week",
            "What's my biggest expense category", 
            "Analyze my spending patterns"
        ]
        
        for query in test_queries:
            print(f"\n   Query: '{query}'")
            response, intent = conversational_ai.handle_conversational_query(user_hash, query)
            print(f"   Response: {response[:100]}...")
            print(f"   Intent: {intent}")
            
            if any(str(amt) in response for amt in ['2915', '8', '1815', '1000']):
                print("   ✅ REAL DATA")
            elif "start logging" in response.lower() or "no data" in response.lower():
                print("   ❌ FALLBACK")
            else:
                print("   ⚠️  UNCLEAR")

if __name__ == "__main__":
    test_fixed_system()