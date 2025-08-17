"""
Pluggable AI adapter system with provider drivers
Supports multiple AI providers with failover and timeout protection
"""
import os
import time
import logging
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from utils.crypto import ensure_hashed

logger = logging.getLogger(__name__)

@dataclass
class AIResponse:
    """Standardized AI response structure"""
    intent: str
    amount: Optional[float] = None
    note: Optional[str] = None
    tips: List[str] = None
    failover: bool = False
    provider: str = "unknown"
    processing_time_ms: float = 0
    
    def __post_init__(self):
        if self.tips is None:
            self.tips = []

class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'FinBrain-AI/{provider_name}/1.0'
        })
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if provider is properly configured and enabled"""
        pass
    
    @abstractmethod
    def process_message(self, text: str, psid_hash: str, context: Dict[str, Any]) -> AIResponse:
        """Process message and return standardized response"""
        pass
    
    def cleanup(self):
        """Clean up resources"""
        self.session.close()

class NoneProvider(AIProvider):
    """Default provider that immediately returns failover"""
    
    def __init__(self):
        super().__init__("none")
    
    def is_enabled(self) -> bool:
        return True
    
    def process_message(self, text: str, psid_hash: str, context: Dict[str, Any]) -> AIResponse:
        """Immediately return failover for regex routing"""
        return AIResponse(
            intent="failover",
            failover=True,
            provider="none",
            processing_time_ms=0
        )

class OpenAIProvider(AIProvider):
    """OpenAI provider implementation (placeholder)"""
    
    def __init__(self):
        super().__init__("openai")
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')  # Fast model default
        self.api_url = 'https://api.openai.com/v1/chat/completions'
        
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
    
    def is_enabled(self) -> bool:
        return bool(self.api_key)
    
    def process_message(self, text: str, psid_hash: str, context: Dict[str, Any]) -> AIResponse:
        """Process message via OpenAI API with expense intelligence"""
        start_time = time.time()
        
        if not self.is_enabled():
            return AIResponse(
                intent="config_error",
                failover=True,
                provider="openai",
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        try:
            # Enhanced prompt for expense processing
            system_prompt = """You are FinBrain, an expense tracking assistant. Analyze messages and extract:

TASK: Parse expense messages and provide intelligent categorization + tips.

RESPONSE FORMAT (JSON):
{
  "intent": "log|summary|help|unknown",
  "amount": number_or_null,
  "category": "food|transport|shopping|bills|entertainment|health|education|travel|misc",
  "note": "clean_description",
  "tips": ["actionable_tip_1", "actionable_tip_2"]
}

RULES:
- Extract amount from any currency format (50, $50, ৳50)
- Categorize based on context clues
- Provide 2 actionable spending tips
- Keep descriptions under 50 chars
- Never include personal identifiers"""
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Message: {text}"}
                ],
                "max_tokens": 200,
                "temperature": 0.1,  # Low temperature for consistent parsing
                "response_format": {"type": "json_object"}
            }
            
            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=6  # 6s timeout to leave buffer for overall 8s
            )
            
            processing_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                try:
                    # Parse JSON response
                    import json
                    ai_data = json.loads(content)
                    
                    return AIResponse(
                        intent=ai_data.get('intent', 'unknown'),
                        amount=ai_data.get('amount'),
                        note=ai_data.get('note', text[:50]),
                        tips=ai_data.get('tips', ["Consider budgeting", "Track expenses daily"]),
                        failover=False,
                        provider="openai",
                        processing_time_ms=processing_time_ms
                    )
                except json.JSONDecodeError:
                    logger.warning("OpenAI returned invalid JSON, falling back")
                    return AIResponse(
                        intent="parse_error",
                        failover=True,
                        provider="openai",
                        processing_time_ms=processing_time_ms
                    )
            else:
                logger.warning(f"OpenAI API error: {response.status_code}")
                return AIResponse(
                    intent="api_error",
                    failover=True,
                    provider="openai",
                    processing_time_ms=processing_time_ms
                )
                
        except requests.exceptions.Timeout:
            logger.warning("OpenAI API timeout (6s)")
            return AIResponse(
                intent="timeout",
                failover=True,
                provider="openai",
                processing_time_ms=6000
            )
        except Exception as e:
            logger.error(f"OpenAI provider error: {str(e)}")
            return AIResponse(
                intent="error",
                failover=True,
                provider="openai",
                processing_time_ms=(time.time() - start_time) * 1000
            )

class GeminiProvider(AIProvider):
    """Google Gemini provider implementation (placeholder)"""
    
    def __init__(self):
        super().__init__("gemini")
        self.api_key = os.environ.get('GEMINI_API_KEY')
        self.model = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')  # Fast model default
        self.api_url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
    
    def is_enabled(self) -> bool:
        return bool(self.api_key)
    
    def process_message(self, text: str, psid_hash: str, context: Dict[str, Any]) -> AIResponse:
        """Process message via Gemini API with expense intelligence"""
        start_time = time.time()
        
        if not self.is_enabled():
            return AIResponse(
                intent="config_error",
                failover=True,
                provider="gemini",
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        try:
            # Enhanced prompt for expense processing
            prompt = f"""You are FinBrain, an expense tracking assistant. Analyze this message and extract expense information:

Message: "{text}"

Respond with valid JSON only:
{{
  "intent": "log|summary|help|unknown",
  "amount": number_or_null,
  "category": "food|transport|shopping|bills|entertainment|health|education|travel|misc",
  "note": "clean_description_under_50_chars",
  "tips": ["actionable_tip_1", "actionable_tip_2"]
}}

RULES:
- Extract amount from any currency format
- Categorize based on context clues  
- Provide 2 actionable spending tips
- No personal identifiers
- JSON only response"""
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 200,
                    "responseMimeType": "application/json"
                }
            }
            
            # Add API key to URL
            url_with_key = f"{self.api_url}?key={self.api_key}"
            
            response = self.session.post(
                url_with_key,
                json=payload,
                timeout=6,
                headers={'Content-Type': 'application/json'}
            )
            
            processing_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract content from Gemini response
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    
                    try:
                        # Parse JSON response
                        import json
                        ai_data = json.loads(content)
                        
                        return AIResponse(
                            intent=ai_data.get('intent', 'unknown'),
                            amount=ai_data.get('amount'),
                            note=ai_data.get('note', text[:50]),
                            tips=ai_data.get('tips', ["Consider budgeting", "Track expenses daily"]),
                            failover=False,
                            provider="gemini",
                            processing_time_ms=processing_time_ms
                        )
                    except json.JSONDecodeError:
                        logger.warning("Gemini returned invalid JSON, falling back")
                        return AIResponse(
                            intent="parse_error",
                            failover=True,
                            provider="gemini",
                            processing_time_ms=processing_time_ms
                        )
                else:
                    logger.warning("Gemini response missing candidates")
                    return AIResponse(
                        intent="no_candidates",
                        failover=True,
                        provider="gemini",
                        processing_time_ms=processing_time_ms
                    )
            else:
                logger.warning(f"Gemini API error: {response.status_code}")
                return AIResponse(
                    intent="api_error",
                    failover=True,
                    provider="gemini",
                    processing_time_ms=processing_time_ms
                )
                
        except requests.exceptions.Timeout:
            logger.warning("Gemini API timeout (6s)")
            return AIResponse(
                intent="timeout",
                failover=True,
                provider="gemini",
                processing_time_ms=6000
            )
        except Exception as e:
            logger.error(f"Gemini provider error: {str(e)}")
            return AIResponse(
                intent="error",
                failover=True,
                provider="gemini",
                processing_time_ms=(time.time() - start_time) * 1000
            )

class AIAdapter:
    """Main AI adapter with pluggable providers and timeout protection"""
    
    def __init__(self):
        self.enabled = os.environ.get('AI_ENABLED', 'false').lower() == 'true'
        self.provider_name = os.environ.get('AI_PROVIDER', 'none').lower()
        self.timeout_seconds = 8  # Overall adapter timeout
        
        # Initialize provider
        self.provider = self._create_provider()
        
        logger.info(f"AI Adapter initialized: enabled={self.enabled}, provider={self.provider_name}")
    
    def _create_provider(self) -> AIProvider:
        """Create the appropriate provider instance"""
        if self.provider_name == 'openai':
            return OpenAIProvider()
        elif self.provider_name == 'gemini':
            return GeminiProvider()
        else:
            return NoneProvider()
    
    def ai_summarize_or_classify(self, text: str, psid: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Public AI processing function with timeout protection
        
        Args:
            text: User message text
            psid: User's Page-Scoped ID (will be hashed)
            context: Additional context (category hints, etc.)
        
        Returns:
            {intent, amount, note, tips, failover} dictionary
        """
        start_time = time.time()
        
        if not self.enabled:
            return {
                "intent": "disabled",
                "amount": None,
                "note": None,
                "tips": [],
                "failover": True,
                "provider": "disabled",
                "processing_time_ms": 0
            }
        
        # Hash PSID for PII protection
        from utils.security import hash_psid
        psid_hash = ensure_hashed(psid)
        
        # Sanitize context to remove PII
        safe_context = self._sanitize_context(context or {})
        
        try:
            # Process with timeout protection
            response = self.provider.process_message(text, psid_hash, safe_context)
            
            # Check overall timeout
            total_time_ms = (time.time() - start_time) * 1000
            if total_time_ms > (self.timeout_seconds * 1000):
                logger.warning(f"AI adapter timeout exceeded: {total_time_ms:.2f}ms")
                response.failover = True
                response.intent = "timeout"
            
            # Log AI processing (PII-safe)
            logger.info(f"AI processing: provider={response.provider}, "
                       f"intent={response.intent}, "
                       f"failover={response.failover}, "
                       f"time={response.processing_time_ms:.2f}ms")
            
            return {
                "intent": response.intent,
                "amount": response.amount,
                "note": response.note,
                "tips": response.tips,
                "failover": response.failover,
                "provider": response.provider,
                "processing_time_ms": response.processing_time_ms
            }
            
        except Exception as e:
            logger.error(f"AI adapter error: {str(e)}")
            return {
                "intent": "error",
                "amount": None,
                "note": None,
                "tips": [],
                "failover": True,
                "provider": self.provider_name,
                "processing_time_ms": (time.time() - start_time) * 1000
            }
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Remove PII from context, keep only safe metadata"""
        safe_keys = ['category_hint', 'previous_amount', 'time_of_day', 'platform']
        return {k: v for k, v in context.items() if k in safe_keys}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current adapter status"""
        return {
            "enabled": self.enabled,
            "provider": self.provider_name,
            "provider_enabled": self.provider.is_enabled() if self.provider else False,
            "timeout_seconds": self.timeout_seconds
        }
    
    def cleanup(self):
        """Clean up adapter resources"""
        if self.provider:
            self.provider.cleanup()

# Global AI adapter instance
ai_adapter = AIAdapter()