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
    
    def generate_insights(self, expenses_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate AI-powered spending insights and recommendations
        
        Args:
            expenses_data: Dictionary containing user's expense data and context
            
        Returns:
            Dict with insights, tips, and analysis
        """
        if not self.enabled:
            return {"failover": True, "reason": "ai_disabled"}
        
        # Route to appropriate provider
        if self.provider == "gemini":
            return self._generate_insights_gemini(expenses_data)
        elif self.provider == "openai":
            return self._generate_insights_openai(expenses_data)
        else:
            return {"failover": True, "reason": "unsupported_provider"}
    
    def _generate_insights_gemini(self, expenses_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights using Gemini API"""
        try:
            # Extract data for prompt
            total_amount = expenses_data.get('total_amount', 0)
            expenses = expenses_data.get('expenses', [])
            timeframe = expenses_data.get('timeframe', 'this month')
            
            # Build expense breakdown text
            expense_breakdown = ""
            if expenses:
                expense_breakdown = "\n".join([
                    f"• {exp.get('category', 'Uncategorized')}: ৳{exp.get('total', 0):,.0f} ({exp.get('percentage', 0):.1f}%)"
                    for exp in expenses[:8]  # Top 8 categories
                ])
            else:
                expense_breakdown = "No expenses found for this period"
            
            # Construct insights prompt
            insights_prompt = f"""Analyze these spending patterns and provide 3-4 actionable financial insights:

SPENDING SUMMARY ({timeframe}):
Total: ৳{total_amount:,.0f}
Breakdown:
{expense_breakdown}

Provide insights in this JSON format:
{{
  "insights": [
    "insight 1: specific observation with actionable advice",
    "insight 2: spending pattern with optimization tip", 
    "insight 3: budget recommendation or saving opportunity"
  ],
  "tone": "encouraging",
  "focus_area": "highest impact category for optimization"
}}

Make insights:
- Specific to their spending patterns
- Actionable (clear next steps)
- Encouraging and positive
- Bengali context-aware (mention local alternatives/tips when relevant)
- 1-2 sentences each, max 50 words per insight"""

            # Prepare API request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": insights_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 800,
                    "topP": 0.8
                }
            }
            
            # Make request with timeout
            response = self.session.post(url, json=payload, timeout=AI_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning(f"Gemini insights API error: {response.status_code}")
                return {"failover": True, "reason": f"api_error_{response.status_code}"}
            
            # Parse response
            data = response.json()
            candidates = data.get('candidates', [])
            
            if not candidates:
                return {"failover": True, "reason": "no_candidates"}
            
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            
            if not parts:
                return {"failover": True, "reason": "no_content"}
            
            ai_text = parts[0].get('text', '').strip()
            
            # Try to parse JSON response
            try:
                import json
                
                # Clean the response - sometimes it comes wrapped in markdown
                clean_text = ai_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                insights_json = json.loads(clean_text)
                return {
                    "success": True,
                    "insights": insights_json.get("insights", []),
                    "focus_area": insights_json.get("focus_area", "spending optimization"),
                    "raw_response": ai_text
                }
            except json.JSONDecodeError:
                # Fallback: extract insights from text
                insights = []
                lines = ai_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('{') and not line.startswith('}'):
                        if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                            insights.append(line[1:].strip())
                        elif len(line) > 20 and len(line) < 200:  # Reasonable insight length
                            insights.append(line)
                
                return {
                    "success": True,
                    "insights": insights[:4],  # Max 4 insights
                    "focus_area": "spending optimization",
                    "raw_response": ai_text
                }
                
        except Exception as e:
            logger.error(f"Gemini insights generation failed: {e}")
            return {"failover": True, "reason": f"exception: {str(e)[:50]}"}
    
    def _generate_insights_openai(self, expenses_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights using OpenAI API (fallback)"""
        # Similar implementation for OpenAI if needed
        return {"failover": True, "reason": "openai_insights_not_implemented"}
    
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
            base_system_prompt = """SYSTEM: You are the AI Interpretation Layer for finbrain (always lowercase).
Mission: Convert each user message into ONE strict Canonical Command (CC) JSON that is deterministic, auditable, and SAFE.
Your output drives (a) raw money capture, (b) overlay updates, and (c) clarifier UI.
Never emit free text—ONLY one JSON object.

INVARIANTS:
- Raw ledger is append-only; you never overwrite/delete it
- Fail closed: if uncertain or time budget breached, choose RAW_ONLY or HELP
- Determinism: same input → same output; no randomness
- ui_note must be ≤ 140 chars (router ensures total message ≤ platform limit)

CANONICAL COMMAND (CC) SCHEMA (pca-v1.2):
{
  "schema_version": "pca-v1.2",
  "cc_id": "auto-generated",
  "schema_hash": "pca-v1.2-cc-keys", 
  "user_id": "auto-populated",
  "intent": "LOG_EXPENSE" | "CORRECT" | "RELABEL" | "VOID" | "QUERY" | "HELP",
  "slots": {
    "amount": <number|null>,
    "currency": "BDT"|"USD"|"EUR"|null,
    "merchant_text": "<string|null>",
    "category": "<string|null>",
    "note": "<string|null>"
  },
  "confidence": <0.0 to 1.0>,
  "decision": "AUTO_APPLY" | "ASK_ONCE" | "RAW_ONLY",
  "clarifier": {
    "type": "category_pick" | "none",
    "options": ["<opt1>", "<opt2>", "<opt3>", "Other"],
    "prompt": "<=80 chars or empty"
  },
  "source_text": "<verbatim user message>",
  "model_version": "gpt-4o-mini-clarifiers",
  "ui_note": "<=140 chars human-friendly summary"
}

DECISION POLICY:
- If confidence ≥ 0.85 → decision="AUTO_APPLY" (no clarifier)
- If 0.55 ≤ confidence < 0.85 → decision="ASK_ONCE" with clarifier (3 options + "Other")
- If confidence < 0.55 and amount exists → decision="RAW_ONLY" (log raw, ask later)
- If no clear intent → intent="HELP" with brief ui_note

UI NOTES (examples):
- AUTO_APPLY: "Logged ৳500 food at 'Cheez' (yesterday)."
- ASK_ONCE: "Saved ৳500. Pick a category to confirm."
- RAW_ONLY: "Saved ৳500; category to confirm."
- HELP: "I log & correct expenses; say 'fix last entry'."

Categories: food, ride, bill, grocery, entertainment, utilities, fees, other

Multi-Currency: Recognize BDT (৳), $, €, £, ₹"""

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
        """Build CC prompt for confidence scoring & clarifier decisions"""
        # Import thresholds for decision logic
        from utils.pca_flags import pca_flags
        tau_high, tau_low = pca_flags.get_clarifier_thresholds()
        
        base_prompt = f"""User Message: "{text}"

Output STRICT Canonical Command JSON (no extra text):

EXAMPLES:

High confidence (≥{tau_high}): "Starbux 780 yesterday"
{{
  "schema_version": "pca-v1.2",
  "intent": "LOG_EXPENSE",
  "slots": {{"amount": 780, "currency": "BDT", "merchant_text": "Starbux", "category": "food", "note": "coffee"}},
  "confidence": 0.93,
  "decision": "AUTO_APPLY",
  "clarifier": {{"type": "none", "options": [], "prompt": ""}},
  "source_text": "{text}",
  "model_version": "gpt-4o-mini-clarifiers",
  "ui_note": "Logged ৳780 food at 'Starbux' (yesterday)."
}}

Mid confidence ({tau_low}-{tau_high}): "bkash 500"
{{
  "schema_version": "pca-v1.2",
  "intent": "LOG_EXPENSE",
  "slots": {{"amount": 500, "currency": "BDT", "merchant_text": "bkash", "category": null, "note": "payment"}},
  "confidence": 0.62,
  "decision": "ASK_ONCE",
  "clarifier": {{"type": "category_pick", "options": ["utilities", "fees", "other", "Other"], "prompt": "What type of payment?"}},
  "source_text": "{text}",
  "model_version": "gpt-4o-mini-clarifiers",
  "ui_note": "Saved ৳500. Pick a category to confirm."
}}

Low confidence (<{tau_low}): "mart payment 1200"
{{
  "schema_version": "pca-v1.2",
  "intent": "LOG_EXPENSE",
  "slots": {{"amount": 1200, "currency": "BDT", "merchant_text": "mart", "category": null, "note": "payment"}},
  "confidence": 0.32,
  "decision": "RAW_ONLY",
  "clarifier": {{"type": "none", "options": [], "prompt": ""}},
  "source_text": "{text}",
  "model_version": "gpt-4o-mini-clarifiers",
  "ui_note": "Saved ৳1200; category to confirm."
}}

Help/unclear: "what can you do"
{{
  "schema_version": "pca-v1.2",
  "intent": "HELP",
  "slots": {{}},
  "confidence": 1.0,
  "decision": "AUTO_APPLY",
  "clarifier": {{"type": "none", "options": [], "prompt": ""}},
  "source_text": "{text}",
  "model_version": "gpt-4o-mini-clarifiers",
  "ui_note": "I log & correct expenses; say 'fix last entry'."
}}

Categories: food, ride, bill, grocery, entertainment, utilities, fees, other
ALWAYS: ui_note ≤140 chars, source_text verbatim, confidence 0.0-1.0"""
        
        # Ensure prompt stays under limit
        if len(base_prompt) > 1400:
            # Truncate message if needed
            max_msg_len = 1400 - (len(base_prompt) - len(text))
            if max_msg_len > 0:
                truncated_text = text[:max_msg_len]
                base_prompt = base_prompt.replace(f'"{text}"', f'"{truncated_text}"')
        
        return base_prompt
    
    def _validate_ai_response(self, ai_response: Dict[str, Any], duration_ms: float) -> Dict[str, Any]:
        """Validate and clean Canonical Command response"""
        try:
            from utils.pca_flags import pca_flags
            
            # Check if this is legacy format vs CC format
            if "schema_version" not in ai_response:
                # Legacy format - convert to minimal CC for backward compatibility
                return self._convert_legacy_response(ai_response, duration_ms)
            
            # Validate CC schema
            validated = {
                "schema_version": ai_response.get("schema_version", "pca-v1.2"),
                "intent": ai_response.get("intent", "HELP"),
                "confidence": float(ai_response.get("confidence", 0.5)),
                "decision": ai_response.get("decision", "RAW_ONLY"),
                "source_text": str(ai_response.get("source_text", ""))[:500],
                "model_version": ai_response.get("model_version", "gpt-4o-mini-clarifiers"),
                "ui_note": str(ai_response.get("ui_note", ""))[:140],  # Enforce 140 char limit
                "failover": False,
                "duration_ms": duration_ms * 1000
            }
            
            # Validate intent
            valid_intents = ["LOG_EXPENSE", "CORRECT", "RELABEL", "VOID", "QUERY", "HELP"]
            if validated["intent"] not in valid_intents:
                validated["intent"] = "HELP"
            
            # Validate decision
            valid_decisions = ["AUTO_APPLY", "ASK_ONCE", "RAW_ONLY"]
            if validated["decision"] not in valid_decisions:
                validated["decision"] = "RAW_ONLY"
            
            # Validate confidence range
            if not (0.0 <= validated["confidence"] <= 1.0):
                validated["confidence"] = 0.5
            
            # Validate slots
            slots = ai_response.get("slots", {})
            if isinstance(slots, dict):
                validated_slots = {}
                if "amount" in slots:
                    try:
                        validated_slots["amount"] = float(slots["amount"])
                    except (ValueError, TypeError):
                        pass
                
                if "currency" in slots and slots["currency"]:
                    currency = str(slots["currency"]).upper()
                    valid_currencies = ["BDT", "USD", "EUR", "GBP", "INR"]
                    if currency in valid_currencies:
                        validated_slots["currency"] = currency
                
                if "category" in slots and slots["category"]:
                    category = str(slots["category"]).lower()
                    valid_categories = ["food", "ride", "bill", "grocery", "entertainment", "utilities", "fees", "other"]
                    if category in valid_categories:
                        validated_slots["category"] = category
                
                if "merchant_text" in slots and slots["merchant_text"]:
                    validated_slots["merchant_text"] = str(slots["merchant_text"])[:100]
                
                if "note" in slots and slots["note"]:
                    validated_slots["note"] = str(slots["note"])[:200]
                
                validated["slots"] = validated_slots
            
            # Validate clarifier
            clarifier = ai_response.get("clarifier", {})
            if isinstance(clarifier, dict):
                validated_clarifier = {
                    "type": str(clarifier.get("type", "none")),
                    "options": clarifier.get("options", []),
                    "prompt": str(clarifier.get("prompt", ""))[:80]
                }
                
                # Validate clarifier type
                valid_clarifier_types = ["category_pick", "none"]
                if validated_clarifier["type"] not in valid_clarifier_types:
                    validated_clarifier["type"] = "none"
                
                # Validate options
                if not isinstance(validated_clarifier["options"], list):
                    validated_clarifier["options"] = []
                else:
                    # Limit to 4 options max, 20 chars each
                    validated_clarifier["options"] = [
                        str(opt)[:20] for opt in validated_clarifier["options"][:4]
                    ]
                
                validated["clarifier"] = validated_clarifier
            
            return validated
            
        except Exception as e:
            logger.error(f"CC validation error: {e}")
            return {"failover": True, "reason": "cc_validation_error"}
    
    def _convert_legacy_response(self, legacy_response: Dict[str, Any], duration_ms: float) -> Dict[str, Any]:
        """Convert legacy response format to CC format for backward compatibility"""
        return {
            "schema_version": "legacy-compat",
            "intent": "HELP",
            "confidence": 0.5,
            "decision": "AUTO_APPLY",
            "ui_note": legacy_response.get("acknowledgment", "I help with expenses")[:140],
            "failover": False,
            "duration_ms": duration_ms * 1000,
            "legacy_data": legacy_response
        }
    
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