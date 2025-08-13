#!/usr/bin/env python3
"""
Provider switching demonstration
Shows how to switch between OpenAI and Gemini at runtime
"""

import requests
import json

BASE_URL = "http://localhost:5000"
AUTH = ("secure_password_here", "admin")

def switch_provider_demo():
    """Demonstrate provider switching capabilities"""
    print("FinBrain Multi-Provider System Demo")
    print("=" * 50)
    
    # Test current configuration
    print("\n=== Current System Status ===")
    try:
        resp = requests.get(f"{BASE_URL}/ops/telemetry", auth=AUTH, timeout=5)
        config = resp.json().get("config", {})
        
        provider = config.get("ai_provider", "none")
        enabled = config.get("ai_enabled_effective", False)
        model = config.get("gemini_model", "not set")
        
        print(f"AI Provider: {provider}")
        print(f"AI Enabled: {enabled}")
        if provider == "gemini":
            print(f"Gemini Model: {model}")
            
    except Exception as e:
        print(f"Error getting status: {e}")
        return
    
    # Test AI ping
    print("\n=== AI Ping Test ===")
    try:
        resp = requests.get(f"{BASE_URL}/ops/ai/ping", auth=AUTH, timeout=10)
        ping_data = resp.json()
        
        print(f"AI Ping Result:")
        print(f"  OK: {ping_data.get('ok', False)}")
        print(f"  Reply: {ping_data.get('reply', 'No reply')}")
        print(f"  Error: {ping_data.get('error', 'No error')}")
        print(f"  Latency: {ping_data.get('latency_ms', 0)}ms")
        
    except Exception as e:
        print(f"Error testing AI ping: {e}")
    
    # Show next steps
    print("\n=== Next Steps for Full AI Functionality ===")
    print("1. For Gemini:")
    print("   - Set GEMINI_API_KEY environment variable")
    print("   - Use /ops/ai/toggle to enable AI")
    print("   - Send test messages")
    print()
    print("2. For OpenAI:")
    print("   - Set AI_PROVIDER=openai")
    print("   - Set OPENAI_API_KEY environment variable") 
    print("   - Use /ops/ai/toggle to enable AI")
    print()
    print("3. Provider switching works by:")
    print("   - Changing AI_PROVIDER environment variable")
    print("   - Restarting the application")
    print("   - System automatically selects correct adapter")
    
    print("\n=== Runtime Toggle Demo ===")
    # Test AI toggle functionality
    try:
        # Toggle off
        resp = requests.post(
            f"{BASE_URL}/ops/ai/toggle",
            auth=AUTH,
            json={"enabled": False},
            timeout=5
        )
        print("AI toggled OFF:", resp.json())
        
        # Toggle back on
        resp = requests.post(
            f"{BASE_URL}/ops/ai/toggle",
            auth=AUTH,
            json={"enabled": True},
            timeout=5
        )
        print("AI toggled ON:", resp.json())
        
    except Exception as e:
        print(f"Error testing toggle: {e}")

if __name__ == "__main__":
    switch_provider_demo()