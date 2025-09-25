"""
Production Analytics and Monitoring for Coaching Flow
Real-time metrics, effectiveness tracking, and performance monitoring
"""

import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class CoachingAnalytics:
    """
    Production analytics and monitoring for coaching effectiveness
    Tracks success rates, conversion metrics, and system health
    """
    
    def __init__(self):
        self.analytics_enabled = os.getenv('COACH_ANALYTICS_ENABLED', 'true').lower() == 'true'
        self.metrics_retention_hours = int(os.getenv('COACH_METRICS_RETENTION_HOURS', '24'))
        self.performance_threshold_ms = int(os.getenv('COACH_PERFORMANCE_THRESHOLD_MS', '500'))
        
        # In-memory metrics store (production would use Redis/InfluxDB)
        self.metrics = {
            'sessions_started': deque(maxlen=1000),
            'sessions_completed': deque(maxlen=1000),
            'sessions_abandoned': deque(maxlen=1000),
            'response_times': deque(maxlen=500),
            'error_counts': defaultdict(int),
            'topic_selections': defaultdict(int),
            'action_commitments': defaultdict(int),
            'user_engagement_scores': {},
            'conversion_events': deque(maxlen=200)
        }
        
        # Real-time health tracking
        self.health_metrics = {
            'last_update': time.time(),
            'total_sessions_today': 0,
            'success_rate_24h': 0.0,
            'avg_response_time_ms': 0.0,
            'error_rate_1h': 0.0,
            'active_sessions': 0
        }
    
    def track_session_start(self, psid_hash: str, trigger_intent: str, context_data: dict[str, Any]):
        """Track coaching session initiation"""
        if not self.analytics_enabled:
            return
        
        try:
            event = {
                'timestamp': time.time(),
                'psid_hash': psid_hash[:8] + '...',
                'trigger': trigger_intent,
                'context_categories': context_data.get('categories', []),
                'context_amount': context_data.get('total_amount', 0),
                'session_id': f"{psid_hash[:8]}_{int(time.time())}"
            }
            
            self.metrics['sessions_started'].append(event)
            self.health_metrics['total_sessions_today'] += 1
            
            logger.info(f"[ANALYTICS] Session started: {trigger_intent} for {psid_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"Analytics tracking error (session_start): {e}")
    
    def track_topic_selection(self, psid_hash: str, topic: str, response_time_ms: float):
        """Track user topic selection and response time"""
        if not self.analytics_enabled:
            return
        
        try:
            self.metrics['topic_selections'][topic] += 1
            self.metrics['response_times'].append(response_time_ms)
            
            # Update health metrics
            self._update_response_time_health(response_time_ms)
            
            logger.debug(f"[ANALYTICS] Topic selected: {topic} ({response_time_ms:.0f}ms)")
            
        except Exception as e:
            logger.error(f"Analytics tracking error (topic_selection): {e}")
    
    def track_action_commitment(self, psid_hash: str, topic: str, action: str, session_duration_sec: float):
        """Track successful action commitment"""
        if not self.analytics_enabled:
            return
        
        try:
            commitment_key = f"{topic}:{action}"
            self.metrics['action_commitments'][commitment_key] += 1
            
            # Record conversion event
            conversion = {
                'timestamp': time.time(),
                'psid_hash': psid_hash[:8] + '...',
                'topic': topic,
                'action': action,
                'session_duration': session_duration_sec,
                'successful_conversion': True
            }
            self.metrics['conversion_events'].append(conversion)
            
            # Track completion
            completion_event = {
                'timestamp': time.time(),
                'psid_hash': psid_hash[:8] + '...',
                'outcome': 'completed',
                'duration_sec': session_duration_sec
            }
            self.metrics['sessions_completed'].append(completion_event)
            
            logger.info(f"[ANALYTICS] Action committed: {topic} -> {action} ({session_duration_sec:.1f}s)")
            
        except Exception as e:
            logger.error(f"Analytics tracking error (action_commitment): {e}")
    
    def track_session_abandonment(self, psid_hash: str, reason: str, stage: str, partial_data: dict[str, Any]):
        """Track session abandonment with context"""
        if not self.analytics_enabled:
            return
        
        try:
            abandonment = {
                'timestamp': time.time(),
                'psid_hash': psid_hash[:8] + '...',
                'reason': reason,
                'stage': stage,
                'turns_completed': partial_data.get('turns', 0),
                'topic_selected': partial_data.get('topic'),
                'duration_sec': time.time() - partial_data.get('started_at', time.time())
            }
            
            self.metrics['sessions_abandoned'].append(abandonment)
            
            logger.info(f"[ANALYTICS] Session abandoned: {reason} at {stage}")
            
        except Exception as e:
            logger.error(f"Analytics tracking error (abandonment): {e}")
    
    def track_error(self, error_type: str, error_details: str, psid_hash: str | None = None):
        """Track coaching system errors"""
        if not self.analytics_enabled:
            return
        
        try:
            self.metrics['error_counts'][error_type] += 1
            
            error_event = {
                'timestamp': time.time(),
                'type': error_type,
                'details': error_details[:100],  # Truncate long errors
                'psid_hash': psid_hash[:8] + '...' if psid_hash else 'unknown'
            }
            
            logger.warning(f"[ANALYTICS] Error tracked: {error_type}")
            
            # Update health metrics
            self._update_error_rate_health()
            
        except Exception as e:
            logger.error(f"Analytics tracking error (error): {e}")
    
    def track_performance(self, operation: str, duration_ms: float, success: bool):
        """Track operation performance"""
        if not self.analytics_enabled:
            return
        
        try:
            self.metrics['response_times'].append(duration_ms)
            
            if duration_ms > self.performance_threshold_ms:
                logger.warning(f"[ANALYTICS] Slow operation: {operation} took {duration_ms:.0f}ms")
            
            # Update health metrics
            self._update_response_time_health(duration_ms)
            
        except Exception as e:
            logger.error(f"Analytics tracking error (performance): {e}")
    
    def get_real_time_metrics(self) -> dict[str, Any]:
        """Get current real-time metrics dashboard"""
        try:
            current_time = time.time()
            
            # Calculate 24h success rate
            completed_24h = len([s for s in self.metrics['sessions_completed'] 
                               if current_time - s['timestamp'] <= 86400])
            started_24h = len([s for s in self.metrics['sessions_started'] 
                             if current_time - s['timestamp'] <= 86400])
            
            success_rate = (completed_24h / started_24h * 100) if started_24h > 0 else 0
            
            # Calculate average response time (last 100 operations)
            recent_times = list(self.metrics['response_times'])[-100:]
            avg_response_time = sum(recent_times) / len(recent_times) if recent_times else 0
            
            # Calculate error rate (last 1 hour)
            total_errors_1h = sum(count for error_type, count in self.metrics['error_counts'].items())
            total_operations_1h = len([s for s in self.metrics['sessions_started'] 
                                     if current_time - s['timestamp'] <= 3600])
            error_rate = (total_errors_1h / max(total_operations_1h, 1)) * 100
            
            # Top topics and actions
            top_topics = dict(sorted(self.metrics['topic_selections'].items(), 
                                   key=lambda x: x[1], reverse=True)[:5])
            top_actions = dict(sorted(self.metrics['action_commitments'].items(), 
                                    key=lambda x: x[1], reverse=True)[:5])
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'health_status': self._get_health_status(),
                'session_metrics': {
                    'started_24h': started_24h,
                    'completed_24h': completed_24h,
                    'success_rate_pct': round(success_rate, 1),
                    'abandonment_rate_pct': round(100 - success_rate, 1)
                },
                'performance_metrics': {
                    'avg_response_time_ms': round(avg_response_time, 1),
                    'slow_operations_pct': len([t for t in recent_times if t > self.performance_threshold_ms]) / max(len(recent_times), 1) * 100,
                    'error_rate_1h_pct': round(error_rate, 2)
                },
                'engagement_metrics': {
                    'top_topics': top_topics,
                    'top_actions': top_actions,
                    'total_conversions': len(self.metrics['conversion_events'])
                },
                'system_health': {
                    'analytics_enabled': self.analytics_enabled,
                    'metrics_retention_hours': self.metrics_retention_hours,
                    'last_update': current_time
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return {'error': str(e), 'timestamp': datetime.utcnow().isoformat()}
    
    def get_coaching_effectiveness_report(self) -> dict[str, Any]:
        """Generate coaching effectiveness analysis"""
        try:
            current_time = time.time()
            
            # Analyze conversion funnel
            total_starts = len(self.metrics['sessions_started'])
            total_completions = len(self.metrics['sessions_completed'])
            total_conversions = len(self.metrics['conversion_events'])
            
            # Topic effectiveness
            topic_effectiveness = {}
            for topic, selections in self.metrics['topic_selections'].items():
                commitments = sum(count for key, count in self.metrics['action_commitments'].items() 
                                if key.startswith(f"{topic}:"))
                effectiveness = (commitments / selections * 100) if selections > 0 else 0
                topic_effectiveness[topic] = {
                    'selections': selections,
                    'commitments': commitments,
                    'effectiveness_pct': round(effectiveness, 1)
                }
            
            # Session duration analysis
            completed_sessions = list(self.metrics['sessions_completed'])
            avg_duration = sum(s.get('duration_sec', 0) for s in completed_sessions) / max(len(completed_sessions), 1)
            
            return {
                'report_timestamp': datetime.utcnow().isoformat(),
                'funnel_analysis': {
                    'sessions_started': total_starts,
                    'sessions_completed': total_completions,
                    'completion_rate_pct': round(total_completions / max(total_starts, 1) * 100, 1),
                    'conversion_rate_pct': round(total_conversions / max(total_starts, 1) * 100, 1)
                },
                'topic_effectiveness': topic_effectiveness,
                'engagement_quality': {
                    'avg_session_duration_sec': round(avg_duration, 1),
                    'quick_abandonment_rate': len([s for s in self.metrics['sessions_abandoned'] 
                                                  if s.get('duration_sec', 0) < 30]) / max(total_starts, 1) * 100
                },
                'recommendations': self._generate_effectiveness_recommendations(topic_effectiveness, avg_duration)
            }
            
        except Exception as e:
            logger.error(f"Error generating effectiveness report: {e}")
            return {'error': str(e), 'report_timestamp': datetime.utcnow().isoformat()}
    
    def _update_response_time_health(self, response_time_ms: float):
        """Update response time health metrics"""
        try:
            recent_times = list(self.metrics['response_times'])[-50:]  # Last 50 operations
            self.health_metrics['avg_response_time_ms'] = sum(recent_times) / len(recent_times)
        except:
            pass
    
    def _update_error_rate_health(self):
        """Update error rate health metrics"""
        try:
            current_time = time.time()
            recent_errors = sum(self.metrics['error_counts'].values())
            recent_operations = len([s for s in self.metrics['sessions_started'] 
                                   if current_time - s['timestamp'] <= 3600])
            self.health_metrics['error_rate_1h'] = recent_errors / max(recent_operations, 1) * 100
        except:
            pass
    
    def _get_health_status(self) -> str:
        """Determine overall health status"""
        try:
            if self.health_metrics['error_rate_1h'] > 10:  # >10% error rate
                return 'unhealthy'
            elif self.health_metrics['avg_response_time_ms'] > self.performance_threshold_ms * 2:
                return 'degraded'
            else:
                return 'healthy'
        except:
            return 'unknown'
    
    def _generate_effectiveness_recommendations(self, topic_effectiveness: dict, avg_duration: float) -> list[str]:
        """Generate coaching improvement recommendations"""
        recommendations = []
        
        try:
            # Low effectiveness topics
            low_effectiveness = [topic for topic, data in topic_effectiveness.items() 
                               if data['effectiveness_pct'] < 50]
            if low_effectiveness:
                recommendations.append(f"Improve coaching for low-effectiveness topics: {', '.join(low_effectiveness)}")
            
            # Session duration insights
            if avg_duration < 30:
                recommendations.append("Sessions are very short - consider more engaging first questions")
            elif avg_duration > 300:  # 5 minutes
                recommendations.append("Sessions are long - consider streamlining the flow")
            
            # General recommendations
            if not recommendations:
                recommendations.append("Coaching effectiveness is good - maintain current approach")
                
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations = ["Unable to generate recommendations due to analysis error"]
        
        return recommendations

# Global analytics manager
coaching_analytics = CoachingAnalytics()