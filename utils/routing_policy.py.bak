"""
PoR v1.1 - Finbrain Deterministic Routing Policy
Implements rules-first routing with bilingual support and state awareness
"""

import os
import re
import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger("finbrain.routing_policy")

class RouterMode(Enum):
    """Router operating modes"""
    AI_FIRST = "ai_first"      # Legacy AI-first routing (fallback)
    HYBRID = "hybrid"          # Rules + AI fallback (recommended)
    RULES_FIRST = "rules_first" # Deterministic rules primary

class RouterScope(Enum):
    """Router scope for gradual rollout"""
    ZERO_LEDGER_ONLY = "zero_ledger_only"       # Users with no transaction history
    ANALYSIS_KEYWORDS_ONLY = "analysis_keywords_only"  # Only explicit analysis requests
    ALL = "all"                                  # All requests (full coverage)

class IntentType(Enum):
    """Intent types with hard precedence: ADMIN → PCA_AUDIT → EXPENSE_LOG → CATEGORY_BREAKDOWN → ANALYSIS → FAQ → COACHING → SMALLTALK → UNKNOWN"""
    ADMIN = "ADMIN"
    PCA_AUDIT = "PCA_AUDIT"
    EXPENSE_LOG = "EXPENSE_LOG"
    CLARIFY_EXPENSE = "CLARIFY_EXPENSE"
    CATEGORY_BREAKDOWN = "CATEGORY_BREAKDOWN"
    ANALYSIS = "ANALYSIS"
    FAQ = "FAQ"
    COACHING = "COACHING"
    SMALLTALK = "SMALLTALK"
    UNKNOWN = "UNKNOWN"

@dataclass
class RoutingSignals:
    """State signals used for routing decisions"""
    ledger_count_30d: int
    has_money: bool
    has_first_person_spent_verb: bool
    has_time_window: bool
    has_analysis_terms: bool
    has_explicit_analysis: bool
    has_coaching_verbs: bool
    has_faq_terms: bool
    in_coaching_session: bool
    is_admin_command: bool

@dataclass
class RoutingResult:
    """Result of routing decision"""
    intent: IntentType
    reason_codes: List[str]
    matched_patterns: List[str]
    confidence: float

class RoutingPolicyFlags:
    """PoR v1.1 routing configuration flags"""
    
    def __init__(self):
        """Initialize routing flags with safe defaults"""
        self.mode = self._get_router_mode()
        self.scope = self._get_router_scope()
        self.rules_version = os.environ.get('ROUTER_RULES_VERSION', '2025-08-27')
        self.pca_audit_mode = os.environ.get('PCA_AUDIT_MODE', 'false').lower() == 'true'
        self.coaching_txn_threshold = int(os.environ.get('COACHING_TXN_THRESHOLD', '10'))
        self.coaching_session_respect = os.environ.get('COACHING_SESSION_RESPECT', 'true').lower() == 'true'
        self.bilingual_routing = os.environ.get('BILINGUAL_ROUTING', 'true').lower() == 'true'
        self.uniqueness_mode = os.environ.get('UNIQUENESS_MODE', 'data_version')
        
        logger.info(f"Routing Policy initialized: mode={self.mode.value}, "
                   f"scope={self.scope.value}, rules_version={self.rules_version}, "
                   f"pca_audit={self.pca_audit_mode}, coaching_threshold={self.coaching_txn_threshold}")
    
    def _get_router_mode(self) -> RouterMode:
        """Get router mode from environment"""
        mode_str = os.environ.get('ROUTER_MODE', 'hybrid').lower()
        try:
            return RouterMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid ROUTER_MODE '{mode_str}', defaulting to hybrid")
            return RouterMode.HYBRID
    
    def _get_router_scope(self) -> RouterScope:
        """Get router scope from environment"""
        scope_str = os.environ.get('ROUTER_SCOPE', 'all').lower()  # Default to ALL for full coverage
        try:
            return RouterScope(scope_str)
        except ValueError:
            logger.warning(f"Invalid ROUTER_SCOPE '{scope_str}', defaulting to all")
            return RouterScope.ALL

class BilingualPatterns:
    """Bilingual (EN + BN) pattern matching for routing"""
    
    def __init__(self):
        """Initialize bilingual patterns"""
        # Time window patterns
        self.time_window_en = re.compile(
            r'\b(today|this (week|month)|last (week|month)|yesterday)\b|\b\d{4}-\d{2}-\d{2}\b',
            re.IGNORECASE | re.UNICODE
        )
        self.time_window_bn = re.compile(
            r'আজ|এই (সপ্তাহ|মাস)|গত (সপ্তাহ|মাস)|গতকাল|\b\d{4}-\d{2}-\d{2}\b',
            re.IGNORECASE | re.UNICODE
        )
        
        # Explicit analysis request patterns  
        self.explicit_analysis_en = re.compile(
            r'\b(analysis please|insights?|analyze|show me insights?|give me insights?|spending (summary|report)|what did i spend|expense report|how much.*spend|spend.*week|spend.*month|analyze my spending)\b',
            re.IGNORECASE | re.UNICODE
        )
        self.explicit_analysis_bn = re.compile(
            r'বিশ্লেষণ( দাও)?|খরচের (সারাংশ|রিপোর্ট)|আমি কত খরচ করেছি|সারাংশ দাও|মাসের খরচ',
            re.IGNORECASE | re.UNICODE
        )
        
        # Analysis terms (non-explicit) - enhanced for better matching
        self.analysis_terms_en = re.compile(
            r'\b(analysis|summary|report|insights?|analyze|breakdown|review|pattern|spent.*month|spent.*week|spend.*week|spend.*month)\b',
            re.IGNORECASE | re.UNICODE
        )
        self.analysis_terms_bn = re.compile(
            r'\b(বিশ্লেষণ|সারাংশ|রিপোর্ট|খরচ.*মাসে|খরচ.*সপ্তাহ)\b',
            re.IGNORECASE | re.UNICODE
        )
        
        # Coaching verb patterns (comprehensive, excluding FAQ contexts)
        self.coaching_verbs_en = re.compile(
            r'(save money|reduce|cut|budget planning|help me reduce|how can I save|'
            r'cut my expenses|reduce transport costs|'
            r'save|planning advice|(?<!subscription\s)plan(?!s\b))',
            re.IGNORECASE | re.UNICODE
        )
        self.coaching_verbs_bn = re.compile(
            r'(সেভ|কমানো|কাট|বাজেট|পরিকল্পনা|কমাতে চাই|সেভ করবো|'
            r'খরচ কমাতে|টাকা সেভ)',
            re.IGNORECASE | re.UNICODE
        )
        
        # FAQ terms (expanded)
        self.faq_terms_en = re.compile(
            r'(what can you do|how (do|does) it work|features?|capabilities?|privacy|'
            r'is my data (safe|private)|security|pricing|cost|subscription plans?|plans?)',
            re.IGNORECASE | re.UNICODE
        )
        self.faq_terms_bn = re.compile(
            r'(তুমি কী করতে পারো|কিভাবে কাজ করে|ফিচার(স)?|ক্ষমতা|প্রাইভেসি|'
            r'ডেটা নিরাপদ|নিরাপত্তা|দাম|মূল্য|সাবস্ক্রিপশন|প্ল্যান|নিরাপত্তা কেমন)',
            re.IGNORECASE | re.UNICODE
        )
        
        # First-person expense verb patterns (for EXPENSE_LOG intent) + implicit items
        self.expense_verbs_en = re.compile(
            r'\b(spent|paid|bought|purchased|cost|costs|ordered|got|took)\b|(coffee|lunch|dinner|breakfast|tea|food)\s+\d',
            re.IGNORECASE | re.UNICODE
        )
        self.expense_verbs_bn = re.compile(
            r'(খরচ করেছি|খরচ করলাম|দিলাম|দিয়েছি|পেমেন্ট করেছি|কিনেছি|নিয়েছি|কিনলাম|ব্যয় করেছি|পয়সা দিয়েছি|টাকা খরচ করেছি|ক্রয় করেছি|অর্ডার করেছি|নিয়েছিলাম|কিনে এনেছি|টাকা দিয়েছি)',
            re.IGNORECASE | re.UNICODE
        )
        
        # Admin command patterns
        self.admin_commands = re.compile(r'^/(id|debug|help)\b', re.IGNORECASE)
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for pattern matching"""
        import unicodedata
        # Remove zero-width characters and normalize Unicode
        text = unicodedata.normalize('NFKC', text)
        # Remove zero-width joiners/non-joiners that Messenger might insert
        text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
        return text.lower().casefold()
    
    def has_time_window(self, text: str) -> bool:
        """Check if text contains time window references"""
        normalized = self.normalize_text(text)
        return bool(self.time_window_en.search(normalized) or self.time_window_bn.search(normalized))
    
    def has_explicit_analysis_request(self, text: str) -> bool:
        """Check if text contains explicit analysis request"""
        normalized = self.normalize_text(text)
        return bool(self.explicit_analysis_en.search(normalized) or self.explicit_analysis_bn.search(normalized))
    
    def has_first_person_spent_verb(self, text: str) -> bool:
        """Check if text contains first-person past-tense expense verbs"""
        normalized = self.normalize_text(text)
        return bool(self.expense_verbs_en.search(normalized) or self.expense_verbs_bn.search(normalized))
    
    def has_analysis_terms(self, text: str) -> bool:
        """Check if text contains general analysis terms"""
        normalized = self.normalize_text(text)
        return bool(self.analysis_terms_en.search(normalized) or self.analysis_terms_bn.search(normalized))
    
    def has_coaching_verbs(self, text: str) -> bool:
        """Check if text contains coaching verbs"""
        normalized = self.normalize_text(text)
        return bool(self.coaching_verbs_en.search(normalized) or self.coaching_verbs_bn.search(normalized))
    
    def has_faq_terms(self, text: str) -> bool:
        """Check if text contains FAQ terms"""
        normalized = self.normalize_text(text)
        return bool(self.faq_terms_en.search(normalized) or self.faq_terms_bn.search(normalized))
    
    def is_admin_command(self, text: str) -> bool:
        """Check if text is an admin command"""
        return bool(self.admin_commands.match(text.strip()))

class DataVersionManager:
    """Manages data-version uniqueness for truthful repetition handling"""
    
    @staticmethod
    def compute_data_version(user_id: str, window_start: datetime, window_end: datetime) -> str:
        """
        Compute strong data version fingerprint
        
        Args:
            user_id: User identifier
            window_start: Start of time window
            window_end: End of time window
            
        Returns:
            SHA-256 hex digest of user's expense data in window
        """
        try:
            from app import db
            from models import Expense
            
            # Strong fingerprint: ID + amount + category + merchant + timestamp
            from sqlalchemy import text
            result = db.session.execute(
                text("""
                SELECT encode(
                  digest(
                    string_agg(
                      concat_ws(
                        ':', id, amount, currency, category, 
                        extract(epoch from updated_at)::bigint
                      ) ORDER BY updated_at, id
                    ),
                    'sha256'
                  ),
                  'hex'
                ) AS data_version
                FROM expenses
                WHERE user_id = :uid
                  AND created_at >= :from_time
                  AND created_at < :to_time
                """),
                {
                    'uid': user_id,
                    'from_time': window_start,
                    'to_time': window_end
                }
            ).fetchone()
            
            return result[0] if result and result[0] else "empty"
            
        except Exception as e:
            logger.warning(f"Strong fingerprint failed, using lightweight fallback: {e}")
            return DataVersionManager.compute_lightweight_version(user_id, window_start, window_end)
    
    @staticmethod 
    def compute_lightweight_version(user_id: str, window_start: datetime, window_end: datetime) -> str:
        """
        Compute lightweight data version fallback
        Uses COUNT + SUM + MAX(updated_at) to catch changes efficiently
        """
        try:
            from app import db
            
            from sqlalchemy import text
            result = db.session.execute(
                text("""
                SELECT encode(
                  digest(
                    concat_ws(':',
                      count(*),
                      coalesce(sum(amount),0),
                      extract(epoch from coalesce(max(updated_at), 'epoch'::timestamptz))::bigint
                    ),
                    'sha256'
                  ),
                  'hex'
                ) AS data_version
                FROM expenses
                WHERE user_id = :uid
                  AND created_at >= :from_time
                  AND created_at < :to_time
                """),
                {
                    'uid': user_id,
                    'from_time': window_start,
                    'to_time': window_end
                }
            ).fetchone()
            
            return result[0] if result and result[0] else "empty"
            
        except Exception as e:
            logger.error(f"Lightweight data version computation failed: {e}")
            return f"fallback_{int(time.time())}"

class DeterministicRouter:
    """PoR v1.1 deterministic routing engine"""
    
    def __init__(self):
        """Initialize deterministic router"""
        self.flags = RoutingPolicyFlags()
        self.patterns = BilingualPatterns()
        self.data_version_mgr = DataVersionManager()
        
    def should_use_deterministic_routing(self, user_signals: RoutingSignals) -> bool:
        """
        Determine if request should use deterministic routing based on scope
        
        Args:
            user_signals: User state signals
            
        Returns:
            True if deterministic routing should be used
        """
        if self.flags.mode == RouterMode.AI_FIRST:
            return False
        
        if self.flags.scope == RouterScope.ZERO_LEDGER_ONLY:
            return user_signals.ledger_count_30d == 0
        
        elif self.flags.scope == RouterScope.ANALYSIS_KEYWORDS_ONLY:
            return (user_signals.ledger_count_30d == 0 or 
                   user_signals.has_explicit_analysis or
                   user_signals.has_time_window)
        
        elif self.flags.scope == RouterScope.ALL:
            return True
        
        return False
    
    def extract_signals(self, text: str, user_id: str) -> RoutingSignals:
        """
        Extract routing signals from text and user state
        
        Args:
            text: User message text
            user_id: User identifier
            
        Returns:
            RoutingSignals with computed state
        """
        # Pattern matching signals
        has_money = self._has_money_pattern(text)
        has_first_person_spent_verb = self.patterns.has_first_person_spent_verb(text)
        has_time_window = self.patterns.has_time_window(text)
        has_analysis_terms = self.patterns.has_analysis_terms(text)
        has_explicit_analysis = self.patterns.has_explicit_analysis_request(text)
        has_coaching_verbs = self.patterns.has_coaching_verbs(text)
        has_faq_terms = self.patterns.has_faq_terms(text)
        is_admin_command = self.patterns.is_admin_command(text)
        
        # Database-derived signals
        ledger_count_30d = self._get_ledger_count_30d(user_id)
        in_coaching_session = self._is_in_coaching_session(user_id)
        
        return RoutingSignals(
            ledger_count_30d=ledger_count_30d,
            has_money=has_money,
            has_first_person_spent_verb=has_first_person_spent_verb,
            has_time_window=has_time_window,
            has_analysis_terms=has_analysis_terms,
            has_explicit_analysis=has_explicit_analysis,
            has_coaching_verbs=has_coaching_verbs,
            has_faq_terms=has_faq_terms,
            in_coaching_session=in_coaching_session,
            is_admin_command=is_admin_command
        )
    
    def route_intent(self, text: str, user_signals: RoutingSignals) -> RoutingResult:
        """
        Route intent using deterministic rules with hard precedence
        
        Args:
            text: User message text
            user_signals: Pre-computed routing signals
            
        Returns:
            RoutingResult with intent and reasoning
        """
        reason_codes = []
        matched_patterns = []
        
        # ADMIN → PCA_AUDIT → EXPENSE_LOG → ANALYSIS → FAQ → COACHING → SMALLTALK
        
        # 1. ADMIN (highest precedence)
        if user_signals.is_admin_command:
            reason_codes.append("ADMIN_COMMAND")
            matched_patterns.append("admin_prefix")
            return RoutingResult(IntentType.ADMIN, reason_codes, matched_patterns, 1.0)
        
        # 2. PCA_AUDIT 
        if self.flags.pca_audit_mode:
            reason_codes.append("PCA_AUDIT_MODE")
            return RoutingResult(IntentType.PCA_AUDIT, reason_codes, matched_patterns, 1.0)
        
        # 3. EXPENSE_LOG (money + first-person past-tense verb)
        if user_signals.has_money and user_signals.has_first_person_spent_verb:
            reason_codes.append("HAS_MONEY")
            reason_codes.append("HAS_FIRST_PERSON_SPENT_VERB")
            matched_patterns.append("money_pattern")
            matched_patterns.append("expense_verb")
            return RoutingResult(IntentType.EXPENSE_LOG, reason_codes, matched_patterns, 0.95)
        
        # 4. CLARIFY_EXPENSE (money without verb, not explicit analysis)
        if user_signals.has_money and not user_signals.has_first_person_spent_verb and not user_signals.has_explicit_analysis:
            reason_codes.append("HAS_MONEY_NO_VERB")
            matched_patterns.append("money_pattern")
            return RoutingResult(IntentType.CLARIFY_EXPENSE, reason_codes, matched_patterns, 0.9)
        
        # 5. CATEGORY_BREAKDOWN (category + timeframe queries)
        if self._is_category_breakdown_query(text):
            reason_codes.append("CATEGORY_BREAKDOWN_DETECTED")
            matched_patterns.append("category_timeframe")
            return RoutingResult(IntentType.CATEGORY_BREAKDOWN, reason_codes, matched_patterns, 0.95)
        
        # 6. ANALYSIS - OR logic: time window OR analysis terms OR explicit analysis
        if (user_signals.has_explicit_analysis or 
            user_signals.has_time_window or 
            user_signals.has_analysis_terms):
            
            if user_signals.has_explicit_analysis:
                reason_codes.append("EXPLICIT_ANALYSIS_REQUEST")
                matched_patterns.append("explicit_analysis")
            if user_signals.has_time_window:
                reason_codes.append("HAS_TIME_WINDOW")
                matched_patterns.append("time_window")
            if user_signals.has_analysis_terms:
                reason_codes.append("HAS_ANALYSIS_TERMS")
                matched_patterns.append("analysis_terms")
            
            return RoutingResult(IntentType.ANALYSIS, reason_codes, matched_patterns, 0.95)
        
        # 7. FAQ (but not if it has coaching context)
        if user_signals.has_faq_terms and not user_signals.has_coaching_verbs:
            reason_codes.append("HAS_FAQ_TERMS")
            matched_patterns.append("faq_terms")
            return RoutingResult(IntentType.FAQ, reason_codes, matched_patterns, 0.9)
        
        # 8. COACHING
        coaching_conditions = [
            # Standard coaching: verbs + sufficient history + not explicit analysis
            (user_signals.has_coaching_verbs and 
             user_signals.ledger_count_30d >= self.flags.coaching_txn_threshold and
             not user_signals.has_explicit_analysis),
            # Session continuity: in session + not explicit analysis override
            (user_signals.in_coaching_session and 
             not user_signals.has_explicit_analysis and
             self.flags.coaching_session_respect)
        ]
        
        if any(coaching_conditions):
            if user_signals.has_coaching_verbs:
                reason_codes.append("HAS_COACHING_VERBS")
                reason_codes.append(f"LEDGER_COUNT_GTE_{self.flags.coaching_txn_threshold}")
                matched_patterns.append("coaching_verbs")
            if user_signals.in_coaching_session:
                reason_codes.append("IN_COACHING_SESSION")
                matched_patterns.append("session_continuity")
            
            return RoutingResult(IntentType.COACHING, reason_codes, matched_patterns, 0.85)
        
        # 9. SMALLTALK (greetings and social conversation)
        smalltalk_patterns_en = r'\b(hello|hi|hey|thanks|thank you|bye|goodbye|good morning|good night|how are you)\b'
        smalltalk_patterns_bn = r'\b(হ্যালো|হাই|ধন্যবাদ|শুভ সকাল|শুভ রাত্রি|কেমন আছেন)\b'
        
        normalized_text = self.patterns.normalize_text(text)
        if (re.search(smalltalk_patterns_en, normalized_text, re.IGNORECASE | re.UNICODE) or
            re.search(smalltalk_patterns_bn, normalized_text, re.IGNORECASE | re.UNICODE)):
            reason_codes.append("SMALLTALK_DETECTED")
            matched_patterns.append("social_conversation")
            return RoutingResult(IntentType.SMALLTALK, reason_codes, matched_patterns, 0.8)
        
        # 10. UNKNOWN (truly unrecognized terms)
        reason_codes.append("UNRECOGNIZED_INPUT")
        return RoutingResult(IntentType.UNKNOWN, reason_codes, matched_patterns, 0.5)
    
    def _has_money_pattern(self, text: str) -> bool:
        """Check if text contains money patterns using existing Bengali-aware utilities"""
        try:
            # Use existing Bengali digit normalization and money detection
            from utils.bn_digits import to_en_digits
            from nlp.money_patterns import has_money_mention
            
            # Normalize Bengali digits to ASCII first
            normalized_text = to_en_digits(text)
            
            # Use proven money pattern detection
            return has_money_mention(normalized_text)
            
        except ImportError:
            # Fallback to basic detection if imports fail
            import re
            normalized = self.patterns.normalize_text(text)
            money_pattern = r'\b\d+\s*(taka|টাকা|৳|dollars?|\$)\b|(?:৳|taka|টাকা|\$)\s*\d+\b'
            return bool(re.search(money_pattern, normalized, re.IGNORECASE | re.UNICODE))
    
    def _is_category_breakdown_query(self, text: str) -> bool:
        """Check if text is asking for category-specific breakdown"""
        text_lower = self.patterns.normalize_text(text)
        
        # Category keywords
        category_keywords = [
            "food", "foods", "eating", "meals", "groceries", "grocery", "dining", "restaurant",
            "restaurants", "lunch", "dinner", "breakfast", "coffee", "snacks", "drinks",
            "transport", "transportation", "travel", "rides", "ride", "riding", "uber", "taxi", 
            "bus", "train", "gas", "fuel", "parking", "shopping", "clothes", "clothing",
            "amazon", "online", "store", "entertainment", "movie", "movies", "games", "cinema",
            "bills", "bill", "utilities", "utility", "rent", "housing", "internet", "phone",
            "health", "medical", "pharmacy", "doctor", "medicine", "hospital"
        ]
        
        # Category query patterns
        category_query_patterns = [
            "how much did i spend on", "what did i spend on", "how much on",
            "spent on", "spending on", "expenses on", "cost of", "total for"
        ]
        
        # Check for category-specific spending queries
        if any(pattern in text_lower for pattern in category_query_patterns):
            if any(category in text_lower for category in category_keywords):
                return True
        
        # Check for "food this month", "transport this week" pattern
        if any(category in text_lower for category in category_keywords):
            timeframe_patterns = ["this month", "this week", "last week", "last month", "today", "yesterday"]
            if any(timeframe in text_lower for timeframe in timeframe_patterns):
                return True
        
        return False

    def _get_ledger_count_30d(self, user_id: str) -> int:
        """Get user's expense count in last 30 days"""
        try:
            from app import db
            from datetime import timedelta
            
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            from sqlalchemy import text
            result = db.session.execute(
                text("SELECT count(*) FROM expenses WHERE user_id = :uid AND created_at >= :since"),
                {'uid': user_id, 'since': thirty_days_ago}
            ).fetchone()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.warning(f"Failed to get ledger count for {user_id[:8]}: {e}")
            return 0
    
    def _is_in_coaching_session(self, user_id: str) -> bool:
        """Check if user is in active coaching session"""
        try:
            from utils.session import get_coaching_session
            session = get_coaching_session(user_id)
            return bool(session and session.get('state') != 'idle')
        except Exception as e:
            logger.warning(f"Failed to check coaching session for {user_id[:8]}: {e}")
            return False
    
    def log_routing_decision(self, user_id: str, text: str, result: RoutingResult, request_id: str):
        """Log routing decision for monitoring and debugging"""
        from utils.structured import log_structured_event
        
        log_structured_event("ROUTE_DECISION", {
            "request_id": request_id,
            "user_id_hash": user_id[:8],
            "text_preview": text[:50],
            "routed_intent": result.intent.value,
            "reason_codes": result.reason_codes,
            "matched_patterns": result.matched_patterns,
            "confidence": result.confidence,
            "router_mode": self.flags.mode.value,
            "router_scope": self.flags.scope.value,
            "rules_version": self.flags.rules_version
        })

# Global instance
deterministic_router = DeterministicRouter()