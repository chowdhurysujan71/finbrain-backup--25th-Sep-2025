"""
Test suite for gap-fix clarifier flow implementation
Tests targeted clarification for missing amount/category with confidence==0.5
"""

import os
from unittest.mock import patch

import pytest

import backend_assistant as ba


class TestClarifyFlow:
    """Test clarifier functionality for gap-fix enhancements"""
    
    def setup_method(self):
        """Setup test environment with flags enabled"""
        self.original_env = os.environ.copy()
        os.environ['ENABLE_CLARIFIERS'] = 'true'
    
    def teardown_method(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_missing_category_triggers_clarifier(self):
        """Test that missing category with amount present triggers clarifier"""
        # Test input with amount but no clear category
        text = "spent 500 on something"
        
        result = ba.propose_expense(text)
        
        # Should have confidence around 0.5 (2/4 signals: amount + currency)
        assert result['confidence'] == 0.5
        assert result['status'] == 'needs_review'
        assert 'clarify' in result
        
        clarify_data = result['clarify']
        assert clarify_data['question'] == "Which category fits best?"
        assert clarify_data['missing'] == 'category'
        assert 'Food' in clarify_data['chips']
        assert 'Transport' in clarify_data['chips']
        assert clarify_data['draft']['amount_minor'] == 50000  # 500 * 100
    
    def test_missing_amount_triggers_clarifier(self):
        """Test that missing amount with category present triggers clarifier"""
        # Test input with category but no amount
        text = "bought food today"
        
        result = ba.propose_expense(text)
        
        # Should have confidence around 0.5 (2/4 signals: category + date_resolved)
        assert result['confidence'] == 0.5  
        assert result['status'] == 'needs_review'
        assert 'clarify' in result
        
        clarify_data = result['clarify']
        assert clarify_data['question'] == "How much was it?"
        assert clarify_data['missing'] == 'amount'
        assert '৳50' in clarify_data['chips']
        assert clarify_data['draft']['category'] == 'food'
    
    def test_confidence_zero_no_clarifier(self):
        """Test that confidence==0 returns generic hint, not clarifier"""
        # Test input with no recognizable expense patterns
        text = "hello how are you"
        
        result = ba.propose_expense(text)
        
        assert result['confidence'] == 0.0
        assert 'clarify' not in result
        assert result['amount_minor'] is None
        assert result['category'] is None
    
    def test_high_confidence_no_clarifier(self):
        """Test that high confidence bypasses clarifier"""
        # Test input with clear amount and category
        text = "spent 200 taka on lunch today"
        
        result = ba.propose_expense(text)
        
        # Should have high confidence (4/4 signals: amount, category, currency, date)
        assert result['confidence'] == 1.0
        assert 'clarify' not in result
        assert result['amount_minor'] == 20000  # 200 * 100
        assert result['category'] == 'food'
    
    def test_clarifier_disabled_fallback(self):
        """Test that disabled clarifier falls back to generic message"""
        os.environ['ENABLE_CLARIFIERS'] = 'false'
        
        # Test input that would normally trigger clarifier
        text = "spent 500 on something"
        
        result = ba.propose_expense(text)
        
        # Should still have confidence 0.5 but no clarifier data
        assert result['confidence'] == 0.5
        assert result['status'] == 'needs_review'
        # Clarifier should return generic message when disabled
        if 'clarify' in result:
            assert "I couldn't fully understand" in result['clarify']['question']
    
    def test_schema_unification_fields(self):
        """Test that all results include schema unification fields"""
        text = "lunch 150"
        
        result = ba.propose_expense(text)
        
        # Schema unification fields should be present
        assert 'raw_text' in result
        assert 'parsed_at_iso' in result
        assert result['raw_text'] == text
        assert result['parsed_at_iso'].endswith('Z')  # ISO format with Z suffix
    
    def test_confidence_bins_logging(self):
        """Test that confidence bins are logged for observability"""
        with patch('backend_assistant.logger') as mock_logger:
            # Test various confidence levels
            test_cases = [
                ("spent 200 on food today", "high"),  # 1.0 confidence
                ("spent 200 on food", "medium"),      # 0.75 confidence  
                ("spent 200", "medium"),              # 0.5 confidence
                ("random text", "none")               # 0.0 confidence
            ]
            
            for text, expected_bin in test_cases:
                ba.propose_expense(text)
                
                # Check that enhanced parsing log was called with correct bin
                mock_logger.info.assert_called()
                last_call = mock_logger.info.call_args[0][0]
                assert "[ENHANCED_PARSING]" in last_call
                assert f"bin={expected_bin}" in last_call


class TestConfidenceHeuristic:
    """Test enhanced confidence scoring with 4 signals"""
    
    def test_all_signals_present(self):
        """Test confidence=1.0 with all 4 signals"""
        text = "spent 200 taka on lunch today"
        result = ba.propose_expense(text)
        
        # All signals: amount(200) + category(lunch→food) + currency(taka) + date(today)
        assert result['confidence'] == 1.0
    
    def test_three_signals_present(self):
        """Test confidence=0.75 with 3/4 signals"""
        text = "spent 200 on food"
        result = ba.propose_expense(text)
        
        # 3 signals: amount(200) + category(food) + currency(default) + no date
        assert result['confidence'] == 0.75
    
    def test_two_signals_present(self):
        """Test confidence=0.5 with 2/4 signals"""
        text = "spent 200"
        result = ba.propose_expense(text)
        
        # 2 signals: amount(200) + currency(default) + no category + no date
        assert result['confidence'] == 0.5
    
    def test_one_signal_present(self):
        """Test confidence=0.25 with 1/4 signals"""
        text = "bought food"
        result = ba.propose_expense(text)
        
        # 1 signal: category(food) only
        assert result['confidence'] == 0.25
    
    def test_no_signals_present(self):
        """Test confidence=0.0 with 0/4 signals"""
        text = "hello world"
        result = ba.propose_expense(text)
        
        # 0 signals: no amount, category, currency word, or date
        assert result['confidence'] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])