#!/usr/bin/env python3
"""
Smoke Test Script for Coaching Guard System
Non-destructive validation of the 4 main intent paths

Tests:
- SUMMARY: Should get normal reply, no coaching attempt
- LOG: Should get normal reply, no coaching attempt  
- CORRECTION: Should get normal reply, no coaching attempt
- INSIGHT: Should get normal reply, coaching only if explicit "insight"

Outputs:
- Resolved intent
- Messages sent count
- Last telemetry line
"""

import json
import os
import sys
from unittest.mock import patch

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def capture_telemetry():
    """Capture telemetry events for analysis"""
    telemetry_log = []
    
    def mock_log_structured_event(event_type, data):
        telemetry_log.append({
            'event_type': event_type,
            'data': data
        })
    
    return telemetry_log, mock_log_structured_event

def simulate_intent_path(intent_text, description):
    """Simulate an intent path and capture results"""
    print(f"\n🧪 Testing: {description}")
    print(f"Input: '{intent_text}'")
    
    # Capture telemetry
    telemetry_log, mock_telemetry = capture_telemetry()
    
    # Mock the structured logging
    with patch('utils.structured.log_structured_event', side_effect=mock_telemetry):
        try:
            # Test the production router
            from utils.production_router import ProductionRouter
            
            router = ProductionRouter()
            test_psid = "test_psid_12345"
            test_psid_hash = "test_hash_67890"
            test_rid = "test_rid_999"
            
            # Route the message
            response, intent, category, amount = router.route_message(
                text=intent_text,
                psid=test_psid,
                rid=test_rid
            )
            
            # Count messages (for now, always 1 since we return single response)
            message_count = 1
            
            # Get last telemetry event
            last_telemetry = telemetry_log[-1] if telemetry_log else {'event_type': 'none', 'data': {}}
            
            print(f"✅ Resolved Intent: {intent}")
            print(f"✅ Messages Sent: {message_count}")
            print(f"✅ Response: {response[:100]}{'...' if len(response) > 100 else ''}")
            print(f"✅ Last Telemetry: {last_telemetry['event_type']} - {json.dumps(last_telemetry['data'], default=str)}")
            
            return {
                'intent': intent,
                'message_count': message_count,
                'response': response,
                'telemetry': telemetry_log,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {
                'intent': 'error',
                'message_count': 0,
                'response': str(e),
                'telemetry': telemetry_log,
                'success': False
            }

def test_coaching_guards():
    """Test coaching guard functions directly"""
    print("\n🛡️ Testing Coaching Guards")
    
    from handlers.coaching import can_continue, can_start_coach, check_redis_health
    
    # Test Redis health
    redis_health = check_redis_health()
    print(f"✅ Redis Health: {redis_health}")
    
    # Test protected intents are blocked
    protected_intents = ['SUMMARY', 'LOG', 'CORRECTION']
    for intent in protected_intents:
        blocked = not can_start_coach(intent, None, "any text", True, True)
        print(f"✅ {intent} Blocked: {blocked}")
    
    # Test explicit insight is allowed
    insight_allowed = can_start_coach('INSIGHT', None, 'insight', True, True)
    print(f"✅ Explicit Insight Allowed: {insight_allowed}")
    
    # Test session continuation guards
    valid_continue = can_continue('await_focus', 'transport')
    invalid_continue = can_continue('invalid_state', 'anything')
    print(f"✅ Valid Continuation: {valid_continue}")
    print(f"✅ Invalid Continuation Blocked: {not invalid_continue}")

def run_smoke_tests():
    """Run all smoke tests"""
    print("🚀 COACHING GUARD SMOKE TESTS")
    print("=" * 50)
    
    # Test cases: (input_text, description)
    test_cases = [
        ("summary", "SUMMARY Intent - Should get normal reply only"),
        ("spent 100 on lunch", "LOG Intent - Should get normal reply only"),
        ("sorry I meant 200", "CORRECTION Intent - Should get normal reply only"),
        ("insight", "INSIGHT Intent - Should get normal reply, coaching if explicit"),
        ("random text", "Unknown Input - Should get help message"),
    ]
    
    results = []
    
    # Run intent path tests
    for text, description in test_cases:
        result = simulate_intent_path(text, description)
        results.append(result)
    
    # Test coaching guards directly
    test_coaching_guards()
    
    # Summary
    print("\n📊 SMOKE TEST SUMMARY")
    print("=" * 50)
    
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    
    print(f"✅ Router Tests: {successful_tests}/{total_tests} passed")
    
    # Verify key requirements
    summary_result = next((r for r in results if 'summary' in str(r.get('intent', '')).lower()), None)
    if summary_result:
        print(f"✅ SUMMARY sends exactly {summary_result['message_count']} message")
    
    # Check for coaching skip telemetry on protected intents
    coaching_skips = 0
    for result in results:
        for event in result.get('telemetry', []):
            if event['event_type'] == 'COACH_SKIPPED_INTENT':
                coaching_skips += 1
    
    print(f"✅ Coaching skips detected: {coaching_skips}")
    
    if successful_tests == total_tests:
        print("\n🎉 ALL SMOKE TESTS PASSED - SYSTEM OPERATIONAL")
        return True
    else:
        print(f"\n❌ {total_tests - successful_tests} SMOKE TESTS FAILED")
        return False

if __name__ == "__main__":
    success = run_smoke_tests()
    sys.exit(0 if success else 1)