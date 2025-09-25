"""
Input sanitization utilities for security hardening
Handles control characters, length limits, and XSS prevention
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict

# Control character patterns (C0 and C1 control blocks)
_CONTROL_CHARS = re.compile(r"[\x00-\x1F\x7F-\x9F]")

# Maximum input lengths for security
MAX_MESSAGE_LENGTH = 2000
MAX_FIELD_LENGTH = 500

class InputSanitizer:
    """Secure input sanitization with dual-view approach"""
    
    @staticmethod
    def sanitize_user_input(raw_input: str) -> dict[str, Any]:
        """
        Sanitize user input while preserving original for audit
        
        Args:
            raw_input: Original user input
            
        Returns:
            Dictionary with raw and sanitized versions
        """
        if not isinstance(raw_input, str):
            return {
                "raw": str(raw_input),
                "safe": "",
                "metadata": {
                    "original_type": type(raw_input).__name__,
                    "truncated": False,
                    "sanitized": True,
                    "security_flags": ["invalid_type"]
                }
            }
        
        security_flags = []
        
        # 1. Length validation and truncation
        truncated = False
        if len(raw_input) > MAX_MESSAGE_LENGTH:
            truncated = True
            security_flags.append("length_capped")
        
        # 2. Remove control characters (but preserve for audit)
        control_chars_found = bool(_CONTROL_CHARS.search(raw_input))
        if control_chars_found:
            security_flags.append("control_chars_removed")
        
        # 3. Create sanitized version
        safe_input = raw_input[:MAX_MESSAGE_LENGTH]  # Truncate first
        safe_input = _CONTROL_CHARS.sub("", safe_input)  # Remove control chars
        safe_input = safe_input.strip()  # Clean whitespace
        
        # 4. HTML escape for XSS prevention
        html_escaped = html.escape(safe_input)
        if html_escaped != safe_input:
            security_flags.append("html_escaped")
        
        return {
            "raw": raw_input,  # Keep original for audit trails
            "safe": html_escaped,  # Use for processing
            "metadata": {
                "original_length": len(raw_input),
                "final_length": len(html_escaped),
                "truncated": truncated,
                "sanitized": len(security_flags) > 0,
                "security_flags": security_flags
            }
        }
    
    @staticmethod
    def sanitize_field(value: str, field_name: str) -> dict[str, Any]:
        """
        Sanitize individual field values (shorter than messages)
        
        Args:
            value: Field value to sanitize
            field_name: Name of the field (for logging)
            
        Returns:
            Sanitized field data
        """
        if not isinstance(value, str):
            return {
                "raw": str(value),
                "safe": "",
                "field": field_name,
                "valid": False,
                "error": f"Invalid type: {type(value).__name__}"
            }
        
        security_flags = []
        
        # Length check
        if len(value) > MAX_FIELD_LENGTH:
            security_flags.append("field_length_capped")
        
        # Control character check
        if _CONTROL_CHARS.search(value):
            security_flags.append("field_control_chars")
        
        # Sanitize
        safe_value = value[:MAX_FIELD_LENGTH]
        safe_value = _CONTROL_CHARS.sub("", safe_value)
        safe_value = html.escape(safe_value.strip())
        
        return {
            "raw": value,
            "safe": safe_value,
            "field": field_name,
            "valid": len(safe_value) > 0,
            "security_flags": security_flags
        }
    
    @staticmethod
    def is_safe_for_processing(sanitized_data: dict[str, Any]) -> bool:
        """
        Check if sanitized data is safe for further processing
        
        Args:
            sanitized_data: Result from sanitize_user_input
            
        Returns:
            True if safe for processing
        """
        metadata = sanitized_data.get("metadata", {})
        safe_text = sanitized_data.get("safe", "")
        
        # Basic safety checks
        if not safe_text or len(safe_text.strip()) == 0:
            return False
        
        # Check for excessive security flags (might indicate attack)
        flags = metadata.get("security_flags", [])
        if len(flags) > 3:  # Too many security issues
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "javascript:",
            "data:",
            "vbscript:",
            "<script",
            "onerror=",
            "onload="
        ]
        
        safe_lower = safe_text.lower()
        for pattern in suspicious_patterns:
            if pattern in safe_lower:
                return False
        
        return True