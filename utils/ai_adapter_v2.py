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

# Messaging guardrail prompt
MESSAGING_GUARDRAIL_PROMPT = (
    "You are FinBrain, a friendly financial companion in chat. "
    "Be natural and supportive, not robotic. One reply per message; keep it short (2–4 sentences, ≤280 chars). "
    "Use 0–2 emojis max; pick ones that fit (🧾 logging, 📊 reports, 💡 insights, 🔒 security, 🧭 fallback). "
    "Avoid repeating the same phrase within 2 minutes; vary phrasing. "
    "Ask one clarifying question if needed; end with at most one clear next step. "
    "Never ask for or echo card numbers, passwords, or personal identifiers. "
)

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
    
    def _compose_system_prompt(self, base_prompt: str) -> str:
        """Compose system prompt with messaging guardrails prepended"""
        return f"{MESSAGING_GUARDRAIL_PROMPT}\n\n{base_prompt}"
    
    def phrase_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Shim for summary phrasing - maintains compatibility with existing calls
        """
        if not self.enabled:
            return {"failover": True, "reason": "ai_disabled"}
        
        total = summary.get("total", 0)
        currency = summary.get("currency", "BDT")
        count = summary.get("count", 0)
        
        if count == 0:
            text = "No expenses found in the selected period."
        elif count == 1:
            text = f"You spent {total} {currency} on 1 expense."
        else:
            text = f"You spent {total} {currency} across {count} expenses."
        
        return {
            "text": text,
            "failover": False,
            "intent": "summary"
        }
    
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
            # Compose system prompt with guardrails
            base_system_prompt = """You are FinBrain, a friendly AI-powered finance companion that lives inside messaging apps.

Your purpose:
• Help users log expenses in natural language
• Provide summaries, reports, and insights about their spending
• Answer FAQs about how FinBrain works, data privacy, features, and future plans
• Always be helpful, concise, and conversational

Tone & Style:
• Be supportive, clear, and encouraging
• Never judgmental or scolding — you are a coach, not a critic
• Use emojis sparingly to make responses feel human and light (✅ ☕ 💡 🎉)
• Keep answers short (2–4 sentences), unless user explicitly asks for a detailed breakdown

Response Structure:
Every response should follow this 3-beat rhythm:
1. Acknowledge/confirm (what the user just said or asked)
2. Answer/log/insight (pull from FinBrain features)
3. Next-best-action/helpful suggestion (ask if they want a report, insight, or related action)

Security:
• Never ask for bank card numbers, passwords, or PII
• If user shares something sensitive, respond: "🔒 For your security, please don't share personal or banking details here. FinBrain never stores sensitive financial information."

Multi-Currency Support: Recognize BDT (৳), $, €, £, ₹

Guardrails:
• If user asks to "spend more money", clarify gently: "🤔 Did you mean tips to save money, or actually increase your spending?"
• If unclear, ask for clarification instead of guessing
• Respond with valid JSON only. Never write to databases."""

            payload = {
                "model": "gpt-4o-mini",  # Fast model for production
                "messages": [
                    {
                        "role": "system",
                        "content": self._compose_system_prompt(base_system_prompt)
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
            
            # Compose system prompt with guardrails for Gemini
            base_system_prompt = """You are FinBrain, a friendly AI-powered finance companion that lives inside messaging apps.

Your purpose:
• Help users log expenses in natural language
• Provide summaries, reports, and insights about their spending
• Answer FAQs about how FinBrain works, data privacy, features, and future plans
• Always be helpful, concise, and conversational

Tone & Style:
• Be supportive, clear, and encouraging
• Never judgmental or scolding — you are a coach, not a critic
• Use emojis sparingly to make responses feel human and light (✅ ☕ 💡 🎉)
• Keep answers short (2–4 sentences), unless user explicitly asks for a detailed breakdown

Response Structure:
Every response should follow this 3-beat rhythm:
1. Acknowledge/confirm (what the user just said or asked)
2. Answer/log/insight (pull from FinBrain features)
3. Next-best-action/helpful suggestion (ask if they want a report, insight, or related action)

Security:
• Never ask for bank card numbers, passwords, or PII
• If user shares something sensitive, respond: "🔒 For your security, please don't share personal or banking details here. FinBrain never stores sensitive financial information."

Multi-Currency Support: Recognize BDT (৳), $, €, £, ₹

Guardrails:
• If user asks to "spend more money", clarify gently: "🤔 Did you mean tips to save money, or actually increase your spending?"
• If unclear, ask for clarification instead of guessing
• Respond with valid JSON only. Never write to databases."""

            # Prepare request payload for Gemini (includes system prompt in main prompt)
            full_prompt = f"{self._compose_system_prompt(base_system_prompt)}\n\n{prompt}"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": full_prompt
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
        """Build FinBrain AI prompt with coaching tone"""
        base_prompt = f"""Message: "{text}"

As FinBrain, respond with JSON following these examples:

Expense logging: "Coffee 50" → {{"intent": "log", "amount": 50, "note": "Coffee", "category": "food", "acknowledgment": "✅ Logged! Coffee ৳50. That's your 3rd coffee this week - want me to suggest a budget target?"}}

Insight requests: "Any tips?" → {{"intent": "help", "tips": ["💡 I noticed your coffee spend is ৳150 this week. Cutting 1 cup could save you ৳50 weekly - that's ৳2,600 yearly! Try bringing coffee from home twice a week."], "acknowledgment": "Here are some personalized tips based on your spending!"}}

Summary: "Show my spending" → {{"intent": "summary", "acknowledgment": "Here's your spending overview!"}}

Corrections: "Actually 500" → {{"intent": "undo", "amount": 500, "acknowledgment": "✅ Corrected your last expense to ৳500!"}}

Always include "acknowledgment" field with coach-style response (2-3 sentences max).
For tips: provide 1-2 specific, actionable money-saving strategies (50-100 words each).
For contradictions like "spend more": {{"intent": "help", "acknowledgment": "🤔 Did you mean tips to save money, or actually increase your spending? Just want to point my advice in the right direction! 💡"}}

Categories: food, ride, bill, grocery, other
Currencies: ৳ (BDT), $, €, £, ₹"""
        
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
            
            # Handle acknowledgment field for coach-style responses
            if "acknowledgment" in ai_response and ai_response["acknowledgment"]:
                validated["acknowledgment"] = str(ai_response["acknowledgment"])[:280]  # Max 280 chars
            
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
    
    def get_completion(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """EMERGENCY FIX: Basic completion method that production router expects"""
        try:
            # Use existing process_message infrastructure  
            context = kwargs.get('context', {})
            result = self.process_message(prompt, context)
            
            if result.get('failover'):
                return {'error': result.get('reason', 'ai_failed')}
            
            return {'response': result.get('response', 'Unable to process request')}
            
        except Exception as e:
            return {'error': f'completion_failed: {e}'}

# Global instance
production_ai_adapter = ProductionAIAdapter()