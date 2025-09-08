"""
FinBrain Growth Telemetry System
Tracks user engagement events and calculates growth metrics
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import text, func
from app import db

logger = logging.getLogger(__name__)

class TelemetryTracker:
    """Central telemetry tracking system for growth metrics"""
    
    @staticmethod
    def track_event(event_type: str, user_id_hash: str, event_data: Dict[str, Any] = None) -> bool:
        """
        Track a telemetry event
        
        Args:
            event_type: Type of event ('expense_logged', 'expense_edited', etc.)
            user_id_hash: Hashed user identifier
            event_data: Additional event data as JSON
            
        Returns:
            bool: True if event was successfully tracked
        """
        try:
            from models import TelemetryEvent
            
            event = TelemetryEvent(
                event_type=event_type,
                user_id_hash=user_id_hash,
                event_data=event_data or {},
                timestamp=datetime.now(timezone.utc)
            )
            
            db.session.add(event)
            db.session.commit()
            
            # Update relevant counters
            TelemetryTracker._update_counter(event_type)
            
            logger.debug(f"Tracked {event_type} event for user {user_id_hash[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to track {event_type} event: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def track_expense_logged(user_id_hash: str, amount: float, category: str, source: str = "form") -> bool:
        """Track when user successfully logs an expense"""
        event_data = {
            "amount": float(amount),
            "category": category,
            "source": source
        }
        return TelemetryTracker.track_event("expense_logged", user_id_hash, event_data)
    
    @staticmethod 
    def track_expense_edited(user_id_hash: str, expense_id: int) -> bool:
        """Track when user edits an existing expense"""
        event_data = {
            "expense_id": expense_id
        }
        return TelemetryTracker.track_event("expense_edited", user_id_hash, event_data)
    
    @staticmethod
    def track_report_requested(user_id_hash: str, report_type: str) -> bool:
        """Track when user requests a financial report"""
        event_data = {
            "report_type": report_type
        }
        return TelemetryTracker.track_event("report_requested", user_id_hash, event_data)
    
    @staticmethod
    def track_pwa_install(user_id_hash: str) -> bool:
        """Track when user installs the PWA"""
        return TelemetryTracker.track_event("install_pwa", user_id_hash)
    
    @staticmethod
    def _update_counter(event_type: str) -> None:
        """Update running counters based on event type"""
        try:
            from models import GrowthCounter
            
            counter_mapping = {
                "expense_logged": "total_expenses",
                "report_requested": "total_reports",
                # "challenge_started": "challenges_started"  # Future feature
            }
            
            counter_name = counter_mapping.get(event_type)
            if counter_name:
                counter = GrowthCounter.query.filter_by(counter_name=counter_name).first()
                if counter:
                    counter.counter_value += 1
                    counter.last_updated = datetime.now(timezone.utc)
                    db.session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update counter for {event_type}: {e}")

class GrowthMetrics:
    """Calculate growth metrics from telemetry data"""
    
    @staticmethod
    def get_dau_today() -> int:
        """Get Daily Active Users for today (UTC)"""
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            from models import TelemetryEvent
            
            dau_count = db.session.query(
                func.count(func.distinct(TelemetryEvent.user_id_hash))
            ).filter(
                TelemetryEvent.event_type == 'expense_logged',
                TelemetryEvent.timestamp >= today_start,
                TelemetryEvent.timestamp < today_end
            ).scalar()
            
            return dau_count or 0
            
        except Exception as e:
            logger.error(f"Failed to calculate DAU today: {e}")
            return 0
    
    @staticmethod
    def get_dau_7day() -> int:
        """Get 7-day Active Users"""
        try:
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            from models import TelemetryEvent
            
            dau_7day = db.session.query(
                func.count(func.distinct(TelemetryEvent.user_id_hash))
            ).filter(
                TelemetryEvent.event_type == 'expense_logged',
                TelemetryEvent.timestamp >= seven_days_ago
            ).scalar()
            
            return dau_7day or 0
            
        except Exception as e:
            logger.error(f"Failed to calculate 7-day DAU: {e}")
            return 0
    
    @staticmethod
    def get_retention_cohorts(days: int = 7) -> List[Dict[str, Any]]:
        """
        Get D1/D3 retention for the last N cohorts
        
        Args:
            days: Number of cohorts to analyze (default 7)
            
        Returns:
            List of cohort data with retention percentages
        """
        try:
            from models import TelemetryEvent
            
            cohorts = []
            
            for day_offset in range(days):
                cohort_date = datetime.now(timezone.utc).date() - timedelta(days=day_offset)
                cohort_start = datetime.combine(cohort_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                cohort_end = cohort_start + timedelta(days=1)
                
                # Get new users in this cohort (first expense_logged event)
                new_users_query = text("""
                    SELECT user_id_hash, MIN(timestamp) as first_expense
                    FROM telemetry_events 
                    WHERE event_type = 'expense_logged'
                    GROUP BY user_id_hash
                    HAVING MIN(timestamp) >= :cohort_start AND MIN(timestamp) < :cohort_end
                """)
                
                new_users_result = db.session.execute(new_users_query, {
                    'cohort_start': cohort_start,
                    'cohort_end': cohort_end
                }).fetchall()
                
                d0_users = len(new_users_result)
                
                if d0_users == 0:
                    cohorts.append({
                        'cohort_date': cohort_date.strftime('%Y-%m-%d'),
                        'd0_users': 0,
                        'd1_retention': 0.0,
                        'd3_retention': 0.0
                    })
                    continue
                
                user_ids = [row[0] for row in new_users_result]
                
                # Calculate D1 retention
                d1_start = cohort_start + timedelta(days=1)
                d1_end = d1_start + timedelta(days=1)
                
                d1_active = db.session.query(
                    func.count(func.distinct(TelemetryEvent.user_id_hash))
                ).filter(
                    TelemetryEvent.event_type == 'expense_logged',
                    TelemetryEvent.user_id_hash.in_(user_ids),
                    TelemetryEvent.timestamp >= d1_start,
                    TelemetryEvent.timestamp < d1_end
                ).scalar() or 0
                
                # Calculate D3 retention
                d3_start = cohort_start + timedelta(days=3)
                d3_end = d3_start + timedelta(days=1)
                
                d3_active = db.session.query(
                    func.count(func.distinct(TelemetryEvent.user_id_hash))
                ).filter(
                    TelemetryEvent.event_type == 'expense_logged',
                    TelemetryEvent.user_id_hash.in_(user_ids),
                    TelemetryEvent.timestamp >= d3_start,
                    TelemetryEvent.timestamp < d3_end
                ).scalar() or 0
                
                cohorts.append({
                    'cohort_date': cohort_date.strftime('%Y-%m-%d'),
                    'd0_users': d0_users,
                    'd1_retention': (d1_active / d0_users * 100) if d0_users > 0 else 0.0,
                    'd3_retention': (d3_active / d0_users * 100) if d0_users > 0 else 0.0
                })
            
            return cohorts
            
        except Exception as e:
            logger.error(f"Failed to calculate retention cohorts: {e}")
            return []
    
    @staticmethod
    def get_running_totals() -> Dict[str, int]:
        """Get all running counter totals"""
        try:
            from models import GrowthCounter
            
            counters = GrowthCounter.query.all()
            totals = {}
            
            for counter in counters:
                totals[counter.counter_name] = counter.counter_value
                
            # Ensure all expected counters are present
            expected_counters = ['total_expenses', 'total_reports', 'challenges_started']
            for counter_name in expected_counters:
                if counter_name not in totals:
                    totals[counter_name] = 0
                    
            return totals
            
        except Exception as e:
            logger.error(f"Failed to get running totals: {e}")
            return {
                'total_expenses': 0,
                'total_reports': 0, 
                'challenges_started': 0
            }
    
    @staticmethod
    def generate_metrics_report() -> str:
        """Generate human-readable metrics report"""
        try:
            # Get all metrics
            dau_today = GrowthMetrics.get_dau_today()
            dau_7day = GrowthMetrics.get_dau_7day()
            cohorts = GrowthMetrics.get_retention_cohorts(7)
            totals = GrowthMetrics.get_running_totals()
            
            # Generate report
            report_lines = [
                "FinBrain Growth Metrics",
                "======================",
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "",
                "Daily Active Users (DAU)",
                f"- Today: {dau_today:,} users",
                f"- 7-day: {dau_7day:,} users",
                "",
                "User Retention (Last 7 Cohorts)",
                "Cohort    | D0 Users | D1 Retention | D3 Retention"
            ]
            
            for cohort in cohorts:
                report_lines.append(
                    f"{cohort['cohort_date']}|    {cohort['d0_users']:2d}    |    {cohort['d1_retention']:5.1f}%     |    {cohort['d3_retention']:5.1f}%"
                )
            
            report_lines.extend([
                "",
                "Running Totals",
                f"- Total Expenses: {totals.get('total_expenses', 0):,}",
                f"- Total Reports: {totals.get('total_reports', 0):,}",
                f"- Challenges Started: {totals.get('challenges_started', 0):,}"
            ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"Failed to generate metrics report: {e}")
            return f"Error generating metrics report: {str(e)}"

def initialize_growth_counters():
    """Initialize growth counters if they don't exist"""
    try:
        from models import GrowthCounter
        
        expected_counters = [
            ('total_expenses', 0),
            ('total_reports', 0),
            ('challenges_started', 0)
        ]
        
        for counter_name, initial_value in expected_counters:
            existing = GrowthCounter.query.filter_by(counter_name=counter_name).first()
            if not existing:
                counter = GrowthCounter(
                    counter_name=counter_name,
                    counter_value=initial_value
                )
                db.session.add(counter)
        
        db.session.commit()
        logger.info("Growth counters initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize growth counters: {e}")
        db.session.rollback()