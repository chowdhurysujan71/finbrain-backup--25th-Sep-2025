"""
Test cases for new user expense logging with money detection
Ensures LOG intent always prioritizes over SUMMARY when money is detected
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock

# Import the functions we need to test
from finbrain.router import contains_money
from parsers.expense import parse_amount_currency_category
from utils.production_router import ProductionRouter
from utils.db import save_expense_idempotent


class TestMoneyDetection:
    """Test the contains_money function"""
    
    def test_currency_symbols(self):
        """Test detection of currency symbols"""
        assert contains_money("৳100 coffee") == True
        assert contains_money("$25 lunch") == True
        assert contains_money("£15.99 book") == True
        assert contains_money("€30 groceries") == True
        assert contains_money("₹200 dinner") == True
    
    def test_action_words(self):
        """Test detection of spent/paid/bought patterns"""
        assert contains_money("spent 100 on lunch") == True
        assert contains_money("paid 50 for coffee") == True
        assert contains_money("bought 200 groceries") == True
        assert contains_money("Spent 150.50 on shopping") == True
    
    def test_preposition_patterns(self):
        """Test detection of amount + on/for patterns"""
        assert contains_money("100 on lunch") == True
        assert contains_money("50 for coffee") == True
        assert contains_money("100 tk for transport") == True
        assert contains_money("25 usd on food") == True
    
    def test_no_money_detected(self):
        """Test cases where no money should be detected"""
        assert contains_money("summary") == False
        assert contains_money("show me my expenses") == False
        assert contains_money("hello") == False
        assert contains_money("recap") == False
        assert contains_money("") == False
        assert contains_money("   ") == False


class TestUnifiedParser:
    """Test the unified expense parser"""
    
    def test_currency_symbol_parsing(self):
        """Test parsing with currency symbols"""
        result = parse_amount_currency_category("৳100 coffee")
        assert result['amount'] == Decimal('100')
        assert result['currency'] == 'BDT'
        assert result['category'] == 'food'
        
        result = parse_amount_currency_category("$25 lunch")
        assert result['amount'] == Decimal('25')
        assert result['currency'] == 'USD'
        assert result['category'] == 'food'
    
    def test_action_word_parsing(self):
        """Test parsing with action words"""
        result = parse_amount_currency_category("spent 100 on lunch")
        assert result['amount'] == Decimal('100')
        assert result['currency'] == 'BDT'  # Default
        assert result['category'] == 'food'
    
    def test_category_detection(self):
        """Test category detection and mapping"""
        result = parse_amount_currency_category("100 tk lunch")
        assert result['category'] == 'food'
        
        result = parse_amount_currency_category("50 for transport")
        assert result['category'] == 'transport'
        
        result = parse_amount_currency_category("200 on groceries")
        assert result['category'] == 'groceries'
    
    def test_decimal_amounts(self):
        """Test parsing decimal amounts"""
        result = parse_amount_currency_category("spent 150.50 on shopping")
        assert result['amount'] == Decimal('150.50')
        assert result['currency'] == 'BDT'
        assert result['category'] == 'shopping'
    
    def test_no_amount_cases(self):
        """Test cases where no amount should be found"""
        assert parse_amount_currency_category("summary") == {}
        assert parse_amount_currency_category("hello") == {}
        assert parse_amount_currency_category("") == {}


class TestNewUserLogging:
    """Test new user expense logging scenarios"""
    
    @pytest.fixture
    def fresh_psid_hash(self):
        """Generate a fresh PSID hash with zero expenses"""
        import hashlib
        import time
        return hashlib.sha256(f"test_user_{time.time()}".encode()).hexdigest()
    
    @pytest.fixture
    def router(self):
        """Create a ProductionRouter instance"""
        return ProductionRouter()
    
    def test_case_a_spent_100_lunch_std(self, fresh_psid_hash, router):
        """Case A: text="Spent 100 on lunch" mode=STD → LOG with amount=100, currency=BDT, category=lunch"""
        with patch('utils.production_router.save_expense_idempotent') as mock_save:
            mock_save.return_value = {'duplicate': False, 'success': True, 'expense_id': 1}
            
            response, intent, category, amount = router.route_message(
                text="Spent 100 on lunch",
                psid=fresh_psid_hash,
                rid="test_msg_1"
            )
            
            assert intent == "log"
            assert amount == 100.0
            assert category == "food"  # lunch maps to food
            assert "100" in response
            assert "logged" in response.lower()
            
            # Verify save_expense_idempotent was called with correct parameters
            mock_save.assert_called_once()
            call_args = mock_save.call_args[1]
            assert call_args['amount'] == 100.0
            assert call_args['currency'] == 'BDT'
            assert call_args['category'] == 'food'
    
    def test_case_b_bdt_100_coffee_std(self, fresh_psid_hash, router):
        """Case B: text="৳100 coffee" mode=STD → LOG with currency=BDT, category=coffee"""
        with patch('utils.production_router.save_expense_idempotent') as mock_save:
            mock_save.return_value = {'duplicate': False, 'success': True, 'expense_id': 2}
            
            response, intent, category, amount = router.route_message(
                text="৳100 coffee",
                psid=fresh_psid_hash,
                rid="test_msg_2"
            )
            
            assert intent == "log"
            assert amount == 100.0
            assert category == "food"  # coffee maps to food
            
            call_args = mock_save.call_args[1]
            assert call_args['currency'] == 'BDT'
            assert call_args['category'] == 'food'
    
    def test_case_c_100_tk_lunch_std(self, fresh_psid_hash, router):
        """Case C: text="100 tk lunch" mode=STD → LOG with BDT"""
        with patch('utils.production_router.save_expense_idempotent') as mock_save:
            mock_save.return_value = {'duplicate': False, 'success': True, 'expense_id': 3}
            
            response, intent, category, amount = router.route_message(
                text="100 tk lunch",
                psid=fresh_psid_hash,
                rid="test_msg_3"
            )
            
            assert intent == "log"
            assert amount == 100.0
            
            call_args = mock_save.call_args[1]
            assert call_args['currency'] == 'BDT'
    
    def test_case_d_duplicate_mid(self, fresh_psid_hash, router):
        """Case D: replay same mid → no second row, duplicate message"""
        with patch('utils.production_router.save_expense_idempotent') as mock_save:
            # First call succeeds
            mock_save.return_value = {'duplicate': False, 'success': True, 'expense_id': 4}
            
            response1, intent1, _, _ = router.route_message(
                text="Spent 100 on lunch",
                psid=fresh_psid_hash,
                rid="duplicate_test_msg"
            )
            
            # Second call with same rid returns duplicate
            mock_save.return_value = {'duplicate': True, 'timestamp': '10:30', 'success': False}
            
            response2, intent2, _, _ = router.route_message(
                text="Spent 100 on lunch",
                psid=fresh_psid_hash,
                rid="duplicate_test_msg"  # Same message ID
            )
            
            assert intent1 == "log"
            assert intent2 == "log_duplicate"
            assert "repeat" in response2.lower()
            assert "10:30" in response2
    
    def test_case_e_summary_zero_expenses(self, fresh_psid_hash, router):
        """Case E: text="summary" with zero expenses → SUMMARY template shown"""
        with patch('utils.dispatcher.handle_message_dispatch') as mock_dispatch:
            mock_dispatch.return_value = ("No recent spending found in the last 7 days.", "summary")
            
            response, intent, _, _ = router.route_message(
                text="summary",
                psid=fresh_psid_hash,
                rid="summary_test_msg"
            )
            
            assert intent == "summary"
            assert "no recent spending" in response.lower()
    
    def test_case_f_paid_usd(self, fresh_psid_hash, router):
        """Case F: text="paid $3" → LOG with USD and amount=3"""
        with patch('utils.production_router.save_expense_idempotent') as mock_save:
            mock_save.return_value = {'duplicate': False, 'success': True, 'expense_id': 5}
            
            response, intent, category, amount = router.route_message(
                text="paid $3",
                psid=fresh_psid_hash,
                rid="usd_test_msg"
            )
            
            assert intent == "log"
            assert amount == 3.0
            
            call_args = mock_save.call_args[1]
            assert call_args['currency'] == 'USD'
            assert call_args['amount'] == 3.0


class TestIdempotencyProtection:
    """Test idempotency protection in database layer"""
    
    def test_save_expense_idempotent_new(self):
        """Test saving new expense with idempotency protection"""
        with patch('utils.db.db') as mock_db:
            mock_db.session.query.return_value.filter_by.return_value.first.return_value = None
            mock_db.session.add = MagicMock()
            mock_db.session.commit = MagicMock()
            
            with patch('utils.db.get_or_create_user') as mock_user:
                mock_user.return_value = MagicMock(total_expenses=0, expense_count=0)
                
                with patch('models.MonthlySummary') as mock_summary:
                    mock_summary.query.filter_by.return_value.first.return_value = None
                    
                    result = save_expense_idempotent(
                        user_identifier="test_hash",
                        description="test expense",
                        amount=100.0,
                        category="food",
                        currency="BDT",
                        platform="facebook",
                        original_message="spent 100 on lunch",
                        unique_id="test_mid_123"
                    )
                    
                    assert result['duplicate'] == False
                    assert result['success'] == True
    
    def test_save_expense_idempotent_duplicate(self):
        """Test duplicate detection with same message ID"""
        with patch('utils.db.db') as mock_db:
            # Mock existing expense found
            mock_existing = MagicMock()
            mock_existing.created_at.strftime.return_value = "10:30"
            mock_existing.id = 123
            
            mock_db.session.query.return_value.filter_by.return_value.first.return_value = mock_existing
            
            result = save_expense_idempotent(
                user_identifier="test_hash",
                description="test expense",
                amount=100.0,
                category="food",
                currency="BDT",
                platform="facebook",
                original_message="spent 100 on lunch",
                unique_id="duplicate_mid_123"
            )
            
            assert result['duplicate'] == True
            assert result['timestamp'] == "10:30"
            assert result['success'] == False
            assert result['expense_id'] == 123


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v"])