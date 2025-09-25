"""
AI resilience and fallback system
Provides reliable AI processing with local fallbacks and retry logic
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger(__name__)

class AIMode(Enum):
    """AI operation modes"""
    PRODUCTION = "production"
    STUB = "stub"
    LOCAL_FALLBACK = "local_fallback"

class AIProvider(Enum):
    """Supported AI providers"""
    GEMINI = "gemini"
    OPENAI = "openai"
    LOCAL = "local"

@dataclass
class AIResponse:
    """Structured AI response with metadata"""
    content: str
    provider: AIProvider
    mode: AIMode
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    tokens_used: int = 0
    retry_count: int = 0
    fallback_used: bool = False
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ResilientAIAdapter:
    """AI adapter with comprehensive fallback and retry logic"""
    
    def __init__(self, 
                 primary_provider: AIProvider = AIProvider.GEMINI,
                 fallback_enabled: bool = True,
                 stub_mode: bool = False,
                 max_retries: int = 3,
                 timeout_seconds: float = 10.0):
        self.primary_provider = primary_provider
        self.fallback_enabled = fallback_enabled
        self.stub_mode = stub_mode
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        
        # Circuit breaker state
        self.circuit_breaker = {
            "failures": 0,
            "last_failure": 0,
            "is_open": False,
            "failure_threshold": 5,
            "recovery_timeout": 300  # 5 minutes
        }
        
        logger.info(f"AI Adapter initialized: provider={primary_provider.value}, "
                   f"fallback={fallback_enabled}, stub={stub_mode}")
    
    def generate_insight(self, 
                        user_id: str, 
                        expense_data: dict[str, Any], 
                        context: dict[str, Any] = None) -> AIResponse:
        """
        Generate AI insight with fallback resilience
        
        Args:
            user_id: User identifier
            expense_data: Expense information
            context: Additional context for AI
            
        Returns:
            AIResponse with insight content
        """
        start_time = time.time()
        
        # Check if in stub mode (for testing/CI)
        if self.stub_mode:
            return self._generate_stub_response(user_id, expense_data, start_time)
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.warning("Circuit breaker open, using local fallback")
            return self._generate_local_fallback(user_id, expense_data, start_time)
        
        # Attempt primary AI provider with retries
        for attempt in range(self.max_retries):
            try:
                response = self._call_primary_ai(user_id, expense_data, context, attempt)
                self._record_success()
                return response
                
            except Exception as e:
                logger.warning(f"AI attempt {attempt + 1} failed: {e}")
                self._record_failure()
                
                # Use exponential backoff for retries
                if attempt < self.max_retries - 1:
                    backoff_time = 2 ** attempt
                    time.sleep(backoff_time)
        
        # All retries failed - use fallback
        if self.fallback_enabled:
            logger.info("Primary AI failed, using local fallback")
            return self._generate_local_fallback(user_id, expense_data, start_time, fallback_used=True)
        else:
            # No fallback available
            raise Exception("AI processing failed and no fallback enabled")
    
    def categorize_expense(self, 
                          expense_text: str, 
                          amount: float, 
                          user_id: str = None) -> AIResponse:
        """
        Categorize expense with AI resilience
        
        Args:
            expense_text: Raw expense text
            amount: Expense amount
            user_id: User identifier
            
        Returns:
            AIResponse with category and confidence
        """
        start_time = time.time()
        
        if self.stub_mode:
            return self._generate_stub_categorization(expense_text, amount, start_time)
        
        if self._is_circuit_breaker_open():
            return self._generate_local_categorization(expense_text, amount, start_time)
        
        # Try primary AI with retries
        for attempt in range(self.max_retries):
            try:
                response = self._call_categorization_ai(expense_text, amount, user_id, attempt)
                self._record_success()
                return response
                
            except Exception as e:
                logger.warning(f"Categorization attempt {attempt + 1} failed: {e}")
                self._record_failure()
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # Fallback to local categorization
        return self._generate_local_categorization(expense_text, amount, start_time, fallback_used=True)
    
    def _call_primary_ai(self, user_id: str, expense_data: dict, context: dict, attempt: int) -> AIResponse:
        """Call primary AI provider (placeholder for actual AI integration)"""
        start_time = time.time()
        
        # Simulate AI call (in real implementation, call actual AI provider)
        time.sleep(0.1)  # Simulate network call
        
        # For testing, return deterministic response
        insight = self._generate_deterministic_insight(expense_data)
        
        processing_time = (time.time() - start_time) * 1000
        
        return AIResponse(
            content=insight,
            provider=self.primary_provider,
            mode=AIMode.PRODUCTION,
            confidence=0.85,
            processing_time_ms=processing_time,
            tokens_used=50,
            retry_count=attempt,
            fallback_used=False
        )
    
    def _call_categorization_ai(self, expense_text: str, amount: float, user_id: str, attempt: int) -> AIResponse:
        """Call AI for expense categorization"""
        start_time = time.time()
        
        # Simulate AI categorization
        time.sleep(0.05)
        
        category = self._determine_local_category(expense_text)
        confidence = 0.90 if category != "Other" else 0.60
        
        processing_time = (time.time() - start_time) * 1000
        
        return AIResponse(
            content=json.dumps({"category": category, "confidence": confidence}),
            provider=self.primary_provider,
            mode=AIMode.PRODUCTION,
            confidence=confidence,
            processing_time_ms=processing_time,
            tokens_used=20,
            retry_count=attempt,
            fallback_used=False
        )
    
    def _generate_stub_response(self, user_id: str, expense_data: dict, start_time: float) -> AIResponse:
        """Generate stub response for testing"""
        processing_time = (time.time() - start_time) * 1000
        
        return AIResponse(
            content="✅ Stub AI Response: Your expenses are being tracked.",
            provider=AIProvider.LOCAL,
            mode=AIMode.STUB,
            confidence=1.0,
            processing_time_ms=processing_time,
            tokens_used=0,
            retry_count=0,
            fallback_used=False,
            metadata={"stub_mode": True}
        )
    
    def _generate_stub_categorization(self, expense_text: str, amount: float, start_time: float) -> AIResponse:
        """Generate stub categorization for testing"""
        processing_time = (time.time() - start_time) * 1000
        
        return AIResponse(
            content=json.dumps({"category": "General", "confidence": 1.0}),
            provider=AIProvider.LOCAL,
            mode=AIMode.STUB,
            confidence=1.0,
            processing_time_ms=processing_time,
            tokens_used=0,
            retry_count=0,
            fallback_used=False
        )
    
    def _generate_local_fallback(self, user_id: str, expense_data: dict, start_time: float, fallback_used: bool = False) -> AIResponse:
        """Generate local fallback response"""
        processing_time = (time.time() - start_time) * 1000
        
        # Simple rule-based insight
        total_amount = expense_data.get("total_amount", 0)
        expense_count = expense_data.get("expense_count", 0)
        
        if total_amount > 1000:
            insight = f"💰 High spending detected: ৳{total_amount:,.0f} across {expense_count} expenses"
        elif expense_count > 10:
            insight = f"📊 Frequent transactions: {expense_count} expenses totaling ৳{total_amount:,.0f}"
        else:
            insight = f"📝 Expenses tracked: {expense_count} items, ৳{total_amount:,.0f} total"
        
        return AIResponse(
            content=insight,
            provider=AIProvider.LOCAL,
            mode=AIMode.LOCAL_FALLBACK,
            confidence=0.75,
            processing_time_ms=processing_time,
            tokens_used=0,
            retry_count=0,
            fallback_used=fallback_used
        )
    
    def _generate_local_categorization(self, expense_text: str, amount: float, start_time: float, fallback_used: bool = False) -> AIResponse:
        """Generate local rule-based categorization"""
        processing_time = (time.time() - start_time) * 1000
        
        category = self._determine_local_category(expense_text)
        confidence = 0.80 if category != "Other" else 0.50
        
        return AIResponse(
            content=json.dumps({"category": category, "confidence": confidence}),
            provider=AIProvider.LOCAL,
            mode=AIMode.LOCAL_FALLBACK,
            confidence=confidence,
            processing_time_ms=processing_time,
            tokens_used=0,
            retry_count=0,
            fallback_used=fallback_used
        )
    
    def _determine_local_category(self, expense_text: str) -> str:
        """Simple rule-based categorization"""
        text_lower = expense_text.lower()
        
        # Food and dining
        food_keywords = ["lunch", "dinner", "breakfast", "restaurant", "cafe", "food", "খাবার", "চা", "কফি"]
        if any(keyword in text_lower for keyword in food_keywords):
            return "Food & Dining"
        
        # Transportation
        transport_keywords = ["bus", "taxi", "transport", "fuel", "rickshaw", "uber", "যাতায়াত"]
        if any(keyword in text_lower for keyword in transport_keywords):
            return "Transportation"
        
        # Shopping
        shopping_keywords = ["shopping", "market", "shop", "buy", "purchase", "কিনেছি", "বাজার"]
        if any(keyword in text_lower for keyword in shopping_keywords):
            return "Shopping"
        
        # Entertainment
        entertainment_keywords = ["movie", "cinema", "entertainment", "game", "sport", "সিনেমা"]
        if any(keyword in text_lower for keyword in entertainment_keywords):
            return "Entertainment"
        
        return "Other"
    
    def _generate_deterministic_insight(self, expense_data: dict) -> str:
        """Generate deterministic insight for testing"""
        total = expense_data.get("total_amount", 0)
        count = expense_data.get("expense_count", 0)
        
        if total > 2000:
            return f"💡 High spending period: ৳{total:,.0f} across {count} transactions. Consider reviewing large expenses."
        elif count > 15:
            return f"📈 Active spending: {count} transactions totaling ৳{total:,.0f}. Great tracking consistency!"
        else:
            return f"📊 Current summary: {count} expenses, ৳{total:,.0f} total. Keep tracking for better insights."
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open"""
        if not self.circuit_breaker["is_open"]:
            return False
        
        # Check if recovery timeout has passed
        if time.time() - self.circuit_breaker["last_failure"] > self.circuit_breaker["recovery_timeout"]:
            self.circuit_breaker["is_open"] = False
            self.circuit_breaker["failures"] = 0
            logger.info("Circuit breaker recovered")
            return False
        
        return True
    
    def _record_success(self):
        """Record successful AI call"""
        self.circuit_breaker["failures"] = 0
        self.circuit_breaker["is_open"] = False
    
    def _record_failure(self):
        """Record failed AI call"""
        self.circuit_breaker["failures"] += 1
        self.circuit_breaker["last_failure"] = time.time()
        
        if self.circuit_breaker["failures"] >= self.circuit_breaker["failure_threshold"]:
            self.circuit_breaker["is_open"] = True
            logger.warning(f"Circuit breaker opened after {self.circuit_breaker['failures']} failures")
    
    def get_health_status(self) -> dict[str, Any]:
        """Get AI adapter health status"""
        return {
            "primary_provider": self.primary_provider.value,
            "mode": AIMode.STUB.value if self.stub_mode else AIMode.PRODUCTION.value,
            "fallback_enabled": self.fallback_enabled,
            "circuit_breaker": {
                "is_open": self.circuit_breaker["is_open"],
                "failures": self.circuit_breaker["failures"],
                "threshold": self.circuit_breaker["failure_threshold"]
            },
            "last_check": time.time()
        }