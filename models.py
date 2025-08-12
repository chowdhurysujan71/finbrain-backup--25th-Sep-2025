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
    daily_message_count = db.Column(db.Integer, default=0)  # Messages today
    hourly_message_count = db.Column(db.Integer, default=0)  # Messages this hour
    last_daily_reset = db.Column(db.Date, default=date.today)  # Last daily counter reset
    last_hourly_reset = db.Column(db.DateTime, default=datetime.utcnow)  # Last hourly counter reset
    
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
