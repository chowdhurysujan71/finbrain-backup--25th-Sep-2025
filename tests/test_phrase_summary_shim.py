import importlib


def test_phrase_summary_exists_and_works():
    ga = importlib.import_module("finbrain.ai.gemini_adapter")
    contracts = importlib.import_module("finbrain.ai.contracts")
    GeminiAdapter = getattr(ga, "GeminiAdapter")
    InboundMessage = getattr(contracts, "InboundMessage")
    AIContext = getattr(contracts, "AIContext")

    adapter = GeminiAdapter()

    # Build minimal message and context using your existing types.
    # Handle both class and TypedDict cases.
    try:
        msg = InboundMessage(psid_hash="x"*64, text="summary", mid="m1", timestamp=0)
    except TypeError:
        msg = {"psid_hash": "x"*64, "text": "summary", "mid": "m1", "timestamp": 0}

    try:
        ctx = AIContext(user_id="x"*64, history=[], app_config={})
    except TypeError:
        ctx = {"user_id": "x"*64, "history": [], "app_config": {}}

    summary = {"total": 180, "currency": "BDT", "count": 2}
    assert hasattr(adapter, "phrase_summary"), "Adapter missing phrase_summary shim"
    res = adapter.phrase_summary(summary, msg, ctx)
    text = getattr(res, "reply_text", None) if hasattr(res, "reply_text") else res.get("reply_text")
    assert isinstance(text, str) and "180" in text