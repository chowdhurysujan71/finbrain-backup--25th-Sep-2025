"""
Canonical Command (CC) Schema and Validation
Deterministic JSON structure for PCA system
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

class CCIntent(Enum):
    """Valid Canonical Command Intents"""
    LOG_EXPENSE = "LOG_EXPENSE"
    CORRECT = "CORRECT"
    RELABEL = "RELABEL"
    VOID = "VOID"
    QUERY = "QUERY"
    TRANSFER_BUDGET = "TRANSFER_BUDGET"
    REFUND = "REFUND"
    SUBSCRIPTION_ACTION = "SUBSCRIPTION_ACTION"
    HELP = "HELP"

class CCDecision(Enum):
    """Valid Canonical Command Decisions"""
    AUTO_APPLY = "AUTO_APPLY"
    ASK_ONCE = "ASK_ONCE"
    RAW_ONLY = "RAW_ONLY"

class ClarifierType(Enum):
    """Valid Clarifier Types"""
    CATEGORY_PICK = "category_pick"
    WHICH_OBJECT = "which_object"
    TIME_CONFIRM = "time_confirm"
    NONE = "none"

@dataclass
class CCSlots:
    """Canonical Command Slots - structured data extraction"""
    # Basic expense fields
    amount: Optional[float] = None
    currency: Optional[str] = None
    time_expr: Optional[str] = None
    time_abs: Optional[str] = None
    merchant_text: Optional[str] = None
    merchant_id: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    account: Optional[str] = None
    person: Optional[str] = None
    period: Optional[str] = None
    note: Optional[str] = None
    
    # Multi-item support
    items: Optional[List[Dict[str, Any]]] = None
    
    # Correction targeting
    target: Optional[Dict[str, Any]] = None
    pattern: Optional[Dict[str, Any]] = None
    rule_set: Optional[Dict[str, Any]] = None
    
    # Special actions
    subscription_action: Optional[str] = None
    transfer: Optional[Dict[str, Any]] = None

@dataclass
class CCClarifier:
    """Canonical Command Clarifier for ambiguous inputs"""
    type: str = "none"
    options: Optional[List[str]] = None
    prompt: str = ""
    
    def __post_init__(self):
        if self.options is None:
            self.options = []

@dataclass
class CanonicalCommand:
    """Complete Canonical Command structure"""
    schema_version: str = "pca-v1.1"  # Updated for overlay system
    cc_id: str = ""
    schema_hash: str = "pca-v1.1-cc-keys"  # Static integrity marker
    user_id: str = ""
    intent: str = ""
    slots: Optional[CCSlots] = None
    confidence: float = 0.0
    decision: str = ""
    clarifier: Optional[CCClarifier] = None
    source_text: str = ""
    model_version: str = ""
    ui_note: str = ""
    
    def __post_init__(self):
        if self.slots is None:
            self.slots = CCSlots()
        if self.clarifier is None:
            self.clarifier = CCClarifier()
        if not self.schema_hash:
            self.schema_hash = self._generate_schema_hash()
    
    def _generate_schema_hash(self) -> str:
        """Generate stable hash of schema structure"""
        from utils.pca_flags import get_schema_hash
        return get_schema_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CanonicalCommand':
        """Create from dictionary"""
        # Extract nested objects
        slots_data = data.get('slots', {})
        clarifier_data = data.get('clarifier', {})
        
        # Create slots object
        slots = CCSlots(**slots_data) if slots_data else CCSlots()
        
        # Create clarifier object
        clarifier = CCClarifier(
            type=clarifier_data.get('type', 'none'),
            options=clarifier_data.get('options', []),
            prompt=clarifier_data.get('prompt', '')
        )
        
        # Create main object
        return cls(
            schema_version=data.get('schema_version', 'pca-v1'),
            cc_id=data.get('cc_id', ''),
            schema_hash=data.get('schema_hash', ''),
            user_id=data.get('user_id', ''),
            intent=data.get('intent', ''),
            slots=slots,
            confidence=data.get('confidence', 0.0),
            decision=data.get('decision', ''),
            clarifier=clarifier,
            source_text=data.get('source_text', ''),
            model_version=data.get('model_version', ''),
            ui_note=data.get('ui_note', '')
        )
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate CC structure and constraints
        
        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        if not self.schema_version:
            return False, "Missing schema_version"
        
        if not self.cc_id:
            return False, "Missing cc_id"
        
        if not self.user_id:
            return False, "Missing user_id"
        
        # Validate intent
        try:
            CCIntent(self.intent)
        except ValueError:
            return False, f"Invalid intent: {self.intent}"
        
        # Validate decision
        try:
            CCDecision(self.decision)
        except ValueError:
            return False, f"Invalid decision: {self.decision}"
        
        # Validate confidence range
        if not (0.0 <= self.confidence <= 1.0):
            return False, f"Invalid confidence: {self.confidence}"
        
        # Validate clarifier type
        if self.clarifier:
            try:
                ClarifierType(self.clarifier.type)
            except ValueError:
                return False, f"Invalid clarifier type: {self.clarifier.type}"
        
        # Validate money events have required data
        if self.intent == CCIntent.LOG_EXPENSE.value:
            if not self.slots or self.slots.amount is None or self.slots.amount <= 0:
                return False, "LOG_EXPENSE requires valid amount"
        
        # Validate correction targets
        if self.intent == CCIntent.CORRECT.value:
            if not self.slots or not self.slots.target:
                return False, "CORRECT intent requires target"
        
        # Validate UI note length
        if len(self.ui_note) > 140:
            return False, "ui_note exceeds 140 characters"
        
        return True, None
    
    def is_money_event(self) -> bool:
        """Check if this CC represents a money event"""
        return (self.intent in [CCIntent.LOG_EXPENSE.value, CCIntent.CORRECT.value] and 
                self.slots is not None and self.slots.amount is not None and self.slots.amount > 0)
    
    def requires_clarification(self) -> bool:
        """Check if this CC requires user clarification"""
        return (self.decision == CCDecision.ASK_ONCE.value and 
                self.clarifier is not None and self.clarifier.type != ClarifierType.NONE.value)

def create_help_cc(user_id: str, cc_id: str, source_text: str, note: str = "") -> CanonicalCommand:
    """Create a HELP Canonical Command for unsupported inputs"""
    return CanonicalCommand(
        cc_id=cc_id,
        user_id=user_id,
        intent=CCIntent.HELP.value,
        confidence=1.0,
        decision=CCDecision.AUTO_APPLY.value,
        source_text=source_text,
        model_version="fallback-v1",
        ui_note=note or "finbrain logs and corrects expenses; ask me to fix or show a report."
    )

def create_fallback_cc(user_id: str, cc_id: str, source_text: str, amount: Optional[float] = None) -> CanonicalCommand:
    """Create a fallback CC when AI parsing fails but amount is detected"""
    if amount and amount > 0:
        # Money event - create RAW_ONLY CC
        from utils.categories import normalize_category
        slots = CCSlots(amount=amount, currency="BDT", category=normalize_category(None))
        return CanonicalCommand(
            cc_id=cc_id,
            user_id=user_id,
            intent=CCIntent.LOG_EXPENSE.value,
            slots=slots,
            confidence=0.3,  # Low confidence
            decision=CCDecision.RAW_ONLY.value,
            source_text=source_text,
            model_version="fallback-v1",
            ui_note=f"Saved ৳{amount}; category to confirm."
        )
    else:
        # No money detected - create HELP CC
        return create_help_cc(user_id, cc_id, source_text, "I didn't find a valid expense amount.")