"""
Phase 1 UAT: Text normalization and signal extraction
Tests the core data handling functionality without touching existing routing
"""
import pytest

from nlp.signals_extractor import extract_signals, parse_time_window
from utils.text_normalizer import normalize_for_processing


class TestTextNormalization:
    """Test text normalization functionality"""
    
    def test_unicode_normalization(self):
        """Test Unicode NFKC normalization"""
        # Test composed characters
        text = "café"  # é as separate e + accent
        normalized = normalize_for_processing(text)
        assert "café" in normalized.lower()
    
    def test_zero_width_removal(self):
        """Test zero-width character removal"""
        text = "anal\u200Bysis\u200D please"  # ZWSP and ZWJ
        normalized = normalize_for_processing(text)
        assert normalized == "analysis please"
    
    def test_case_folding(self):
        """Test international case folding"""
        text = "ANALYSIS বিশ্লেষণ"
        normalized = normalize_for_processing(text)
        assert "analysis" in normalized
        assert "বিশ্লেষণ" in normalized
    
    def test_whitespace_collapse(self):
        """Test whitespace normalization"""
        text = "analysis   \t\n  please"
        normalized = normalize_for_processing(text)
        assert normalized == "analysis please"

class TestSignalExtraction:
    """Test signal extraction for different patterns"""
    
    def test_english_analysis_explicit(self):
        """Test explicit English analysis requests"""
        signals = extract_signals("analysis please")
        assert signals["explicit_analysis_request"] is True
        assert signals["has_analysis_terms"] is True
        
        signals = extract_signals("spending summary")
        assert signals["explicit_analysis_request"] is True
    
    def test_bengali_analysis_explicit(self):
        """Test explicit Bengali analysis requests"""
        signals = extract_signals("বিশ্লেষণ দাও")
        assert signals["explicit_analysis_request"] is True
        assert signals["has_analysis_terms"] is True
        
        signals = extract_signals("খরচের রিপোর্ট")
        assert signals["explicit_analysis_request"] is True
    
    def test_mixed_language_analysis(self):
        """Test mixed English-Bengali analysis"""
        signals = extract_signals("আজকের analysis please")
        assert signals["has_time_window"] is True
        assert signals["explicit_analysis_request"] is True
    
    def test_money_detection_english(self):
        """Test money detection in English"""
        signals = extract_signals("lunch 500 taka")
        assert signals["has_money"] is True
        assert any("500" in mention for mention in signals["money_mentions"])
        
        signals = extract_signals("coffee ৳150")
        assert signals["has_money"] is True
    
    def test_money_detection_bengali(self):
        """Test money detection with Bengali currency"""
        signals = extract_signals("খাবারে ৳1,250.50 খরচ")
        assert signals["has_money"] is True
        assert any("1,250.50" in mention for mention in signals["money_mentions"])
    
    def test_coaching_patterns(self):
        """Test coaching intent detection"""
        signals = extract_signals("help me save money")
        assert signals["has_coaching_verbs"] is True
        
        signals = extract_signals("টাকা সেভ করবো কিভাবে")
        assert signals["has_coaching_verbs"] is True
    
    def test_faq_patterns(self):
        """Test FAQ intent detection"""
        signals = extract_signals("what can you do")
        assert signals["has_faq_terms"] is True
        
        signals = extract_signals("তুমি কী করতে পারো")
        assert signals["has_faq_terms"] is True
    
    def test_admin_commands(self):
        """Test admin command detection"""
        signals = extract_signals("/id")
        assert signals["is_admin"] is True
        
        signals = extract_signals("/debug")
        assert signals["is_admin"] is True

class TestTimeWindowParsing:
    """Test time window parsing functionality"""
    
    def test_today_parsing(self):
        """Test today window parsing"""
        window = parse_time_window("Asia/Dhaka", "today spending")
        assert window is not None
        assert window["description"] == "today"
        assert "from" in window and "to" in window
    
    def test_bengali_today(self):
        """Test Bengali today parsing"""
        window = parse_time_window("Asia/Dhaka", "আজ কত খরচ")
        assert window is not None
        assert window["description"] == "today"
    
    def test_this_month_parsing(self):
        """Test this month window parsing"""
        window = parse_time_window("Asia/Dhaka", "this month analysis")
        assert window is not None
        assert window["description"] == "this month"
    
    def test_iso_date_parsing(self):
        """Test ISO date parsing"""
        window = parse_time_window("Asia/Dhaka", "expenses on 2024-12-25")
        assert window is not None
        assert "2024-12-25" in window["from"]

class TestIntegrationScenarios:
    """Test realistic usage scenarios"""
    
    def test_complex_bilingual_expense(self):
        """Test complex bilingual expense message"""
        text = "আজ lunch এ ৳500 টাকা খরচ করেছি"
        signals = extract_signals(text)
        
        assert signals["has_money"] is True
        assert signals["has_time_window"] is True
        assert len(signals["money_mentions"]) > 0
        assert signals["window"]["description"] == "today"
    
    def test_analysis_with_time_window(self):
        """Test analysis request with time window"""
        text = "last week এর spending analysis দাও"
        signals = extract_signals(text)
        
        assert signals["explicit_analysis_request"] is True
        assert signals["has_time_window"] is True
        assert signals["window"]["description"] == "last week"
    
    def test_coaching_request_complex(self):
        """Test complex coaching request"""
        text = "help me reduce খরচ this month"
        signals = extract_signals(text)
        
        assert signals["has_coaching_verbs"] is True
        assert signals["has_time_window"] is True

def run_phase1_uat():
    """Run Phase 1 UAT and return results"""
    import subprocess
    import sys
    
    # Run the tests
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_phase1_signals.py", 
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