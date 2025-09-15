#!/usr/bin/env python3
"""
Test script to verify centralized configuration is working correctly
Validates all constants can be imported and have expected default values
"""

def test_centralized_config():
    """Test all centralized configuration constants"""
    
    print("=== CENTRALIZED CONFIGURATION TEST ===")
    
    # Test rate limiting configuration
    from config import AI_RL_USER_LIMIT, AI_RL_WINDOW_SEC, AI_RL_GLOBAL_LIMIT
    assert AI_RL_USER_LIMIT == 4, f"Expected 4, got {AI_RL_USER_LIMIT}"
    assert AI_RL_WINDOW_SEC == 60, f"Expected 60, got {AI_RL_WINDOW_SEC}"
    assert AI_RL_GLOBAL_LIMIT == 120, f"Expected 120, got {AI_RL_GLOBAL_LIMIT}"
    print("✓ Rate limiting config: OK")
    
    # Test application constants
    from config import MSG_MAX_CHARS, TIMEZONE, CURRENCY_SYMBOL, DEFAULT_CATEGORY
    assert MSG_MAX_CHARS == 280, f"Expected 280, got {MSG_MAX_CHARS}"
    assert TIMEZONE == "Asia/Dhaka", f"Expected Asia/Dhaka, got {TIMEZONE}"
    assert CURRENCY_SYMBOL == "৳", f"Expected ৳, got {CURRENCY_SYMBOL}"
    assert DEFAULT_CATEGORY == "other", f"Expected other, got {DEFAULT_CATEGORY}"
    print("✓ Application constants: OK")
    
    # Test textutil integration
    from utils.textutil import MAX_REPLY_LEN
    assert MAX_REPLY_LEN == MSG_MAX_CHARS, f"Textutil integration failed: {MAX_REPLY_LEN} != {MSG_MAX_CHARS}"
    print("✓ Textutil integration: OK")
    
    # Test rate limiter integration
    from limiter import can_use_ai, RL2_USER, RL2_GLOBAL
    assert RL2_USER.limit == AI_RL_USER_LIMIT, f"RL2_USER limit mismatch: {RL2_USER.limit} != {AI_RL_USER_LIMIT}"
    assert RL2_GLOBAL.limit == AI_RL_GLOBAL_LIMIT, f"RL2_GLOBAL limit mismatch: {RL2_GLOBAL.limit} != {AI_RL_GLOBAL_LIMIT}"
    print("✓ Rate limiter integration: OK")
    
    print("\n=== CONFIGURATION SMOKE TEST ===")
    
    # Test rate limiting functionality
    allowed, retry = can_use_ai("test_user_config")
    assert allowed == True, "First request should be allowed"
    print(f"✓ Rate limiter: {allowed}, retry: {retry}s")
    
    # Test multiple requests up to limit
    for i in range(2, AI_RL_USER_LIMIT + 1):
        allowed, retry = can_use_ai("test_user_config")
        assert allowed == True, f"Request {i} should be allowed"
    
    # Test limit exceeded
    allowed, retry = can_use_ai("test_user_config")
    assert allowed == False, "Request beyond limit should be denied"
    assert retry > 0, "Retry time should be positive"
    print(f"✓ Rate limit enforced: denied with {retry}s retry")
    
    print("\n✅ ALL TESTS PASSED - CENTRALIZED CONFIG WORKING")
    return True

if __name__ == "__main__":
    try:
        test_centralized_config()
        exit(0)
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        exit(1)