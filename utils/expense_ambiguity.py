"""
FinBrain Expense Ambiguity Detection and Clarification System
Handles items like "mouse" that could be multiple categories (computer mouse vs food)
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Ambiguous items with their possible categories and confidence scores
AMBIGUOUS_ITEMS = {
    'mouse': {
        'electronics': {'keywords': ['wireless', 'gaming', 'optical', 'bluetooth', 'computer', 'usb'], 'base_confidence': 75},
        'food': {'keywords': ['chocolate', 'dessert', 'sweet', 'cafe', 'restaurant'], 'base_confidence': 15},
        'pet': {'keywords': ['pet', 'cage', 'toy', 'feeding'], 'base_confidence': 10}
    },
    'tablet': {
        'electronics': {'keywords': ['ipad', 'samsung', 'android', 'screen', 'wifi', 'storage'], 'base_confidence': 85},
        'health': {'keywords': ['medicine', 'pharmacy', 'prescription', 'mg', 'pill'], 'base_confidence': 15}
    },
    'apple': {
        'electronics': {'keywords': ['iphone', 'macbook', 'ipad', 'store', 'tech'], 'base_confidence': 70},
        'food': {'keywords': ['fruit', 'grocery', 'organic', 'fresh', 'market'], 'base_confidence': 30}
    },
    'berry': {
        'food': {'keywords': ['fruit', 'fresh', 'organic', 'grocery', 'smoothie'], 'base_confidence': 90},
        'electronics': {'keywords': ['blackberry', 'phone', 'device'], 'base_confidence': 10}
    },
    'charge': {
        'bills': {'keywords': ['fee', 'service', 'bank', 'account', 'monthly'], 'base_confidence': 60},
        'electronics': {'keywords': ['charger', 'cable', 'battery', 'phone', 'power'], 'base_confidence': 40}
    },
    'speaker': {
        'electronics': {'keywords': ['bluetooth', 'audio', 'sound', 'wireless', 'music'], 'base_confidence': 85},
        'entertainment': {'keywords': ['event', 'conference', 'talk', 'seminar'], 'base_confidence': 15}
    },
    'case': {
        'electronics': {'keywords': ['phone', 'laptop', 'protective', 'cover'], 'base_confidence': 60},
        'shopping': {'keywords': ['luggage', 'suitcase', 'travel'], 'base_confidence': 25},
        'food': {'keywords': ['beer', 'wine', 'bottle'], 'base_confidence': 15}
    }
}

# Price range hints for different categories (in BDT)
CATEGORY_PRICE_RANGES = {
    'electronics': {'min': 500, 'max': 50000, 'typical': 2000},
    'food': {'min': 10, 'max': 2000, 'typical': 200},
    'pet': {'min': 50, 'max': 5000, 'typical': 300},
    'health': {'min': 20, 'max': 1000, 'typical': 150},
    'bills': {'min': 100, 'max': 10000, 'typical': 1500},
    'entertainment': {'min': 200, 'max': 20000, 'typical': 1000},
    'shopping': {'min': 100, 'max': 20000, 'typical': 1500}
}

class AmbiguityDetector:
    """Detects when an expense item could belong to multiple categories"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.AmbiguityDetector")
    
    def detect_ambiguity(self, item_text: str, amount: float, context: str = "") -> Dict[str, Any]:
        """
        Detect if an item is ambiguous and return clarification options
        
        Args:
            item_text: The expense item (e.g., "mouse")
            amount: The expense amount (helps with categorization)
            context: Additional context from the original message
            
        Returns:
            Dict with ambiguity info and clarification options
        """
        item_clean = self._clean_item_text(item_text)
        
        # Check if this is a known ambiguous item
        if item_clean not in AMBIGUOUS_ITEMS:
            return {'is_ambiguous': False, 'item': item_clean}
        
        ambiguous_info = AMBIGUOUS_ITEMS[item_clean]
        
        # Calculate confidence scores for each possible category
        category_scores = self._calculate_category_scores(
            item_clean, amount, context, ambiguous_info
        )
        
        # Determine if clarification is needed
        needs_clarification = self._needs_clarification(category_scores)
        
        if not needs_clarification:
            # Clear winner - use the highest scoring category
            best_category = max(category_scores.items(), key=lambda x: x[1])
            return {
                'is_ambiguous': False,
                'item': item_clean,
                'auto_category': best_category[0],
                'confidence': best_category[1]
            }
        
        # Generate clarification options
        clarification_options = self._generate_clarification_options(
            item_clean, category_scores
        )
        
        return {
            'is_ambiguous': True,
            'item': item_clean,
            'clarification_needed': True,
            'options': clarification_options,
            'category_scores': category_scores
        }
    
    def _clean_item_text(self, text: str) -> str:
        """Clean and normalize item text for matching"""
        # Extract the main item word
        text = text.lower().strip()
        
        # Remove common expense words
        remove_words = ['spent', 'bought', 'paid', 'for', 'on', 'the', 'a', 'an']
        words = text.split()
        words = [w for w in words if w not in remove_words and not w.isdigit()]
        
        # Look for the main item (usually a noun)
        if words:
            # Return the first non-trivial word
            for word in words:
                if len(word) > 2:  # Skip very short words
                    return word
        
        return text
    
    def _calculate_category_scores(self, item: str, amount: float, context: str, 
                                 ambiguous_info: Dict) -> Dict[str, float]:
        """Calculate confidence scores for each possible category"""
        scores = {}
        context_lower = context.lower()
        
        for category, info in ambiguous_info.items():
            score = info['base_confidence']
            
            # Context keyword bonus
            keywords = info.get('keywords', [])
            for keyword in keywords:
                if keyword in context_lower:
                    score += 20  # Strong context boost
            
            # Price range bonus
            price_info = CATEGORY_PRICE_RANGES.get(category, {})
            if price_info:
                typical_price = price_info.get('typical', 1000)
                min_price = price_info.get('min', 0)
                max_price = price_info.get('max', 100000)
                
                if min_price <= amount <= max_price:
                    # Within range bonus
                    score += 15
                    
                    # Close to typical price bonus
                    if abs(amount - typical_price) / typical_price < 0.5:
                        score += 10
            
            scores[category] = min(score, 100)  # Cap at 100
        
        return scores
    
    def _needs_clarification(self, scores: Dict[str, float]) -> bool:
        """Determine if user clarification is needed"""
        if not scores:
            return False
        
        sorted_scores = sorted(scores.values(), reverse=True)
        
        # If top score is very high (>80), don't ask
        if sorted_scores[0] > 80:
            return False
        
        # If there's a clear winner with >30 point lead, don't ask
        if len(sorted_scores) > 1 and (sorted_scores[0] - sorted_scores[1]) > 30:
            return False
        
        # If top two scores are close, ask for clarification
        return True
    
    def _generate_clarification_options(self, item: str, scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """Generate user-friendly clarification options"""
        options = []
        
        # Sort categories by score
        sorted_categories = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Take top 3 most likely categories
        for category, score in sorted_categories[:3]:
            if score > 20:  # Only include reasonable options
                option = {
                    'category': category,
                    'display_name': self._get_friendly_category_name(category),
                    'example': self._get_category_example(item, category),
                    'confidence': score
                }
                options.append(option)
        
        # Add "something else" option
        options.append({
            'category': 'other',
            'display_name': 'Something else',
            'example': 'Let me specify',
            'confidence': 0
        })
        
        return options
    
    def _get_friendly_category_name(self, category: str) -> str:
        """Get user-friendly category name"""
        friendly_names = {
            'electronics': 'Electronics/Tech',
            'food': 'Food & Drinks',
            'pet': 'Pet Care',
            'health': 'Health/Medicine',
            'bills': 'Bills/Fees',
            'entertainment': 'Entertainment',
            'shopping': 'Shopping',
            'transport': 'Transportation',
            'other': 'Other'
        }
        return friendly_names.get(category, category.title())
    
    def _get_category_example(self, item: str, category: str) -> str:
        """Get example clarification for the category"""
        examples = {
            ('mouse', 'electronics'): 'Computer mouse',
            ('mouse', 'food'): 'Chocolate mousse/dessert',
            ('mouse', 'pet'): 'Pet mouse',
            ('tablet', 'electronics'): 'iPad/tablet device',
            ('tablet', 'health'): 'Medicine tablet',
            ('apple', 'electronics'): 'Apple device/store',
            ('apple', 'food'): 'Fresh fruit',
            ('case', 'electronics'): 'Phone/laptop case',
            ('case', 'shopping'): 'Luggage/suitcase',
            ('case', 'food'): 'Case of beverages'
        }
        
        return examples.get((item, category), f"{item.title()} ({category})")


# Initialize the global detector
ambiguity_detector = AmbiguityDetector()