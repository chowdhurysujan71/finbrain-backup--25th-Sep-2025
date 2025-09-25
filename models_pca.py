"""
PCA (Precision Capture & Audit) Overlay Database Models
Phase 1: Overlay Schema - Additive tables that don't touch core ledger
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Index

from db_base import db


class TransactionEffective(db.Model):
    """
    User-facing truth table - what the user sees after corrections/rules
    Overlay on top of raw expenses table
    """
    __tablename__ = 'transactions_effective'
    
    id = db.Column(db.Integer, primary_key=True)
    tx_id = db.Column(db.String(32), unique=True, nullable=False)  # Canonical transaction ID
    user_id = db.Column(db.String(255), nullable=False)  # SHA-256 hashed user identifier
    
    # Effective values (after corrections/rules)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='BDT')
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100), nullable=True)
    merchant_text = db.Column(db.String(255), nullable=True)
    merchant_id = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    
    # Timing information
    transaction_date = db.Column(db.Date, nullable=False)
    transaction_time = db.Column(db.Time, nullable=True)
    
    # Status and metadata
    status = db.Column(db.String(20), default='active')  # active, voided, superseded
    decided_by = db.Column(db.String(50), nullable=False)  # ai_auto, ai_clarified, user_corrected, rule_applied
    decided_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Link back to raw expense
    raw_expense_id = db.Column(db.Integer, nullable=False)  # Reference to original Expense.id
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_transactions_effective_user_date', 'user_id', 'transaction_date'),
        Index('idx_transactions_effective_tx_id', 'tx_id'),
        Index('idx_transactions_effective_raw_expense', 'raw_expense_id'),
    )
    
    def __repr__(self):
        return f'<TransactionEffective {self.tx_id}: {self.amount} {self.currency} - {self.category}>'

class UserCorrection(db.Model):
    """
    Per-user corrections log - tracks what users have changed
    Preserves correction history for audit transparency
    """
    __tablename__ = 'user_corrections'
    
    id = db.Column(db.Integer, primary_key=True)
    corr_id = db.Column(db.String(32), unique=True, nullable=False)  # Unique correction ID
    tx_id = db.Column(db.String(32), nullable=False)  # Links to TransactionEffective
    user_id = db.Column(db.String(255), nullable=False)  # SHA-256 hashed user identifier
    
    # What was changed
    fields_json = db.Column(JSON, nullable=False)  # {"amount": {"old": 100, "new": 150}, "category": {"old": "food", "new": "entertainment"}}
    reason = db.Column(db.String(255), nullable=True)  # User-provided or detected reason
    correction_type = db.Column(db.String(50), nullable=False)  # manual, ai_suggested, bulk_rule
    
    # Timing and context
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    source_message = db.Column(db.Text, nullable=True)  # Original correction message
    cc_id = db.Column(db.String(32), nullable=True)  # Link to Canonical Command
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_corrections_user_created', 'user_id', 'created_at'),
        Index('idx_user_corrections_tx_id', 'tx_id'),
        Index('idx_user_corrections_corr_id', 'corr_id'),
    )
    
    def __repr__(self):
        return f'<UserCorrection {self.corr_id}: {self.tx_id} by {self.user_id[:8]}...>'

class UserRule(db.Model):
    """
    Per-user categorization and processing rules
    Allows users to teach finbrain their preferences
    """
    __tablename__ = 'user_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.String(32), unique=True, nullable=False)  # Unique rule ID
    user_id = db.Column(db.String(255), nullable=False)  # SHA-256 hashed user identifier
    
    # Rule matching pattern
    pattern_json = db.Column(JSON, nullable=False)  # {"merchant": "starbucks", "text_contains": ["coffee", "latte"]}
    
    # Rule application
    rule_set_json = db.Column(JSON, nullable=False)  # {"category": "coffee", "subcategory": "beverages"}
    
    # Rule metadata
    scope = db.Column(db.String(50), default='future')  # future, historical, both
    confidence = db.Column(db.Float, default=0.9)  # How confident is this rule
    priority = db.Column(db.Integer, default=100)  # Rule application priority
    
    # Timing and usage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_applied = db.Column(db.DateTime, nullable=True)
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_rules_user_active', 'user_id', 'is_active'),
        Index('idx_user_rules_rule_id', 'rule_id'),
    )
    
    def __repr__(self):
        return f'<UserRule {self.rule_id}: {self.user_id[:8]}... priority={self.priority}>'

class InferenceSnapshot(db.Model):
    """
    Canonical Command snapshots for full auditability
    Every message processed gets a snapshot regardless of mode
    """
    __tablename__ = 'inference_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    cc_id = db.Column(db.String(32), unique=True, nullable=False)  # Canonical Command ID
    user_id = db.Column(db.String(255), nullable=False)  # SHA-256 hashed user identifier
    
    # Canonical Command data
    intent = db.Column(db.String(50), nullable=False)
    slots_json = db.Column(JSON, nullable=False)  # Complete CC slots structure
    confidence = db.Column(db.Float, nullable=False)
    decision = db.Column(db.String(20), nullable=False)  # AUTO_APPLY, ASK_ONCE, RAW_ONLY
    clarifier_json = db.Column(JSON, nullable=True)  # Clarification options if needed
    
    # AI metadata
    model_version = db.Column(db.String(100), nullable=False)
    processing_time_ms = db.Column(db.Integer, nullable=True)
    
    # Context and audit
    source_text = db.Column(db.Text, nullable=False)  # Original user message
    ui_note = db.Column(db.Text, nullable=True)  # User-facing response note
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Processing metadata
    pca_mode = db.Column(db.String(20), nullable=False)  # FALLBACK, SHADOW, DRYRUN, ON
    applied = db.Column(db.Boolean, default=False)  # Was this CC actually applied
    error_message = db.Column(db.Text, nullable=True)  # Any processing errors
    
    # Indexes for performance and analytics
    __table_args__ = (
        Index('idx_inference_snapshots_user_created', 'user_id', 'created_at'),
        Index('idx_inference_snapshots_intent_decision', 'intent', 'decision'),
        Index('idx_inference_snapshots_cc_id', 'cc_id'),
        Index('idx_inference_snapshots_confidence', 'confidence'),
    )
    
    def __repr__(self):
        return f'<InferenceSnapshot {self.cc_id}: {self.intent} conf={self.confidence:.2f}>'

# Helper function to generate IDs
def generate_pca_id(prefix: str) -> str:
    """Generate a short, readable ID for PCA entities"""
    import hashlib
    import time
    
    # Use timestamp + random for uniqueness
    unique_string = f"{time.time()}{uuid.uuid4().hex[:8]}"
    hash_digest = hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    
    return f"{prefix}_{hash_digest[:8]}_{hash_digest[8:16]}"