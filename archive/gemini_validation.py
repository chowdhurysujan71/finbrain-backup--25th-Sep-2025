#!/usr/bin/env python3
"""
Quick Gemini validation script
Tests the new Gemini integration with streamlined architecture
"""

import requests
import json
import os

BASE_URL = "http://localhost:5000"
AUTH = ("secure_password_here", "admin")

def test_config():
    """1) Verify Gemini config in telemetry"""
    print("=== Config Verification ===")
    
    try:
        resp = requests.get(f"{BASE_URL}/ops/telemetry", auth=AUTH, timeout=5)
        data = resp.json()
        
        config = data.get("config", {})
        ai_enabled = config.get("ai_enabled_effective", False)
        provider = config.get("ai_provider", "none")
        gemini_model = config.get("gemini_model", "not set")
        rl = config.get("rl", {})
        
        print(f"AI Enabled (effective): {ai_enabled}")
        print(f"AI Provider: {provider}")
        print(f"Gemini Model: {gemini_model}")
        print(f"Rate Limits: {rl}")
        
        if provider == "gemini":
            print("✓ PASS: Gemini provider configured")
            return True
        else:
            print("✗ FAIL: Provider not set to gemini")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

def test_ai_ping():
    """2) Health-check the Gemini adapter"""
    print("\n=== AI Ping Test ===")
    
    try:
        resp = requests.get(f"{BASE_URL}/ops/ai/ping", auth=AUTH, timeout=10)
        data = resp.json()
        
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get("ok") and "PONG" in data.get("reply", "").upper():
            print("✓ PASS: Gemini responding correctly")
            return True
        else:
            print("✗ FAIL: Gemini not responding correctly")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

def test_rate_limiting():
    """3) Test rate limiting behavior"""
    print("\n=== Rate Limiting Test ===")
    print("Note: This test simulates the behavior.")
    print("In real usage, send 3 messages <60s to same user")
    print("Expected: first two 'path=ai', third 'path=fallback' reason=rate_limit")
    
    # For now, just verify the rate limiting stats are available
    try:
        resp = requests.get(f"{BASE_URL}/ops/telemetry", auth=AUTH, timeout=5)
        data = resp.json()
        
        rate_limiting = data.get("rate_limiting", {})
        print(f"Rate limiting stats: {json.dumps(rate_limiting, indent=2)}")
        
        if "global_limit" in rate_limiting and "per_user_limit" in rate_limiting:
            print("✓ PASS: Rate limiting configured")
            return True
        else:
            print("✗ FAIL: Rate limiting not properly configured")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

def run_validation():
    """Run Gemini validation suite"""
    print("FinBrain Gemini Integration Validation")
    print("=" * 50)
    
    tests = [
        ("Config Verification", test_config),
        ("AI Ping Test", test_ai_ping),
        ("Rate Limiting Check", test_rate_limiting)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"Test '{test_name}' crashed: {e}")
    
    print("\n" + "=" * 50)
    print("GEMINI VALIDATION RESULTS")
    print("=" * 50)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 GEMINI INTEGRATION READY")
        print("\nNext steps:")
        print("1. Set GEMINI_API_KEY in environment")
        print("2. Use /ops/ai/toggle to enable AI")
        print("3. Send test messages to verify AI responses")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nTroubleshooting:")
        print("- Check GEMINI_API_KEY is set")
        print("- Verify AI_PROVIDER=gemini in environment")
        print("- Check google-genai package is installed")
    
    return passed == total

if __name__ == "__main__":
    success = run_validation()
    exit(0 if success else 1)