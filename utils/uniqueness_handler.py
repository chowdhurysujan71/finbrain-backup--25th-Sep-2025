"""
Data-Version Uniqueness Handler for PoR v1.1
Implements truthful uniqueness messaging with micro-insights
"""

import os
import logging
import hashlib
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from utils.routing_policy import DataVersionManager

logger = logging.getLogger("finbrain.uniqueness")

class UniquenessHandler:
    """Handles data-version based uniqueness with truthful messaging"""
    
    def __init__(self):
        """Initialize uniqueness handler"""
        self.data_mgr = DataVersionManager()
        self.uniqueness_mode = os.environ.get('UNIQUENESS_MODE', 'data_version')
        
    def check_uniqueness(self, user_id: str, text: str, window_start: datetime, window_end: datetime) -> Tuple[bool, Optional[str]]:
        """
        Check if request is unique or should be suppressed
        
        Args:
            user_id: User identifier
            text: User message text
            window_start: Analysis window start
            window_end: Analysis window end
            
        Returns:
            Tuple of (is_unique, suppression_message)
            - is_unique: False if should suppress (unchanged data)
            - suppression_message: Message to send if suppressing
        """
        if self.uniqueness_mode == 'timestamp':
            # Legacy timestamp-based uniqueness (always unique)
            return True, None
        
        try:
            # Compute current data version
            current_data_version = self.data_mgr.compute_data_version(user_id, window_start, window_end)
            
            # Get last data version for this user
            last_data_version = self._get_last_data_version(user_id)
            
            # Check if data changed
            if current_data_version == last_data_version and last_data_version != "empty":
                # Data unchanged - generate suppression message
                suppression_msg = self._generate_suppression_message(user_id, window_start, window_end)
                logger.info(f"[UNIQUENESS] Suppressing repeat for {user_id[:8]}: data_version={current_data_version[:8]}")
                return False, suppression_msg
            else:
                # Data changed or first request - allow through
                self._store_data_version(user_id, current_data_version)
                logger.debug(f"[UNIQUENESS] Allowing request for {user_id[:8]}: data_version={current_data_version[:8]}")
                return True, None
                
        except Exception as e:
            logger.error(f"[UNIQUENESS] Error checking uniqueness for {user_id[:8]}: {e}")
            # Fail open - allow request through
            return True, None
    
    def _generate_suppression_message(self, user_id: str, window_start: datetime, window_end: datetime) -> str:
        """Generate truthful suppression message with micro-insight"""
        
        # Base message (bilingual)
        base_en = "No changes since your last check. Add a new expense to refresh your analysis."
        base_bn = "শেষবারের পর থেকে নতুন পরিবর্তন নেই। নতুন খরচ যোগ করলে বিশ্লেষণ আপডেট হবে।"
        
        # Try to add micro-insight
        micro_insight = self._generate_micro_insight(user_id, window_start, window_end)
        
        if micro_insight:
            return f"{base_en}\n\n{micro_insight}"
        else:
            return base_en
    
    def _generate_micro_insight(self, user_id: str, window_start: datetime, window_end: datetime) -> Optional[str]:
        """Generate deterministic micro-insight for unchanged data"""
        try:
            from app import db
            
            # Check eligibility: only for users with ≥5 transactions and non-zero total
            result = db.session.execute(
                """
                SELECT 
                    count(*) as txn_count,
                    sum(amount) as total_amount,
                    category,
                    sum(amount) as cat_amount
                FROM expenses 
                WHERE user_id = :uid 
                  AND created_at >= :from_time 
                  AND created_at < :to_time
                GROUP BY category
                ORDER BY sum(amount) DESC
                LIMIT 1
                """,
                {
                    'uid': user_id,
                    'from_time': window_start,
                    'to_time': window_end
                }
            ).fetchone()
            
            if not result or result.txn_count < 5 or result.total_amount <= 0:
                return None
            
            # Calculate top category percentage
            top_category = result.category or "Other"
            cat_amount = float(result.cat_amount)
            total_amount = float(result.total_amount)
            percentage = (cat_amount / total_amount) * 100
            
            # Deterministic micro-insight
            tip_en = f"💡 Tip: your top category this month is {top_category} (~{percentage:.0f}%). Want ideas to trim it?"
            
            return tip_en
            
        except Exception as e:
            logger.warning(f"[UNIQUENESS] Failed to generate micro-insight for {user_id[:8]}: {e}")
            return None
    
    def _get_last_data_version(self, user_id: str) -> Optional[str]:
        """Get last stored data version for user"""
        try:
            from utils.session import get_from_cache
            cache_key = f"data_version:{user_id}"
            return get_from_cache(cache_key)
        except:
            return None
    
    def _store_data_version(self, user_id: str, data_version: str):
        """Store data version for user"""
        try:
            from utils.session import store_in_cache
            cache_key = f"data_version:{user_id}"
            # Store for 24 hours
            store_in_cache(cache_key, data_version, ttl_seconds=86400)
        except Exception as e:
            logger.warning(f"Failed to store data version for {user_id[:8]}: {e}")

# Global instance
uniqueness_handler = UniquenessHandler()