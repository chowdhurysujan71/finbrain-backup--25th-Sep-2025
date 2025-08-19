import logging
from flask import Flask
from utils.production_router import webhook_bp

def test_modes_are_logged(caplog):
    caplog.set_level(logging.INFO, logger="finbrain.router")
    app = Flask(__name__)
    app.register_blueprint(webhook_bp)
    c = app.test_client()

    def post(text):
        payload = {
            "object":"page",
            "entry":[{"messaging":[{"sender":{"id":"T"},
                                     "message":{"text":text,"mid":"m"},
                                     "timestamp":1734567890000}]}]
        }
        return c.post("/webhook/messenger", json=payload)

    post("coffee 100")
    post("summary")

    lines = [r.getMessage() for r in caplog.records if r.name=="finbrain.router"]
    assert any("ai_path_exit" in s for s in lines)
    assert any("mode" in s and "LOG" in s for s in lines)
    assert any("mode" in s and "AI" in s for s in lines)