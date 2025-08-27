"""
Comprehensive test for the Bengali money fix
Validates the exact failing cases mentioned in the specification
"""
import pytest
from nlp.signals_extractor import extract_signals
from utils.bn_digits import to_en_digits
from nlp.money_patterns import extract_money_mentions, has_money_mention

class TestBengaliMoneyFix:
    """Test the specific Bengali money cases that were failing"""
    
    def test_bengali_money_word_after_number(self):
        """Test: চা ৫০ টাকা (the originally failing case)"""
        signals = extract_signals("চা ৫০ টাকা")
        
        assert signals["has_money"] is True, "Should detect money in Bengali"
        assert len(signals["money_mentions"]) > 0, "Should have money mentions"
        assert any("50" in mention for mention in signals["money_mentions"]), "Should contain converted Bengali numerals"
    
    def test_bengali_money_word_before_number(self):
        """Test: টাকা ১,২৫০.৫০"""
        signals = extract_signals("টাকা ১,২৫০.৫০")
        
        assert signals["has_money"] is True, "Should detect money with Bengali word first"
        assert len(signals["money_mentions"]) > 0, "Should have money mentions"
        # Should find either 1,250.50 or 1250.50 (with or without comma)
        assert any("1250" in mention or "1,250" in mention for mention in signals["money_mentions"]), "Should handle Bengali comma formatting"
    
    def test_symbol_before_number_bengali_digits(self):
        """Test: ৳২৫০ (symbol before Bengali digits)"""
        signals = extract_signals("৳২৫০")
        
        assert signals["has_money"] is True, "Should detect money with symbol before Bengali digits"
        assert any("250" in mention for mention in signals["money_mentions"]), "Should convert Bengali digits to ASCII"
    
    def test_mixed_bengali_english_money(self):
        """Test: lunch ৳৫০০ taka"""
        signals = extract_signals("lunch ৳৫০০ taka")
        
        assert signals["has_money"] is True, "Should detect money in mixed language context"
        assert any("500" in mention for mention in signals["money_mentions"]), "Should handle mixed context"
    
    def test_bengali_digit_conversion(self):
        """Test Bengali digit conversion utility"""
        test_cases = [
            ("০১২৩৪৫৬৭৮৯", "0123456789"),
            ("৫০০", "500"),
            ("১,২৫০.৫০", "1,250.50"),
            ("চা ৫০ টাকা", "চা 50 টাকা"),
        ]
        
        for bengali_text, expected_ascii in test_cases:
            result = to_en_digits(bengali_text)
            assert result == expected_ascii, f"Failed to convert {bengali_text} to {expected_ascii}, got {result}"
    
    def test_money_pattern_recognition_comprehensive(self):
        """Test comprehensive money pattern recognition"""
        test_cases = [
            # Bengali word cases
            ("চা ৫০ টাকা", True),
            ("টাকা ১০০", True),
            ("খাবার ২৫০ টাকা", True),
            
            # Symbol cases
            ("৳৫০০", True),
            ("কফি ৳১২৫", True),
            ("২০০ ৳", True),
            
            # English cases (should still work)
            ("lunch 500 taka", True),
            ("500 tk", True),
            ("bdt 250", True),
            
            # Mixed cases
            ("চা ৳৫০ today", True),
            ("spending ১০০ টাকা yesterday", True),
            
            # Negative cases (no money)
            ("চা খেয়েছি", False),
            ("lunch today", False),
            ("analysis please", False),
        ]
        
        for text, should_have_money in test_cases:
            signals = extract_signals(text)
            actual_has_money = signals["has_money"]
            assert actual_has_money == should_have_money, f"Failed for '{text}': expected {should_have_money}, got {actual_has_money}"
    
    def test_edge_cases_bengali_money(self):
        """Test edge cases for Bengali money detection"""
        edge_cases = [
            # Spacing variations
            ("চা৫০টাকা", True),  # No spaces
            ("চা  ৫০  টাকা", True),  # Multiple spaces
            ("চা\t৫০\nটাকা", True),  # Whitespace characters
            
            # Case variations
            ("চা ৫০ TAKA", True),
            ("চা ৫০ Taka", True),
            
            # Complex amounts
            ("খাবার ১,২৫০.৫০ টাকা", True),
            ("বই ৯৯৯.৯৯ ৳", True),
            
            # Multiple mentions
            ("চা ৫০ টাকা এবং কফি ৳৩০", True),
        ]
        
        for text, should_have_money in edge_cases:
            signals = extract_signals(text)
            assert signals["has_money"] == should_have_money, f"Edge case failed for: {text}"

class TestDataHandlingIntegration:
    """Test integration with existing data handling system"""
    
    def test_phase1_gains_preserved_with_bengali_fix(self):
        """Ensure Phase 1 gains are preserved with Bengali money fix"""
        # All these should still work from Phase 1
        phase1_cases = [
            {"input": "analysis please", "expects": {"explicit_analysis_request": True}},
            {"input": "বিশ্লেষণ দাও", "expects": {"explicit_analysis_request": True}},
            {"input": "today spending", "expects": {"has_time_window": True}},
            {"input": "help me save money", "expects": {"has_coaching_verbs": True}},
            {"input": "what can you do", "expects": {"has_faq_terms": True}},
            {"input": "/id", "expects": {"is_admin": True}},
        ]
        
        for case in phase1_cases:
            signals = extract_signals(case["input"])
            for key, expected in case["expects"].items():
                actual = signals.get(key, False)
                assert actual == expected, f"Phase 1 regression in '{case['input']}': {key} expected {expected}, got {actual}"
    
    def test_complex_bilingual_scenarios(self):
        """Test complex bilingual scenarios with money detection"""
        complex_cases = [
            {
                "input": "আজ lunch এ ৳৫০০ টাকা খরচ করেছি",
                "expects": {
                    "has_money": True,
                    "has_time_window": True
                }
            },
            {
                "input": "গত সপ্তাহের spending analysis দাও ৳২,০০০ এর বেশি",
                "expects": {
                    "has_money": True,
                    "has_time_window": True,
                    "explicit_analysis_request": True
                }
            },
            {
                "input": "help me reduce খরচ this month ৳১০,০০০ budget",
                "expects": {
                    "has_money": True,
                    "has_time_window": True,
                    "has_coaching_verbs": True
                }
            }
        ]
        
        for case in complex_cases:
            signals = extract_signals(case["input"])
            for key, expected in case["expects"].items():
                actual = signals.get(key, False)
                assert actual == expected, f"Complex case failed for '{case['input']}': {key} expected {expected}, got {actual}"

def run_comprehensive_money_tests():
    """Run comprehensive money fix validation"""
    import sys
    import subprocess
    
    # Run the tests
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_comprehensive_money_fix.py", 
        "-v", "--tb=short"
    ], capture_output=True, text=True, cwd=".")
    
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0
    }

if __name__ == "__main__":
    # Allow direct execution for testing
    pytest.main([__file__, "-v"])