from datetime import UTC, date, datetime

from flask_login import UserMixin
from sqlalchemy import JSON

from db_base import db

# Import PCA overlay models
try:
    from models_pca import (
        InferenceSnapshot,
        TransactionEffective,
        UserCorrection,
        UserRule,
    )
except ImportError:
    # PCA models not available yet
    pass

class Expense(db.Model):
    """Detailed expense log table"""
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False)  # Legacy: kept for backwards compatibility
    user_id_hash = db.Column(db.String(255), nullable=False, index=True)  # SHA-256 hashed user identifier (PRIMARY)
    description = db.Column(db.Text, default='')  # Original expense message
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # Expense amount
    amount_minor = db.Column(db.BigInteger, nullable=False)  # Amount in minor units (e.g., cents)
    category = db.Column(db.String(50), nullable=False)  # AI-categorized expense type
    currency = db.Column(db.String(10), default='৳')  # Currency symbol
    date = db.Column(db.Date, nullable=False, default=date.today)  # Expense date
    time = db.Column(db.Time, nullable=False, default=lambda: datetime.now().time())  # Expense time
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    unique_id = db.Column(db.Text, nullable=False)  # Unique identifier per expense
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Database insertion timestamp
    platform = db.Column(db.String(20), default='messenger')  # Facebook Messenger
    source = db.Column(db.String(20), nullable=False, default='chat')  # Source type for single-writer constraint
    original_message = db.Column(db.Text, default='')  # Full original message
    ai_insights = db.Column(db.Text, default='')  # Future AI insights storage
    mid = db.Column(db.String(255), nullable=True)  # Facebook message ID for idempotency
    correlation_id = db.Column(db.String(36), nullable=True)  # UUID for idempotency across channels
    
    # Expense correction tracking (backwards-compatible)
    superseded_by = db.Column(db.BigInteger, nullable=True)  # ID of expense that supersedes this one
    corrected_at = db.Column(db.DateTime(timezone=True), nullable=True)  # When this expense was corrected
    corrected_reason = db.Column(db.Text, nullable=True)  # Short reason for correction
    
    # Natural Language Processing metadata
    nl_confidence = db.Column(db.Float, nullable=True)  # AI confidence score (0.0-1.0)
    nl_language = db.Column(db.String(20), nullable=True)  # 'bangla', 'english', 'mixed'
    needed_clarification = db.Column(db.Boolean, default=False)  # Whether this expense needed clarification
    
    # Database security trigger bypass
    idempotency_key = db.Column(db.String(255), nullable=True)  # Required by database trigger, format: "api:<uuid>"
    
    # Soft delete support
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)  # When this expense was soft deleted
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)  # Soft delete flag
    
    def soft_delete(self):
        """Soft delete this expense"""
        self.is_deleted = True
        self.deleted_at = datetime.now(UTC)
    
    def restore(self):
        """Restore this expense from soft delete"""
        self.is_deleted = False
        self.deleted_at = None
    
    @classmethod
    def query_active(cls):
        """Query only non-deleted expenses"""
        return cls.query.filter(cls.is_deleted.is_(False))
    
    def __repr__(self):
        return f'<Expense {self.id}: {self.description} - {self.amount}>'

class ExpenseEdit(db.Model):
    """Audit trail for expense corrections and edits"""
    __tablename__ = 'expense_edits'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=False)
    editor_user_id = db.Column(db.String(255), nullable=False)  # User who made the edit
    edited_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Before state
    old_amount = db.Column(db.Numeric(10, 2), nullable=True)
    old_category = db.Column(db.String(50), nullable=True)
    old_memo = db.Column(db.Text, nullable=True)
    
    # After state  
    new_amount = db.Column(db.Numeric(10, 2), nullable=True)
    new_category = db.Column(db.String(50), nullable=True)
    new_memo = db.Column(db.Text, nullable=True)
    
    # Edit metadata
    reason = db.Column(db.Text, nullable=True)
    edit_type = db.Column(db.String(20), nullable=False)  # 'amount', 'category', 'description', 'full_edit'
    checksum_before = db.Column(db.String(64), nullable=True)  # Hash of record state before edit
    checksum_after = db.Column(db.String(64), nullable=True)  # Hash of record state after edit
    
    # Session info for idempotency
    audit_session_id = db.Column(db.String(36), nullable=True)  # UUID for grouping related edits
    client_info = db.Column(JSON, default=dict)  # Browser, IP (hashed), timestamp
    confidence_score = db.Column(db.Float, nullable=True)  # AI confidence when edit was made
    source = db.Column(db.String(20), default='manual_form')  # 'manual_form', 'nl_correction', 'bulk_import'
    
    def __repr__(self):
        return f'<ExpenseEdit {self.id}: Expense {self.expense_id} edited by {self.editor_user_id[:8]}...>'

class User(UserMixin, db.Model):
    """User tracking table"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), unique=True, nullable=False)  # SHA-256 hashed user ID
    
    # Authentication fields
    email = db.Column(db.String(120), unique=True, nullable=True)  # User email (for web auth)
    password_hash = db.Column(db.String(256), nullable=True)  # Password hash (for web auth)
    name = db.Column(db.String(100), nullable=True)  # User name (for web auth)
    
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
    
    # Privacy and legal compliance
    privacy_consent_given = db.Column(db.Boolean, default=False)  # Privacy policy consent
    privacy_consent_at = db.Column(db.DateTime, nullable=True)  # When privacy consent was given
    terms_accepted = db.Column(db.Boolean, default=False)  # Terms of service acceptance
    terms_accepted_at = db.Column(db.DateTime, nullable=True)  # When ToS was accepted
    
    # Growth Metrics - Block 4 Analytics (Silent Data Collection)
    signup_source = db.Column(db.String(20), default='other')  # fb-ad|organic|referral|other
    d1_logged = db.Column(db.Boolean, default=False)  # First expense within 24h of signup
    d3_completed = db.Column(db.Boolean, default=False)  # 3+ expenses within 72h of signup
    reports_requested = db.Column(db.Integer, default=0)  # Count of REPORT generations
    
    # Growth Metrics - Milestone Tracking (User-Visible Nudges)
    last_milestone_date = db.Column(db.Date, nullable=True)  # Last day milestone was fired (daily cap)
    consecutive_days = db.Column(db.Integer, default=0)  # Current streak of consecutive days with logs
    last_log_date = db.Column(db.Date, nullable=True)  # Last day user logged expense (for streak calc)
    
    # Block 6 - 3-Day Challenge Tracking
    challenge_active = db.Column(db.Boolean, default=False)  # Active challenge state
    challenge_start_date = db.Column(db.Date, nullable=True)  # Challenge start date
    challenge_end_date = db.Column(db.Date, nullable=True)  # Challenge end date (start + 2 days)
    challenge_completed = db.Column(db.Boolean, default=False)  # Successfully completed challenge
    challenge_report_sent = db.Column(db.Boolean, default=False)  # Auto-report completion flag
    
    # Soft delete support
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)  # When this user was soft deleted
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)  # Soft delete flag
    
    def soft_delete(self):
        """Soft delete this user"""
        self.is_deleted = True
        self.deleted_at = datetime.now(UTC)
    
    def restore(self):
        """Restore this user from soft delete"""
        self.is_deleted = False
        self.deleted_at = None
    
    @classmethod
    def query_active(cls):
        """Query only non-deleted users"""
        return cls.query.filter(cls.is_deleted.is_(False))
    
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

class UserMilestone(db.Model):
    """User milestone achievement tracking"""
    __tablename__ = 'user_milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), nullable=False, index=True)  # SHA-256 hashed user ID
    milestone_type = db.Column(db.String(20), nullable=False)  # 'streak-3' or '10-logs'
    fired_at = db.Column(db.DateTime, default=datetime.utcnow)  # When milestone was achieved
    daily_count_date = db.Column(db.Date, default=date.today)  # For daily cap enforcement
    
    # Unique constraint: each milestone can only fire once per user
    __table_args__ = (
        db.UniqueConstraint('user_id_hash', 'milestone_type', name='ux_user_milestone_type'),
    )
    
    def __repr__(self):
        return f'<UserMilestone {self.user_id_hash[:8]}...: {self.milestone_type}>'

class ReportFeedback(db.Model):
    """Report feedback tracking for Money Stories"""
    __tablename__ = 'report_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), nullable=False, index=True)  # SHA-256 hashed user ID
    report_context_id = db.Column(db.String(100), nullable=False)  # Unique report identifier
    signal = db.Column(db.String(10), nullable=False)  # 'up' or 'down'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Feedback timestamp
    
    # Idempotency constraint: only one feedback per user per report
    __table_args__ = (
        db.UniqueConstraint('user_id_hash', 'report_context_id', name='ux_user_report_feedback'),
        db.CheckConstraint("signal IN ('up', 'down')", name='ck_feedback_signal'),
    )
    
    def __repr__(self):
        return f'<ReportFeedback {self.user_id_hash[:8]}...: {self.signal}>'

class TelemetryEvent(db.Model):
    """Growth telemetry events tracking"""
    __tablename__ = 'telemetry_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # expense_logged, expense_edited, etc.
    user_id_hash = db.Column(db.String(64), nullable=True, index=True)  # Hashed user identifier
    event_data = db.Column(JSON, default=dict)  # Event-specific data as JSON
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TelemetryEvent {self.event_type} - {self.user_id_hash[:8] if self.user_id_hash else "anon"}>'

class GrowthCounter(db.Model):
    """Running totals for growth metrics"""
    __tablename__ = 'growth_counters'
    
    id = db.Column(db.Integer, primary_key=True)
    counter_name = db.Column(db.String(50), unique=True, nullable=False)  # total_expenses, total_reports, etc.
    counter_value = db.Column(db.BigInteger, default=0, nullable=False)  # Current counter value
    last_updated = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GrowthCounter {self.counter_name}: {self.counter_value}>'

class PendingExpense(db.Model):
    """Temporary storage for expenses awaiting user clarification"""
    __tablename__ = 'pending_expenses'
    
    pending_id = db.Column(db.String(255), primary_key=True)  # Format: {user_hash}_{mid}_{timestamp}
    user_id_hash = db.Column(db.String(255), nullable=False, index=True)  # SHA-256 hashed user identifier
    amount_minor = db.Column(db.BigInteger, nullable=False)  # Amount in minor units (cents)
    currency = db.Column(db.String(10), nullable=False, default='BDT')  # Currency code
    description = db.Column(db.Text, nullable=False)  # Expense description
    suggested_category = db.Column(db.String(50), nullable=True)  # AI's suggested category
    original_text = db.Column(db.Text, nullable=False)  # Original user input
    item = db.Column(db.String(255), nullable=False)  # The main expense item
    mid = db.Column(db.String(255), nullable=True)  # Message ID for tracking
    options_json = db.Column(db.Text, nullable=False)  # JSON serialized clarification options
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)  # TTL: 10 minutes from creation
    
    def __repr__(self):
        return f'<PendingExpense {self.pending_id}: {self.item} - ৳{self.amount_minor/100:.0f}>'
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired pending expenses"""
        from datetime import timezone
        now = datetime.now(UTC)
        expired_count = db.session.query(cls).filter(cls.expires_at < now).delete()
        if expired_count > 0:
            db.session.commit()
        return expired_count
    
    @classmethod
    def find_by_user(cls, user_id_hash: str):
        """Find active pending expense for user"""
        from datetime import timezone
        now = datetime.now(UTC)
        return db.session.query(cls).filter(
            cls.user_id_hash == user_id_hash,
            cls.expires_at > now
        ).first()
    
    def to_dict(self):
        """Convert to dictionary format for compatibility with existing code"""
        import json
        return {
            'user_hash': self.user_id_hash,
            'original_text': self.original_text,
            'amount': self.amount_minor / 100.0,  # Convert back to major units
            'item': self.item,
            'mid': self.mid,
            'options': json.loads(self.options_json) if self.options_json else [],
            'created_at': self.created_at,
            'expires_at': self.expires_at
        }

class Banner(db.Model):
    """In-app nudges and banners for web-only interface"""
    __tablename__ = 'banners'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), nullable=False, index=True)  # SHA-256 hashed user identifier
    
    # Banner content and configuration
    banner_type = db.Column(db.String(50), nullable=False)  # 'spending_alert', 'streak_reminder', 'category_tip', 'milestone'
    title = db.Column(db.String(200), nullable=False)  # Banner title/headline
    message = db.Column(db.Text, nullable=False)  # Banner message content
    action_text = db.Column(db.String(100), nullable=True)  # Optional CTA button text
    action_url = db.Column(db.String(500), nullable=True)  # Optional CTA URL or route
    
    # Display configuration
    priority = db.Column(db.Integer, default=5, nullable=False)  # 1=highest, 10=lowest priority
    style = db.Column(db.String(20), default='info')  # 'info', 'warning', 'success', 'error'
    dismissible = db.Column(db.Boolean, default=True, nullable=False)  # Can user dismiss?
    auto_hide_seconds = db.Column(db.Integer, nullable=True)  # Auto-hide after N seconds (null = manual dismiss)
    
    # Trigger metadata for spending alerts
    trigger_data = db.Column(JSON, default=dict)  # {amount: 1500, threshold: 1000, period: 'daily'}
    context_expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)  # Related expense if applicable
    
    # State tracking
    shown_count = db.Column(db.Integer, default=0, nullable=False)  # How many times shown
    last_shown_at = db.Column(db.DateTime, nullable=True)  # When last displayed
    dismissed_at = db.Column(db.DateTime, nullable=True)  # When user dismissed (null = still active)
    clicked_at = db.Column(db.DateTime, nullable=True)  # When user clicked action (null = not clicked)
    
    # Lifecycle timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Banner expiry (null = no expiry)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Soft delete support
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    
    # Constraint: active banners should not exceed reasonable limits per user
    __table_args__ = (
        db.CheckConstraint("priority >= 1 AND priority <= 10", name='ck_banner_priority_range'),
        db.CheckConstraint("style IN ('info', 'warning', 'success', 'error')", name='ck_banner_style'),
        db.CheckConstraint("banner_type IN ('spending_alert', 'streak_reminder', 'category_tip', 'milestone', 'onboarding', 'feature_tip', 'goal_setting', 'goal_celebration', 'goal_adjustment', 'goal_suggestion', 'goal_achievement')", name='ck_banner_type'),
        db.Index('ix_banners_user_active', 'user_id_hash', 'is_deleted', 'dismissed_at'),
        db.Index('ix_banners_priority_created', 'priority', 'created_at'),
    )
    
    def soft_delete(self):
        """Soft delete this banner"""
        self.is_deleted = True
        self.deleted_at = datetime.now(UTC)
    
    def restore(self):
        """Restore this banner from soft delete"""
        self.is_deleted = False
        self.deleted_at = None
    
    @classmethod
    def query_active(cls):
        """Query only non-deleted, non-dismissed banners"""
        return cls.query.filter(
            cls.is_deleted.is_(False),
            cls.dismissed_at.is_(None)
        )
    
    @classmethod
    def get_active_for_user(cls, user_id_hash: str, limit: int = 5):
        """Get active banners for a user ordered by priority"""
        from datetime import timezone
        now = datetime.now(UTC)
        return cls.query_active().filter(
            cls.user_id_hash == user_id_hash,
            db.or_(cls.expires_at.is_(None), cls.expires_at > now)
        ).order_by(cls.priority.asc(), cls.created_at.desc()).limit(limit).all()
    
    def mark_shown(self):
        """Mark banner as shown (increment counter)"""
        self.shown_count += 1
        self.last_shown_at = datetime.utcnow()
    
    def dismiss(self):
        """Mark banner as dismissed by user"""
        self.dismissed_at = datetime.utcnow()
    
    def click_action(self):
        """Mark banner action as clicked"""
        self.clicked_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if banner is currently active and should be shown"""
        if self.is_deleted or self.dismissed_at:
            return False
        
        now = datetime.now(UTC)
        if self.expires_at and self.expires_at <= now:
            return False
        
        return True
    
    def to_dict(self):
        """Convert banner to dictionary for API responses"""
        return {
            'id': self.id,
            'banner_type': self.banner_type,
            'title': self.title,
            'message': self.message,
            'action_text': self.action_text,
            'action_url': self.action_url,
            'priority': self.priority,
            'style': self.style,
            'dismissible': self.dismissible,
            'auto_hide_seconds': self.auto_hide_seconds,
            'trigger_data': self.trigger_data or {},
            'context_expense_id': self.context_expense_id,
            'shown_count': self.shown_count,
            'last_shown_at': self.last_shown_at.isoformat() if self.last_shown_at else None,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active()
        }
    
    def __repr__(self):
        return f'<Banner {self.id}: {self.banner_type} for {self.user_id_hash[:8]}...>'

class Goal(db.Model):
    """Goal tracking table for budget goals and financial targets"""
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id_hash = db.Column(db.String(255), nullable=False, index=True)  # SHA-256 hashed user identifier
    type = db.Column(db.String(50), nullable=False, index=True)  # 'daily_spend_under', etc.
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Goal amount
    currency = db.Column(db.String(3), nullable=False)  # 'BDT', 'USD', etc.
    start_date = db.Column(db.Date, nullable=False, default=date.today)  # Goal start date
    status = db.Column(db.String(20), nullable=False, default='active')  # 'active', 'inactive'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ensure at most one active goal per type per user
    __table_args__ = (
        db.Index('ix_goals_user_type_status', 'user_id_hash', 'type', 'status'),
        db.Index('ux_goals_user_type_active', 'user_id_hash', 'type', unique=True, 
                 postgresql_where=db.text("status = 'active'")),  # Partial unique index for active goals
        db.CheckConstraint("status IN ('active', 'inactive')", name='ck_goals_status'),
    )
    
    @classmethod
    def get_active_for_user(cls, user_id_hash: str, goal_type: str | None = None):
        """Get active goals for a user, optionally filtered by type"""
        query = cls.query.filter(
            cls.user_id_hash == user_id_hash,
            cls.status == 'active'
        )
        if goal_type:
            query = query.filter(cls.type == goal_type)
        return query.all()
    
    @classmethod
    def get_or_create_daily_goal(cls, user_id_hash: str, amount: float, currency: str = 'BDT'):
        """Get existing daily goal or create new one (thread-safe upsert)"""
        from sqlalchemy.exc import IntegrityError
        
        try:
            # Attempt to create new goal directly - let unique constraint handle duplicates
            new_goal = cls(
                user_id_hash=user_id_hash,
                type='daily_spend_under',
                amount=amount,
                currency=currency,
                status='active'
            )
            db.session.add(new_goal)
            db.session.flush()  # Force constraint check before commit
            return new_goal
            
        except IntegrityError:
            # Unique constraint violation - active goal already exists
            db.session.rollback()
            
            # Deactivate existing goal and create new one in a nested transaction
            with db.session.begin_nested():
                # Lock the existing active goal
                existing = cls.query.filter(
                    cls.user_id_hash == user_id_hash,
                    cls.type == 'daily_spend_under',
                    cls.status == 'active'
                ).with_for_update().first()
                
                if existing:
                    existing.status = 'inactive'
                    existing.updated_at = datetime.utcnow()
                    db.session.flush()
                
                # Create new goal
                new_goal = cls(
                    user_id_hash=user_id_hash,
                    type='daily_spend_under',
                    amount=amount,
                    currency=currency,
                    status='active'
                )
                db.session.add(new_goal)
                db.session.flush()
                
                # Context manager will commit automatically
                return new_goal
    
    def deactivate(self):
        """Deactivate this goal"""
        self.status = 'inactive'
        self.updated_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert goal to dictionary for API responses"""
        return {
            'id': self.id,
            'type': self.type,
            'amount': float(self.amount),
            'currency': self.currency,
            'start_date': self.start_date.isoformat(),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Goal {self.id}: {self.type} {self.amount} {self.currency} for {self.user_id_hash[:8]}...>'
