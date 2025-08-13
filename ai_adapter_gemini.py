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
            contents=[{"role": "user", "parts": [{"text": user_text}]}],
            timeout=TIMEOUT
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
        logger.warning(f"Gemini generation failed in {latency_ms}ms: {str(e)}")
        
        return {
            "ok": False, 
            "error": str(e), 
            "latency_ms": latency_ms
        }

def get_stats():
    """Get Gemini adapter status"""
    return {
        "configured": client is not None,
        "provider": "gemini",
        "model": MODEL,
        "timeout_ms": AI_TIMEOUT_MS
    }