"""
Enhanced conversational AI system that uses user-level memory for organic conversations
Provides intelligent summaries and maintains conversational flow based on user data
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from utils.identity import psid_hash

logger = logging.getLogger(__name__)

class ConversationalAI:
    """AI system that maintains conversational flow using user-level memory"""
    
    def __init__(self):
        self.logger = logger
    
    def get_user_expense_context(self, psid: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user expense context for conversations"""
        from models import Expense
        from app import db
        from utils.identity import psid_hash as ensure_hashed
        from utils.tracer import trace_event
        
        # Use consistent hashing (avoid double-hashing)
        user_id = ensure_hashed(psid)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Trace the lookup
        trace_event("get_expense_context", user_id=user_id, path="legacy", window=days)
        
        self.logger.info(f"Getting expense context for user: {user_id[:16]}... from {cutoff_date}")
        
        try:
            expenses = Expense.query.filter(
                Expense.user_id_hash == user_id,
                Expense.created_at >= cutoff_date
            ).order_by(Expense.created_at.desc()).all()
            
            # Trace the result
            trace_event("expense_context_result", user_id=user_id, found_expenses=len(expenses), path="legacy")
            self.logger.info(f"Found {len(expenses)} expenses for hash {user_id[:16]}...")
            
            if not expenses:
                return {
                    'has_data': False,
                    'total_expenses': 0,
                    'total_amount': 0.0,
                    'categories': {},
                    'recent_expenses': [],
                    'patterns': 'No expense data available'
                }
            
            # Calculate totals and categories
            total_amount = sum(float(exp.amount) for exp in expenses)
            categories = {}
            
            for expense in expenses:
                category = expense.category.lower()
                amount = float(expense.amount)
                
                if category not in categories:
                    categories[category] = {'amount': 0.0, 'count': 0}
                
                categories[category]['amount'] += amount
                categories[category]['count'] += 1
            
            # Get recent expenses for context
            recent_expenses = []
            for expense in expenses[:5]:  # Last 5 expenses
                recent_expenses.append({
                    'amount': float(expense.amount),
                    'description': expense.description,
                    'category': expense.category,
                    'date': expense.created_at.strftime('%m/%d')
                })
            
            # Analyze spending patterns
            top_category = max(categories.items(), key=lambda x: x[1]['amount'])
            patterns = self._analyze_spending_patterns(categories, total_amount, len(expenses))
            
            return {
                'has_data': True,
                'total_expenses': len(expenses),
                'total_amount': total_amount,
                'categories': categories,
                'recent_expenses': recent_expenses,
                'top_category': top_category,
                'patterns': patterns,
                'days_analyzed': days
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user expense context: {e}")
            return {
                'has_data': False,
                'total_expenses': 0,
                'total_amount': 0.0,
                'categories': {},
                'recent_expenses': [],
                'patterns': 'Unable to analyze spending data'
            }
    
    def _analyze_spending_patterns(self, categories: Dict, total_amount: float, total_count: int) -> str:
        """Analyze spending patterns for conversation context"""
        if not categories:
            return "No spending patterns available"
        
        # Find top spending category
        top_cat = max(categories.items(), key=lambda x: x[1]['amount'])
        top_name, top_data = top_cat
        top_percentage = (top_data['amount'] / total_amount) * 100 if total_amount > 0 else 0
        
        # Calculate average per expense
        avg_expense = total_amount / total_count if total_count > 0 else 0
        
        # Build pattern analysis
        patterns = f"Top category: {top_name} ({top_percentage:.0f}% of spending). "
        patterns += f"Average expense: {avg_expense:.0f}. "
        
        if len(categories) >= 3:
            patterns += f"Diverse spending across {len(categories)} categories."
        elif len(categories) == 2:
            patterns += "Spending focused on 2 main categories."
        else:
            patterns += "Spending concentrated in one category."
        
        return patterns
    
    def generate_conversational_response(self, psid_hash: str, user_message: str) -> Tuple[str, str]:
        """EMERGENCY FIX: Generate conversational response that production router expects"""
        return self.handle_conversational_query_with_hash(psid_hash, user_message)
    
    def generate_summary_response_direct(self, psid_hash: str, user_message: str) -> Tuple[str, str]:
        """Generate intelligent summary response based on user data (direct hash access)"""
        from utils.ai_adapter_v2 import production_ai_adapter
        
        # Get user expense context using direct hash
        context = self.get_user_expense_context_direct(psid_hash, days=30)
        
        if not context['has_data']:
            return ("I don't see any expense data to summarize yet. "
                   "Start logging expenses and I'll provide detailed insights!"), "summary_no_data"
        
        # Build context-rich prompt for AI
        summary_prompt = self._build_summary_prompt(context, user_message)
        
        # Generate AI response with user context
        ai_result = generate_with_schema(
            user_text=user_message,
            system_prompt=summary_prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "insights": {"type": "string"},
                    "recommendations": {"type": "string"}
                },
                "required": ["summary", "insights", "recommendations"]
            }
        )
        
        if ai_result["ok"] and "data" in ai_result:
            data = ai_result["data"]
            response = f"{data['summary']}\n\n{data['insights']}\n\n{data['recommendations']}"
            return response, "summary_provided"
        else:
            # Fallback with context data
            return self._generate_fallback_summary(context), "summary_fallback"
    
    def _build_summary_prompt(self, context: Dict, user_message: str) -> str:
        """Build context-rich prompt for AI summary generation"""
        return f"""You are a personal finance assistant providing expense summaries and insights.

User's Expense Data (Last 30 days):
- Total expenses: {context['total_expenses']} transactions
- Total amount: {context['total_amount']:.2f}
- Top category: {context['top_category'][0]} ({context['top_category'][1]['amount']:.2f})
- Spending pattern: {context['patterns']}

Recent Expenses:
{self._format_recent_expenses(context['recent_expenses'])}

Category Breakdown:
{self._format_categories(context['categories'])}

User asked: "{user_message}"

Provide a conversational, insightful response that:
1. Summarizes their spending with specific numbers
2. Gives actionable insights about their patterns
3. Offers personalized recommendations
4. Maintains friendly, engaging tone
5. Keep under 300 words total"""
    
    def _format_recent_expenses(self, recent: List[Dict]) -> str:
        """Format recent expenses for prompt"""
        if not recent:
            return "No recent expenses"
        
        formatted = []
        for exp in recent:
            formatted.append(f"- {exp['date']}: {exp['amount']:.0f} for {exp['description']} ({exp['category']})")
        
        return "\n".join(formatted)
    
    def _format_categories(self, categories: Dict) -> str:
        """Format category breakdown for prompt"""
        if not categories:
            return "No category data"
        
        formatted = []
        for cat, data in sorted(categories.items(), key=lambda x: x[1]['amount'], reverse=True):
            formatted.append(f"- {cat.title()}: {data['amount']:.0f} ({data['count']} transactions)")
        
        return "\n".join(formatted)
    
    def _generate_fallback_summary(self, context: Dict) -> str:
        """Generate fallback summary when AI fails"""
        if not context['has_data']:
            return "No expense data to summarize yet. Start logging expenses for insights!"
        
        total = context['total_amount']
        count = context['total_expenses']
        top_cat = context['top_category']
        
        summary = f"Your spending summary: {count} expenses totaling {total:.0f}. "
        summary += f"Top category is {top_cat[0]} at {top_cat[1]['amount']:.0f}. "
        
        if len(context['categories']) >= 3:
            summary += f"You're spending across {len(context['categories'])} different categories - good diversity!"
        
        return summary
    
    def handle_conversational_query_with_hash(self, psid_hash: str, user_message: str) -> Tuple[str, str]:
        """Handle conversational queries using user-level memory with pre-computed hash"""
        # --- DEFENSIVE TYPE GUARD ---
        if callable(psid_hash) or not isinstance(psid_hash, str):
            import logging
            logging.error("BUG: psid_hash must be string, got %s", type(psid_hash))
            raise ValueError("psid_hash must be a string")
        # --- END GUARD ---
        
        message_lower = user_message.lower()
        
        # Detect summary requests
        if any(word in message_lower for word in ['summary', 'recap', 'overview', 'how much', 'total', 'spent']):
            return self.generate_summary_response_direct(psid_hash, user_message)
        
        # Detect analysis requests
        elif any(word in message_lower for word in ['analyze', 'pattern', 'trend', 'insight', 'advice']):
            return self.generate_analysis_response_direct(psid_hash, user_message)
        
        # General conversational queries
        else:
            return self.generate_contextual_response_direct(psid_hash, user_message)
    
    def handle_conversational_query(self, psid_or_hash: str, user_message: str) -> Tuple[str, str]:
        """Handle conversational queries using user-level memory (legacy method for backwards compatibility)"""
        message_lower = user_message.lower()
        
        # Determine if we have a PSID or hash (hash length is 64 chars)
        if len(psid_or_hash) == 64:  # Already hashed
            user_hash = psid_or_hash
        else:
            user_hash = psid_hash(psid_or_hash)
        
        return self.handle_conversational_query_with_hash(user_hash, user_message)
    
    def generate_analysis_response_direct(self, psid_hash: str, user_message: str) -> Tuple[str, str]:
        """Generate analysis response with user context (direct hash access)"""
        context = self.get_user_expense_context_direct(psid_hash)
        
        if not context['has_data']:
            return ("I need some expense data to provide analysis. "
                   "Log a few expenses and I'll give you detailed insights!"), "analysis_no_data"
        
        # Build analysis-focused prompt
        analysis_prompt = f"""Analyze the user's spending patterns and provide insights.

{self._build_context_summary(context)}

User asked: "{user_message}"

Provide specific financial analysis including:
1. Spending pattern insights
2. Category-specific observations  
3. Actionable recommendations
4. Areas for improvement
Keep response conversational and under 280 characters."""
        
        from utils.ai_adapter_v2 import production_ai_adapter
        
        ai_result = production_ai_adapter.generate_insights({
            "expenses": context.get('recent_expenses', []),
            "total_amount": context.get('total_amount', 0),
            "timeframe": "recent week"
        }, user_id="unknown")
        
        if ai_result and not ai_result.get("failover", True):
            # Handle AI adapter response format
            insights = ai_result.get('insights', [])
            if insights:
                response = ". ".join(insights[:2])  # Use first 2 insights
                return response, "analysis_provided"
            else:
                return str(ai_result.get('response', 'Analysis generated')), "analysis_provided"
        else:
            return self._generate_fallback_analysis(context), "analysis_fallback"
    
    def get_user_expense_context_direct(self, psid_hash: str, days: int = 30) -> Dict[str, Any]:
        """Get user expense context using pre-hashed PSID (no double hashing)"""
        from models import Expense
        from app import db
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        self.logger.info(f"Getting expense context DIRECT for hash: {psid_hash[:16]}... from {cutoff_date}")
        
        try:
            expenses = Expense.query.filter(
                Expense.user_id_hash == psid_hash,
                Expense.created_at >= cutoff_date
            ).order_by(Expense.created_at.desc()).all()
            
            self.logger.info(f"Found {len(expenses)} expenses for direct hash lookup")
            
            if not expenses:
                return {
                    'has_data': False,
                    'total_expenses': 0,
                    'total_amount': 0.0,
                    'categories': {},
                    'recent_expenses': [],
                    'patterns': 'No expense data available'
                }
            
            # Calculate totals and categories
            total_amount = sum(float(exp.amount) for exp in expenses)
            categories = {}
            
            for expense in expenses:
                category = expense.category.lower()
                amount = float(expense.amount)
                
                if category not in categories:
                    categories[category] = {'amount': 0.0, 'count': 0}
                
                categories[category]['amount'] += amount
                categories[category]['count'] += 1
            
            # Get recent expenses for context
            recent_expenses = []
            for expense in expenses[:5]:  # Last 5 expenses
                recent_expenses.append({
                    'amount': float(expense.amount),
                    'description': expense.description,
                    'category': expense.category,
                    'date': expense.created_at.strftime('%m/%d')
                })
            
            # Analyze spending patterns
            top_category = max(categories.items(), key=lambda x: x[1]['amount'])
            patterns = self._analyze_spending_patterns(categories, total_amount, len(expenses))
            
            return {
                'has_data': True,
                'total_expenses': len(expenses),
                'total_amount': total_amount,
                'categories': categories,
                'recent_expenses': recent_expenses,
                'top_category': top_category,
                'patterns': patterns,
                'days_analyzed': days
            }
            
        except Exception as e:
            self.logger.error(f"Error getting direct expense context: {e}")
            return {
                'has_data': False,
                'total_expenses': 0,
                'total_amount': 0.0,
                'categories': {},
                'recent_expenses': [],
                'patterns': 'Unable to analyze spending data'
            }
    
    def generate_contextual_response_direct(self, psid_hash: str, user_message: str) -> Tuple[str, str]:
        """Generate contextual response using user data (direct hash access)"""
        context = self.get_user_expense_context_direct(psid_hash, days=7)  # Recent week
        
        contextual_prompt = f"""Respond to the user query using their expense context for personalization.

{self._build_context_summary(context) if context['has_data'] else 'User is new to expense tracking'}

User message: "{user_message}"

Provide a helpful, personalized response that:
1. References their actual spending when relevant
2. Offers specific advice based on their patterns
3. Maintains conversational flow
4. Stays under 280 characters"""
        
        from utils.ai_adapter_v2 import production_ai_adapter
        
        ai_result = production_ai_adapter.generate_insights({
            "expenses": context.get('recent_expenses', []),
            "total_amount": context.get('total_amount', 0),
            "user_message": user_message,
            "timeframe": "recent week"
        }, user_id="unknown")
        
        if ai_result and not ai_result.get("failover", True):
            # Handle AI adapter response format  
            insights = ai_result.get('insights', [])
            if insights:
                response = insights[0] if insights else "I'm here to help with your finances."
                return response, "contextual_response"
            else:
                return str(ai_result.get('response', 'I can help with your finances.')), "contextual_response"
        else:
            return "I'm here to help with your finances. What would you like to know?", "contextual_fallback"
    
    def _build_context_summary(self, context: Dict) -> str:
        """Build context summary for AI prompts"""
        if not context['has_data']:
            return "User has no expense data yet."
        
        summary = f"User Data: {context['total_expenses']} expenses, {context['total_amount']:.0f} total. "
        summary += f"Top category: {context['top_category'][0]} ({context['top_category'][1]['amount']:.0f}). "
        summary += f"Pattern: {context['patterns']}"
        
        return summary
    
    def _generate_fallback_analysis(self, context: Dict) -> str:
        """Generate fallback analysis when AI fails"""
        if not context['has_data']:
            return "Start tracking expenses for personalized analysis!"
        
        total = context['total_amount']
        top_cat = context['top_category']
        avg = total / context['total_expenses'] if context['total_expenses'] > 0 else 0
        
        return f"Analysis: {context['total_expenses']} transactions, avg {avg:.0f} per expense. {top_cat[0]} is your top category at {top_cat[1]['amount']:.0f}. Consider reviewing this area for savings opportunities."

# Global instance
conversational_ai = ConversationalAI()