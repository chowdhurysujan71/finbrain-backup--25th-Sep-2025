"""
AI Contamination Monitor: Detect cross-user data contamination in AI responses
"""
import logging
import hashlib
from typing import Dict, Any, Set, List
from datetime import datetime

logger = logging.getLogger(__name__)

class AIContaminationMonitor:
    """Monitor AI responses for cross-user data contamination"""
    
    def __init__(self):
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        self.response_fingerprints: Dict[str, str] = {}
    
    def log_request(self, user_id: str, expenses_data: Dict[str, Any]) -> str:
        """Log an AI request and return a request ID"""
        request_id = f"{user_id[:8]}_{datetime.now().isoformat()}"
        
        # Extract key data points for contamination detection
        amounts = []
        categories = []
        
        for expense in expenses_data.get('expenses', []):
            amounts.append(float(expense.get('total', 0)))
            categories.append(expense.get('category', ''))
        
        self.active_requests[request_id] = {
            'user_id': user_id,
            'amounts': sorted(amounts),  # Sorted for comparison
            'categories': sorted(categories),
            'total_amount': expenses_data.get('total_amount', 0),
            'expense_count': len(expenses_data.get('expenses', [])),
            'timestamp': datetime.now()
        }
        
        logger.info(f"AI request logged: {request_id} user={user_id[:8]}... amounts={len(amounts)} categories={len(set(categories))}")
        return request_id
    
    def check_response(self, request_id: str, response_text: str) -> Dict[str, Any]:
        """Check AI response for contamination and log results"""
        if request_id not in self.active_requests:
            return {"status": "unknown_request", "contamination": False}
        
        request_data = self.active_requests[request_id]
        user_id = request_data['user_id']
        
        # Create response fingerprint
        response_hash = hashlib.md5(response_text.encode()).hexdigest()
        
        contamination_issues = []
        
        # Check for amounts from other users
        other_users_amounts = []
        for other_req_id, other_data in self.active_requests.items():
            if other_data['user_id'] != user_id:
                other_users_amounts.extend(other_data['amounts'])
        
        # Scan response for foreign amounts
        for amount in other_users_amounts:
            if str(int(amount)) in response_text or f"৳{amount:,.0f}" in response_text:
                contamination_issues.append(f"Response contains amount {amount} from different user")
        
        # Check for identical responses (suspicious)
        for prev_req_id, prev_fingerprint in self.response_fingerprints.items():
            if prev_fingerprint == response_hash and prev_req_id != request_id:
                prev_user = self.active_requests.get(prev_req_id, {}).get('user_id', 'unknown')
                if prev_user != user_id:
                    contamination_issues.append(f"Identical response to different user {prev_user[:8]}...")
        
        # Log response fingerprint
        self.response_fingerprints[request_id] = response_hash
        
        # Clean up old requests (keep last 100)
        if len(self.active_requests) > 100:
            oldest_keys = sorted(self.active_requests.keys())[:50]
            for key in oldest_keys:
                del self.active_requests[key]
                if key in self.response_fingerprints:
                    del self.response_fingerprints[key]
        
        result = {
            "status": "checked",
            "contamination": len(contamination_issues) > 0,
            "issues": contamination_issues,
            "response_hash": response_hash
        }
        
        if contamination_issues:
            logger.error(f"🚨 AI CONTAMINATION DETECTED for user {user_id[:8]}...: {contamination_issues}")
        else:
            logger.info(f"✅ AI response clean for user {user_id[:8]}...")
        
        return result

# Global monitor instance
ai_contamination_monitor = AIContaminationMonitor()