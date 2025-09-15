"""
Demo script to test the UAT system with mock user interactions
Simulates a complete UAT flow to verify all features work
"""
import sys
import time
from app import app
from utils.production_router import production_router

def simulate_uat_flow():
    """Simulate complete UAT testing flow"""
    
    with app.app_context():
        print("🚀 FINBRAIN UAT DEMO - Live Testing Simulation")
        print("=" * 60)
        
        test_psid = "UAT_DEMO_USER_001"
        
        # Test messages simulating user interaction
        test_sequence = [
            ("start uat", "Initiate UAT testing"),
            ("hello", "Welcome response"),
            ("I spent 500 BDT on groceries yesterday", "Expense logging test"),
            ("2000 BDT for rent", "Categorization test"),
            ("150 BDT for transport", "Multi-entry test"),
            ("summary", "Summary/advice trigger"),
            ("test1", "Rate limit test 1"),
            ("test2", "Rate limit test 2"),
            ("test3", "Rate limit test 3"),
            ("test4", "Rate limit test 4"),
            ("test5", "Rate limit test 5 (should hit limit)"),
            ("What did I spend most on?", "Context recall test")
        ]
        
        print(f"Testing with PSID: {test_psid}")
        print(f"Total test messages: {len(test_sequence)}")
        print()
        
        # Execute test sequence
        for i, (message, description) in enumerate(test_sequence, 1):
            print(f"Step {i}: {description}")
            print(f"   User: {message}")
            
            try:
                # Route message through production system
                response, intent, category, amount = production_router.route_message(
                    text=message,
                    psid=test_psid,
                    rid=f"uat_demo_{i:03d}"
                )
                
                print(f"   Bot: {response}")
                print(f"   Intent: {intent}")
                
                if category:
                    print(f"   Category: {category}")
                if amount:
                    print(f"   Amount: {amount}")
                
            except Exception as e:
                print(f"   ERROR: {e}")
            
            print("-" * 40)
            
            # Small delay to simulate real interaction timing
            time.sleep(0.5)
        
        print("\n✅ UAT Demo completed!")
        print("\nCheck the results above to verify:")
        print("- ✓ UAT system starts and guides user through steps")
        print("- ✓ Expense logging works with amount/category extraction")
        print("- ✓ Rate limiting triggers after 4 AI requests")
        print("- ✓ Fallback responses when rate limited")
        print("- ✓ Context recall for spending analysis")

if __name__ == "__main__":
    simulate_uat_flow()