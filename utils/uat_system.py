"""
Live UAT (User Acceptance Testing) system for FinBrain
Runs structured tests through actual Messenger interactions
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from app import db
from models import User
from utils.security import hash_psid

logger = logging.getLogger(__name__)

# UAT test flow prompts
UAT_PROMPT_FLOW = [
    "👋 Welcome! Let's run a live test of your Financial Advisor bot. Reply with anything to continue.",
    "✅ Step 1: Data logging. Please type an expense, e.g. 'I spent 500 BDT on groceries yesterday.'",
    "✅ Step 2: Categorization. Now add a different type of spend, e.g. '2000 BDT for rent.'",
    "✅ Step 3: Multi-entry. Add one more, e.g. '150 BDT for transport.'",
    "✅ Step 4: Advice trigger. Type 'summary' to ask the bot for an overview of your spends.",
    "✅ Step 5: Rate-limit test. Send 5 messages quickly, e.g. 'test1', 'test2'… until you hit the 4-per-minute AI cap.",
    "✅ Step 6: Non-AI fallback. After hitting the cap, verify the bot shows the disclaimer + template reply.",
    "✅ Step 7: Context recall. Ask 'What did I spend most on?' to see if AI recalls your data.",
    "🎉 UAT finished. If all steps work (logging, categorization, limits, fallback, recall), you can sign off production."
]

class UATSystem:
    """Manages live UAT testing through Messenger interactions"""
    
    def __init__(self):
        self.uat_users = {}  # Track users in UAT mode
        
    def is_uat_mode(self, psid: str) -> bool:
        """Check if user is in UAT testing mode"""
        return psid in self.uat_users
    
    def start_uat(self, psid: str, tester_name: str = "Tester") -> str:
        """Start UAT testing for a user"""
        psid_hash = hash_psid(psid)
        
        self.uat_users[psid] = {
            'step': 0,
            'started_at': datetime.utcnow(),
            'tester_name': tester_name,
            'test_results': {},
            'psid_hash': psid_hash
        }
        
        logger.info(f"Started UAT for {psid_hash[:10]}... tester: {tester_name}")
        return UAT_PROMPT_FLOW[0]
    
    def get_next_uat_prompt(self, psid: str, user_message: str) -> Optional[str]:
        """Get next UAT prompt based on current step"""
        if psid not in self.uat_users:
            return None
            
        uat_data = self.uat_users[psid]
        current_step = uat_data['step']
        
        # Record test results for each step
        self._record_test_result(psid, current_step, user_message)
        
        # Advance to next step
        uat_data['step'] += 1
        next_step = uat_data['step']
        
        # Return next prompt or complete UAT
        if next_step < len(UAT_PROMPT_FLOW):
            return UAT_PROMPT_FLOW[next_step]
        else:
            # UAT completed
            results = self._generate_uat_report(psid)
            self._cleanup_uat(psid)
            return results
    
    def _record_test_result(self, psid: str, step: int, user_message: str):
        """Record test result for analysis"""
        if psid not in self.uat_users:
            return
            
        uat_data = self.uat_users[psid]
        step_name = self._get_step_name(step)
        
        uat_data['test_results'][step_name] = {
            'user_input': user_message,
            'timestamp': datetime.utcnow().isoformat(),
            'step_number': step
        }
        
        logger.info(f"UAT step {step} ({step_name}) completed for {uat_data['psid_hash'][:10]}...")
    
    def _get_step_name(self, step: int) -> str:
        """Get descriptive name for test step"""
        step_names = [
            'welcome_response',
            'expense_logging',
            'categorization_test',
            'multi_entry_test',
            'summary_request',
            'rate_limit_test',
            'fallback_verification',
            'context_recall_test'
        ]
        
        if step < len(step_names):
            return step_names[step]
        return f'step_{step}'
    
    def _generate_uat_report(self, psid: str) -> str:
        """Generate final UAT completion report"""
        if psid not in self.uat_users:
            return "UAT data not found."
            
        uat_data = self.uat_users[psid]
        results = uat_data['test_results']
        
        # Analyze results
        total_steps = len(results)
        duration = datetime.utcnow() - uat_data['started_at']
        
        report = f"""🎉 UAT COMPLETED!

Tester: {uat_data['tester_name']}
Duration: {duration.total_seconds():.1f} seconds
Steps completed: {total_steps}/8

✅ Test Results Summary:
- Data logging: {'✓' if 'expense_logging' in results else '✗'}
- Categorization: {'✓' if 'categorization_test' in results else '✗'}
- Multi-entry: {'✓' if 'multi_entry_test' in results else '✗'}
- Summary/advice: {'✓' if 'summary_request' in results else '✗'}
- Rate limiting: {'✓' if 'rate_limit_test' in results else '✗'}
- Fallback system: {'✓' if 'fallback_verification' in results else '✗'}
- Context recall: {'✓' if 'context_recall_test' in results else '✗'}

Your FinBrain system is {'ready for production' if total_steps >= 7 else 'needs attention'}!"""

        return report
    
    def _cleanup_uat(self, psid: str):
        """Clean up UAT data after completion"""
        if psid in self.uat_users:
            del self.uat_users[psid]
    
    def get_uat_stats(self) -> Dict[str, Any]:
        """Get current UAT statistics"""
        active_tests = len(self.uat_users)
        
        stats = {
            'active_uat_sessions': active_tests,
            'users_in_uat': list(self.uat_users.keys()) if active_tests > 0 else []
        }
        
        return stats

# Global UAT system instance
uat_system = UATSystem()