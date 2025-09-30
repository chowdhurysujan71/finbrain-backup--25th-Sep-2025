"""
Truth & Safety Guardrails - Zero-Hallucination Response Layer
Ensures all numeric claims are provable and verifiable
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo

from db_base import db
from models import Expense

logger = logging.getLogger(__name__)

# Asia/Dhaka timezone for all date/time operations
DHAKA_TZ = ZoneInfo("Asia/Dhaka")


class TruthLayer:
    """Truth & safety layer for verifiable AI responses"""
    
    @staticmethod
    def build_verify_url(base_path: str, **params) -> str:
        """
        Build a properly encoded verify URL
        
        Args:
            base_path: Base path (e.g., '/history')
            **params: Query parameters to encode
            
        Returns:
            Encoded URL string
        """
        # Remove None values
        clean_params = {k: v for k, v in params.items() if v is not None}
        
        if not clean_params:
            return base_path
        
        query_string = urlencode(clean_params)
        return f"{base_path}?{query_string}"
    
    @staticmethod
    def format_amount(amount: Decimal | float, decimals: int = 2) -> str:
        """
        Format amount consistently with specified decimals
        
        Args:
            amount: Amount to format
            decimals: Number of decimal places (default 2)
            
        Returns:
            Formatted string like "৳450.00"
        """
        return f"৳{float(amount):,.{decimals}f}"
    
    @staticmethod
    def get_dhaka_now() -> datetime:
        """Get current time in Asia/Dhaka timezone"""
        return datetime.now(DHAKA_TZ)
    
    @staticmethod
    def get_dhaka_today() -> date:
        """Get current date in Asia/Dhaka timezone"""
        return TruthLayer.get_dhaka_now().date()
    
    @staticmethod
    def format_timeframe(start_date: date, end_date: date | None = None) -> str:
        """
        Format timeframe display with Asia/Dhaka timezone clarity
        
        Examples:
            - "Today (30 Sep 2025, Asia/Dhaka)"
            - "Yesterday (29 Sep 2025, Asia/Dhaka)"
            - "7-30 Sep 2025 (Asia/Dhaka)"
        """
        today = TruthLayer.get_dhaka_today()
        
        if end_date is None or start_date == end_date:
            # Single day
            if start_date == today:
                return f"Today ({start_date.strftime('%-d %b %Y')}, Asia/Dhaka)"
            elif start_date == today - timedelta(days=1):
                return f"Yesterday ({start_date.strftime('%-d %b %Y')}, Asia/Dhaka)"
            else:
                return f"{start_date.strftime('%-d %b %Y')} (Asia/Dhaka)"
        else:
            # Date range
            if start_date.year == end_date.year and start_date.month == end_date.month:
                # Same month: "7-30 Sep 2025 (Asia/Dhaka)"
                return f"{start_date.day}-{end_date.day} {start_date.strftime('%b %Y')} (Asia/Dhaka)"
            elif start_date.year == end_date.year:
                # Same year: "7 Sep - 3 Oct 2025 (Asia/Dhaka)"
                return f"{start_date.strftime('%-d %b')} - {end_date.strftime('%-d %b %Y')} (Asia/Dhaka)"
            else:
                # Different years: "7 Sep 2024 - 3 Oct 2025 (Asia/Dhaka)"
                return f"{start_date.strftime('%-d %b %Y')} - {end_date.strftime('%-d %b %Y')} (Asia/Dhaka)"
    
    @staticmethod
    def verify_expense_total(user_id_hash: str, start_date: date, end_date: date | None = None) -> Dict[str, Any]:
        """
        Calculate verifiable expense total with full data provenance
        
        Returns:
            {
                'total': Decimal,
                'count': int,
                'timeframe': str,
                'verifiable': True,
                'query_sql': str,  # For debugging/audit
                'verify_url': str  # Direct link to filtered history
            }
        """
        if end_date is None:
            end_date = start_date
        
        try:
            # Calculate total
            result = db.session.query(
                db.func.count(Expense.id),
                db.func.sum(Expense.amount_minor)
            ).filter(
                Expense.user_id_hash == user_id_hash,
                Expense.date >= start_date,
                Expense.date <= end_date,
                Expense.is_deleted.is_(False)  # type: ignore
            ).first()
            
            count = result[0] if result else 0
            total_minor = result[1] if result else 0
            total = Decimal(total_minor or 0) / 100
            
            timeframe = TruthLayer.format_timeframe(start_date, end_date)
            
            # Build verify URL with proper encoding
            verify_url = TruthLayer.build_verify_url(
                '/history',
                start=start_date.isoformat(),
                end=end_date.isoformat()
            )
            
            return {
                'total': float(total),
                'total_formatted': TruthLayer.format_amount(total, decimals=2),
                'count': count,
                'timeframe': timeframe,
                'verifiable': True,
                'verify_url': verify_url,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"verify_expense_total failed: {e}", exc_info=True)
            return {
                'total': 0,
                'count': 0,
                'timeframe': TruthLayer.format_timeframe(start_date, end_date),
                'verifiable': False,
                'error': str(e)
            }
    
    @staticmethod
    def verify_category_breakdown(user_id_hash: str, start_date: date, end_date: date | None = None) -> Dict[str, Any]:
        """
        Calculate verifiable category breakdown with full data provenance
        
        Returns:
            {
                'categories': [{'name': str, 'total': Decimal, 'count': int, 'percentage': float}],
                'timeframe': str,
                'verifiable': True,
                'verify_url': str
            }
        """
        if end_date is None:
            end_date = start_date
        
        try:
            # SQL GROUP BY for performance (as recommended by architect)
            results = db.session.query(
                Expense.category,
                db.func.count(Expense.id).label('count'),
                db.func.sum(Expense.amount_minor).label('total_minor')
            ).filter(
                Expense.user_id_hash == user_id_hash,
                Expense.date >= start_date,
                Expense.date <= end_date,
                Expense.is_deleted.is_(False)  # type: ignore
            ).group_by(Expense.category).all()
            
            # Calculate grand total for percentages
            grand_total = sum(r.total_minor or 0 for r in results)
            
            categories = []
            for result in results:
                total = Decimal(result.total_minor or 0) / 100
                percentage = (float(result.total_minor or 0) / grand_total * 100) if grand_total > 0 else 0
                
                # Build category verify URL with proper encoding
                category_verify_url = TruthLayer.build_verify_url(
                    '/history',
                    cat=result.category,
                    start=start_date.isoformat(),
                    end=end_date.isoformat()
                )
                
                categories.append({
                    'name': result.category,
                    'total': float(total),
                    'total_formatted': TruthLayer.format_amount(total, decimals=2),
                    'count': result.count,
                    'percentage': round(percentage, 1),
                    'verify_url': category_verify_url
                })
            
            # Sort by total (highest first)
            categories.sort(key=lambda x: x['total'], reverse=True)
            
            timeframe = TruthLayer.format_timeframe(start_date, end_date)
            
            # Build overall verify URL
            overall_verify_url = TruthLayer.build_verify_url(
                '/history',
                start=start_date.isoformat(),
                end=end_date.isoformat()
            )
            
            return {
                'categories': categories,
                'timeframe': timeframe,
                'verifiable': True,
                'verify_url': overall_verify_url
            }
            
        except Exception as e:
            logger.error(f"verify_category_breakdown failed: {e}", exc_info=True)
            return {
                'categories': [],
                'timeframe': TruthLayer.format_timeframe(start_date, end_date),
                'verifiable': False,
                'error': str(e)
            }
    
    @staticmethod
    def i_dont_have_that_yet(requested_feature: str, alternative: str | None = None) -> str:
        """
        Generate honest "I don't have that yet" responses
        
        Args:
            requested_feature: What the user asked for
            alternative: Optional suggestion for what they can do instead
            
        Examples:
            - "I don't have budget forecasting yet. I can show you your spending patterns for the last 7 days."
            - "I don't have receipt scanning yet. You can log expenses by typing them in chat."
        """
        base_response = f"I don't have {requested_feature} yet."
        
        if alternative:
            return f"{base_response} {alternative}"
        
        return base_response
    
    @staticmethod
    def add_verify_cta(number_claim: str, verify_url: str) -> str:
        """
        Add 'Tap to verify' CTA to numeric claims
        
        Args:
            number_claim: The numeric claim (e.g., "You spent ৳450 today")
            verify_url: URL to verify the claim
            
        Returns:
            Enhanced claim with CTA (e.g., "You spent ৳450 today [Tap to verify](/history?date=2025-09-30)")
        """
        return f"{number_claim} [Tap to verify]({verify_url})"
    
    @staticmethod
    def wrap_with_provenance(
        claim: str, 
        data_source: Dict[str, Any], 
        confidence: str = "exact"
    ) -> Dict[str, Any]:
        """
        Wrap a claim with full data provenance for audit trails
        
        Args:
            claim: The textual claim
            data_source: The source data (from verify_* methods)
            confidence: 'exact' | 'estimated' | 'uncertain'
            
        Returns:
            {
                'claim': str,
                'provenance': {
                    'verifiable': bool,
                    'confidence': str,
                    'data_source': dict,
                    'verify_url': str
                }
            }
        """
        return {
            'claim': claim,
            'provenance': {
                'verifiable': data_source.get('verifiable', False),
                'confidence': confidence,
                'timeframe': data_source.get('timeframe', ''),
                'verify_url': data_source.get('verify_url', ''),
                'data': data_source
            }
        }
    
    @staticmethod
    def safe_number_response(
        user_id_hash: str,
        question: str,
        start_date: date,
        end_date: date | None = None
    ) -> Dict[str, Any]:
        """
        Generate a safe, verifiable numeric response to user questions
        
        This is the primary method for generating any response with numbers.
        It ensures:
        1. All numbers are backed by actual data
        2. Timeframes are clearly stated with Asia/Dhaka timezone
        3. Verify CTAs are included
        4. "I don't have that yet" for unsupported queries
        
        Args:
            user_id_hash: User identifier
            question: User's question (for intent detection)
            start_date: Start of timeframe
            end_date: End of timeframe (optional)
            
        Returns:
            {
                'answer': str,  # The response text
                'data': dict,   # The underlying verifiable data
                'safe': bool    # True if fully verifiable
            }
        """
        # Detect question intent
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['total', 'spent', 'spend', 'much']):
            # Total spending question
            data = TruthLayer.verify_expense_total(user_id_hash, start_date, end_date)
            
            if not data.get('verifiable'):
                return {
                    'answer': TruthLayer.i_dont_have_that_yet(
                        'spending data for that timeframe',
                        'Try asking about a different date range.'
                    ),
                    'data': data,
                    'safe': False
                }
            
            answer = f"You spent {data['total_formatted']} {data['timeframe']} ({data['count']} expenses)"
            answer_with_cta = TruthLayer.add_verify_cta(answer, data['verify_url'])
            
            return {
                'answer': answer_with_cta,
                'data': data,
                'safe': True
            }
        
        elif any(word in question_lower for word in ['category', 'categories', 'breakdown', 'where']):
            # Category breakdown question
            data = TruthLayer.verify_category_breakdown(user_id_hash, start_date, end_date)
            
            if not data.get('verifiable') or not data.get('categories'):
                return {
                    'answer': TruthLayer.i_dont_have_that_yet(
                        'category breakdown for that timeframe',
                        'Try logging some expenses first.'
                    ),
                    'data': data,
                    'safe': False
                }
            
            # Build category summary
            top_categories = data['categories'][:3]  # Top 3
            category_text = ', '.join([f"{c['name']} {c['total_formatted']}" for c in top_categories])
            
            answer = f"Your spending {data['timeframe']}: {category_text}"
            answer_with_cta = TruthLayer.add_verify_cta(answer, data['verify_url'])
            
            return {
                'answer': answer_with_cta,
                'data': data,
                'safe': True
            }
        
        else:
            # Unsupported question type
            return {
                'answer': TruthLayer.i_dont_have_that_yet(
                    'that type of analysis',
                    'I can show you your total spending or category breakdown.'
                ),
                'data': {},
                'safe': False
            }
