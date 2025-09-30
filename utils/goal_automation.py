"""
Automated Goal Analysis and Adjustment System
Provides intelligent, agentic goal management using Redis background jobs
"""
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from sqlalchemy import func

logger = logging.getLogger(__name__)

class GoalAutomationEngine:
    """Agentic AI system for automated goal analysis and adjustments"""
    
    def __init__(self):
        self.analysis_enabled = True
        logger.info("Goal Automation Engine initialized")
    
    def analyze_user_goal_performance(self, user_id_hash: str) -> Dict[str, Any]:
        """
        Analyze a user's goal performance and suggest adjustments
        Returns comprehensive analysis with actionable insights
        """
        try:
            from models import Goal, Expense
            from db_base import db
            
            # Get user's active daily spending goals
            active_goals = Goal.get_active_for_user(user_id_hash, 'daily_spend_under')
            
            if not active_goals:
                return {
                    'user_id_hash': user_id_hash,
                    'has_goals': False,
                    'recommendation': 'suggest_goal_creation',
                    'message': 'No active spending goals found. Consider setting a daily budget goal!'
                }
            
            goal = active_goals[0]  # Use most recent goal
            goal_amount = float(goal.amount)
            
            # Analyze last 14 days of spending vs goal
            two_weeks_ago = datetime.now(UTC).date() - timedelta(days=14)
            recent_expenses = Expense.query_active().filter(
                Expense.user_id_hash == user_id_hash,
                Expense.date >= two_weeks_ago
            ).all()
            
            # Calculate daily totals
            daily_totals = {}
            for expense in recent_expenses:
                date_key = expense.date.isoformat()
                daily_totals[date_key] = daily_totals.get(date_key, 0) + float(expense.amount)
            
            # Goal performance analysis
            days_with_data = len(daily_totals)
            days_over_goal = sum(1 for total in daily_totals.values() if total > goal_amount)
            days_under_goal = days_with_data - days_over_goal
            
            avg_daily_spend = sum(daily_totals.values()) / max(days_with_data, 1)
            success_rate = (days_under_goal / max(days_with_data, 1)) * 100
            
            # Determine goal adjustment strategy
            analysis = self._generate_goal_insights(
                goal_amount=goal_amount,
                avg_daily_spend=avg_daily_spend,
                success_rate=success_rate,
                days_with_data=days_with_data,
                days_over_goal=days_over_goal
            )
            
            return {
                'user_id_hash': user_id_hash,
                'has_goals': True,
                'current_goal': goal_amount,
                'avg_daily_spend': round(avg_daily_spend, 2),
                'success_rate': round(success_rate, 1),
                'days_analyzed': days_with_data,
                'days_over_goal': days_over_goal,
                'analysis': analysis,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Goal analysis failed for user {user_id_hash}: {e}")
            return {
                'user_id_hash': user_id_hash,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _generate_goal_insights(self, goal_amount: float, avg_daily_spend: float, 
                               success_rate: float, days_with_data: int, days_over_goal: int) -> Dict[str, Any]:
        """Generate intelligent insights and recommendations based on goal performance"""
        
        suggested_amount = 0.0  # Initialize to avoid unbound variable
        
        # Success rate categories
        if success_rate >= 85:
            performance = "excellent"
            insight = f"🎉 Outstanding! You're staying under your ৳{goal_amount:,.0f} goal {success_rate:.0f}% of the time."
            recommendation = "consider_stretch_goal" if avg_daily_spend < goal_amount * 0.7 else "maintain_current"
            
        elif success_rate >= 65:
            performance = "good"
            insight = f"👍 Good progress! You're meeting your ৳{goal_amount:,.0f} goal {success_rate:.0f}% of the time."
            recommendation = "maintain_current"
            
        elif success_rate >= 40:
            performance = "challenging"
            insight = f"🤔 Your ৳{goal_amount:,.0f} goal is challenging - you're over budget {days_over_goal} out of {days_with_data} days."
            # Suggest adjustment to 85% success rate sweet spot
            suggested_amount = avg_daily_spend * 1.1  # 10% buffer above average
            recommendation = "adjust_upward"
            
        else:
            performance = "too_ambitious"
            insight = f"💡 Your ৳{goal_amount:,.0f} goal might be too ambitious. You're averaging ৳{avg_daily_spend:,.0f} daily."
            suggested_amount = avg_daily_spend * 1.15  # 15% buffer for realistic success
            recommendation = "adjust_upward"
        
        # Generate coaching message based on performance
        coaching_message = self._generate_coaching_message(performance, goal_amount, avg_daily_spend, success_rate)
        
        result = {
            'performance': performance,
            'insight': insight,
            'recommendation': recommendation,
            'coaching_message': coaching_message,
            'success_rate': success_rate
        }
        
        # Add suggested goal amount for adjustment cases
        if recommendation == "adjust_upward":
            result['suggested_goal'] = round(suggested_amount, 0)
            result['adjustment_reason'] = f"Targeting 85% success rate based on your ৳{avg_daily_spend:.0f} average"
        elif recommendation == "consider_stretch_goal":
            result['suggested_goal'] = round(goal_amount * 0.9, 0)  # 10% more challenging
            result['adjustment_reason'] = "You're doing great! Ready for a slightly more challenging goal?"
            
        return result
    
    def _generate_coaching_message(self, performance: str, goal_amount: float, 
                                 avg_spend: float, success_rate: float) -> str:
        """Generate personalized coaching messages based on performance"""
        
        messages = {
            "excellent": [
                f"You're crushing your ৳{goal_amount:,.0f} goal! This kind of consistency builds lasting financial habits.",
                f"Fantastic discipline! Staying under budget {success_rate:.0f}% of the time shows real financial mastery.",
                f"Your spending control is impressive. You're building a strong foundation for financial growth!"
            ],
            "good": [
                f"Solid progress on your ৳{goal_amount:,.0f} goal! Small consistent wins lead to big financial changes.",
                f"You're building great habits. {success_rate:.0f}% success rate shows you're getting the hang of budgeting.",
                f"Good momentum! Keep this up and you'll see your financial confidence grow."
            ],
            "challenging": [
                f"Budget goals take practice - you're learning! Consider trying ৳{avg_spend*1.1:.0f} daily for better success.",
                f"Every expert was once a beginner. Your ৳{avg_spend:.0f} average suggests a ৳{avg_spend*1.1:.0f} goal might feel better.",
                f"Goals should challenge you, not overwhelm you. Let's find your sweet spot for consistent wins."
            ],
            "too_ambitious": [
                f"Big goals show ambition! Let's start with ৳{avg_spend*1.15:.0f} daily and build up your success habit.",
                f"The best goal is one you can achieve consistently. Starting with ৳{avg_spend*1.15:.0f} can build momentum.",
                f"Success breeds success. A ৳{avg_spend*1.15:.0f} goal might give you the wins needed to go even lower later."
            ]
        }
        
        import random
        return random.choice(messages.get(performance, messages["good"]))
    
    def should_create_goal_banner(self, analysis: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Determine if a goal-related banner should be created based on analysis"""
        
        if not analysis.get('has_goals'):
            return {
                'type': 'goal_suggestion',
                'title': '🎯 Ready to Set a Spending Goal?',
                'message': 'Daily spending goals help build financial discipline. Start with a comfortable target and build the habit!',
                'action_text': 'Set Daily Goal',
                'action_url': '/challenge',
                'style': 'info'
            }
        
        performance = analysis.get('analysis', {}).get('performance')
        
        if performance == "excellent":
            return {
                'type': 'goal_celebration',
                'title': f"🎉 Goal Mastery: {analysis['success_rate']:.0f}% Success!",
                'message': analysis['analysis']['coaching_message'],
                'action_text': 'View Progress',
                'action_url': '/report',
                'style': 'success'
            }
        
        elif performance == "too_ambitious" and analysis['analysis'].get('suggested_goal'):
            suggested = analysis['analysis']['suggested_goal']
            return {
                'type': 'goal_adjustment',
                'title': f"💡 Goal Suggestion: Try ৳{suggested:,.0f} Daily",
                'message': f"Your current goal might be too challenging. A ৳{suggested:,.0f} target could give you more consistent wins!",
                'action_text': 'Adjust Goal',
                'action_url': f'/challenge?suggest={suggested:.0f}',
                'style': 'warning'
            }
        
        return None

# Global instance for job processing
goal_automation = GoalAutomationEngine()

def process_daily_goal_analysis_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background job processor for daily goal analysis
    Called by Redis job queue for automated goal insights
    """
    try:
        user_id_hash = payload.get('user_id_hash')
        if not user_id_hash:
            raise ValueError("user_id_hash required in payload")
        
        logger.info(f"Processing goal analysis job for user {user_id_hash[:8]}...")
        
        # Run goal analysis
        analysis = goal_automation.analyze_user_goal_performance(user_id_hash)
        
        # Check if we should create a banner based on analysis
        banner_data = goal_automation.should_create_goal_banner(analysis)
        
        if banner_data:
            # Create banner using existing banner system
            from models import Banner
            from db_base import db
            
            # Check for existing goal banners today to avoid spam
            today = datetime.now(UTC).date()
            existing_banner = Banner.query_active().filter(
                Banner.user_id_hash == user_id_hash,
                Banner.banner_type.in_(['goal_suggestion', 'goal_celebration', 'goal_adjustment']),
                func.date(Banner.created_at) == today
            ).first()
            
            if not existing_banner:
                banner = Banner()
                banner.user_id_hash = user_id_hash
                banner.banner_type = banner_data['type']
                banner.title = banner_data['title']
                banner.message = banner_data['message']
                banner.action_text = banner_data['action_text']
                banner.action_url = banner_data['action_url']
                banner.style = banner_data['style']
                banner.priority = 1  # Standard priority
                banner.trigger_data = {
                    'goal_analysis': analysis,
                    'auto_generated': True
                }
                banner.expires_at = datetime.now(UTC) + timedelta(hours=24)
                
                db.session.add(banner)
                db.session.commit()
                
                logger.info(f"Created {banner_data['type']} banner for user {user_id_hash[:8]}")
                analysis['banner_created'] = banner_data['type']
            else:
                logger.info(f"Goal banner already exists for user {user_id_hash[:8]} today")
                analysis['banner_created'] = False
        
        return {
            'status': 'success',
            'analysis': analysis,
            'processed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Goal analysis job failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'processed_at': datetime.utcnow().isoformat()
        }

def schedule_goal_analysis_for_user(user_id_hash: str) -> bool:
    """
    Schedule a goal analysis job for a specific user
    Returns True if job was queued successfully
    """
    try:
        from utils.job_queue import job_queue
        
        if not job_queue or not job_queue.redis_available:
            logger.warning("Job queue not available, skipping goal analysis scheduling")
            return False
        
        job_id = job_queue.enqueue(
            job_type='daily_goal_analysis',
            payload={'user_id_hash': user_id_hash},
            user_id=user_id_hash,
            idempotency_key=f"goal_analysis_{user_id_hash}_{datetime.now(UTC).date()}"
        )
        
        logger.info(f"Scheduled goal analysis job {job_id} for user {user_id_hash[:8]}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to schedule goal analysis for user {user_id_hash}: {e}")
        return False