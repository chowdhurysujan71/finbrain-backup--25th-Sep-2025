"""
Phase 2 UAT: Input sanitization and security hardening
Tests security features without affecting routing system
"""
import pytest
from utils.input_sanitizer import InputSanitizer

class TestInputSanitization:
    """Test input sanitization functionality"""
    
    def test_normal_text_passthrough(self):
        """Test that normal text passes through unchanged"""
        result = InputSanitizer.sanitize_user_input("lunch 500 taka")
        assert result["safe"] == "lunch 500 taka"
        assert result["raw"] == "lunch 500 taka"
        assert not result["metadata"]["sanitized"]
    
    def test_control_character_removal(self):
        """Test control character removal"""
        # Text with various control characters
        text_with_controls = "lunch\x00\x1F 500\x7F taka\x9F"
        result = InputSanitizer.sanitize_user_input(text_with_controls)
        
        assert result["safe"] == "lunch 500 taka"
        assert "control_chars_removed" in result["metadata"]["security_flags"]
        assert result["metadata"]["sanitized"]
    
    def test_length_truncation(self):
        """Test length limit enforcement"""
        long_text = "a" * 2500  # Exceeds MAX_MESSAGE_LENGTH (2000)
        result = InputSanitizer.sanitize_user_input(long_text)
        
        assert len(result["safe"]) <= 2000
        assert result["metadata"]["truncated"]
        assert "length_capped" in result["metadata"]["security_flags"]
    
    def test_html_escape(self):
        """Test HTML entity escaping"""
        html_text = "Price: <script>alert('xss')</script> 500 taka"
        result = InputSanitizer.sanitize_user_input(html_text)
        
        assert "&lt;script&gt;" in result["safe"]
        assert "&lt;/script&gt;" in result["safe"]
        assert "html_escaped" in result["metadata"]["security_flags"]
    
    def test_bengali_text_preservation(self):
        """Test that Bengali text is preserved during sanitization"""
        bengali_text = "খাবারে ৳১,২৫০.৫০ খরচ"
        result = InputSanitizer.sanitize_user_input(bengali_text)
        
        assert result["safe"] == bengali_text
        assert result["raw"] == bengali_text
        # Should not trigger security flags for normal Bengali
        assert len(result["metadata"]["security_flags"]) == 0
    
    def test_mixed_language_security(self):
        """Test security with mixed language content"""
        mixed_text = "analysis <script>alert('hack')</script> বিশ্লেষণ"
        result = InputSanitizer.sanitize_user_input(mixed_text)
        
        assert "&lt;script&gt;" in result["safe"]
        assert "বিশ্লেষণ" in result["safe"]  # Bengali preserved
        assert "html_escaped" in result["metadata"]["security_flags"]

class TestFieldSanitization:
    """Test field-level sanitization"""
    
    def test_valid_field_sanitization(self):
        """Test normal field sanitization"""
        result = InputSanitizer.sanitize_field("user123", "user_id")
        
        assert result["safe"] == "user123"
        assert result["valid"]
        assert result["field"] == "user_id"
    
    def test_field_length_limits(self):
        """Test field length enforcement"""
        long_field = "x" * 600  # Exceeds MAX_FIELD_LENGTH (500)
        result = InputSanitizer.sanitize_field(long_field, "description")
        
        assert len(result["safe"]) <= 500
        assert "field_length_capped" in result["security_flags"]
    
    def test_invalid_field_type(self):
        """Test handling of non-string field values"""
        result = InputSanitizer.sanitize_field(12345, "amount")
        
        assert not result["valid"]
        assert "Invalid type" in result["error"]

class TestSafetyValidation:
    """Test safety validation logic"""
    
    def test_safe_content_approval(self):
        """Test that safe content is approved"""
        safe_data = InputSanitizer.sanitize_user_input("analysis please")
        assert InputSanitizer.is_safe_for_processing(safe_data)
    
    def test_empty_content_rejection(self):
        """Test that empty content is rejected"""
        empty_data = {"safe": "", "metadata": {"security_flags": []}}
        assert not InputSanitizer.is_safe_for_processing(empty_data)
    
    def test_suspicious_pattern_rejection(self):
        """Test that suspicious patterns are rejected"""
        suspicious_data = InputSanitizer.sanitize_user_input("javascript:alert('xss')")
        assert not InputSanitizer.is_safe_for_processing(suspicious_data)
    
    def test_excessive_flags_rejection(self):
        """Test that content with too many security flags is rejected"""
        bad_data = {
            "safe": "some text",
            "metadata": {
                "security_flags": ["flag1", "flag2", "flag3", "flag4", "flag5"]
            }
        }
        assert not InputSanitizer.is_safe_for_processing(bad_data)

class TestSecurityIntegration:
    """Test security integration scenarios"""
    
    def test_expense_message_security(self):
        """Test security for typical expense messages"""
        expense_msg = "lunch ৳500 at <restaurant>name</restaurant>"
        result = InputSanitizer.sanitize_user_input(expense_msg)
        
        assert "&lt;restaurant&gt;" in result["safe"]
        assert "৳500" in result["safe"]  # Bengali currency preserved
        assert InputSanitizer.is_safe_for_processing(result)
    
    def test_analysis_request_security(self):
        """Test security for analysis requests"""
        analysis_msg = "spending analysis <img src=x onerror=alert(1)>"
        result = InputSanitizer.sanitize_user_input(analysis_msg)
        
        assert "&lt;img" in result["safe"]
        assert "spending analysis" in result["safe"]
        # Should be rejected due to suspicious pattern
        assert not InputSanitizer.is_safe_for_processing(result)
    
    def test_coaching_request_security(self):
        """Test security for coaching requests"""
        coaching_msg = "help me save money <script>steal_data()</script>"
        result = InputSanitizer.sanitize_user_input(coaching_msg)
        
        assert "&lt;script&gt;" in result["safe"]
        assert "help me save money" in result["safe"]
        assert not InputSanitizer.is_safe_for_processing(result)
    
    def test_bengali_expense_security(self):
        """Test security for Bengali expense messages"""
        bengali_msg = "আজ চা ৫০ টাকা খরচ করেছি"
        result = InputSanitizer.sanitize_user_input(bengali_msg)
        
        assert result["safe"] == bengali_msg  # No changes needed
        assert InputSanitizer.is_safe_for_processing(result)
        assert len(result["metadata"]["security_flags"]) == 0

def run_phase2_uat():
    """Run Phase 2 UAT and return results"""
    import sys
    import subprocess
    
    # Run the tests
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_phase2_security.py", 
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