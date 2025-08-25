from app import db
from datetime import datetime, date, time
from sqlalchemy import JSON

class Expense(db.Model):
    """Detailed expense log table"""
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False)  # SHA-256 hashed user identifier
    description = db.Column(db.Text, default='')  # Original expense message
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # Expense amount
    category = db.Column(db.String(50), nullable=False)  # AI-categorized expense type
    currency = db.Column(db.String(10), default='৳')  # Currency symbol
    date = db.Column(db.Date, nullable=False, default=date.today)  # Expense date
    time = db.Column(db.Time, nullable=False, default=lambda: datetime.now().time())  # Expense time
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    unique_id = db.Column(db.Text, nullable=False)  # Unique identifier per expense
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Database insertion timestamp
    platform = db.Column(db.String(20), default='messenger')  # Facebook Messenger
    original_message = db.Column(db.Text, default='')  # Full original message
    ai_insights = db.Column(db.Text, default='')  # Future AI insights storage
    mid = db.Column(db.String(255), nullable=True)  # Facebook message ID for idempotency
    
    # Expense correction tracking (backwards-compatible)
    superseded_by = db.Column(db.BigInteger, nullable=True)  # ID of expense that supersedes this one
    corrected_at = db.Column(db.DateTime(timezone=True), nullable=True)  # When this expense was corrected
    corrected_reason = db.Column(db.Text, nullable=True)  # Short reason for correction
    
    def __repr__(self):
        return f'<Expense {self.id}: {self.description} - {self.amount}>'

class User(db.Model):
    """User tracking table"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), unique=True, nullable=False)  # SHA-256 hashed user ID
    platform = db.Column(db.String(20), nullable=False)  # Facebook Messenger
    total_expenses = db.Column(db.Numeric(12, 2), default=0)  # Lifetime total expenses
    expense_count = db.Column(db.Integer, default=0)  # Total number of expenses
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # User first interaction
    last_interaction = db.Column(db.DateTime, default=datetime.utcnow)  # Last message timestamp
    last_user_message_at = db.Column(db.DateTime, default=datetime.utcnow)  # 24-hour policy window
    daily_message_count = db.Column(db.Integer, default=0)  # Messages today
    hourly_message_count = db.Column(db.Integer, default=0)  # Messages this hour
    last_daily_reset = db.Column(db.Date, default=date.today)  # Last daily counter reset
    last_hourly_reset = db.Column(db.DateTime, default=datetime.utcnow)  # Last hourly counter reset
    
    # Engagement and onboarding fields
    is_new = db.Column(db.Boolean, default=True)  # New user flag
    has_completed_onboarding = db.Column(db.Boolean, default=False)  # Onboarding completion
    onboarding_step = db.Column(db.Integer, default=0)  # Current onboarding step
    interaction_count = db.Column(db.Integer, default=0)  # Total interactions for habit formation
    first_name = db.Column(db.String(100), default='')  # User's first name for personalization
    
    # User preferences from onboarding (AI-adaptive)
    income_range = db.Column(db.String(50), default='')  # Income bracket
    spending_categories = db.Column(JSON, default=list)  # Array of spending categories
    primary_category = db.Column(db.String(50), default='')  # Main spending category
    focus_area = db.Column(db.String(50), default='')  # saving/budgeting/investment
    additional_info = db.Column(JSON, default=dict)  # Flexible AI-extracted data
    preferences = db.Column(JSON, default=dict)  # Additional user preferences
    
    # Smart reminder system (23-hour compliance)
    reminder_scheduled_for = db.Column(db.DateTime, nullable=True)  # Next reminder time
    reminder_preference = db.Column(db.String(20), default='none')  # 'none', 'daily', 'weekly'
    last_reminder_sent = db.Column(db.DateTime, nullable=True)  # Last reminder timestamp
    
    def to_dict(self):
        """Convert user to dictionary for AI processing"""
        return {
            'id': self.id,
            'user_id_hash': self.user_id_hash,
            'first_name': self.first_name,
            'is_new': self.is_new,
            'onboarding_step': self.onboarding_step,
            'has_completed_onboarding': self.has_completed_onboarding,
            'income_range': self.income_range,
            'spending_categories': self.spending_categories or [],
            'primary_category': self.primary_category,
            'focus_area': self.focus_area,
            'additional_info': self.additional_info or {},
            'preferences': self.preferences or {},
            'interaction_count': self.interaction_count,
            'last_interaction': self.last_interaction,
            'platform': self.platform
        }
    
    def update_from_dict(self, data: dict):
        """Update user from dictionary (AI-friendly)"""
        for key, value in data.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
    
    def __repr__(self):
        return f'<User {self.user_id_hash}: {self.platform}>'

class MonthlySummary(db.Model):
    """Monthly analytics table"""
    __tablename__ = 'monthly_summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), nullable=False)  # SHA-256 hashed user ID
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # Monthly total
    expense_count = db.Column(db.Integer, nullable=False, default=0)  # Monthly expense count
    categories = db.Column(JSON, default=dict)  # Category breakdown
    ai_insights = db.Column(db.Text, default='')  # Monthly insights
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Summary creation
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Last update
    
    def __repr__(self):
        return f'<MonthlySummary {self.user_id_hash}: {self.month} - {self.total_amount}>'

class RateLimit(db.Model):
    """Rate limiting tracking table"""
    __tablename__ = 'rate_limits'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    daily_count = db.Column(db.Integer, default=0)
    hourly_count = db.Column(db.Integer, default=0)
    last_daily_reset = db.Column(db.Date, default=date.today)
    last_hourly_reset = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<RateLimit {self.user_id_hash}: {self.platform}>'
