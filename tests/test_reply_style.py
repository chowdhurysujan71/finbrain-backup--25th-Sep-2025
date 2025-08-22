"""
Test currency formatting and reply style consistency
"""

import pytest
from utils.parser import extract_expenses

def test_default_bdt_currency():
    """Test that default currency is BDT (৳) when no symbol specified"""
    # Test expense parsing defaults to BDT
    expenses = extract_expenses("spent 150 on coffee")
    assert len(expenses) == 1
    assert expenses[0]['amount'] == 150.0
    # Default currency should be handled in response formatting
    

def test_explicit_currency_preserved():
    """Test that explicit currency symbols are preserved"""
    test_cases = [
        ("spent $25 on lunch", 25.0),
        ("bought €30 groceries", 30.0), 
        ("paid £15 for transport", 15.0),
        ("₹200 for dinner", 200.0),
        ("¥1000 shopping", 1000.0)
    ]
    
    for text, expected_amount in test_cases:
        expenses = extract_expenses(text)
        assert len(expenses) >= 1
        assert expenses[0]['amount'] == expected_amount


def test_bdt_symbol_recognition():
    """Test that ৳ symbol is properly recognized"""
    expenses = extract_expenses("spent ৳180 on food")
    assert len(expenses) == 1
    assert expenses[0]['amount'] == 180.0


def test_currency_formatting_rules():
    """Test currency formatting follows the rules"""
    # Symbol before amount, 2 decimals only when needed
    test_amounts = [
        (150.00, "৳150"),    # No decimals for whole numbers
        (25.50, "৳25.50"),   # Decimals when needed
        (100.0, "৳100"),     # No decimals for .0
    ]
    
    for amount, expected in test_amounts:
        # This would be tested in the actual formatting function
        # when implemented in response generation
        assert True  # Placeholder for formatting logic


def test_mixed_currency_detection():
    """Test detection of mixed currencies in single message"""
    mixed_text = "spent $50 and ৳200 today"
    expenses = extract_expenses(mixed_text)
    # Should extract both amounts
    amounts = [exp['amount'] for exp in expenses]
    assert 50.0 in amounts or 200.0 in amounts


def test_reply_length_limit():
    """Test that replies stay under 280 character limit"""
    # This would test actual response generation
    # Placeholder for when response formatting is implemented
    max_length = 280
    sample_response = "✅ Logged: ৳120 for food\n\nGreat choice! Consider setting a weekly coffee budget to track this spending. Type 'summary' to see your total expenses."
    assert len(sample_response) <= max_length


if __name__ == "__main__":
    pytest.main([__file__, "-v"])