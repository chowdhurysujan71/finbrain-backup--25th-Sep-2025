"""
Production AI adapter with strict constraints and failover handling
Flag-gated, never writes DB, timeout-protected with structured responses
"""
import os
import json
import time
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration
AI_ENABLED = os.environ.get("AI_ENABLED", "false").lower() == "true"
AI_PROVIDER = os.environ.get("AI_PROVIDER", "none")  # none|openai|gemini
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AI_TIMEOUT = 8  # 8 second timeout (increased for reliability)
AI_MAX_RETRIES = 1  # 1 retry only

class ProductionAIAdapter:
    """
    Production-ready AI adapter with strict constraints
    - Flag-gated operation (AI_ENABLED)
    - Never writes to database
    - Strict timeouts and error handling
    - Structured JSON responses only
    """
    
    def __init__(self):
        self.enabled = AI_ENABLED
        self.provider = AI_PROVIDER
        self.session = requests.Session()
        
        # Setup provider-specific configuration
        if self.provider == "openai" and OPENAI_API_KEY:
            self.session.headers.update({
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            })
        elif self.provider == "gemini" and GEMINI_API_KEY:
            self.session.headers.update({
                "Content-Type": "application/json"
            })
        
        logger.info(f"Production AI Adapter initialized: enabled={self.enabled}, provider={self.provider}")
    
    def ai_parse(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse text with AI and return structured response
        
        Returns:
        {
            "intent": "log" | "summary" | "help" | "undo",
            "amount": float (optional),
            "note": str (optional),
            "category": str (optional),
            "tips": List[str] (optional),
            "failover": bool (true if AI failed)
        }
        """
        # Immediate failover if AI disabled
        if not self.enabled:
            return {"failover": True, "reason": "ai_disabled"}
        
        # Validate input constraints
        if not text or len(text) > 1200:
            return {"failover": True, "reason": "invalid_input"}
        
        # Route to appropriate provider
        if self.provider == "openai":
            return self._parse_openai(text, context)
        elif self.provider == "gemini":
            return self._parse_gemini(text, context)
        else:
            return {"failover": True, "reason": "unsupported_provider"}
    
    def _parse_openai(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse using OpenAI API with strict constraints"""
        try:
            # Construct prompt (≤1200 chars total)
            prompt = self._build_prompt(text, context)
            
            # Prepare request payload
            payload = {
                "model": "gpt-4o-mini",  # Fast model for production
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expense tracking assistant. Parse user messages and respond with valid JSON only. Never write to databases."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            
            start_time = time.time()
            
            # Make API call with retry logic
            for attempt in range(AI_MAX_RETRIES + 1):
                try:
                    response = self.session.post(
                        "https://api.openai.com/v1/chat/completions",
                        json=payload,
                        timeout=AI_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        # Parse AI response as JSON
                        ai_response = json.loads(content)
                        
                        # Validate and clean response
                        return self._validate_ai_response(ai_response, time.time() - start_time)
                    
                    elif response.status_code == 429:
                        # Rate limited by OpenAI
                        logger.warning(f"OpenAI rate limited: {response.status_code}")
                        return {"failover": True, "reason": "openai_rate_limited"}
                    
                    else:
                        logger.warning(f"OpenAI API error: {response.status_code}")
                        if attempt < AI_MAX_RETRIES:
                            time.sleep(0.5)  # Brief retry delay
                            continue
                        
                except requests.Timeout:
                    logger.warning(f"OpenAI timeout on attempt {attempt + 1}")
                    if attempt < AI_MAX_RETRIES:
                        continue
                    
                except requests.RequestException as e:
                    logger.warning(f"OpenAI request error: {e}")
                    if attempt < AI_MAX_RETRIES:
                        continue
            
            # All retries failed
            return {"failover": True, "reason": "openai_failed"}
            
        except Exception as e:
            logger.error(f"AI parsing error: {e}")
            return {"failover": True, "reason": "parse_error"}
    
    def _parse_gemini(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse using Gemini API with strict constraints"""
        try:
            # Construct prompt
            prompt = self._build_prompt(text, context)
            
            # Prepare request payload for Gemini
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 400,  # Increased from 150 to support longer responses
                    "responseMimeType": "application/json"
                }
            }
            
            start_time = time.time()
            
            # Make API call with retry logic
            for attempt in range(AI_MAX_RETRIES + 1):
                try:
                    response = self.session.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}",
                        json=payload,
                        timeout=AI_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        
                        # Clean up markdown JSON wrapper if present
                        content = content.strip()
                        if content.startswith("```json"):
                            content = content[7:]  # Remove ```json
                        if content.startswith("```"):
                            content = content[3:]   # Remove ```
                        if content.endswith("```"):
                            content = content[:-3]  # Remove closing ```
                        content = content.strip()
                        
                        # Debug log the content before parsing
                        logger.debug(f"Gemini response after cleanup: {repr(content[:500])}")
                        
                        # Robust JSON parsing with fallback for malformed strings
                        try:
                            ai_response = json.loads(content)
                        except json.JSONDecodeError as json_error:
                            # Try to fix common JSON issues
                            logger.warning(f"JSON parse error: {json_error}, attempting repair")
                            
                            # Fix unterminated strings by finding the error position
                            try:
                                # Extract just the valid JSON structure if possible
                                import re
                                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                                if json_match:
                                    fixed_content = json_match.group(0)
                                    # Fix common quote escaping issues
                                    fixed_content = fixed_content.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                                    ai_response = json.loads(fixed_content)
                                else:
                                    raise json_error
                            except:
                                # If all repair attempts fail, create minimal valid response
                                ai_response = {
                                    "intent": "help",
                                    "tips": ["Try logging expenses with: log [amount] [description]"]
                                }
                        
                        # Validate and clean response
                        return self._validate_ai_response(ai_response, time.time() - start_time)
                    
                    elif response.status_code == 429:
                        # Rate limited by Gemini
                        logger.warning(f"Gemini rate limited: {response.status_code}")
                        return {"failover": True, "reason": "gemini_rate_limited"}
                    
                    else:
                        logger.warning(f"Gemini API error: {response.status_code}")
                        if attempt < AI_MAX_RETRIES:
                            time.sleep(0.5)  # Brief retry delay
                            continue
                        
                except requests.Timeout:
                    logger.warning(f"Gemini timeout on attempt {attempt + 1} (waited {AI_TIMEOUT}s)")
                    if attempt < AI_MAX_RETRIES:
                        continue
                    
                except requests.RequestException as e:
                    logger.warning(f"Gemini request error: {e}")
                    if attempt < AI_MAX_RETRIES:
                        continue
            
            # All retries failed
            return {"failover": True, "reason": "gemini_failed"}
            
        except Exception as e:
            logger.error(f"Gemini parsing error: {e}")
            return {"failover": True, "reason": "parse_error"}
    
    def _build_prompt(self, text: str, context: Dict[str, Any]) -> str:
        """Build AI prompt with strict length constraints"""
        base_prompt = f"""Parse this expense message and respond with JSON:

Message: "{text}"

Expected JSON format:
{{
  "intent": "log|summary|help|undo",
  "amount": 123.45,
  "note": "description",
  "category": "food|ride|bill|grocery|other",
  "tips": ["helpful tip"]
}}

For expense logging, extract amount and description.
For summary requests, set intent to "summary".
For help/unclear messages, set intent to "help" and provide practical financial advice in tips.
For help requests, include 1-2 detailed money-saving tips (50-100 words each)."""
        
        # Ensure prompt stays under limit
        if len(base_prompt) > 1000:
            # Truncate message if needed
            max_msg_len = 1000 - (len(base_prompt) - len(text))
            if max_msg_len > 0:
                truncated_text = text[:max_msg_len]
                base_prompt = base_prompt.replace(f'"{text}"', f'"{truncated_text}"')
        
        return base_prompt
    
    def _validate_ai_response(self, ai_response: Dict[str, Any], duration_ms: float) -> Dict[str, Any]:
        """Validate and clean AI response"""
        try:
            # Ensure required fields
            validated = {
                "intent": ai_response.get("intent", "help"),
                "failover": False,
                "duration_ms": duration_ms * 1000
            }
            
            # Validate intent
            valid_intents = ["log", "summary", "help", "undo"]
            if validated["intent"] not in valid_intents:
                validated["intent"] = "help"
            
            # Clean optional fields
            if "amount" in ai_response:
                try:
                    validated["amount"] = float(ai_response["amount"])
                except (ValueError, TypeError):
                    pass
            
            if "note" in ai_response and ai_response["note"]:
                validated["note"] = str(ai_response["note"])[:100]  # Cap length
            
            if "category" in ai_response and ai_response["category"]:
                category = str(ai_response["category"]).lower()
                valid_categories = ["food", "ride", "bill", "grocery", "other"]
                if category in valid_categories:
                    validated["category"] = category
                else:
                    validated["category"] = "other"
            
            if "tips" in ai_response and isinstance(ai_response["tips"], list):
                # Keep only first 2 tips, max 50 chars each
                tips = []
                for tip in ai_response["tips"][:2]:
                    if isinstance(tip, str) and tip.strip():
                        tips.append(str(tip)[:400])  # Doubled from 200 to 400 chars for comprehensive advice
                if tips:
                    validated["tips"] = tips
            
            return validated
            
        except Exception as e:
            logger.error(f"AI response validation error: {e}")
            return {"failover": True, "reason": "validation_error"}
    
    def ai_mode(self, text: str) -> bool:
        """
        Determine if message should use AI processing
        Simple heuristics for canary rollout
        """
        if not self.enabled:
            return False
        
        # For now, use AI for all messages when enabled
        # Can add more sophisticated routing later
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get AI adapter status for telemetry"""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "timeout_s": AI_TIMEOUT,
            "max_retries": AI_MAX_RETRIES,
            "has_api_key": bool(OPENAI_API_KEY) if self.provider == "openai" else bool(GEMINI_API_KEY) if self.provider == "gemini" else None
        }
    
    def cleanup(self):
        """Cleanup resources"""
        if self.session:
            self.session.close()

# Global instance
production_ai_adapter = ProductionAIAdapter()