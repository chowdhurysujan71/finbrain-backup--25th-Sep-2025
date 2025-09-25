"""
Unit tests for expense repair system
Tests repair logic, category normalization, and circuit breaker patterns
"""

import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_assistant import normalize_category
from utils.expense_repair import (
    extract_amount_minor,
    guess_category,
    looks_like_expense,
    repair_expense_with_fallback,
)


class TestExpenseDetection:
    """Test expense detection patterns"""
    
    def test_looks_like_expense_positive_cases(self):
        """Test positive expense detection"""
        test_cases = [
            "I spent 300 on lunch",
            "Paid 50 taka for bus",
            "Bought groceries for ৳200",
            "Cost me 150 tk",
            "Purchased coffee ৳25"
        ]
        
        for case in test_cases:
            assert looks_like_expense(case), f"Should detect expense in: {case}"
    
    def test_looks_like_expense_negative_cases(self):
        """Test negative expense detection"""
        test_cases = [
            "Hello how are you",
            "What's the weather like",
            "I spent time reading",  # Has 'spent' but no amount
            "The cost is high",       # Has 'cost' but no amount
            "I have 300 taka"        # Has amount but no expense verb
        ]
        
        for case in test_cases:
            assert not looks_like_expense(case), f"Should NOT detect expense in: {case}"
    
    def test_empty_or_none_input(self):
        """Test edge cases with empty input"""
        assert not looks_like_expense("")
        assert not looks_like_expense(None)

class TestAmountExtraction:
    """Test amount extraction functionality"""
    
    def test_extract_amount_minor_various_formats(self):
        """Test amount extraction from various formats"""
        test_cases = [
            ("I spent 300 taka", 30000),
            ("Paid ৳50", 5000),
            ("Cost 25.50 tk", 2550),
            ("Bought for 100", None),  # No clear currency indicator
            ("300 for lunch", 30000),
            ("Spent 75.25", 7525)
        ]
        
        for text, expected in test_cases:
            result = extract_amount_minor(text)
            assert result == expected, f"Expected {expected} for '{text}', got {result}"
    
    def test_extract_amount_edge_cases(self):
        """Test amount extraction edge cases"""
        assert extract_amount_minor("") is None
        assert extract_amount_minor(None) is None
        assert extract_amount_minor("No amount here") is None
        assert extract_amount_minor("spent money") is None

class TestCategoryGuessing:
    """Test category guessing logic"""
    
    def test_guess_category_food(self):
        """Test food category detection"""
        test_cases = [
            "lunch at restaurant",
            "bought dinner",
            "coffee and tea",
            "breakfast this morning",
            "food shopping"
        ]
        
        for case in test_cases:
            assert guess_category(case) == "food", f"Should detect food in: {case}"
    
    def test_guess_category_transport(self):
        """Test transport category detection"""
        test_cases = [
            "uber ride home",
            "bus fare",
            "taxi to airport",
            "train ticket",
            "rickshaw ride"
        ]
        
        for case in test_cases:
            assert guess_category(case) == "transport", f"Should detect transport in: {case}"
    
    def test_guess_category_bills(self):
        """Test bills category detection"""
        test_cases = [
            "electricity bill",
            "water bill payment",
            "internet charges",
            "phone bill",
            "utility payment"
        ]
        
        for case in test_cases:
            assert guess_category(case) == "bills", f"Should detect bills in: {case}"
    
    def test_guess_category_shopping(self):
        """Test shopping category detection"""
        test_cases = [
            "bought new shirt",
            "shopping at mall",
            "purchased shoes",
            "store visit",
            "buy clothes"
        ]
        
        for case in test_cases:
            assert guess_category(case) == "shopping", f"Should detect shopping in: {case}"
    
    def test_guess_category_uncategorized(self):
        """Test fallback to uncategorized"""
        test_cases = [
            "random expense",
            "something else",
            "",
            None
        ]
        
        for case in test_cases:
            assert guess_category(case) == "uncategorized", f"Should default to uncategorized for: {case}"

class TestCategoryNormalization:
    """Test category normalization functionality"""
    
    def test_normalize_category_canonical(self):
        """Test canonical categories pass through"""
        canonical_categories = ['food', 'transport', 'bills', 'shopping', 'uncategorized']
        
        for category in canonical_categories:
            assert normalize_category(category) == category
            assert normalize_category(category.upper()) == category  # Test case insensitivity
    
    def test_normalize_category_synonyms(self):
        """Test synonym mapping"""
        test_cases = [
            ("grocery", "food"),
            ("groceries", "food"),
            ("lunch", "food"),
            ("uber", "transport"),
            ("taxi", "transport"),
            ("utilities", "bills"),
            ("clothes", "shopping"),
            ("other", "uncategorized"),
            ("misc", "uncategorized")
        ]
        
        for input_category, expected in test_cases:
            assert normalize_category(input_category) == expected, \
                f"Expected {expected} for {input_category}, got {normalize_category(input_category)}"
    
    def test_normalize_category_edge_cases(self):
        """Test edge cases"""
        assert normalize_category("") == "uncategorized"
        assert normalize_category(None) == "uncategorized"
        assert normalize_category("  ") == "uncategorized"
        assert normalize_category("unknown_category") == "uncategorized"

class TestRepairSystemIntegration:
    """Test the complete repair system with circuit breaker"""
    
    def test_repair_no_change_needed(self):
        """Test when no repair is needed"""
        text = "I spent 100 on lunch"
        intent, amount, category = repair_expense_with_fallback(
            text=text,
            original_intent="add_expense",
            original_amount=10000,
            original_category="food"
        )
        
        # Should pass through unchanged
        assert intent == "add_expense"
        assert amount == 10000
        assert category == "food"
    
    def test_repair_misclassified_intent(self):
        """Test repair of misclassified intent"""
        text = "I spent 100 taka on lunch"
        intent, amount, category = repair_expense_with_fallback(
            text=text,
            original_intent="analysis",  # AI misclassified
            original_amount=None,
            original_category=None
        )
        
        # Should be repaired to expense
        assert intent == "add_expense"
        assert amount == 10000  # 100 taka = 10000 minor units
        assert category == "food"  # Guessed from "lunch"
    
    def test_repair_missing_amount(self):
        """Test repair when amount is missing"""
        text = "bought groceries for 50 taka"
        intent, amount, category = repair_expense_with_fallback(
            text=text,
            original_intent="chat",
            original_amount=None,
            original_category="food"
        )
        
        # Should extract amount and change intent
        assert intent == "add_expense"
        assert amount == 5000  # 50 taka = 5000 minor units
        assert category == "food"  # Normalized
    
    def test_repair_category_normalization(self):
        """Test category normalization during repair"""
        text = "spent 100 on groceries"
        intent, amount, category = repair_expense_with_fallback(
            text=text,
            original_intent="add_expense",
            original_amount=10000,
            original_category="grocery"  # Should be normalized to "food"
        )
        
        assert intent == "add_expense"
        assert amount == 10000
        assert category == "food"  # Normalized from "grocery"
    
    def test_repair_no_amount_detected(self):
        """Test when repair cannot detect amount"""
        text = "had a great chat about expenses"
        intent, amount, category = repair_expense_with_fallback(
            text=text,
            original_intent="chat",
            original_amount=None,
            original_category=None
        )
        
        # Should not change intent since no amount detected
        assert intent == "chat"
        assert amount is None
        assert category == "uncategorized"  # Normalized
    
    def test_repair_circuit_breaker(self):
        """Test circuit breaker with exception handling"""
        # Test with invalid input that might cause exceptions
        intent, amount, category = repair_expense_with_fallback(
            text="test",
            original_intent="chat",
            original_amount=None,
            original_category="invalid_category"
        )
        
        # Should handle gracefully and normalize category
        assert intent == "chat"
        assert amount is None
        assert category == "uncategorized"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])