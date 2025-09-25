#!/usr/bin/env python3
"""
Quick routing test to debug E2E issues
"""

from app import app


def test_routing_debug():
    with app.app_context():
        from utils.routing_policy import deterministic_router
        
        # Test 1: Bengali expense
        print("=== Bengali Expense Test ===")
        bengali_message = "আজ চা ৫০ টাকা খরচ করেছি"
        bengali_signals = deterministic_router.extract_signals(bengali_message, "test_user_bengali")
        bengali_signals.ledger_count_30d = 5
        
        print(f"Message: {bengali_message}")
        print(f"Signals: {bengali_signals}")
        
        bengali_result = deterministic_router.route_intent(bengali_message, bengali_signals)
        print(f"Result: {bengali_result}")
        print(f"Expected: SMALLTALK, Got: {bengali_result.intent.value}")
        print(f"Success: {bengali_result.intent.value == 'SMALLTALK'}")
        
        print("\n=== Coaching Test ===")
        coaching_message = "help me টাকা সেভ করতে this month"
        coaching_signals = deterministic_router.extract_signals(coaching_message, "test_user_coaching")
        coaching_signals.ledger_count_30d = 20
        coaching_signals.has_coaching_verbs = True
        
        print(f"Message: {coaching_message}")
        print(f"Signals: {coaching_signals}")
        
        coaching_result = deterministic_router.route_intent(coaching_message, coaching_signals)
        print(f"Result: {coaching_result}")
        print(f"Expected: COACHING, Got: {coaching_result.intent.value}")
        print(f"Success: {coaching_result.intent.value == 'COACHING'}")

if __name__ == "__main__":
    test_routing_debug()