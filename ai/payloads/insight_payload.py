"""
Insight Payload Builder: Structures data for AI insight generation
Ensures proper user isolation and handles no-data scenarios
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
import hashlib
from datetime import datetime


def build_insight_payload(user_id: str, expenses: List[Dict], total_amount: float, 
                         timeframe: str = "this month") -> Dict[str, Any]:
    """
    Build structured payload for AI insight generation
    
    Args:
        user_id: Isolated user identifier  
        expenses: List of expense dictionaries with category, total, percentage
        total_amount: Total expense amount for the timeframe
        timeframe: Time period being analyzed
        
    Returns:
        Structured payload with user isolation and insufficient_data flag
    """
    
    # Generate data version hash for caching
    expense_data = sorted([
        (exp.get('category', ''), float(exp.get('total', 0)))
        for exp in expenses
    ])
    data_version = hashlib.md5(str(expense_data + [total_amount, timeframe]).encode()).hexdigest()[:12]
    
    # Check for insufficient data
    insufficient_data = (
        total_amount == 0 or 
        len(expenses) == 0 or
        all(exp.get('total', 0) == 0 for exp in expenses)
    )
    
    payload = {
        "meta": {
            "user_id": user_id,
            "request_timestamp": datetime.now().isoformat(),
            "data_version": data_version,
            "insufficient_data": insufficient_data,
            "expense_count": len(expenses)
        },
        "data": {
            "total_amount": total_amount,
            "expenses": expenses,
            "timeframe": timeframe
        },
        "_echo": {
            "user_id": user_id  # For contamination detection
        }
    }
    
    return payload


def validate_insight_response(response: Dict[str, Any], expected_user_id: str) -> Dict[str, Any]:
    """
    Validate AI insight response for user isolation and schema compliance
    
    Args:
        response: AI response dictionary
        expected_user_id: Expected user ID for validation
        
    Returns:
        Validation result with pass/fail and issues
    """
    
    validation_result = {
        "valid": True,
        "issues": [],
        "contamination": False
    }
    
    # Check for _echo.user_id match
    echo_user_id = response.get("_echo", {}).get("user_id")
    if echo_user_id != expected_user_id:
        validation_result["valid"] = False
        validation_result["contamination"] = True
        validation_result["issues"].append(f"Echo user_id mismatch: expected {expected_user_id[:8]}..., got {echo_user_id}")
    
    # Check required fields
    required_fields = ["insights", "success"]
    for field in required_fields:
        if field not in response:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Missing required field: {field}")
    
    # Check insights structure
    insights = response.get("insights", [])
    if not isinstance(insights, list):
        validation_result["valid"] = False
        validation_result["issues"].append("Insights must be a list")
    
    return validation_result