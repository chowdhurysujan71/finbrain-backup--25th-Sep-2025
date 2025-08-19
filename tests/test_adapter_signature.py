import importlib

def test_gemini_adapter_has_process_method():
    ga = importlib.import_module("finbrain.ai.gemini_adapter")
    contracts = importlib.import_module("finbrain.ai.contracts")
    GeminiAdapter = getattr(ga, "GeminiAdapter")
    InboundMessage = getattr(contracts, "InboundMessage")
    AIContext = getattr(contracts, "AIContext")

    adapter = GeminiAdapter()

    try:
        msg = InboundMessage(psid_hash="x"*64, text="test", mid="m1", timestamp=0)
    except TypeError:
        msg = {"psid_hash": "x"*64, "text": "test", "mid": "m1", "timestamp": 0}

    try:
        ctx = AIContext(user_id="x"*64, history=[], app_config={})
    except TypeError:
        ctx = {"user_id": "x"*64, "history": [], "app_config": {}}

    assert hasattr(adapter, "process"), "Adapter missing process method"
    result = adapter.process(msg, ctx)
    assert result is not None
    reply_text = getattr(result, "reply_text", None) if hasattr(result, "reply_text") else result.get("reply_text")
    assert isinstance(reply_text, str)