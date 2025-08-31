"""
Pre-computed Aggregation Cache for Ultra-Fast Lookups
Maintains running totals and category breakdowns for instant reporting
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

# Global aggregation cache
_AGGREGATION_CACHE = {}

class AggregationCache:
    """Lightning-fast pre-computed aggregations"""
    
    def __init__(self):
        self.cache_timeout_minutes = 15  # Refresh every 15 minutes
    
    def get_user_aggregations(self, user_id: str, days_window: int) -> Optional[Dict]:
        """Get pre-computed aggregations for user"""
        cache_key = f"{user_id}:{days_window}"
        
        if cache_key in _AGGREGATION_CACHE:
            cached_data = _AGGREGATION_CACHE[cache_key]
            
            # Check if cache is still fresh
            if cached_data["expires_at"] > datetime.now():
                logger.debug(f"Aggregation cache HIT for user {user_id[:8]}...")
                return cached_data["data"]
            else:
                # Expired
                del _AGGREGATION_CACHE[cache_key]
        
        return None
    
    def update_user_aggregations(self, user_id: str, days_window: int, expenses) -> Dict:
        """Compute and cache aggregations"""
        try:
            # Compute aggregations in single pass
            aggregations = self._compute_aggregations(expenses)
            
            # Cache with TTL
            cache_key = f"{user_id}:{days_window}"
            _AGGREGATION_CACHE[cache_key] = {
                "data": aggregations,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(minutes=self.cache_timeout_minutes)
            }
            
            logger.debug(f"Updated aggregation cache for user {user_id[:8]}...")
            return aggregations
            
        except Exception as e:
            logger.error(f"Aggregation computation failed: {e}")
            return self._empty_aggregations()
    
    def _compute_aggregations(self, expenses) -> Dict:
        """Lightning-fast aggregation computation"""
        if not expenses:
            return self._empty_aggregations()
        
        # Single-pass computation with minimal object creation
        total_amount = 0.0
        categories = defaultdict(float)  # More efficient than dict with checks
        
        for expense in expenses:
            amount = float(expense.amount)
            total_amount += amount
            cat = expense.category or "other"
            categories[cat] += amount
        
        # Find top category (optimized)
        if categories:
            top_category = max(categories.keys(), key=lambda k: categories[k])
            top_amount = categories[top_category]
            top_percentage = int((top_amount / total_amount) * 100) if total_amount > 0 else 0
        else:
            top_category = "general"
            top_amount = 0.0
            top_percentage = 0
        
        return {
            "total_logs": len(expenses),
            "total_amount": total_amount,
            "categories": dict(categories),  # Convert back to regular dict
            "top_category": top_category,
            "top_amount": top_amount,
            "top_percentage": top_percentage
        }
    
    def _empty_aggregations(self) -> Dict:
        """Return empty aggregation structure"""
        return {
            "total_logs": 0,
            "total_amount": 0.0,
            "categories": {},
            "top_category": "general",
            "top_amount": 0.0,
            "top_percentage": 0
        }

# Global aggregation cache instance
aggregation_cache = AggregationCache()