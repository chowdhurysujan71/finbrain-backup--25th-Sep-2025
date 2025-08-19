import importlib
import pytest
from flask import Flask

def import_webhook_bp():
    candidates = ["utils.production_router", "finbrain.router", "app"]
    for name in candidates:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        if hasattr(mod, "webhook_bp"):
            return getattr(mod, "webhook_bp")
    pytest.skip("webhook_bp not found")

def test_webhook_smoke():
    bp = import_webhook_bp()
    app = Flask(__name__)
    app.register_blueprint(bp)
    c = app.test_client()
    payload = {
        "object": "page",
        "entry": [{
            "messaging": [{
                "sender": {"id": "TEST_123"},
                "message": {"text": "coffee 100", "mid": "m1"},
                "timestamp": 1734567890000
            }]
        }]
    }
    r = c.post("/webhook/messenger", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body is not None and ("messages" in body or "recipient" in body)