"""
Read-time Precedence Engine for PCA Overlay System
Implements deterministic resolution order for user-specific views
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
import json

logger = logging.getLogger("finbrain.precedence")

@dataclass
class PrecedenceResult:
    """Result of precedence resolution"""
    category: str
    subcategory: Optional[str]
    amount: float
    merchant_text: Optional[str]
    source: str  # 'correction', 'rule', 'effective', 'raw'
    applied_rule_id: Optional[int] = None
    correction_id: Optional[int] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category,
            'subcategory': self.subcategory,
            'amount': self.amount,
            'merchant_text': self.merchant_text,
            'source': self.source,
            'applied_rule_id': self.applied_rule_id,
            'correction_id': self.correction_id,
            'confidence': self.confidence
        }

class PrecedenceEngine:
    """
    Deterministic precedence resolution for overlay data
    Order: UserCorrection > UserRule > TransactionEffective > Raw
    """
    
    def __init__(self):
        self.cache = {}  # Simple request-level cache
        
    def get_effective_view(self, user_id: str, tx_id: str, 
                          raw_expense: Optional[Dict] = None) -> PrecedenceResult:
        """
        Get the effective view of a transaction for a specific user
        
        Args:
            user_id: SHA-256 hashed user identifier
            tx_id: Canonical transaction ID
            raw_expense: Optional raw expense data (for fallback)
            
        Returns:
            PrecedenceResult with resolved values
        """
        cache_key = f"{user_id}:{tx_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        try:
            # Check if overlay is enabled
            import os
            overlay_enabled = os.environ.get('PCA_OVERLAY_ENABLED', 'false').lower() == 'true'
            if not overlay_enabled:
                return self._raw_fallback(raw_expense)
                
            # 1. Check for user corrections (highest priority)
            correction = self._get_latest_correction(user_id, tx_id)
            if correction:
                result = self._apply_correction(correction, raw_expense)
                self.cache[cache_key] = result
                return result
                
            # 2. Check for matching user rules
            matching_rule = self._get_matching_rule(user_id, raw_expense)
            if matching_rule:
                result = self._apply_rule(matching_rule, raw_expense)
                self.cache[cache_key] = result
                return result
                
            # 3. Check transaction effective table
            effective = self._get_transaction_effective(user_id, tx_id)
            if effective:
                result = self._from_effective(effective)
                self.cache[cache_key] = result
                return result
                
            # 4. Fall back to raw data
            result = self._raw_fallback(raw_expense)
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"Precedence resolution failed: {e}")
            return self._raw_fallback(raw_expense)
    
    def _get_latest_correction(self, user_id: str, tx_id: str) -> Optional[Dict]:
        """Get the most recent user correction for a transaction"""
        try:
            from db_base import db
            from models_pca import UserCorrection
            
            correction = db.session.query(UserCorrection).filter_by(
                user_id=user_id,
                tx_id=tx_id
            ).order_by(UserCorrection.created_at.desc()).first()
            
            if correction:
                return {
                    'id': correction.id,
                    'fields': correction.fields_json,
                    'reason': correction.reason,
                    'created_at': correction.created_at
                }
            return None
            
        except Exception as e:
            logger.warning(f"Failed to fetch correction: {e}")
            return None
    
    def _get_matching_rule(self, user_id: str, raw_expense: Optional[Dict]) -> Optional[Dict]:
        """Find the highest priority matching rule for the user"""
        if not raw_expense:
            return None
            
        try:
            from db_base import db
            from models_pca import UserRule
            
            # Get all user rules
            rules = db.session.query(UserRule).filter_by(
                user_id=user_id,
                active=True
            ).all()
            
            if not rules:
                return None
                
            # Score and sort rules by specificity
            scored_rules = []
            for rule in rules:
                score = self._calculate_rule_specificity(rule.pattern_json, raw_expense)
                if score > 0:  # Rule matches
                    scored_rules.append((score, rule))
                    
            if not scored_rules:
                return None
                
            # Sort by score (desc) then by recency (desc)
            scored_rules.sort(key=lambda x: (x[0], x[1].created_at), reverse=True)
            
            # Return highest priority rule
            best_rule = scored_rules[0][1]
            return {
                'id': best_rule.id,
                'pattern': best_rule.pattern_json,
                'rule_set': best_rule.rule_set_json,
                'created_at': best_rule.created_at
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch matching rule: {e}")
            return None
    
    def _calculate_rule_specificity(self, pattern: Dict, expense: Dict) -> int:
        """
        Calculate rule specificity score
        Higher score = more specific = higher priority
        
        Returns 0 if rule doesn't match, positive score if matches
        """
        score = 0
        
        # Check if rule matches at all
        merchant_text = expense.get('merchant_text', '').lower()
        category = expense.get('category', '').lower()
        
        # Exact merchant_id match (highest specificity)
        if pattern.get('merchant_id') and pattern['merchant_id'] == expense.get('merchant_id'):
            score += 100
            
        # Vertical + store name match
        if pattern.get('vertical') and pattern.get('store_name_contains'):
            if (pattern['vertical'].lower() in merchant_text and 
                pattern['store_name_contains'].lower() in merchant_text):
                score += 50
                
        # Store name contains
        elif pattern.get('store_name_contains'):
            if pattern['store_name_contains'].lower() in merchant_text:
                score += 30
                
        # Text contains
        elif pattern.get('text_contains'):
            if pattern['text_contains'].lower() in merchant_text:
                score += 20
                
        # Category was (for corrections)
        elif pattern.get('category_was'):
            if pattern['category_was'].lower() == category:
                score += 10
                
        return score
    
    def _get_transaction_effective(self, user_id: str, tx_id: str) -> Optional[Dict]:
        """Get transaction from effective table"""
        try:
            from db_base import db
            from models_pca import TransactionEffective
            
            effective = db.session.query(TransactionEffective).filter_by(
                user_id=user_id,
                tx_id=tx_id,
                status='active'
            ).first()
            
            if effective:
                return {
                    'category': effective.category,
                    'subcategory': effective.subcategory,
                    'amount': float(effective.amount),
                    'merchant_text': effective.merchant_text,
                    'confidence': 0.85  # Default confidence for effective
                }
            return None
            
        except Exception as e:
            logger.warning(f"Failed to fetch effective transaction: {e}")
            return None
    
    def _apply_correction(self, correction: Dict, raw_expense: Optional[Dict]) -> PrecedenceResult:
        """Apply user correction to create precedence result"""
        fields = correction['fields']
        base = raw_expense or {}
        
        return PrecedenceResult(
            category=fields.get('category', base.get('category', 'unknown')),
            subcategory=fields.get('subcategory', base.get('subcategory')),
            amount=fields.get('amount', base.get('amount', 0)),
            merchant_text=fields.get('merchant_text', base.get('merchant_text')),
            source='correction',
            correction_id=correction['id'],
            confidence=1.0  # User corrections have full confidence
        )
    
    def _apply_rule(self, rule: Dict, raw_expense: Optional[Dict]) -> PrecedenceResult:
        """Apply user rule to create precedence result"""
        rule_set = rule['rule_set']
        base = raw_expense or {}
        
        return PrecedenceResult(
            category=rule_set.get('category', base.get('category', 'unknown')),
            subcategory=rule_set.get('subcategory', base.get('subcategory')),
            amount=base.get('amount', 0),
            merchant_text=base.get('merchant_text'),
            source='rule',
            applied_rule_id=rule['id'],
            confidence=0.9  # Rules have high confidence
        )
    
    def _from_effective(self, effective: Dict) -> PrecedenceResult:
        """Create precedence result from effective transaction"""
        return PrecedenceResult(
            category=effective['category'],
            subcategory=effective.get('subcategory'),
            amount=effective['amount'],
            merchant_text=effective.get('merchant_text'),
            source='effective',
            confidence=effective.get('confidence', 0.85)
        )
    
    def _raw_fallback(self, raw_expense: Optional[Dict]) -> PrecedenceResult:
        """Fallback to raw expense data"""
        if not raw_expense:
            return PrecedenceResult(
                category='unknown',
                subcategory=None,
                amount=0,
                merchant_text=None,
                source='raw',
                confidence=0.0
            )
            
        return PrecedenceResult(
            category=raw_expense.get('category', 'unknown'),
            subcategory=raw_expense.get('subcategory'),
            amount=raw_expense.get('amount', 0),
            merchant_text=raw_expense.get('merchant_text'),
            source='raw',
            confidence=raw_expense.get('confidence', 0.5)
        )
    
    def clear_cache(self):
        """Clear the request-level cache"""
        self.cache.clear()

# Global precedence engine instance
precedence_engine = PrecedenceEngine()