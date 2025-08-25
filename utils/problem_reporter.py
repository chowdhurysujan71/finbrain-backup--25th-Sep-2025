"""
Problem Reporter System
Logs user-reported issues to prevent them from escalating to negative reviews or support DMs
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from models import db, User

logger = logging.getLogger(__name__)

class ProblemReporter:
    """Handles user problem reports and ticket logging"""
    
    def __init__(self):
        self.ticket_counter = 0
        
    def log_problem_ticket(self, user_hash: str, user_message: str, context: Dict[str, Any] = None) -> str:
        """
        Log a problem ticket from user report
        
        Args:
            user_hash: User's PSID hash
            user_message: User's description of the problem
            context: Additional context (last action, error, etc.)
            
        Returns:
            Ticket ID for reference
        """
        try:
            # Generate ticket ID
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self.ticket_counter += 1
            ticket_id = f"FB_{timestamp}_{self.ticket_counter:03d}"
            
            # Get user info
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            user_info = {
                'user_hash': user_hash,
                'onboarding_step': user.onboarding_step if user else 'unknown',
                'created_at': user.created_at.isoformat() if user and user.created_at else 'unknown'
            }
            
            # Build ticket data
            ticket_data = {
                'ticket_id': ticket_id,
                'timestamp': datetime.utcnow().isoformat(),
                'user_message': user_message,
                'user_info': user_info,
                'context': context or {},
                'status': 'open',
                'priority': self._determine_priority(user_message),
                'category': self._categorize_problem(user_message)
            }
            
            # Log to file for review
            self._write_ticket_to_file(ticket_data)
            
            # Log for immediate monitoring
            logger.warning(f"PROBLEM_TICKET ticket_id={ticket_id} user={user_hash[:8]} category={ticket_data['category']} priority={ticket_data['priority']}")
            
            return ticket_id
            
        except Exception as e:
            logger.error(f"Failed to log problem ticket: {e}")
            return f"ERR_{datetime.utcnow().strftime('%H%M%S')}"
    
    def _determine_priority(self, message: str) -> str:
        """Determine ticket priority based on message content"""
        message_lower = message.lower()
        
        # High priority keywords
        high_priority = ['crash', 'error', 'broken', 'not working', 'can\'t log', 'lost money', 'wrong amount']
        
        # Medium priority keywords  
        medium_priority = ['slow', 'confusing', 'unclear', 'suggestion', 'feature']
        
        if any(keyword in message_lower for keyword in high_priority):
            return 'high'
        elif any(keyword in message_lower for keyword in medium_priority):
            return 'medium'
        else:
            return 'low'
    
    def _categorize_problem(self, message: str) -> str:
        """Categorize the problem type"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['expense', 'money', 'amount', 'log']):
            return 'expense_logging'
        elif any(word in message_lower for word in ['slow', 'timeout', 'loading']):
            return 'performance'
        elif any(word in message_lower for word in ['confusing', 'unclear', 'understand']):
            return 'ux_confusion'
        elif any(word in message_lower for word in ['crash', 'error', 'broken']):
            return 'technical_error'
        else:
            return 'general'
    
    def _write_ticket_to_file(self, ticket_data: Dict[str, Any]) -> None:
        """Write ticket to local file for review"""
        try:
            # Create tickets directory if it doesn't exist
            tickets_dir = "/tmp/finbrain_tickets"
            os.makedirs(tickets_dir, exist_ok=True)
            
            # Write ticket to individual file
            ticket_file = f"{tickets_dir}/{ticket_data['ticket_id']}.json"
            with open(ticket_file, 'w') as f:
                json.dump(ticket_data, f, indent=2)
            
            # Also append to daily log
            daily_log = f"{tickets_dir}/tickets_{datetime.utcnow().strftime('%Y%m%d')}.log"
            with open(daily_log, 'a') as f:
                f.write(f"{ticket_data['timestamp']} | {ticket_data['ticket_id']} | {ticket_data['priority']} | {ticket_data['category']} | {ticket_data['user_message'][:100]}\n")
                
        except Exception as e:
            logger.error(f"Failed to write ticket to file: {e}")

# Global instance
problem_reporter = ProblemReporter()

def report_problem(user_hash: str, problem_description: str, last_action: str = None) -> str:
    """
    Report a user problem - main entry point
    
    Args:
        user_hash: User's PSID hash
        problem_description: User's description of the issue
        last_action: What the user was trying to do
        
    Returns:
        Ticket ID for tracking
    """
    context = {}
    if last_action:
        context['last_action'] = last_action
    
    ticket_id = problem_reporter.log_problem_ticket(user_hash, problem_description, context)
    
    # Log structured event for monitoring
    logger.info(f"USER_PROBLEM_REPORTED ticket_id={ticket_id} user={user_hash[:8]} description='{problem_description[:50]}...'")
    
    return ticket_id

def get_problem_report_response(ticket_id: str) -> str:
    """Get user-facing response after problem is reported"""
    return (
        f"🎫 Thanks for reporting this! We've logged ticket #{ticket_id} and will look into it.\n\n"
        "Your feedback helps us catch issues early and improve finbrain for everyone. "
        "You can continue using the app normally - we'll fix this behind the scenes."
    )

# For monitoring/admin purposes
def get_ticket_stats() -> Dict[str, Any]:
    """Get statistics about reported problems"""
    try:
        tickets_dir = "/tmp/finbrain_tickets"
        if not os.path.exists(tickets_dir):
            return {'total_tickets': 0, 'message': 'No tickets directory found'}
        
        ticket_files = [f for f in os.listdir(tickets_dir) if f.endswith('.json')]
        
        stats = {
            'total_tickets': len(ticket_files),
            'latest_tickets': ticket_files[-5:] if ticket_files else [],
            'tickets_today': 0
        }
        
        # Count today's tickets
        today = datetime.utcnow().strftime('%Y%m%d')
        for filename in ticket_files:
            if today in filename:
                stats['tickets_today'] += 1
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get ticket stats: {e}")
        return {'error': str(e)}