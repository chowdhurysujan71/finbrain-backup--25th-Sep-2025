"""
OpenAI AI adapter - clean implementation for multi-provider architecture
Direct OpenAI integration with 3s timeout and immediate fallback
"""
import os
import time
import logging
from config import AI_TIMEOUT_MS, OPENAI_API_KEY
from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

def generate(user_text, sys="You are FinBrain, a concise personal finance assistant. Keep replies under 120 tokens."):
    """
    Generate AI response with fail-fast approach
    Returns: {"ok": bool, "text": str, "latency_ms": int, "error": str}
    """
    start = time.time()
    
    if not client:
        return {
            "ok": False, 
            "error": "OpenAI not configured", 
            "latency_ms": int((time.time()-start)*1000)
        }
    
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user_text}
            ],
            temperature=0.2,
            timeout=AI_TIMEOUT_MS/1000.0,
            max_tokens=120
        )
        
        txt = resp.choices[0].message.content.strip()
        latency_ms = int((time.time()-start)*1000)
        
        logger.info(f"OpenAI response generated in {latency_ms}ms")
        
        return {
            "ok": True, 
            "text": txt, 
            "latency_ms": latency_ms
        }
        
    except Exception as e:
        latency_ms = int((time.time()-start)*1000)
        logger.warning(f"OpenAI generation failed in {latency_ms}ms: {str(e)}")
        
        return {
            "ok": False, 
            "error": str(e), 
            "latency_ms": latency_ms
        }

def get_stats():
    """Get OpenAI adapter status"""
    return {
        "configured": client is not None,
        "provider": "openai",
        "model": "gpt-4o-mini",
        "timeout_ms": AI_TIMEOUT_MS
    }