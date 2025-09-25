"""
Comprehensive test suite for continuous coaching flow
Tests session management, rate limiting, and conversation flow
"""

import unittest
from unittest.mock import patch

from handlers.coaching import handle_coaching_response, maybe_continue
from utils.session import (
    delete_coaching_session,
    get_coaching_session,
    get_daily_coaching_count,
    increment_daily_coaching_count,
)


class TestCoachingFlow(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        self.test_psid = "test_psid_12345678"
        # Clean up any existing session
        delete_coaching_session(self.test_psid)
        
    def tearDown(self):
        """Clean up after tests"""
        delete_coaching_session(self.test_psid)
    
    @patch('utils.structured.log_structured_event')
    def test_coaching_start_from_insight(self, mock_log):
        """A) Start from insight → expect COACH_START, Q1 with quick replies"""
        
        # Call maybe_continue with insight intent
        result = maybe_continue(self.test_psid, 'insight', {'categories': ['transport', 'food']})
        
        # Should return coaching reply
        self.assertIsNotNone(result)
        self.assertEqual(result['intent'], 'coaching')
        self.assertIn('Which area do you want to improve', result['text'])
        self.assertIn('quick_replies', result)
        
        # Should have quick reply buttons
        quick_replies = result['quick_replies']
        reply_titles = [qr['title'] for qr in quick_replies]
        self.assertIn('Transport', reply_titles)
        self.assertIn('Food', reply_titles)
        self.assertIn('Skip', reply_titles)
        
        # Should log COACH_START event
        mock_log.assert_any_call("COACH_START", {"topic": "transport"})
        
        # Should create session
        session = get_coaching_session(self.test_psid)
        self.assertIsNotNone(session)
        self.assertEqual(session['state'], 'await_focus')
        self.assertEqual(session['turns'], 1)
    
    @patch('utils.structured.log_structured_event')
    def test_focus_response_transport(self, mock_log):
        """B) User replies transport → Q2 with two options"""
        
        # Start coaching session
        maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        
        # User selects transport
        result = handle_coaching_response(self.test_psid, 'transport')
        
        # Should return commit question
        self.assertIsNotNone(result, "Should get response for transport selection")
        self.assertEqual(result['intent'], 'coaching')
        self.assertIn('Nice choice!', result['text'])
        self.assertIn('batch trips or off-peak', result['text'])
        
        # Should have action options
        quick_replies = result['quick_replies']
        reply_titles = [qr['title'] for qr in quick_replies]
        self.assertIn('Batch Trips', reply_titles)
        self.assertIn('Off-Peak', reply_titles)
        
        # Should log Q2 event
        mock_log.assert_any_call("COACH_Q2_SENT", {"topic": "transport", "options": ['batch trips', 'off-peak']})
        
        # Session should be updated
        session = get_coaching_session(self.test_psid)
        self.assertEqual(session['state'], 'await_commit')
        self.assertEqual(session['topic'], 'transport')
        self.assertEqual(session['turns'], 2)
    
    @patch('utils.structured.log_structured_event')
    def test_commit_response_completion(self, mock_log):
        """C) User picks off-peak → COACH_END completed, cooldown set, daily count++"""
        
        # Start and progress to commit phase
        maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        handle_coaching_response(self.test_psid, 'transport')
        
        initial_count = get_daily_coaching_count(self.test_psid)
        
        # User commits to off-peak
        result = handle_coaching_response(self.test_psid, 'off-peak')
        
        # Should return completion message
        self.assertIsNotNone(result)
        self.assertEqual(result['intent'], 'coaching_complete')
        self.assertIn('Perfect!' if 'Perfect!' in result['text'] else 'Awesome!', result['text'])
        
        # Should log action selected and end events
        mock_log.assert_any_call("COACH_ACTION_SELECTED", {"action": "off-peak", "topic": "transport"})
        mock_log.assert_any_call("COACH_END", {"reason": "completed"})
        
        # Session should be in cooldown
        session = get_coaching_session(self.test_psid)
        self.assertIsNotNone(session)
        self.assertEqual(session['state'], 'cooldown')
        
        # Daily count should increment
        new_count = get_daily_coaching_count(self.test_psid)
        self.assertEqual(new_count, initial_count + 1)
    
    @patch('utils.structured.log_structured_event')
    def test_turn_limit_exceeded(self, mock_log):
        """D) Exceed COACH_MAX_TURNS → COACH_END turn_limit"""
        
        # Start coaching
        maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        
        # Simulate unclear responses to hit turn limit
        result1 = handle_coaching_response(self.test_psid, 'unclear message')
        self.assertIsNotNone(result1, "Should get response for unclear message")
        if result1:
            self.assertIn('Which area interests you', result1['text'])  # Re-ask
        
        result2 = handle_coaching_response(self.test_psid, 'another unclear message')
        self.assertIn('Which area interests you', result2['text'])  # Re-ask again
        
        result3 = handle_coaching_response(self.test_psid, 'final unclear message')
        self.assertIn("I'll let you think about it", result3['text'])  # Turn limit hit
        
        # Should log turn limit end
        mock_log.assert_any_call("COACH_END", {"reason": "turn_limit"})
        
        # Session should be deleted
        session = get_coaching_session(self.test_psid)
        self.assertIsNone(session)
    
    @patch('utils.structured.log_structured_event')
    def test_daily_rate_limit(self, mock_log):
        """E) Hit daily cap → COACH_RATE_LIMIT_HIT and normal replies only"""
        
        # Simulate reaching daily limit
        from utils.config import COACH_PER_DAY_MAX
        
        # Set daily count to max
        for _ in range(COACH_PER_DAY_MAX):
            increment_daily_coaching_count(self.test_psid)
        
        # Try to start coaching
        result = maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        
        # Should not return coaching reply
        self.assertIsNone(result)
        
        # Should log rate limit hit
        # Check for rate limit logging (count may vary due to test isolation)
        rate_limit_calls = [call for call in mock_log.call_args_list if 'COACH_RATE_LIMIT_HIT' in str(call)]
        self.assertTrue(len(rate_limit_calls) > 0, "Should log rate limit hit")
    
    def test_session_expiry_graceful_handling(self, ):
        """F) Expiry (TTL) mid-flow → resumes gracefully or exits"""
        
        # Start coaching session
        maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        
        # Manually expire session by deleting it
        delete_coaching_session(self.test_psid)
        
        # Try to handle response with expired session
        result = handle_coaching_response(self.test_psid, 'transport')
        
        # Should return None (no active session)
        self.assertIsNone(result)
    
    def test_cooldown_enforcement(self):
        """Test cooldown period enforcement"""
        
        # Complete a coaching session to trigger cooldown
        maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        handle_coaching_response(self.test_psid, 'transport')
        handle_coaching_response(self.test_psid, 'off-peak')
        
        # Try to start new coaching immediately
        result = maybe_continue(self.test_psid, 'summary', {'categories': ['food']})
        
        # Should be blocked by cooldown
        self.assertIsNone(result)
    
    def test_skip_responses(self):
        """Test user skip responses at different stages"""
        
        # Test skip at focus stage
        maybe_continue(self.test_psid, 'insight', {'categories': ['transport']})
        result = handle_coaching_response(self.test_psid, 'skip')
        
        self.assertIsNotNone(result, "Should get response for skip")
        self.assertIn("No worries", result['text'])
        
        # Session should be ended
        session = get_coaching_session(self.test_psid)
        self.assertIsNone(session)

if __name__ == '__main__':
    unittest.main()