#!/usr/bin/env python3
"""
Debug analysis terms detection
"""

from app import app


def debug_analysis_terms():
    with app.app_context():
        from utils.routing_policy import BilingualPatterns
        
        patterns = BilingualPatterns()
        
        # Test the problematic Bengali message
        bengali_message = "আজ চা ৫০ টাকা খরচ করেছি"
        
        print(f"Testing message: {bengali_message}")
        print(f"has_time_window: {patterns.has_time_window(bengali_message)}")
        print(f"has_analysis_terms: {patterns.has_analysis_terms(bengali_message)}")
        print(f"has_explicit_analysis_request: {patterns.has_explicit_analysis_request(bengali_message)}")
        
        # Test individual pattern matches
        print("\nTesting individual patterns:")
        print(f"time_window_en match: {patterns.time_window_en.search(bengali_message)}")
        print(f"time_window_bn match: {patterns.time_window_bn.search(bengali_message)}")
        print(f"analysis_terms_en match: {patterns.analysis_terms_en.search(bengali_message)}")
        print(f"analysis_terms_bn match: {patterns.analysis_terms_bn.search(bengali_message)}")

if __name__ == "__main__":
    debug_analysis_terms()