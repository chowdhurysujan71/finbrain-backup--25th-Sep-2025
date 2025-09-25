"""
Comprehensive test suite for FinBrain expense corrections
Tests SMART_CORRECTIONS feature with full coverage of correction scenarios
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from db_base import db
from handlers.expense import handle_correction
from models import Expense
from parsers.expense import (
    is_correction_message,
    parse_correction_reason,
    similar_category,
    similar_merchant,
)
from utils.feature_flags import is_smart_corrections_enabled
from utils.identity import psid_hash


class TestCorrectionParsing:
    """Test correction message detection and parsing"""
    
    def test_correction_message_detection(self):
        """Test various correction phrase patterns"""
        # Positive cases - should detect corrections
        assert is_correction_message("sorry, I meant 500") == True
        assert is_correction_message("actually 300 for coffee") == True
        assert is_correction_message("replace last with 400") == True
        assert is_correction_message("not ৳50, ৳500") == True
        assert is_correction_message("typo - make it $100") == True
        assert is_correction_message("correction: should be 250") == True
        
        # Negative cases - should not detect corrections
        assert is_correction_message("spent 100 on lunch") == False
        assert is_correction_message("actually quite nice") == False  # No money
        assert is_correction_message("sorry for the delay") == False  # No money
        assert is_correction_message("") == False
        assert is_correction_message(None) == False
    
    def test_correction_reason_parsing(self):
        """Test extraction of correction reasons"""
        assert parse_correction_reason("sorry, I meant 500") == "sorry, i meant"
        assert parse_correction_reason("actually 300") == "actually"
        assert parse_correction_reason("typo - 400") == "typo fix"
        assert parse_correction_reason("replace with 500") == "replace"
        assert parse_correction_reason("make it 600") == "make it"
        assert parse_correction_reason("fix amount to 700") == "amount correction"
    
    def test_similar_category_matching(self):
        """Test category similarity logic"""
        # Direct matches
        assert similar_category("food", "food") == True
        assert similar_category("transport", "transport") == True
        
        # Substring matches
        assert similar_category("food", "foods") == True
        assert similar_category("coffee", "coffee shop") == True
        
        # Category group matches
        assert similar_category("lunch", "dinner") == True  # Both food
        assert similar_category("taxi", "uber") == True     # Both transport
        assert similar_category("medicine", "pharmacy") == True  # Both health
        
        # Non-matches
        assert similar_category("food", "transport") == False
        assert similar_category("", "food") == False
        assert similar_category(None, "food") == False
    
    def test_similar_merchant_matching(self):
        """Test merchant similarity logic"""
        # Direct matches
        assert similar_merchant("Starbucks", "Starbucks") == True
        assert similar_merchant("The Wind Lounge", "The Wind Lounge") == True
        
        # Case insensitive
        assert similar_merchant("starbucks", "STARBUCKS") == True
        
        # Partial matches
        assert similar_merchant("Wind Lounge", "The Wind Lounge") == True
        assert similar_merchant("KFC", "KFC Restaurant") == True
        
        # Word overlap (50%+ threshold)
        assert similar_merchant("ABC Coffee Shop", "ABC Coffee") == True
        
        # Non-matches
        assert similar_merchant("Starbucks", "McDonald's") == False
        assert similar_merchant("", "Starbucks") == False
        assert similar_merchant(None, "Starbucks") == False

class TestCorrectionHandler:
    """Test correction handler business logic"""
    
    @patch('app.db.session')
    def test_successful_correction(self, mock_session):
        """Test A) Fresh mistake corrected quickly"""
        # Setup - mock existing expense to correct
        user_hash = psid_hash("test_user_123")
        mid = "test_msg_456"
        now = datetime.utcnow()
        
        # Mock existing expense (created 2 minutes ago)
        old_expense = MagicMock()
        old_expense.id = 1
        old_expense.user_id = user_hash
        old_expense.amount = Decimal('50.00')
        old_expense.currency = 'BDT'
        old_expense.category = 'food'
        old_expense.created_at = now - timedelta(minutes=2)
        old_expense.superseded_by = None
        
        # Mock query results
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [old_expense]
        mock_session.query.return_value.filter.return_value.first.return_value = None  # No duplicate
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()
        mock_session.commit = MagicMock()
        
        # Test correction
        result = handle_correction(user_hash, mid, "sorry, I meant 500 for coffee", now)
        
        # Verify result
        assert result['intent'] == 'correction_applied'
        assert result['amount'] == 500.0
        assert result['category'] == 'food'
        assert 'Got it — corrected food from ৳50 → ৳500' in result['text']
        
        # Verify database operations
        mock_session.add.assert_called_once()  # New expense added
        mock_session.commit.assert_called_once()
        
        # Verify old expense was marked as superseded
        assert old_expense.superseded_by is not None
        assert old_expense.corrected_at == now
        assert old_expense.corrected_reason == "sorry, i meant"
    
    @patch('app.db.session')
    def test_correction_no_candidate(self, mock_session):
        """Test D) No candidate in window - logs as new"""
        user_hash = psid_hash("test_user_789")
        mid = "test_msg_789"
        now = datetime.utcnow()
        
        # Mock no expenses found in window
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        
        # Test correction with no candidate
        result = handle_correction(user_hash, mid, "actually 400 for lunch", now)
        
        # Verify it logs as new expense
        assert result['intent'] == 'correction_logged_as_new'
        assert result['amount'] == 400.0
        assert 'Logged food ৳400 as new' in result['text']
        
        # Verify new expense was created
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @patch('app.db.session')
    def test_duplicate_correction_protection(self, mock_session):
        """Test C) Duplicate protection - same mid doesn't create third row"""
        user_hash = psid_hash("test_user_dup")
        mid = "test_msg_duplicate"
        now = datetime.utcnow()
        
        # Mock existing correction with same mid
        existing_correction = MagicMock()
        existing_correction.unique_id = f"correction_{mid}_123456"
        
        # Mock query to find existing correction
        mock_session.query.return_value.filter.return_value.first.return_value = existing_correction
        
        # Test duplicate correction
        result = handle_correction(user_hash, mid, "actually 600", now)
        
        # Verify duplicate detection
        assert result['intent'] == 'correction_duplicate'
        assert 'already processed that correction' in result['text']
        
        # Verify no new database operations
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()
    
    @patch('app.db.session')
    def test_merchant_and_venue_correction(self, mock_session):
        """Test B) Merchant and venue text preservation"""
        user_hash = psid_hash("test_user_merchant")
        mid = "test_msg_merchant"
        now = datetime.utcnow()
        
        # Mock existing expense with merchant
        old_expense = MagicMock()
        old_expense.id = 2
        old_expense.amount = Decimal('300.00')
        old_expense.currency = 'BDT'
        old_expense.category = 'food'
        old_expense.created_at = now - timedelta(minutes=1)
        old_expense.superseded_by = None
        
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [old_expense]
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test correction with merchant
        result = handle_correction(user_hash, mid, "actually 500 lunch at The Wind Lounge", now)
        
        # Verify merchant is preserved in new expense
        assert result['intent'] == 'correction_applied'
        assert result['amount'] == 500.0
        assert 'corrected food from ৳300 → ৳500' in result['text']

class TestFeatureFlags:
    """Test feature flag behavior"""
    
    @patch.dict('os.environ', {'SMART_CORRECTIONS_DEFAULT': 'false'})
    def test_corrections_disabled_by_default(self):
        """Test corrections are disabled by default"""
        user_hash = psid_hash("test_user_flag")
        assert is_smart_corrections_enabled(user_hash) == False
    
    @patch.dict('os.environ', {
        'SMART_CORRECTIONS_DEFAULT': 'false',
        'FEATURE_ALLOWLIST_SMART_CORRECTIONS': 'abc123,def456'
    })
    def test_corrections_enabled_for_allowlist(self):
        """Test corrections enabled for allowlist users"""
        # User in allowlist should have corrections enabled
        assert is_smart_corrections_enabled("abc123") == True
        
        # User not in allowlist should have corrections disabled
        user_hash = psid_hash("not_in_allowlist")
        assert is_smart_corrections_enabled(user_hash) == False
    
    @patch.dict('os.environ', {'SMART_CORRECTIONS_DEFAULT': 'true'})
    def test_corrections_enabled_globally(self):
        """Test corrections enabled for all users when global flag is on"""
        user_hash = psid_hash("any_user")
        assert is_smart_corrections_enabled(user_hash) == True

class TestCrossCurrencyCorrections:
    """Test E) Cross-currency corrections"""
    
    @patch('app.db.session')
    def test_cross_currency_correction(self, mock_session):
        """Test correction maintains currency consistency"""
        user_hash = psid_hash("test_user_currency")
        mid = "test_msg_currency"
        now = datetime.utcnow()
        
        # Mock USD expense to correct
        old_expense = MagicMock()
        old_expense.id = 3
        old_expense.amount = Decimal('3.00')
        old_expense.currency = 'USD'
        old_expense.category = 'food'
        old_expense.created_at = now - timedelta(minutes=1)
        old_expense.superseded_by = None
        
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [old_expense]
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test USD correction
        result = handle_correction(user_hash, mid, "meant $5 at Starbucks", now)
        
        # Verify USD currency is maintained
        assert result['intent'] == 'correction_applied'
        assert result['amount'] == 5.0
        assert 'corrected food from $3 → $5' in result['text']

@pytest.mark.integration
class TestEndToEndCorrections:
    """End-to-end integration tests"""
    
    def setup_method(self):
        """Setup test database state"""
        db.create_all()
        
    def teardown_method(self):
        """Cleanup test database"""
        db.session.rollback()
        db.drop_all()
    
    def test_full_correction_flow(self):
        """Test complete correction flow with real database"""
        user_hash = psid_hash("integration_user")
        now = datetime.utcnow()
        
        # Step 1: Create initial expense
        initial_expense = Expense()
        initial_expense.user_id = user_hash
        initial_expense.amount = Decimal('50.00')
        initial_expense.currency = 'BDT'
        initial_expense.category = 'food'
        initial_expense.description = 'coffee'
        initial_expense.date = now.date()
        initial_expense.time = now.time()
        initial_expense.month = now.strftime('%Y-%m')
        initial_expense.unique_id = f"test_{int(now.timestamp())}"
        initial_expense.created_at = now
        initial_expense.platform = 'messenger'
        
        db.session.add(initial_expense)
        db.session.commit()
        
        # Step 2: Apply correction
        correction_result = handle_correction(
            user_hash, 
            "correction_msg_123",
            "sorry, I meant 500 for coffee",
            now + timedelta(seconds=30)
        )
        
        # Step 3: Verify correction applied
        assert correction_result['intent'] == 'correction_applied'
        assert correction_result['amount'] == 500.0
        
        # Step 4: Verify database state
        # Original expense should be superseded
        original = db.session.query(Expense).filter_by(id=initial_expense.id).first()
        assert original.superseded_by is not None
        assert original.corrected_at is not None
        assert original.corrected_reason == "sorry, i meant"
        
        # New corrected expense should exist
        corrected = db.session.query(Expense).filter_by(id=original.superseded_by).first()
        assert corrected is not None
        assert corrected.amount == Decimal('500.00')
        assert corrected.category == 'food'
        assert corrected.superseded_by is None  # Not corrected itself
        
        # Step 5: Verify summaries exclude superseded expense
        uncorrected_expenses = db.session.query(Expense).filter(
            Expense.user_id == user_hash,
            Expense.superseded_by.is_(None)
        ).all()
        
        assert len(uncorrected_expenses) == 1
        assert uncorrected_expenses[0].amount == Decimal('500.00')

if __name__ == "__main__":
    pytest.main([__file__, "-v"])