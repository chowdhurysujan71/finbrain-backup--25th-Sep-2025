"""
AI adapter with "never empty" contract
Guarantees user-visible responses even during vendor failures
"""
from __future__ import annotations
import time
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AIContractResponse:
    """Guaranteed non-empty AI response with contract validation"""
    bullet_points: list[str]
    flags: Dict[str, bool]
    metadata: Dict[str, Any]
    
    def validate(self) -> bool:
        """Validate response meets contract"""
        return (
            isinstance(self.bullet_points, list) and
            len(self.bullet_points) > 0 and
            all(isinstance(bp, str) and len(bp.strip()) > 0 for bp in self.bullet_points) and
            isinstance(self.flags, dict) and
            isinstance(self.metadata, dict)
        )

class AIAdapterNeverEmpty:
    """AI adapter with hard guarantee of non-empty responses"""
    
    def __init__(self, stub_mode: bool = False):
        self.stub_mode = stub_mode
        self.fallback_cache = {}  # Simple in-memory stale cache
        
    def generate_insights_for_user(self, user_id: str, window: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate insights with hard contract: never empty response
        
        Returns:
            Dictionary with bullet_points and flags, guaranteed non-empty
        """
        data_version = payload.get("meta", {}).get("data_version", "none")
        
        try:
            # Primary: Try vendor AI (or stub)
            response = self._generate_with_resilience(payload, user_id, data_version)
            
            # Validate contract
            if self._validate_response(response):
                # Cache successful response for stale fallback
                self._cache_response(user_id, response)
                return response
            
            logger.warning(f"AI response failed validation for user {user_id}")
            
        except Exception as e:
            logger.error(f"AI generation failed for user {user_id}: {e}")
        
        # Fallback 1: Use stale cached response
        if user_id in self.fallback_cache:
            stale_response = self.fallback_cache[user_id].copy()
            stale_response["metadata"]["source"] = "stale_cache"
            logger.info(f"Using stale cache for user {user_id}")
            return stale_response
        
        # Fallback 2: Generate deterministic minimal response
        minimal_response = self._generate_minimal_safe_response(payload)
        logger.info(f"Using minimal safe response for user {user_id}")
        return minimal_response
    
    def _generate_with_resilience(self, payload: Dict[str, Any], user_id: str, data_version: str) -> Dict[str, Any]:
        """Generate response with vendor AI or stub"""
        
        if self.stub_mode:
            return self._generate_stub_response(payload)
        
        # In production, this would call actual AI vendors
        # For now, return deterministic response based on payload
        return self._generate_deterministic_response(payload)
    
    def _generate_stub_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate stub response for CI/testing"""
        totals = payload.get("totals", {})
        grand_total = totals.get("grand_total", 0)
        
        if grand_total == 0:
            return {
                "bullet_points": ["Not enough data to analyze yet."],
                "flags": {"insufficient_data": True},
                "metadata": {"source": "stub", "confidence": 1.0}
            }
        
        return {
            "bullet_points": [
                f"Total spending tracked: ৳{grand_total:,.0f}",
                "Consistent tracking helps identify patterns",
                "Keep logging expenses for better insights"
            ],
            "flags": {"insufficient_data": False},
            "metadata": {"source": "stub", "confidence": 1.0}
        }
    
    def _generate_deterministic_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate deterministic response based on payload data"""
        totals = payload.get("totals", {})
        grand_total = totals.get("grand_total", 0)
        meta = payload.get("meta", {})
        
        # Handle insufficient data case
        if grand_total == 0 or meta.get("insufficient_data", False):
            return {
                "bullet_points": ["Not enough data to analyze yet."],
                "flags": {"insufficient_data": True},
                "metadata": {"source": "deterministic", "confidence": 0.9}
            }
        
        # Generate insights based on spending patterns
        bullet_points = []
        
        if grand_total > 50000:  # > 50k BDT
            bullet_points.append(f"High spending period: ৳{grand_total:,.0f} total")
            bullet_points.append("Consider reviewing large expense categories")
        elif grand_total > 20000:  # 20k-50k BDT
            bullet_points.append(f"Moderate spending: ৳{grand_total:,.0f} tracked")
            bullet_points.append("Good expense tracking consistency")
        else:
            bullet_points.append(f"Light spending period: ৳{grand_total:,.0f}")
            bullet_points.append("Excellent budget control")
        
        # Add category-specific insights if available
        food_total = totals.get("food", 0)
        transport_total = totals.get("transport", 0)
        
        if food_total > grand_total * 0.4:
            bullet_points.append("Food expenses are significant - consider meal planning")
        elif transport_total > grand_total * 0.3:
            bullet_points.append("Transport costs are notable - explore alternatives")
        else:
            bullet_points.append("Spending distribution looks balanced")
        
        return {
            "bullet_points": bullet_points,
            "flags": {"insufficient_data": False},
            "metadata": {"source": "deterministic", "confidence": 0.85}
        }
    
    def _generate_minimal_safe_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Last resort: minimal safe response that always works"""
        return {
            "bullet_points": ["Expense tracking is active and working properly."],
            "flags": {"insufficient_data": True},
            "metadata": {"source": "minimal_safe", "confidence": 0.7}
        }
    
    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """Validate response meets the never-empty contract"""
        try:
            bullet_points = response.get("bullet_points", [])
            flags = response.get("flags", {})
            
            # Must have non-empty bullet points
            if not isinstance(bullet_points, list) or len(bullet_points) == 0:
                return False
            
            # All bullet points must be non-empty strings
            for bp in bullet_points:
                if not isinstance(bp, str) or len(bp.strip()) == 0:
                    return False
            
            # Must have flags dict
            if not isinstance(flags, dict):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Response validation error: {e}")
            return False
    
    def _cache_response(self, user_id: str, response: Dict[str, Any]):
        """Cache successful response for stale fallback"""
        # Simple in-memory cache (in production, use Redis)
        self.fallback_cache[user_id] = response.copy()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get adapter health status"""
        return {
            "mode": "stub" if self.stub_mode else "production",
            "cached_users": len(self.fallback_cache),
            "contract_guarantee": "never_empty",
            "last_check": time.time()
        }