"""
Enhanced AI-powered expense parser that handles multi-item messages
Evolves the system to parse complex expense entries like:
"coffee 100, burger 300 and watermelon juice 300"
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class AIExpenseParser:
    """AI-powered expense parser that handles complex multi-item messages"""
    
    def __init__(self):
        self.logger = logger
        
    def parse_message(self, text: str) -> Dict[str, Any]:
        """
        Parse user message for expenses using enhanced regex and AI
        
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
            if regex_result["success"] and regex_result["item_count"] > 0:
                return regex_result
            
            # Fallback to single expense parsing
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
    
    def _try_regex_multi_parse(self, text: str) -> Dict[str, Any]:
        """Try regex-based parsing for multi-item messages"""
        try:
            # Replace "and" with comma for uniform splitting
            normalized_text = re.sub(r'\s+and\s+', ', ', text.lower())
            
            # Split on commas to get individual items
            parts = [part.strip() for part in normalized_text.split(',')]
            
            # Only proceed if we have multiple parts
            if len(parts) < 2:
                return {"success": False, "expenses": [], "item_count": 0, "total_amount": 0, "intent": "other", "confidence": 0, "original_text": text}
            
            expenses = []
            
            # Patterns to match: item amount OR amount item
            patterns = [
                r'(\w+(?:\s+\w+)*)\s+(\d+(?:\.\d{2})?)',  # item amount (coffee 100)
                r'(\d+(?:\.\d{2})?)\s+(\w+(?:\s+\w+)*)',  # amount item (100 coffee)
            ]
            
            for part in parts:
                if not part.strip():
                    continue
                    
                # Try to extract amount and description from each part
                found_expense = False
                for pattern in patterns:
                    matches = re.findall(pattern, part)
                    if matches:
                        for match in matches:
                            if pattern.startswith(r'(\w+'):  # item amount format
                                description, amount_str = match
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
                                found_expense = True
                                break
                            except ValueError:
                                continue
                        if found_expense:
                            break
            
            if len(expenses) >= 1:  # At least one expense found
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
        
        food_keywords = ['coffee', 'burger', 'juice', 'lunch', 'dinner', 'food', 'breakfast', 'snack', 'drink', 'watermelon']
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
    
    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        """Basic fallback parsing when regex fails"""
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

# Global instance
ai_expense_parser = AIExpenseParser()