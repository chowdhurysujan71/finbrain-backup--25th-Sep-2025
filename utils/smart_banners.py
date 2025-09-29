"""
Smart Banner Service - Goal-Aware Banner Intelligence System
Enhances existing banner system with automated goal analysis and coaching
"""
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class SmartBannerService:
    """Intelligent banner service with goal-aware coaching capabilities"""
    
    def __init__(self):
        self.enabled = True
        logger.info("Smart Banner Service initialized")
    
    def get_goal_aware_banners(self, user_id_hash: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get banners with enhanced goal intelligence
        
        This method combines regular banners with goal-aware coaching banners
        and prioritizes them based on user context and goal performance
        """
        try:
            from models import Banner, Goal, Expense
            from db_base import db
            from sqlalchemy import func
            
            # Get regular banners from existing system
            regular_banners = Banner.get_active_for_user(user_id_hash, limit=limit)
            
            # Check for real-time goal violations that need immediate banners
            immediate_banner = self._check_immediate_goal_violations(user_id_hash)
            
            # Combine banners with goal-aware prioritization
            all_banners = []
            
            # Add immediate goal banner if exists (highest priority)
            if immediate_banner:
                all_banners.append(immediate_banner)
            
            # Add existing banners
            for banner in regular_banners:
                banner.mark_shown()
                banner_data = banner.to_dict()
                
                # Enhance banner with goal context if relevant
                banner_data = self._enhance_banner_with_goal_context(banner_data, user_id_hash)
                all_banners.append(banner_data)
            
            # Sort by priority and limit results
            all_banners.sort(key=lambda x: x.get('priority', 10))
            
            # Commit shown count updates
            db.session.commit()
            
            return all_banners[:limit]
            
        except Exception as e:
            logger.error(f"Error getting goal-aware banners for user {user_id_hash[:8]}: {e}")
            # Fallback to regular banner system
            try:
                from models import Banner
                regular_banners = Banner.get_active_for_user(user_id_hash, limit=limit)
                banner_data = []
                for banner in regular_banners:
                    banner.mark_shown()
                    banner_data.append(banner.to_dict())
                db.session.commit()
                return banner_data
            except:
                return []
    
    def _check_immediate_goal_violations(self, user_id_hash: str) -> Optional[Dict[str, Any]]:
        """
        Check for immediate goal violations that warrant real-time coaching banners
        
        Returns a virtual banner dict if immediate action is needed, None otherwise
        """
        try:
            from models import Goal, Expense
            from datetime import date, datetime, UTC
            from sqlalchemy import func
            
            # Get user's active daily goals
            active_goals = Goal.get_active_for_user(user_id_hash, 'daily_spend_under')
            
            if not active_goals:
                return None
            
            goal = active_goals[0]  # Primary daily goal
            goal_amount = float(goal.amount)
            
            # Check today's spending
            today = date.today()
            today_expenses = Expense.query_active().filter(
                Expense.user_id_hash == user_id_hash,
                Expense.date == today
            ).all()
            
            today_total = sum(float(expense.amount) for expense in today_expenses)
            
            # Goal violation logic
            if today_total > goal_amount:
                overspend_amount = today_total - goal_amount
                overspend_percentage = (overspend_amount / goal_amount) * 100
                
                # Check if we already showed a goal violation banner today
                from models import Banner
                existing_banner = Banner.query_active().filter(
                    Banner.user_id_hash == user_id_hash,
                    Banner.banner_type == 'goal_violation',
                    func.date(Banner.created_at) == today
                ).first()
                
                if not existing_banner:
                    return {
                        'id': 'virtual_goal_violation',
                        'banner_type': 'goal_violation',
                        'title': f"🚨 Daily Goal Exceeded: +৳{overspend_amount:.0f}",
                        'message': f"You've spent ৳{today_total:.0f} against your ৳{goal_amount:.0f} daily goal ({overspend_percentage:.0f}% over). Small adjustments can help you get back on track tomorrow!",
                        'action_text': 'View Spending',
                        'action_url': '/report',
                        'priority': 1,  # Highest priority
                        'style': 'warning',
                        'dismissible': True,
                        'auto_hide_seconds': None,
                        'trigger_data': {
                            'goal_amount': goal_amount,
                            'actual_amount': today_total,
                            'overspend_amount': overspend_amount,
                            'overspend_percentage': overspend_percentage,
                            'date': today.isoformat(),
                            'virtual_banner': True
                        },
                        'context_expense_id': None,
                        'shown_count': 0,
                        'last_shown_at': None,
                        'created_at': datetime.now(UTC).isoformat(),
                        'expires_at': None,
                        'is_active': True
                    }
            
            # Check for goal achievement (spending well under budget)
            elif today_total < goal_amount * 0.7 and today_total > 0:  # More than 30% under budget
                savings_amount = goal_amount - today_total
                
                # Check if we already showed a goal achievement banner today
                from models import Banner
                existing_banner = Banner.query_active().filter(
                    Banner.user_id_hash == user_id_hash,
                    Banner.banner_type == 'goal_achievement',
                    func.date(Banner.created_at) == today
                ).first()
                
                if not existing_banner:
                    return {
                        'id': 'virtual_goal_achievement',
                        'banner_type': 'goal_achievement', 
                        'title': f"🎉 Great Job! ৳{savings_amount:.0f} Under Budget",
                        'message': f"You've spent ৳{today_total:.0f} of your ৳{goal_amount:.0f} daily budget. Excellent financial discipline!",
                        'action_text': 'See Progress',
                        'action_url': '/report',
                        'priority': 2,
                        'style': 'success',
                        'dismissible': True,
                        'auto_hide_seconds': 10,  # Auto-hide positive messages
                        'trigger_data': {
                            'goal_amount': goal_amount,
                            'actual_amount': today_total,
                            'savings_amount': savings_amount,
                            'date': today.isoformat(),
                            'virtual_banner': True
                        },
                        'context_expense_id': None,
                        'shown_count': 0,
                        'last_shown_at': None,
                        'created_at': datetime.now(UTC).isoformat(),
                        'expires_at': None,
                        'is_active': True
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking immediate goal violations: {e}")
            return None
    
    def _enhance_banner_with_goal_context(self, banner_data: Dict[str, Any], user_id_hash: str) -> Dict[str, Any]:
        """
        Enhance existing banner with goal-aware context
        
        This adds goal performance data to existing banners to make them more relevant
        """
        try:
            from models import Goal, Expense
            from datetime import date
            
            # Only enhance certain banner types
            if banner_data.get('banner_type') not in ['spending_alert', 'category_tip', 'milestone']:
                return banner_data
            
            # Get user's active goals
            active_goals = Goal.get_active_for_user(user_id_hash, 'daily_spend_under')
            if not active_goals:
                return banner_data
            
            goal = active_goals[0]
            goal_amount = float(goal.amount)
            
            # Get today's spending
            today = date.today()
            today_expenses = Expense.query_active().filter(
                Expense.user_id_hash == user_id_hash,
                Expense.date == today
            ).all()
            
            today_total = sum(float(expense.amount) for expense in today_expenses)
            remaining_budget = goal_amount - today_total
            
            # Enhance the banner with goal context
            banner_data['goal_context'] = {
                'daily_goal': goal_amount,
                'spent_today': today_total,
                'remaining_budget': remaining_budget,
                'goal_status': 'on_track' if today_total <= goal_amount else 'over_budget'
            }
            
            # Modify message to include goal context for specific types
            if banner_data.get('banner_type') == 'spending_alert' and remaining_budget > 0:
                original_message = banner_data.get('message', '')
                banner_data['message'] = f"{original_message} You have ৳{remaining_budget:.0f} left in your daily budget."
            
            return banner_data
            
        except Exception as e:
            logger.error(f"Error enhancing banner with goal context: {e}")
            return banner_data
    
    def trigger_goal_analysis_jobs_for_active_users(self) -> Dict[str, Any]:
        """
        Trigger goal analysis jobs for users who have recent activity
        
        This is called periodically to schedule goal analysis for active users
        """
        try:
            from models import Expense
            from datetime import date, timedelta
            from utils.goal_automation import schedule_goal_analysis_for_user
            from sqlalchemy import func
            
            # Get users who have expenses in the last 7 days
            seven_days_ago = date.today() - timedelta(days=7)
            
            recent_users = db.session.query(
                Expense.user_id_hash
            ).filter(
                Expense.date >= seven_days_ago,
                Expense.is_deleted.is_(False)
            ).group_by(Expense.user_id_hash).limit(100).all()  # Safety limit
            
            scheduled_jobs = 0
            failed_jobs = 0
            
            for (user_id_hash,) in recent_users:
                try:
                    if schedule_goal_analysis_for_user(user_id_hash):
                        scheduled_jobs += 1
                    else:
                        failed_jobs += 1
                except Exception as e:
                    logger.error(f"Failed to schedule job for user {user_id_hash[:8]}: {e}")
                    failed_jobs += 1
            
            logger.info(f"Goal analysis jobs scheduled: {scheduled_jobs} success, {failed_jobs} failed")
            
            return {
                'scheduled': scheduled_jobs,
                'failed': failed_jobs,
                'total_users': len(recent_users),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error triggering goal analysis jobs: {e}")
            return {
                'scheduled': 0,
                'failed': 0,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def cleanup_expired_goal_banners(self) -> int:
        """
        Clean up expired goal-related banners to prevent banner spam
        
        Returns number of banners cleaned up
        """
        try:
            from models import Banner
            from datetime import datetime, timedelta, UTC
            
            # Mark goal banners older than 24 hours as dismissed
            cutoff_time = datetime.now(UTC) - timedelta(hours=24)
            
            expired_banners = Banner.query_active().filter(
                Banner.banner_type.in_(['goal_celebration', 'goal_adjustment', 'goal_suggestion']),
                Banner.created_at < cutoff_time
            ).all()
            
            for banner in expired_banners:
                banner.dismiss()
            
            db.session.commit()
            
            logger.info(f"Cleaned up {len(expired_banners)} expired goal banners")
            return len(expired_banners)
            
        except Exception as e:
            logger.error(f"Error cleaning up goal banners: {e}")
            return 0

# Global instance
smart_banner_service = SmartBannerService()