import inspect
import importlib

def test_adapter_signature_is_stable():
    ga = importlib.import_module("finbrain.ai.gemini_adapter")
    GeminiAdapter = getattr(ga, "GeminiAdapter")
    sig = inspect.signature(GeminiAdapter.process)
    assert list(sig.parameters.keys()) == ["self", "message", "context"], sig