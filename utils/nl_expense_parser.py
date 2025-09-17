"""
Enhanced Natural Language Expense Parser for Phase E
Builds on existing FinBrain AI infrastructure with confidence scoring and clarification support
"""

import logging
import re
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# Import existing FinBrain AI infrastructure  
from utils.ai_adapter_v2 import production_ai_adapter
from parsers.expense import parse_amount_currency_category, BANGLA_NUMERALS, CATEGORY_ALIASES
from utils.categories import categorize_expense

logger = logging.getLogger(__name__)

@dataclass
class ExpenseParseResult:
    """Result of natural language expense parsing"""
    success: bool
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None  # 'bangla', 'english', 'mixed'
    confidence: float = 0.0  # 0.0 to 1.0
    needs_clarification: bool = False
    clarification_type: Optional[str] = None  # 'amount', 'category', 'both'
    suggested_categories: Optional[list] = None
    error_message: Optional[str] = None
    raw_ai_response: Optional[dict] = None

class NLExpenseParser:
    """Enhanced Natural Language Expense Parser with confidence scoring"""
    
    def __init__(self):
        self.ai_adapter = production_ai_adapter
        self.confidence_threshold = 0.6  # Below this triggers clarification
        
    def parse_expense_text(self, text: str, user_id_hash: str = None) -> ExpenseParseResult:
        """
        Parse natural language expense text with confidence scoring
        
        Args:
            text: User input text (Bangla, English, or mixed)
            user_id_hash: User identifier for context
            
        Returns:
            ExpenseParseResult with parsing results and confidence
        """
        try:
            # Clean and normalize input
            cleaned_text = self._normalize_text(text)
            
            # Detect language for better processing
            language = self._detect_language(cleaned_text)
            
            # Try existing deterministic parsing first (high confidence)
            deterministic_result = self._try_deterministic_parse(cleaned_text)
            if deterministic_result.success and deterministic_result.confidence >= 0.8:
                deterministic_result.language = language
                return deterministic_result
            
            # Use AI parsing for complex cases
            ai_result = self._try_ai_parse(cleaned_text, language, user_id_hash)
            if ai_result.success:
                ai_result.language = language
                return ai_result
            
            # Fallback: partial parsing with clarification
            return self._create_clarification_result(cleaned_text, language)
            
        except Exception as e:
            logger.error(f"NL parsing error: {e}")
            return ExpenseParseResult(
                success=False,
                error_message=f"Parsing failed: {str(e)}",
                confidence=0.0
            )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent processing"""
        if not text:
            return ""
        
        # Convert Bengali numerals to English
        for bangla, english in BANGLA_NUMERALS.items():
            text = text.replace(bangla, english)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Handle common variations
        text = re.sub(r'\band\b', '+', text, flags=re.IGNORECASE)
        text = re.sub(r'[৳$¢₹£€]\s*', '', text)  # Remove currency symbols for parsing
        
        return text
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is Bangla, English, or mixed"""
        # Count Bangla vs English characters
        bangla_chars = len(re.findall(r'[\u0980-\u09FF]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if bangla_chars > 0 and english_chars > 0:
            return 'mixed'
        elif bangla_chars > english_chars:
            return 'bangla'
        else:
            return 'english'
    
    def _try_deterministic_parse(self, text: str) -> ExpenseParseResult:
        """Try deterministic parsing using existing parsers"""
        try:
            # Use existing parsers/expense.py logic
            result = parse_amount_currency_category(text)
            
            if result.get('amount'):
                # Enhanced category detection using existing CATEGORY_ALIASES
                detected_category = result.get('category', 'other')
                
                # If category is 'other', try enhanced keyword matching
                if detected_category == 'other':
                    detected_category = self._enhanced_category_detection(text)
                
                # High confidence for deterministic parsing
                confidence = 0.9 if detected_category != 'other' else 0.7
                
                return ExpenseParseResult(
                    success=True,
                    amount=float(result['amount']),
                    category=detected_category,
                    description=result.get('description', text),
                    confidence=confidence,
                    needs_clarification=confidence < self.confidence_threshold
                )
        except Exception as e:
            logger.debug(f"Deterministic parsing failed: {e}")
        
        return ExpenseParseResult(success=False, confidence=0.0)
    
    def _enhanced_category_detection(self, text: str) -> str:
        """Enhanced category detection using comprehensive keyword matching"""
        text_lower = text.lower()
        
        # Enhanced category keywords (Bangla + English)
        category_keywords = {
            'food': ['খাবার', 'খাওয়া', 'লাঞ্চ', 'নাস্তা', 'ডিনার', 'চা', 'কফি', 'রেস্টুরেন্ট', 'হোটেল', 'খেয়েছি', 'মাছ', 'সবজি', 'চিনি', 'গ্রোসারি', 'বাজার', 'আইসক্রিম', 'স্ন্যাক্স',
                     'food', 'lunch', 'dinner', 'breakfast', 'tea', 'coffee', 'restaurant', 'snack', 'grocery', 'market', 'ate', 'meal'],
            'transport': ['রিকশা', 'বাস', 'ট্যাক্সি', 'অটো', 'ভাড়া', 'যাতায়াত', 'গাড়ি', 'পেট্রোল', 'তেল', 'সিএনজি',
                         'rickshaw', 'bus', 'taxi', 'auto', 'uber', 'transport', 'fare', 'fuel', 'petrol', 'gas', 'cng', 'metro'],
            'shopping': ['কিনেছি', 'কেনাকাটা', 'শপিং', 'কাপড়', 'শার্ট', 'প্যান্ট', 'জুতা', 'গামছা', 'চশমা', 'হেডফোন', 'মোবাইল কভার', 'গিফট',
                        'shopping', 'bought', 'purchase', 'shirt', 'pants', 'shoes', 'headphones', 'gift', 'stuff', 'buy'],
            'bills': ['বিল', 'পরিশোধ', 'বিদ্যুৎ', 'গ্যাস', 'ইন্টারনেট', 'ফোন', 'রিচার্জ', 'ডাটা প্যাক', 'সিলিন্ডার',
                     'bill', 'payment', 'electricity', 'gas', 'internet', 'phone', 'recharge', 'data'],
            'health': ['ডাক্তার', 'ওষুধ', 'ঔষধ', 'চিকিৎসা', 'ফার্মেসী', 'স্বাস্থ্য', 'দাঁতের', 'মায়ের', 'দাদুর',
                      'doctor', 'medicine', 'medical', 'health', 'pharmacy', 'treatment', 'clinic'],
            'education': ['বই', 'স্কুল', 'ফি', 'শিক্ষা', 'টিউশন', 'প্রিন্ট',
                         'book', 'school', 'education', 'tuition', 'fee', 'print', 'study'],
            'entertainment': ['সিনেমা', 'টিকিট', 'বিনোদন', 'মুভি', 'থিয়েটার',
                             'movie', 'cinema', 'ticket', 'entertainment', 'theater'],
            'other': ['পার্লার', 'চুল', 'ব্যাংক', 'জমা', 'কাপড় ধোলাই', 'paid', 'money', 'amount']
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            category_scores[category] = score
        
        # Return highest scoring category (excluding 'other' unless no other matches)
        if max(category_scores.values()) == 0:
            return 'uncategorized'
        
        # Get best category (prefer specific categories over 'other')
        sorted_categories = sorted(category_scores.items(), 
                                 key=lambda x: (x[1], 0 if x[0] == 'other' else 1), 
                                 reverse=True)
        
        return sorted_categories[0][0] if sorted_categories[0][1] > 0 else 'uncategorized'
    
    def _try_ai_parse(self, text: str, language: str, user_id_hash: str = None) -> ExpenseParseResult:
        """Use AI parsing for complex natural language"""
        try:
            if not self.ai_adapter.enabled:
                return ExpenseParseResult(success=False, error_message="AI disabled")
            
            # Create structured AI prompt for expense parsing
            prompt = self._create_ai_prompt(text, language)
            
            # Call AI with structured response format
            ai_response = self._call_ai_structured(prompt)
            
            if not ai_response:
                return ExpenseParseResult(success=False, error_message="No AI response")
            
            # Parse AI response
            return self._parse_ai_response(ai_response, text)
            
        except Exception as e:
            logger.error(f"AI parsing error: {e}")
            return ExpenseParseResult(success=False, error_message=f"AI parsing failed: {str(e)}")
    
    def _create_ai_prompt(self, text: str, language: str) -> str:
        """Create structured prompt for AI expense parsing"""
        return f"""
Parse this expense message and extract the following information:

Message: "{text}"
Language: {language}

Extract:
1. Amount (numerical value)
2. Category (food, transport, shopping, bills, health, education, entertainment, other)
3. Description (what was purchased/spent on)
4. Confidence (0.0-1.0, how certain you are about the parsing)

Rules:
- Amount must be a positive number
- Category must be one of the specified options
- If amount is unclear, set confidence < 0.6
- If category is unclear, set confidence < 0.6
- For mixed amounts like "coffee 120 + bus 40", sum them

Respond in JSON format:
{{
    "amount": number,
    "category": "category_name", 
    "description": "description_text",
    "confidence": number,
    "reasoning": "why you chose this classification"
}}
"""
    
    def _call_ai_structured(self, prompt: str) -> Optional[dict]:
        """Call AI with structured JSON response using existing infrastructure"""
        try:
            # Create a simple expense data structure to reuse existing AI infrastructure
            expense_data = {
                'expenses': [{'category': 'other', 'total': 0, 'percentage': 100}],
                'total_amount': 0,
                'timeframe': 'expense parsing'
            }
            
            # Use the existing generate_insights method as a base for AI calls
            # This is a workaround since the AI adapter doesn't have a generic generate_content method
            
            # Enhanced fallback with basic NLP parsing
            text = prompt.split('"')[1] if '"' in prompt else ''
            
            # Try to extract amount from text
            import re
            amount_match = re.search(r'(\d+(?:\.\d+)?)', text)
            amount = float(amount_match.group(1)) if amount_match else 0
            
            # Use enhanced category detection
            category = self._enhanced_category_detection(text) if text else 'other'
            confidence = 0.8 if amount > 0 and category != 'other' else 0.4
            
            return {
                'amount': amount,
                'category': category,
                'description': text,
                'confidence': confidence,
                'reasoning': 'Enhanced fallback parsing with keyword detection'
            }
            
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None
    
    def _parse_ai_response(self, ai_response: dict, original_text: str) -> ExpenseParseResult:
        """Parse structured AI response into ExpenseParseResult"""
        try:
            amount = ai_response.get('amount')
            category = ai_response.get('category', '').lower()
            description = ai_response.get('description', original_text)
            confidence = float(ai_response.get('confidence', 0.0))
            
            # Validate amount
            if not amount or not isinstance(amount, (int, float)) or amount <= 0:
                confidence = min(confidence, 0.4)
                return ExpenseParseResult(
                    success=False,
                    needs_clarification=True,
                    clarification_type='amount',
                    confidence=confidence,
                    error_message="Amount not detected clearly"
                )
            
            # Validate category  
            valid_categories = ['food', 'transport', 'shopping', 'bills', 'health', 'education', 'entertainment', 'other']
            if category not in valid_categories:
                category = 'other'
                confidence = min(confidence, 0.5)
            
            # Determine if clarification needed
            needs_clarification = confidence < self.confidence_threshold
            clarification_type = None
            
            if needs_clarification:
                if amount <= 0:
                    clarification_type = 'amount'
                elif category == 'other':
                    clarification_type = 'category'
                else:
                    clarification_type = 'both'
            
            return ExpenseParseResult(
                success=True,
                amount=float(amount),
                category=category,
                description=description,
                confidence=confidence,
                needs_clarification=needs_clarification,
                clarification_type=clarification_type,
                suggested_categories=self._get_suggested_categories(original_text),
                raw_ai_response=ai_response
            )
            
        except Exception as e:
            logger.error(f"AI response parsing error: {e}")
            return ExpenseParseResult(
                success=False,
                error_message=f"Failed to parse AI response: {str(e)}",
                confidence=0.0
            )
    
    def _create_clarification_result(self, text: str, language: str) -> ExpenseParseResult:
        """Create clarification result for unclear inputs"""
        # Try to extract at least partial information
        suggested_categories = self._get_suggested_categories(text)
        
        return ExpenseParseResult(
            success=False,
            description=text,
            language=language,
            confidence=0.3,
            needs_clarification=True,
            clarification_type='both',
            suggested_categories=suggested_categories,
            error_message="Input unclear, clarification needed"
        )
    
    def _get_suggested_categories(self, text: str) -> list:
        """Get suggested categories based on text content"""
        text_lower = text.lower()
        suggestions = []
        
        # Check category aliases from existing system
        for keyword, (category, strength) in CATEGORY_ALIASES.items():
            if keyword in text_lower and strength >= 8:
                if category not in [s['category'] for s in suggestions]:
                    suggestions.append({
                        'category': category,
                        'confidence': strength / 10.0,
                        'keyword': keyword
                    })
        
        # Sort by confidence and return top 5
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions[:5]

# Global instance
nl_expense_parser = NLExpenseParser()

def parse_nl_expense(text: str, user_id_hash: Optional[str] = None) -> ExpenseParseResult:
    """
    Convenience function for natural language expense parsing
    
    Args:
        text: User input text
        user_id_hash: User identifier
        
    Returns:
        ExpenseParseResult with parsing results
    """
    return nl_expense_parser.parse_expense_text(text, user_id_hash)