"""
Enhanced AI-powered expense parser that handles multi-item messages
Evolves the system to parse complex expense entries like:
"coffee 100, burger 300 and watermelon juice 300"
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from ai_adapter_gemini import generate_with_schema

logger = logging.getLogger(__name__)

# Enhanced parsing schema for multi-item expenses
EXPENSE_PARSING_SCHEMA = {
    "type": "object",
    "properties": {
        "expenses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["amount", "description", "category"]
            }
        },
        "intent": {
            "type": "string",
            "enum": ["log_expenses", "summary", "help", "question", "other"]
        },
        "total_items": {"type": "number"},
        "parsing_confidence": {"type": "number"}
    },
    "required": ["expenses", "intent", "total_items"]
}

class AIExpenseParser:
    """AI-powered expense parser that handles complex multi-item messages"""
    
    def __init__(self):
        self.logger = logger
        
    def parse_message(self, text: str) -> Dict[str, Any]:
        """
        Parse user message for expenses using AI
        
        Returns:
        {
            "success": bool,
            "expenses": [{"amount": float, "description": str, "category": str}],
            "intent": str,
            "total_amount": float,
            "item_count": int,
            "confidence": float
        }
        """
        try:
            # Clean and prepare text
            cleaned_text = self._clean_text(text)
            
            # First try regex-based multi-item detection for reliable parsing
            regex_result = self._try_regex_multi_parse(cleaned_text)
            if regex_result["success"] and regex_result["item_count"] > 1:
                return regex_result
            
            # Use AI to parse the message
            system_prompt = """You are an expert expense parser. Extract ALL expenses from user messages, especially comma-separated lists.

CRITICAL: Look for multiple expenses in a single message!

Parsing Rules:
1. Find ALL amounts and descriptions in the text
2. Handle comma-separated lists: "coffee 100, burger 300, juice 300" = 3 separate expenses
3. Handle "and" separators: "coffee 100 and burger 300" = 2 separate expenses  
4. Categories: food, transport, shopping, bills, entertainment, other
5. NEVER miss expenses in lists - parse each item separately

Key Examples:
- "coffee 100, burger 300 and watermelon juice 300" → THREE expenses:
  * 100.0 for coffee (food)
  * 300.0 for burger (food) 
  * 300.0 for watermelon juice (food)
- "taxi 120, coffee 80" → TWO expenses:
  * 120.0 for taxi (transport)
  * 80.0 for coffee (food)

IMPORTANT: When you see commas or "and" between items with amounts, treat each as a separate expense!"""

            ai_result = generate_with_schema(
                user_text=f"Extract ALL individual expenses from this message: {cleaned_text}\n\nRemember: comma-separated items are SEPARATE expenses!",
                system_prompt=system_prompt,
                response_schema=EXPENSE_PARSING_SCHEMA
            )
            
            if ai_result.get("ok") and "data" in ai_result:
                parsed_data = ai_result["data"]
                expenses = parsed_data.get("expenses", [])
                
                # Calculate totals
                total_amount = sum(exp.get("amount", 0) for exp in expenses)
                item_count = len(expenses)
                confidence = parsed_data.get("parsing_confidence", 0.8)
                
                return {
                    "success": True,
                    "expenses": expenses,
                    "intent": parsed_data.get("intent", "log_expenses"),
                    "total_amount": total_amount,
                    "item_count": item_count,
                    "confidence": confidence,
                    "original_text": text
                }
            else:
                # Fallback to basic parsing
                return self._fallback_parse(text)
                
        except Exception as e:
            self.logger.error(f"AI expense parsing error: {e}")
            return self._fallback_parse(text)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for parsing"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Handle common currency symbols
        text = re.sub(r'[৳$¢₹£€]', '', text)
        
        return text
    
    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        """Basic fallback parsing when AI fails"""
        try:
            # Simple regex patterns for single expenses
            patterns = [
                r'(?:log|spent|add)?\s*(\d+(?:\.\d{2})?)\s+(.+)',
                r'(.+?)\s+(\d+(?:\.\d{2})?)',
                r'(\d+(?:\.\d{2})?)\s+(.+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        if pattern.endswith(r'(.+)'):  # Amount first
                            amount = float(match.group(1))
                            description = match.group(2).strip()
                        else:  # Description first
                            amount = float(match.group(2))
                            description = match.group(1).strip()
                        
                        return {
                            "success": True,
                            "expenses": [{
                                "amount": amount,
                                "description": description,
                                "category": "other",
                                "confidence": 0.6
                            }],
                            "intent": "log_expenses",
                            "total_amount": amount,
                            "item_count": 1,
                            "confidence": 0.6,
                            "original_text": text
                        }
                    except ValueError:
                        continue
            
            # No valid expenses found
            return {
                "success": False,
                "expenses": [],
                "intent": "other",
                "total_amount": 0,
                "item_count": 0,
                "confidence": 0,
                "original_text": text
            }
            
        except Exception as e:
            self.logger.error(f"Fallback parsing error: {e}")
            return {
                "success": False,
                "expenses": [],
                "intent": "other", 
                "total_amount": 0,
                "item_count": 0,
                "confidence": 0,
                "original_text": text
            }
    
    def _try_regex_multi_parse(self, text: str) -> Dict[str, Any]:
        """Try regex-based parsing for multi-item messages"""
        try:
            # Look for comma or "and" separated expense patterns
            # Pattern: item amount, item amount and item amount
            patterns = [
                r'(\w+(?:\s+\w+)*)\s+(\d+(?:\.\d{2})?)',  # item amount
                r'(\d+(?:\.\d{2})?)\s+(\w+(?:\s+\w+)*)',  # amount item
            ]
            
            # Split on commas and "and" to find multiple items
            items = []
            
            # Replace "and" with comma for uniform splitting
            normalized_text = re.sub(r'\s+and\s+', ', ', text.lower())
            
            # Split on commas to get individual items
            parts = [part.strip() for part in normalized_text.split(',')]
            
            expenses = []
            
            for part in parts:
                if not part:
                    continue
                    
                # Try to extract amount and description from each part
                for pattern in patterns:
                    matches = re.findall(pattern, part)
                    if matches:
                        for match in matches:
                            if pattern.startswith(r'(\w+'):  # item amount format
                                description, amount_str = match
                                try:
                                    amount = float(amount_str)
                                    expenses.append({
                                        "amount": amount,
                                        "description": description.strip(),
                                        "category": self._categorize_simple(description),
                                        "confidence": 0.9
                                    })
                                except ValueError:
                                    continue
                            else:  # amount item format
                                amount_str, description = match
                                try:
                                    amount = float(amount_str)
                                    expenses.append({
                                        "amount": amount,
                                        "description": description.strip(),
                                        "category": self._categorize_simple(description),
                                        "confidence": 0.9
                                    })
                                except ValueError:
                                    continue
                        break  # Found matches with this pattern
            
            if len(expenses) >= 2:  # Multi-item detected
                total_amount = sum(exp["amount"] for exp in expenses)
                return {
                    "success": True,
                    "expenses": expenses,
                    "intent": "log_expenses",
                    "total_amount": total_amount,
                    "item_count": len(expenses),
                    "confidence": 0.9,
                    "original_text": text
                }
            else:
                return {"success": False, "expenses": [], "item_count": 0, "total_amount": 0, "intent": "other", "confidence": 0, "original_text": text}
                
        except Exception as e:
            self.logger.error(f"Regex multi-parse error: {e}")
            return {"success": False, "expenses": [], "item_count": 0, "total_amount": 0, "intent": "other", "confidence": 0, "original_text": text}
    
    def _categorize_simple(self, description: str) -> str:
        """Simple categorization for regex-parsed items"""
        desc_lower = description.lower()
        
        food_keywords = ['coffee', 'burger', 'juice', 'lunch', 'dinner', 'food', 'breakfast', 'snack', 'drink']
        transport_keywords = ['taxi', 'bus', 'uber', 'transport', 'fuel', 'gas']
        shopping_keywords = ['shopping', 'clothes', 'shirt', 'shoes']
        
        for keyword in food_keywords:
            if keyword in desc_lower:
                return 'food'
        
        for keyword in transport_keywords:
            if keyword in desc_lower:
                return 'transport'
        
        for keyword in shopping_keywords:
            if keyword in desc_lower:
                return 'shopping'
        
        return 'other'
            
        except Exception as e:
            self.logger.error(f"Fallback parsing error: {e}")
            return {
                "success": False,
                "expenses": [],
                "intent": "other", 
                "total_amount": 0,
                "item_count": 0,
                "confidence": 0,
                "original_text": text
            }

# Global instance
ai_expense_parser = AIExpenseParser()