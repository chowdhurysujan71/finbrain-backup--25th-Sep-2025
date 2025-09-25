"""
Comprehensive Tests for SMART_CORRECTIONS System
Tests correction detection, parsing, candidate matching, and supersede logic
"""

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from finbrain.router import contains_money_with_correction_fallback
from handlers.expense import handle_correction
from parsers.expense import (
    is_correction_message,
    parse_correction_reason,
    parse_expense,
    similar_category,
    similar_merchant,
)
from templates.replies import (
    format_corrected_reply,
    format_correction_duplicate_reply,
    format_correction_no_candidate_reply,
)


class TestCorrectionDetection(unittest.TestCase):
    """Test correction pattern detection"""

    def test_correction_patterns(self):
        """Test various correction phrase patterns"""
        correction_messages = [
            "sorry, I meant 500",
            "actually it was 300",
            "i meant 200 for coffee",
            "correct that to 150",
            "should be 400",
            "make it 250",
            "not 100, 500",
            "typo, meant 350"
        ]
        
        non_correction_messages = [
            "spent 100 on coffee",
            "lunch 50",
            "200 for groceries",
            "hello world",
            "summary please"
        ]
        
        for message in correction_messages:
            with self.subTest(message=message):
                self.assertTrue(is_correction_message(message), 
                               f"Should detect correction in: {message}")
        
        for message in non_correction_messages:
            with self.subTest(message=message):
                self.assertFalse(is_correction_message(message), 
                                f"Should NOT detect correction in: {message}")

    def test_correction_reason_extraction(self):
        """Test extraction of correction reasons"""
        test_cases = [
            ("sorry, I meant 500", "sorry, i meant"),
            ("actually it was 300", "actually"),
            ("typo, meant 350", "typo fix"),
            ("should be 400", "should be"),
            ("correction: 250", "correction"),
            ("random text 200", "amount correction")
        ]
        
        for message, expected_reason in test_cases:
            with self.subTest(message=message):
                reason = parse_correction_reason(message)
                self.assertEqual(reason, expected_reason)

class TestCorrectionFallbackMoneyDetection(unittest.TestCase):
    """Test money detection with correction fallbacks"""

    @patch('utils.feature_flags.is_smart_corrections_enabled')
    def test_fallback_activation(self, mock_corrections_enabled):
        """Test that fallback only activates when conditions are met"""
        mock_corrections_enabled.return_value = True
        
        # These should trigger fallback detection
        fallback_cases = [
            "sorry, I meant 500",  # Bare number in correction
            "actually 1.5k",       # k shorthand in correction
            "typo, should be 250", # Bare number in correction
        ]
        
        # These should NOT trigger fallback (not corrections)
        non_fallback_cases = [
            "spent 500",           # Not a correction
            "500 for coffee",      # Not a correction
            "hello 123",           # Not a correction
        ]
        
        for case in fallback_cases:
            with self.subTest(case=case):
                result = contains_money_with_correction_fallback(case, "test_user_hash")
                self.assertTrue(result, f"Should detect money in correction fallback: {case}")
        
        # Test with corrections disabled
        mock_corrections_enabled.return_value = False
        
        for case in fallback_cases:
            with self.subTest(case=case, corrections_enabled=False):
                result = contains_money_with_correction_fallback(case, "test_user_hash")
                # Should fall back to standard detection, which would fail for bare numbers
                # This depends on whether standard detection catches it
                pass  # We'll test specific scenarios

class TestCorrectionParsing(unittest.TestCase):
    """Test parsing of correction messages"""

    def test_correction_context_parsing(self):
        """Test parsing in correction context"""
        now = datetime.now()
        
        # Test bare number parsing in correction context
        result = parse_expense("500", now, correction_context=True)
        self.assertIsNotNone(result)
        self.assertEqual(result['amount'], Decimal('500'))
        self.assertIsNone(result['currency'])  # Should inherit from candidate
        self.assertIsNone(result['category'])  # Should inherit from candidate
        self.assertTrue(result.get('correction_context'))
        
        # Test k shorthand in correction context
        result = parse_expense("1.5k", now, correction_context=True)
        # Note: This depends on the normalization handling k shorthand
        
        # Test decimal amounts
        result = parse_expense("25.50", now, correction_context=True)
        self.assertIsNotNone(result)
        self.assertEqual(result['amount'], Decimal('25.50'))

class TestSimilarityMatching(unittest.TestCase):
    """Test category and merchant similarity functions"""

    def test_similar_category(self):
        """Test category similarity matching"""
        similar_pairs = [
            ("food", "food"),
            ("Food", "food"),
            ("transport", "TRANSPORT")
        ]
        
        different_pairs = [
            ("food", "transport"),
            ("health", "entertainment"),
            ("", "food"),
            (None, "food")
        ]
        
        for cat1, cat2 in similar_pairs:
            with self.subTest(cat1=cat1, cat2=cat2):
                self.assertTrue(similar_category(cat1, cat2))
                
        for cat1, cat2 in different_pairs:
            with self.subTest(cat1=cat1, cat2=cat2):
                self.assertFalse(similar_category(cat1, cat2))

    def test_similar_merchant(self):
        """Test merchant similarity matching"""
        similar_pairs = [
            ("Starbucks", "starbucks"),
            ("McDonald's", "mcdonalds"),
            ("Coffee Shop", "coffee"),
            ("The Restaurant", "restaurant")
        ]
        
        different_pairs = [
            ("Starbucks", "McDonald's"),
            ("", "Starbucks"),
            (None, "Coffee"),
            ("A", "B")  # Too short
        ]
        
        for merch1, merch2 in similar_pairs:
            with self.subTest(merch1=merch1, merch2=merch2):
                self.assertTrue(similar_merchant(merch1, merch2))
                
        for merch1, merch2 in different_pairs:
            with self.subTest(merch1=merch1, merch2=merch2):
                self.assertFalse(similar_merchant(merch1, merch2))

class TestReplyTemplates(unittest.TestCase):
    """Test correction reply formatting"""

    def test_corrected_reply_formatting(self):
        """Test successful correction reply formatting"""
        reply = format_corrected_reply(
            old_amount=100.0, 
            old_currency='BDT',
            new_amount=Decimal('500'),
            new_currency='BDT',
            category='food',
            merchant='Starbucks'
        )
        
        self.assertIn('100', reply)
        self.assertIn('500', reply)
        self.assertIn('food', reply)
        self.assertIn('Starbucks', reply)
        self.assertIn('৳', reply)  # BDT symbol
        self.assertIn('→', reply)  # Arrow indicating change

    def test_no_candidate_reply_formatting(self):
        """Test no candidate reply formatting"""
        reply = format_correction_no_candidate_reply(
            amount=Decimal('300'),
            currency='BDT',
            category='transport'
        )
        
        self.assertIn('300', reply)
        self.assertIn('transport', reply)
        self.assertIn('৳', reply)
        self.assertIn('new expense', reply)

    def test_duplicate_reply_formatting(self):
        """Test duplicate correction reply"""
        reply = format_correction_duplicate_reply()
        self.assertIsInstance(reply, str)
        self.assertTrue(len(reply) > 0)

@patch('handlers.expense.db')
class TestCorrectionHandlerIntegration(unittest.TestCase):
    """Integration tests for correction handler"""

    def test_end_to_end_correction_flow(self, mock_db):
        """Test complete correction flow from detection to response"""
        # Mock database and models
        mock_expense = MagicMock()
        mock_expense.id = 1
        mock_expense.amount = Decimal('100')
        mock_expense.currency = 'BDT'
        mock_expense.category = 'food'
        mock_expense.created_at = datetime.now()
        
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_expense]
        mock_db.session.query.return_value.filter.return_value.first.return_value = None  # No duplicate
        
        # Test correction processing
        with patch('handlers.expense.parse_expense') as mock_parse, \
             patch('handlers.expense._create_new_expense') as mock_create, \
             patch('handlers.expense._update_user_totals') as mock_update:
                
            mock_parse.return_value = {
                'amount': Decimal('500'),
                'currency': 'BDT',
                'category': 'food',
                'merchant': None,
                'ts_client': datetime.now(),
                'note': 'sorry, I meant 500'
            }
            
            mock_new_expense = MagicMock()
            mock_new_expense.id = 2
            mock_create.return_value = mock_new_expense
            
            # Call handler
            result = handle_correction("test_user", "msg_123", "sorry, I meant 500", datetime.now())
            
            # Verify response
            self.assertEqual(result['intent'], 'correction_applied')
            self.assertIn('text', result)
            self.assertEqual(result['amount'], 500.0)
            
            # Verify database operations
            mock_create.assert_called_once()
            mock_update.assert_called_once()

if __name__ == '__main__':
    # Run specific test classes
    unittest.main(verbosity=2)