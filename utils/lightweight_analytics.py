"""
Lightweight Analytics System
Builds on existing structured telemetry infrastructure to track key metrics
100% additive - no changes to existing functionality
"""

import json
import logging
import os
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

class LightweightAnalytics:
    """Lightweight analytics that extends existing structured logging"""
    
    def __init__(self):
        self.enabled = os.getenv('ENABLE_ANALYTICS', 'true').lower() == 'true'
        
        # In-memory counters (lightweight, no database changes)
        self.daily_metrics = {
            'dau': set(),  # Daily active users
            'new_conversations': 0,
            'expense_logs': 0,
            'ai_calls': 0,
            'abandonment_events': deque(maxlen=100)
        }
        
        # Reset daily counters
        self.last_reset_date = date.today()
        
    def track_dau(self, user_hash: str) -> None:
        """Track daily active user (zero cost - just adds to set)"""
        if not self.enabled:
            return
            
        try:
            self._check_daily_reset()
            self.daily_metrics['dau'].add(user_hash[:8])  # Only store first 8 chars for privacy
            
            # Log structured event using existing infrastructure
            self._log_analytics_event('DAU_TRACKED', {
                'user_hash_prefix': user_hash[:8],
                'daily_unique_users': len(self.daily_metrics['dau'])
            })
            
        except Exception as e:
            # Fail-safe: analytics errors never break main flow
            logger.warning(f"DAU tracking failed: {e}")
    
    def track_new_conversation(self, user_hash: str, is_new_user: bool) -> None:
        """Track new conversation start"""
        if not self.enabled:
            return
            
        try:
            self._check_daily_reset()
            self.daily_metrics['new_conversations'] += 1
            
            self._log_analytics_event('NEW_CONVERSATION', {
                'user_hash_prefix': user_hash[:8],
                'is_new_user': is_new_user,
                'daily_conversations': self.daily_metrics['new_conversations']
            })
            
        except Exception as e:
            logger.warning(f"Conversation tracking failed: {e}")
    
    def track_expense_logged(self, user_hash: str, amount: float, category: str) -> None:
        """Track successful expense logging"""
        if not self.enabled:
            return
            
        try:
            self._check_daily_reset()
            self.daily_metrics['expense_logs'] += 1
            
            self._log_analytics_event('EXPENSE_LOGGED', {
                'user_hash_prefix': user_hash[:8],
                'amount': amount,
                'category': category,
                'daily_expenses': self.daily_metrics['expense_logs']
            })
            
        except Exception as e:
            logger.warning(f"Expense logging tracking failed: {e}")
    
    def track_ai_call(self, user_hash: str, intent: str, response_time_ms: float) -> None:
        """Track AI API calls and performance"""
        if not self.enabled:
            return
            
        try:
            self._check_daily_reset()
            self.daily_metrics['ai_calls'] += 1
            
            self._log_analytics_event('AI_CALL', {
                'user_hash_prefix': user_hash[:8],
                'intent': intent,
                'response_time_ms': response_time_ms,
                'daily_ai_calls': self.daily_metrics['ai_calls']
            })
            
        except Exception as e:
            logger.warning(f"AI call tracking failed: {e}")
    
    def track_abandonment(self, user_hash: str, step: str, context: dict[str, Any] = None) -> None:
        """Track user abandonment at specific steps"""
        if not self.enabled:
            return
            
        try:
            abandonment_event = {
                'timestamp': datetime.utcnow().isoformat(),
                'user_hash_prefix': user_hash[:8],
                'abandonment_step': step,
                'context': context or {}
            }
            
            self.daily_metrics['abandonment_events'].append(abandonment_event)
            
            self._log_analytics_event('USER_ABANDONMENT', abandonment_event)
            
        except Exception as e:
            logger.warning(f"Abandonment tracking failed: {e}")
    
    def get_daily_metrics(self) -> dict[str, Any]:
        """Get current daily metrics for monitoring"""
        try:
            self._check_daily_reset()
            
            # Recent abandonment analysis
            recent_abandonments = list(self.daily_metrics['abandonment_events'])[-20:]
            abandonment_by_step = defaultdict(int)
            for event in recent_abandonments:
                abandonment_by_step[event['abandonment_step']] += 1
            
            return {
                'date': date.today().isoformat(),
                'dau': len(self.daily_metrics['dau']),
                'new_conversations': self.daily_metrics['new_conversations'],
                'expense_logs': self.daily_metrics['expense_logs'],
                'ai_calls': self.daily_metrics['ai_calls'],
                'abandonment_events': len(recent_abandonments),
                'top_abandonment_steps': dict(abandonment_by_step),
                'analytics_enabled': self.enabled
            }
            
        except Exception as e:
            logger.error(f"Failed to get daily metrics: {e}")
            return {'error': str(e), 'analytics_enabled': self.enabled}
    
    def _check_daily_reset(self) -> None:
        """Reset daily counters if new day"""
        current_date = date.today()
        if current_date > self.last_reset_date:
            self.daily_metrics = {
                'dau': set(),
                'new_conversations': 0,
                'expense_logs': 0,
                'ai_calls': 0,
                'abandonment_events': deque(maxlen=100)
            }
            self.last_reset_date = current_date
            
            self._log_analytics_event('DAILY_RESET', {
                'reset_date': current_date.isoformat()
            })
    
    def _log_analytics_event(self, event_name: str, data: dict[str, Any]) -> None:
        """Log analytics event using existing structured logging"""
        try:
            # Use existing structured logging infrastructure
            from utils.structured import log_structured_event
            
            # Add analytics prefix for easy filtering
            analytics_data = {
                'analytics_event': True,
                'timestamp': datetime.utcnow().isoformat(),
                **data
            }
            
            log_structured_event(f"ANALYTICS_{event_name}", analytics_data)
            
        except Exception:
            # Use basic logging as fallback
            logger.info(f"ANALYTICS_{event_name} {json.dumps(data)}")

# Global analytics instance
lightweight_analytics = LightweightAnalytics()

# Convenient wrapper functions for easy integration
def track_user_activity(user_hash: str, is_new_user: bool = False) -> None:
    """Track user activity (DAU + new conversation if applicable)"""
    lightweight_analytics.track_dau(user_hash)
    if is_new_user:
        lightweight_analytics.track_new_conversation(user_hash, True)

def track_expense_success(user_hash: str, amount: float, category: str) -> None:
    """Track successful expense logging"""
    lightweight_analytics.track_expense_logged(user_hash, amount, category)

def track_ai_usage(user_hash: str, intent: str, response_time_ms: float) -> None:
    """Track AI API usage and performance"""
    lightweight_analytics.track_ai_call(user_hash, intent, response_time_ms)

def track_user_abandonment(user_hash: str, step: str, context: dict[str, Any] = None) -> None:
    """Track user abandonment at critical steps"""
    lightweight_analytics.track_abandonment(user_hash, step, context)

def get_analytics_summary() -> dict[str, Any]:
    """Get daily analytics summary"""
    return lightweight_analytics.get_daily_metrics()

# Health check function for monitoring
def analytics_health_check() -> dict[str, Any]:
    """Health check for analytics system"""
    try:
        metrics = get_analytics_summary()
        
        return {
            'status': 'healthy',
            'enabled': lightweight_analytics.enabled,
            'current_metrics': metrics,
            'last_reset': lightweight_analytics.last_reset_date.isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'enabled': lightweight_analytics.enabled
        }