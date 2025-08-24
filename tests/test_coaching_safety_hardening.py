#!/usr/bin/env python3
"""
Production Safety Test Suite for Coaching Hardening
Tests all safety mechanisms for bulletproof coaching operation

Test Cases A-H for Production Hardening Validation:
A: Protected intents (SUMMARY/LOG/CORRECTION) always get normal replies
B: Redis failure detection prevents coaching gracefully  
C: Rate limit validation blocks coaching when exceeded
D: Guard functions make correct safety decisions
E: Intent-first short-circuit ensures normal replies first
F: Coaching only triggers on explicit "insight" keyword
G: Session continuation guards prevent invalid state transitions
H: Error handling never breaks normal message flow
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import time

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

class TestCoachingSafetyHardening(unittest.TestCase):
    """Production safety test suite for coaching hardening"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_psid_hash = "test_user_123456"
        self.test_text = "summary"
        
    def test_a_protected_intents_always_get_normal_replies(self):
        """Test A: Protected intents (SUMMARY/LOG/CORRECTION) always get normal replies"""
        print("\n=== TEST A: Protected Intents Always Get Normal Replies ===")
        
        from handlers.coaching import can_start_coach
        
        # Test all protected intents
        protected_intents = ['SUMMARY', 'LOG', 'CORRECTION']
        
        for intent in protected_intents:
            # Even with perfect conditions, protected intents should never trigger coaching
            result = can_start_coach(
                intent=intent,
                last_outbound_intent=None,
                user_text="any text",
                redis_ok=True,
                caps_ok=True
            )
            
            self.assertFalse(result, f"Protected intent {intent} should never allow coaching")
            print(f"✅ {intent}: Correctly blocked coaching")
        
        print("✅ Test A PASSED: All protected intents block coaching")
    
    def test_b_redis_failure_detection(self):
        """Test B: Redis failure detection prevents coaching gracefully"""
        print("\n=== TEST B: Redis Failure Detection ===")
        
        from handlers.coaching import can_start_coach, check_redis_health
        
        # Test Redis health check
        redis_health = check_redis_health()
        print(f"Current Redis health: {redis_health}")
        
        # Test coaching blocked when Redis fails
        result_redis_down = can_start_coach(
            intent='INSIGHT',
            last_outbound_intent=None,
            user_text="insight",
            redis_ok=False,  # Redis failure
            caps_ok=True
        )
        
        self.assertFalse(result_redis_down, "Coaching should be blocked when Redis fails")
        print("✅ Coaching correctly blocked when Redis unavailable")
        
        # Test coaching allowed when Redis healthy
        result_redis_up = can_start_coach(
            intent='INSIGHT', 
            last_outbound_intent=None,
            user_text="insight",
            redis_ok=True,   # Redis healthy
            caps_ok=True
        )
        
        self.assertTrue(result_redis_up, "Coaching should be allowed when Redis healthy")
        print("✅ Coaching correctly allowed when Redis healthy")
        
        print("✅ Test B PASSED: Redis failure detection works")
    
    def test_c_rate_limit_validation(self):
        """Test C: Rate limit validation blocks coaching when exceeded"""
        print("\n=== TEST C: Rate Limit Validation ===")
        
        from handlers.coaching import can_start_coach
        
        # Test coaching blocked when rate limited
        result_rate_limited = can_start_coach(
            intent='INSIGHT',
            last_outbound_intent=None,
            user_text="insight",
            redis_ok=True,
            caps_ok=False  # Rate limited
        )
        
        self.assertFalse(result_rate_limited, "Coaching should be blocked when rate limited")
        print("✅ Coaching correctly blocked when rate limited")
        
        # Test coaching allowed when within limits
        result_within_limits = can_start_coach(
            intent='INSIGHT',
            last_outbound_intent=None, 
            user_text="insight",
            redis_ok=True,
            caps_ok=True   # Within limits
        )
        
        self.assertTrue(result_within_limits, "Coaching should be allowed when within limits")
        print("✅ Coaching correctly allowed when within limits")
        
        print("✅ Test C PASSED: Rate limit validation works")
    
    def test_d_guard_function_decisions(self):
        """Test D: Guard functions make correct safety decisions"""
        print("\n=== TEST D: Guard Function Safety Decisions ===")
        
        from handlers.coaching import can_start_coach, can_continue
        
        # Test can_start_coach edge cases
        test_cases = [
            # (intent, last_intent, user_text, redis_ok, caps_ok, expected, description)
            ('INSIGHT', None, 'insight', True, True, True, 'Explicit insight opt-in'),
            ('INSIGHT', 'SUMMARY', 'transport', True, True, True, 'Valid follow-up after SUMMARY'),
            ('INSIGHT', 'INSIGHT', 'food', True, True, True, 'Valid follow-up after INSIGHT'),
            ('INSIGHT', None, 'random text', True, True, False, 'Random text should not trigger'),
            ('INSIGHT', 'LOG', 'insight', True, True, True, 'Explicit insight always works'),
            ('OTHER', None, 'insight', True, True, True, 'Non-INSIGHT intent with explicit opt-in'),
        ]
        
        for intent, last_intent, user_text, redis_ok, caps_ok, expected, desc in test_cases:
            result = can_start_coach(intent, last_intent, user_text, redis_ok, caps_ok)
            self.assertEqual(result, expected, f"Failed: {desc}")
            print(f"✅ {desc}: {'✓' if result == expected else '✗'}")
        
        # Test can_continue edge cases
        continue_cases = [
            # (state, user_text, expected, description)
            ('await_focus', 'transport', True, 'Valid focus response'),
            ('await_focus', 'food', True, 'Valid focus response'),
            ('await_focus', 'random', False, 'Invalid focus response'),
            ('await_commit', 'yes', True, 'Valid commit response'),
            ('await_commit', 'sure', True, 'Valid commit response'),
            ('await_commit', 'no way', False, 'Invalid commit response'),
            ('invalid_state', 'anything', False, 'Invalid state'),
        ]
        
        for state, user_text, expected, desc in continue_cases:
            result = can_continue(state, user_text)
            self.assertEqual(result, expected, f"Failed: {desc}")
            print(f"✅ {desc}: {'✓' if result == expected else '✗'}")
        
        print("✅ Test D PASSED: Guard functions make correct decisions")
    
    def test_e_intent_first_shortcircuit(self):
        """Test E: Intent-first short-circuit ensures normal replies first"""
        print("\n=== TEST E: Intent-First Short-Circuit ===")
        
        from handlers.coaching import maybe_continue
        
        # Test that protected intents are immediately short-circuited
        protected_intents = ['SUMMARY', 'LOG', 'CORRECTION']
        
        for intent in protected_intents:
            result = maybe_continue(
                psid_hash=self.test_psid_hash,
                intent=intent,
                parsed_data={'original_text': 'test message'}
            )
            
            self.assertIsNone(result, f"Intent {intent} should be short-circuited")
            print(f"✅ {intent}: Correctly short-circuited")
        
        print("✅ Test E PASSED: Intent-first short-circuit works")
    
    def test_f_explicit_insight_trigger(self):
        """Test F: Coaching only triggers on explicit 'insight' keyword"""
        print("\n=== TEST F: Explicit Insight Trigger ===")
        
        from handlers.coaching import can_start_coach
        
        # Test various user inputs
        test_inputs = [
            ('insight', True, 'Exact "insight" keyword'),
            ('INSIGHT', True, 'Uppercase "INSIGHT"'),
            ('  insight  ', True, 'Padded "insight"'),
            ('insight.', True, 'Insight with punctuation'),
            ('I want insight', False, 'Insight in sentence'),
            ('insightful', False, 'Contains insight but not exact'),
            ('summary', False, 'Different keyword'),
            ('help', False, 'Help keyword'),
            ('random text', False, 'Random text'),
        ]
        
        for user_text, expected, desc in test_inputs:
            result = can_start_coach(
                intent='INSIGHT',
                last_outbound_intent=None,
                user_text=user_text,
                redis_ok=True,
                caps_ok=True
            )
            
            self.assertEqual(result, expected, f"Failed: {desc}")
            status = '✓' if result == expected else '✗'
            print(f"{status} '{user_text}': {desc}")
        
        print("✅ Test F PASSED: Only explicit 'insight' triggers coaching")
    
    def test_g_session_continuation_guards(self):
        """Test G: Session continuation guards prevent invalid state transitions"""
        print("\n=== TEST G: Session Continuation Guards ===")
        
        from handlers.coaching import can_continue
        
        # Test state transition validation
        valid_states = ['await_focus', 'await_commit']
        invalid_states = ['idle', 'completed', 'error', 'unknown']
        
        # Test valid states with valid responses
        for state in valid_states:
            result = can_continue(state, 'yes')
            print(f"✅ State '{state}' with valid response: {result}")
        
        # Test invalid states (should always return False)
        for state in invalid_states:
            result = can_continue(state, 'yes')
            self.assertFalse(result, f"Invalid state {state} should not continue")
            print(f"✅ State '{state}': Correctly blocked")
        
        print("✅ Test G PASSED: Session continuation guards work")
    
    def test_h_error_handling_preserves_normal_flow(self):
        """Test H: Error handling never breaks normal message flow"""
        print("\n=== TEST H: Error Handling Preserves Normal Flow ===")
        
        # Test that exceptions in coaching don't break normal replies
        with patch('handlers.coaching.check_redis_health', side_effect=Exception("Redis error")):
            from handlers.coaching import maybe_continue
            
            # Even with Redis exception, function should return None (not crash)
            result = maybe_continue(
                psid_hash=self.test_psid_hash,
                intent='INSIGHT',
                parsed_data={'original_text': 'insight'}
            )
            
            self.assertIsNone(result, "Exception should not crash, should return None")
            print("✅ Redis exception handled gracefully")
        
        # Test session manager exceptions
        with patch('utils.session.get_coaching_session', side_effect=Exception("Session error")):
            from handlers.coaching import handle_coaching_response
            
            # Exception should not crash the function
            result = handle_coaching_response(self.test_psid_hash, "test message")
            
            self.assertIsNone(result, "Session exception should not crash")
            print("✅ Session exception handled gracefully")
        
        print("✅ Test H PASSED: Error handling preserves normal flow")

def run_safety_tests():
    """Run all safety test cases"""
    print("🔒 COACHING SAFETY HARDENING TEST SUITE")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCoachingSafetyHardening)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("🎉 ALL SAFETY TESTS PASSED - PRODUCTION READY")
        print(f"✅ {result.testsRun} tests passed")
    else:
        print("❌ SAFETY TESTS FAILED")
        print(f"❌ {len(result.failures)} failures, {len(result.errors)} errors")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  {test}: {traceback}")
                
        if result.errors:
            print("\nErrors:")  
            for test, traceback in result.errors:
                print(f"  {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_safety_tests()
    sys.exit(0 if success else 1)