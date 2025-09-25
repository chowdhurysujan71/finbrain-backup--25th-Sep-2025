"""
Test suite for summary intent detection and routing
"""
from utils.production_router import _is_summary_command


def test_summary_detection_variants():
    """Test various summary command patterns"""
    # Basic commands
    assert _is_summary_command("summary")
    assert _is_summary_command("Summary")
    assert _is_summary_command("SUMMARY")
    
    # Natural language variations
    assert _is_summary_command("Can you do a summary?")
    assert _is_summary_command("what did I spend this week?")
    assert _is_summary_command("how much did i spend")
    assert _is_summary_command("show me my spending")
    assert _is_summary_command("show my expenses")
    
    # Alternative keywords
    assert _is_summary_command("recap")
    assert _is_summary_command("overview")
    assert _is_summary_command("report")
    
    # In-sentence detection
    assert _is_summary_command("Please give me a summary of my spending")
    assert _is_summary_command("I need a recap please")
    
    # Negative cases
    assert not _is_summary_command("hello there")
    assert not _is_summary_command("coffee 100")
    assert not _is_summary_command("lunch 250")
    assert not _is_summary_command("")
    assert not _is_summary_command(None)

def test_summary_routing_bypasses_rate_limits():
    """Test that summary commands bypass AI rate limits"""
    from utils.production_router import ProductionRouter
    
    router = ProductionRouter()
    
    # Test summary command - should work even if rate limited
    response, intent, category, amount = router.route_message("summary", "test_psid", "test_rid")
    
    assert intent == "summary"
    assert "No recent spending" in response or "BDT total" in response
    # Summary should never be rate limited
    assert "rate_limited" not in intent

if __name__ == "__main__":
    test_summary_detection_variants()
    test_summary_routing_bypasses_rate_limits()
    print("All tests passed!")