#!/usr/bin/env python3
"""
AI Adapter Smoke Test for FinBrain Diagnostic
Tests AI parsing capabilities without external API calls if keys missing
"""
import json
import sys
import os
from datetime import datetime

def test_ai_adapter():
    """Test AI adapter with realistic expense parsing scenarios"""
    
    try:
        # Import the production AI adapter
        sys.path.append('/home/runner/workspace')
        from utils.ai_adapter_v2 import ProductionAIAdapter
        
        adapter = ProductionAIAdapter()
        
        # Test scenarios
        test_cases = [
            {
                "name": "simple_expense",
                "input": "bought coffee for 150 taka",
                "expected_items": 1
            },
            {
                "name": "ambiguous_sentence", 
                "input": "had a good day today",
                "expected_items": 0
            },
            {
                "name": "multi_expense",
                "input": "lunch 200 taka and uber 100 and shopping for shoes 1500",
                "expected_items": 3
            }
        ]
        
        results = []
        
        for test_case in test_cases:
            print(f"Testing: {test_case['name']}")
            
            try:
                # Try dry-run mode if available, otherwise skip if no API key
                result = adapter.parse_expense_message(
                    test_case["input"], 
                    user_hash="test_user_hash"
                )
                
                # Validate result structure
                success = True
                error_msg = None
                
                if not isinstance(result, dict):
                    success = False
                    error_msg = f"Expected dict, got {type(result)}"
                elif 'expenses' not in result:
                    success = False
                    error_msg = "Missing 'expenses' key in result"
                elif not isinstance(result['expenses'], list):
                    success = False
                    error_msg = "Expenses should be a list"
                
                results.append({
                    "test": test_case['name'],
                    "input": test_case['input'],
                    "success": success,
                    "error": error_msg,
                    "expense_count": len(result.get('expenses', [])) if success else 0,
                    "result": result if success else str(result)
                })
                
            except Exception as e:
                results.append({
                    "test": test_case['name'],
                    "input": test_case['input'],
                    "success": False,
                    "error": str(e),
                    "expense_count": 0,
                    "result": None
                })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "adapter_info": {
                "class": "ProductionAIAdapter",
                "provider": getattr(adapter, 'provider', 'unknown'),
                "enabled": getattr(adapter, 'enabled', False)
            },
            "tests": results,
            "summary": {
                "total_tests": len(results),
                "passed": sum(1 for r in results if r['success']),
                "failed": sum(1 for r in results if not r['success'])
            }
        }
        
    except Exception as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "error": f"Failed to import or initialize AI adapter: {e}",
            "tests": [],
            "summary": {"total_tests": 0, "passed": 0, "failed": 0}
        }

if __name__ == "__main__":
    result = test_ai_adapter()
    print(json.dumps(result, indent=2))