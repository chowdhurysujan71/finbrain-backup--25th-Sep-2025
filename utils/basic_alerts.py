"""
Basic Alerts System for Go-Live
Minimal alerting for 5xx errors, webhook failures, and AI error rates
"""

import logging
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import os

logger = logging.getLogger(__name__)

class BasicAlertsSystem:
    """Lightweight alerting system for production monitoring"""
    
    def __init__(self):
        self.enabled = os.getenv('ENABLE_ALERTS', 'true').lower() == 'true'
        
        # Alert thresholds
        self.error_5xx_threshold = 5  # 5xx errors per 5 minutes
        self.webhook_failure_threshold = 3  # webhook failures per 5 minutes  
        self.ai_error_rate_threshold = 0.3  # 30% AI error rate
        self.window_minutes = 5
        
        # Sliding windows for tracking
        self.error_5xx_window = deque()
        self.webhook_failure_window = deque()
        self.ai_calls_window = deque()
        self.ai_errors_window = deque()
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Alert states to prevent spam
        self.alert_states = {
            '5xx_errors': False,
            'webhook_failures': False,
            'ai_error_rate': False
        }
        
        logger.info(f"Basic Alerts System initialized: enabled={self.enabled}")
    
    def _cleanup_windows(self):
        """Remove entries older than window_minutes"""
        cutoff_time = time.time() - (self.window_minutes * 60)
        
        # Clean all windows
        for window in [self.error_5xx_window, self.webhook_failure_window, 
                      self.ai_calls_window, self.ai_errors_window]:
            while window and window[0] < cutoff_time:
                window.popleft()
    
    def log_5xx_error(self, status_code: int, endpoint: str):
        """Log a 5xx server error"""
        if not self.enabled or status_code < 500:
            return
        
        with self._lock:
            self.error_5xx_window.append(time.time())
            self._cleanup_windows()
            
            # Check threshold
            if len(self.error_5xx_window) >= self.error_5xx_threshold:
                if not self.alert_states['5xx_errors']:
                    self._trigger_alert('5xx_errors', f"{len(self.error_5xx_window)} 5xx errors in {self.window_minutes}min")
                    self.alert_states['5xx_errors'] = True
            else:
                self.alert_states['5xx_errors'] = False
    
    def log_webhook_failure(self, reason: str):
        """Log a webhook processing failure"""
        if not self.enabled:
            return
        
        with self._lock:
            self.webhook_failure_window.append(time.time())
            self._cleanup_windows()
            
            # Check threshold
            if len(self.webhook_failure_window) >= self.webhook_failure_threshold:
                if not self.alert_states['webhook_failures']:
                    self._trigger_alert('webhook_failures', f"{len(self.webhook_failure_window)} webhook failures in {self.window_minutes}min")
                    self.alert_states['webhook_failures'] = True
            else:
                self.alert_states['webhook_failures'] = False
    
    def log_ai_call(self, success: bool):
        """Log an AI API call result"""
        if not self.enabled:
            return
        
        with self._lock:
            current_time = time.time()
            self.ai_calls_window.append(current_time)
            
            if not success:
                self.ai_errors_window.append(current_time)
            
            self._cleanup_windows()
            
            # Check AI error rate (only if we have enough calls)
            if len(self.ai_calls_window) >= 10:  # Minimum 10 calls for meaningful rate
                error_rate = len(self.ai_errors_window) / len(self.ai_calls_window)
                
                if error_rate >= self.ai_error_rate_threshold:
                    if not self.alert_states['ai_error_rate']:
                        self._trigger_alert('ai_error_rate', f"AI error rate: {error_rate:.1%} ({len(self.ai_errors_window)}/{len(self.ai_calls_window)})")
                        self.alert_states['ai_error_rate'] = True
                else:
                    self.alert_states['ai_error_rate'] = False
    
    def _trigger_alert(self, alert_type: str, message: str):
        """Trigger an alert (log-based for now, can be extended)"""
        timestamp = datetime.now().isoformat()
        alert_message = f"ALERT [{alert_type.upper()}] {message} at {timestamp}"
        
        # Log the alert
        logger.error(alert_message)
        
        # In a full system, this would send to:
        # - Email notifications
        # - Slack/Discord webhook
        # - PagerDuty/incident management
        # - SMS alerts
        
        # For now, just structured logging that can be monitored
        try:
            from utils.structured import structured_log
            structured_log("SYSTEM_ALERT", {
                "alert_type": alert_type,
                "message": message,
                "timestamp": timestamp,
                "severity": "error"
            })
        except:
            pass  # Don't break if structured logging fails
    
    def get_status(self) -> Dict:
        """Get current alerting system status"""
        with self._lock:
            self._cleanup_windows()
            
            # Calculate current AI error rate
            ai_error_rate = 0.0
            if len(self.ai_calls_window) > 0:
                ai_error_rate = len(self.ai_errors_window) / len(self.ai_calls_window)
            
            return {
                'enabled': self.enabled,
                'window_minutes': self.window_minutes,
                'current_counts': {
                    '5xx_errors': len(self.error_5xx_window),
                    'webhook_failures': len(self.webhook_failure_window),
                    'ai_calls': len(self.ai_calls_window),
                    'ai_errors': len(self.ai_errors_window),
                    'ai_error_rate': ai_error_rate
                },
                'thresholds': {
                    '5xx_errors': self.error_5xx_threshold,
                    'webhook_failures': self.webhook_failure_threshold,
                    'ai_error_rate': self.ai_error_rate_threshold
                },
                'alert_states': self.alert_states.copy()
            }
    
    def get_health(self) -> Dict:
        """Health check for monitoring systems"""
        try:
            status = self.get_status()
            
            if not status['enabled']:
                return {'status': 'disabled', 'message': 'Alerts disabled via ENABLE_ALERTS=false'}
            
            # Check if any alerts are currently active
            active_alerts = [k for k, v in status['alert_states'].items() if v]
            
            if active_alerts:
                return {
                    'status': 'alerting',
                    'active_alerts': active_alerts,
                    'message': f"Active alerts: {', '.join(active_alerts)}"
                }
            else:
                return {
                    'status': 'healthy',
                    'message': 'No active alerts',
                    'monitoring': status['current_counts']
                }
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

# Global alerts instance
basic_alerts = BasicAlertsSystem()

# Convenience functions for easy integration
def log_5xx_error(status_code: int, endpoint: str = "unknown"):
    """Log a 5xx server error"""
    basic_alerts.log_5xx_error(status_code, endpoint)

def log_webhook_failure(reason: str):
    """Log a webhook processing failure"""
    basic_alerts.log_webhook_failure(reason)

def log_ai_call_result(success: bool):
    """Log an AI API call result"""
    basic_alerts.log_ai_call(success)

def get_alerts_status():
    """Get current alerting system status"""
    return basic_alerts.get_status()

def get_alerts_health():
    """Get alerting system health for monitoring"""
    return basic_alerts.get_health()