"""
Gemini AI adapter - drop-in replacement for OpenAI
Uses google-genai SDK with gemini-2.5-flash-lite model
"""
import os
import time
import logging
from config import GEMINI_API_KEY, GEMINI_MODEL, AI_TIMEOUT_MS

logger = logging.getLogger(__name__)

# Initialize Gemini client
client = None
if GEMINI_API_KEY:
    try:
        from google.genai import Client
        from google.genai.types import GenerateContentConfig
        client = Client(api_key=GEMINI_API_KEY)
    except ImportError as e:
        logger.error(f"Failed to import google-genai: {e}")
        client = None

# Configuration
MODEL = GEMINI_MODEL
TIMEOUT = AI_TIMEOUT_MS / 1000.0
SYSTEM = "You are FinBrain, a concise personal finance assistant. Keep replies under 120 tokens."

def generate(user_text: str):
    """
    Generate AI response using Gemini
    Returns: {"ok": bool, "text": str, "latency_ms": int, "error": str}
    """
    start = time.time()
    
    if not client:
        return {
            "ok": False, 
            "error": "Gemini not configured", 
            "latency_ms": int((time.time()-start)*1000)
        }
    
    try:
        from google.genai.types import GenerateContentConfig
        
        cfg = GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0.2,
            max_output_tokens=160,
        )
        
        resp = client.models.generate_content(
            model=MODEL,
            config=cfg,
            contents=[{"role": "user", "parts": [{"text": user_text}]}]
        )
        
        # Extract text from response
        txt = resp.text.strip() if hasattr(resp, "text") and resp.text else ""
        
        if not txt:
            return {
                "ok": False,
                "error": "Empty response from Gemini",
                "latency_ms": int((time.time()-start)*1000)
            }
        
        latency_ms = int((time.time()-start)*1000)
        logger.info(f"Gemini response generated in {latency_ms}ms")
        
        return {
            "ok": True, 
            "text": txt, 
            "latency_ms": latency_ms
        }
        
    except Exception as e:
        latency_ms = int((time.time()-start)*1000)
        
        # Sanitize error message - never log API keys
        error_msg = str(e)
        if 'api_key' in error_msg.lower() or 'x-goog' in error_msg.lower():
            error_msg = "API authentication error (details redacted for security)"
        
        logger.warning(f"Gemini generation failed in {latency_ms}ms: {error_msg}")
        
        return {
            "ok": False, 
            "error": error_msg, 
            "latency_ms": latency_ms
        }

def generate_with_schema(user_text, system_prompt, response_schema=None):
    """
    Generate Gemini response with JSON schema enforcement
    
    Args:
        user_text: User message
        system_prompt: System instruction
        response_schema: JSON schema for structured response
        
    Returns:
        Dict with structured response or error
    """
    start = time.time()
    
    if not client:
        return {"ok": False, "error": "Gemini not configured"}
    
    try:
        from google.genai.types import GenerateContentConfig
        
        cfg = GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            max_output_tokens=400
        )
        
        # Enable JSON mode if schema provided
        if response_schema:
            cfg.response_mime_type = "application/json"
        
        resp = client.models.generate_content(
            model=MODEL,
            config=cfg,
            contents=[{"role": "user", "parts": [{"text": user_text}]}]
        )
        
        txt = resp.text.strip() if hasattr(resp, "text") and resp.text else ""
        
        if not txt:
            return {"ok": False, "error": "Empty response from Gemini"}
        
        latency_ms = int((time.time()-start)*1000)
        
        # Parse JSON if schema requested
        if response_schema:
            try:
                import json
                # Clean common formatting issues
                if txt.startswith("```json"):
                    txt = txt.replace("```json", "").replace("```", "").strip()
                
                parsed = json.loads(txt)
                
                # Validate required fields
                if "required" in response_schema:
                    missing = [field for field in response_schema["required"] if field not in parsed]
                    if missing:
                        return {"ok": False, "error": f"Missing required fields: {missing}"}
                
                return {"ok": True, "data": parsed, "latency_ms": latency_ms}
                
            except json.JSONDecodeError as e:
                return {"ok": False, "error": f"JSON parse failed: {e}", "raw_text": txt}
        
        return {"ok": True, "text": txt, "latency_ms": latency_ms}
        
    except Exception as e:
        latency_ms = int((time.time()-start)*1000)
        error_msg = str(e)
        if 'api_key' in error_msg.lower() or 'x-goog' in error_msg.lower():
            error_msg = "API authentication error (details redacted for security)"
        
        return {"ok": False, "error": error_msg, "latency_ms": latency_ms}

def get_stats():
    """Get Gemini adapter status"""
    return {
        "configured": client is not None,
        "provider": "gemini",
        "model": MODEL,
        "timeout_ms": AI_TIMEOUT_MS
    }