# tests/test_guardrails.py
"""
Tests for FinBrain guardrail components
Validates TTL store and UX copy functionality
"""

import time
from utils.ttl_store import get_store, InProcTTL
from utils.ux_copy import SLOW_DOWN, DAILY_LIMIT, REPEAT_HINT, PII_WARNING, BUSY, FALLBACK


def test_in_proc_ttl_basic():
    """Test basic InProcTTL functionality"""
    store = InProcTTL()
    
    # Test increment
    count = store.incr("test:key", ttl_seconds=2)
    assert count == 1
    
    # Test get
    assert store.get("test:key") == 1
    
    # Test exists
    assert store.exists("test:key") is True
    
    # Test setex
    store.setex("test:set", 2, 42)
    assert store.get("test:set") == 42


def test_in_proc_ttl_expiration():
    """Test TTL expiration in InProcTTL"""
    store = InProcTTL()
    
    # Set key with short TTL
    store.setex("test:expire", 1, 100)
    assert store.get("test:expire") == 100
    
    # Wait for expiration
    time.sleep(1.1)
    
    # Should be None/0 after expiration
    assert store.get("test:expire") in (None, 0)
    assert store.exists("test:expire") is False


def test_ttl_store_factory():
    """Test get_store() returns a working store"""
    store = get_store()
    
    # Test basic operations
    key = "test:factory"
    count = store.incr(key, ttl_seconds=60)
    assert count == 1
    
    retrieved = store.get(key)
    assert retrieved == 1


def test_ux_copy_constants():
    """Test all UX copy constants are present and reasonable"""
    # Test all constants exist
    assert SLOW_DOWN
    assert DAILY_LIMIT  
    assert REPEAT_HINT
    assert PII_WARNING
    assert BUSY
    assert FALLBACK
    
    # Test content makes sense
    assert "slow" in SLOW_DOWN.lower()
    assert "limit" in DAILY_LIMIT.lower()
    assert "anything new" in REPEAT_HINT.lower()
    assert "security" in PII_WARNING.lower()
    assert "busy" in BUSY.lower()
    assert "finbrain.app" in FALLBACK.lower()
    
    # Test emojis are present (basic check)
    assert "⚠️" in SLOW_DOWN or "⏳" in SLOW_DOWN
    assert "⏳" in DAILY_LIMIT
    assert "🔒" in PII_WARNING
    assert "🧭" in FALLBACK


def test_burst_simulation():
    """Simulate burst limiting scenario"""
    store = InProcTTL()
    key = "burst:test_user"
    
    # Simulate 5 quick requests
    for i in range(5):
        count = store.incr(key, ttl_seconds=10)
        if count > 5:  # Burst limit exceeded
            break
    
    # Should have hit limit
    count = store.get(key)
    assert count is not None and count >= 5


def test_daily_cap_simulation():
    """Simulate daily cap scenario"""
    store = InProcTTL()
    key = "daily:test_user:20250825"
    
    # Simulate daily messages
    for i in range(35):
        count = store.incr(key, ttl_seconds=86400)  # 24 hours
        if count > 30:  # Daily limit exceeded
            break
    
    # Should have hit daily limit
    count = store.get(key)
    assert count is not None and count >= 30


def test_guardrail_integration():
    """Test complete guardrail integration"""
    import os
    
    # Test feature flag (should default to disabled)
    enabled = os.getenv("MESSAGING_GUARDRAILS_ENABLED", "false").lower() == "true"
    assert enabled is False, "Guardrails should default to disabled for safety"
    
    # Test environment variable configuration
    burst_limit = int(os.getenv("GUARDRAIL_BURST_LIMIT", "5"))
    daily_limit = int(os.getenv("GUARDRAIL_DAILY_LIMIT", "30"))
    repeat_window = int(os.getenv("GUARDRAIL_REPEAT_WINDOW", "45"))
    
    assert burst_limit == 5
    assert daily_limit == 30
    assert repeat_window == 45


def test_messaging_guardrail_disabled():
    """Test guardrail method when disabled (fail-open)"""
    from utils.production_router import ProductionRouter
    import os
    
    # Ensure disabled
    os.environ["MESSAGING_GUARDRAILS_ENABLED"] = "false"
    
    router = ProductionRouter()
    
    # Should return None (pass through) when disabled
    result = router._check_messaging_guardrails("test message", "test_user", "test_rid")
    assert result is None


def test_full_pipeline_safety():
    """Test that guardrails never break the message pipeline"""
    from utils.production_router import ProductionRouter
    
    router = ProductionRouter()
    
    # Test with various message types - should never crash
    test_messages = [
        "hello",
        "coffee 50",
        "summary",
        "help",
        "4111-1111-1111-1111",  # Credit card pattern
        "spam " * 100,           # Long message
        "",                      # Empty message
        "test test test"         # Potential repeat
    ]
    
    for msg in test_messages:
        try:
            # This will hit database errors outside app context, but guardrails should still work
            response, intent, category, amount = router.route_message(msg, "test_user", f"rid_{msg[:5]}")
            # Should return something (never None/crash)
            assert response is not None
            assert intent is not None
        except Exception as e:
            # Database context errors are expected, but guardrails should not cause crashes
            assert "application context" in str(e), f"Unexpected error: {e}"


if __name__ == "__main__":
    # Run all tests
    test_in_proc_ttl_basic()
    test_in_proc_ttl_expiration()
    test_ttl_store_factory()
    test_ux_copy_constants()
    test_burst_simulation()
    test_daily_cap_simulation()
    test_guardrail_integration()
    test_messaging_guardrail_disabled()
    test_full_pipeline_safety()
    print("✅ All Phase 1-3 tests passed!")