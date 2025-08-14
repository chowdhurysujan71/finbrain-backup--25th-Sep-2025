# finbrain_diagnose.py
import os, time, json, requests

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
PSID = os.environ.get("PSID", "TEST_PSID")

def get(path):
    try:
        r = requests.get(BASE + path, timeout=5)
        return r.status_code, r.headers, r.json() if r.headers.get("content-type","").startswith("application/json") else r.text
    except Exception as e:
        return 0, {}, str(e)

def post(path, payload):
    try:
        r = requests.post(BASE + path, json=payload, timeout=12)
        body = r.json() if r.headers.get("content-type","").startswith("application/json") else r.text
        return r.status_code, r.headers, body
    except Exception as e:
        return 0, {}, str(e)

def fb_payload(text):
    return {
        "object": "page",
        "entry": [{
            "id": "PAGE_ID",
            "time": int(time.time()*1000),
            "messaging": [{
                "sender": {"id": PSID},
                "recipient": {"id": "PAGE_ID"},
                "timestamp": int(time.time()*1000),
                "message": {"mid": f"m_{int(time.time()*1000)}", "text": text}
            }]
        }]
    }

def clip(x, n=160):
    s = x if isinstance(x, str) else json.dumps(x)
    return (s[:n] + "…") if len(s) > n else s

print("== FinBrain E2E Diagnosis ==")
print("Base:", BASE, "| PSID:", PSID)

# 1) Health + Telemetry
print("\n[1] Health/Telemetry")
code,h,body = get("/health")
print("GET /health ->", code, "|", clip(body))
code2,h2,body2 = get("/ops/telemetry")
ai_flag = None
try:
    ai_flag = (body2 or {}).get("ai_status") or (body2 or {}).get("AI_ENABLED")
except Exception: pass
print("GET /ops/telemetry ->", code2, "| AI:", ai_flag, "| Extra:", clip(body2))

# 2) Direct AI sanity (optional endpoint)
print("\n[2] Direct AI Adapter Test (POST /ai/insight)")
code,h,body = post("/ai/insight", {"ask":"Where can I save money this week?","window":"7d"})
if code == 404 or code == 0:
    print("Direct AI endpoint unavailable -> N/A (this is OK if you only expose AI via router)")
else:
    print("Status:", code, "| Excerpt:", clip(body, 200))

# 3) Router/intent tests
def routed_test(text):
    code,h,body = post("/webhook/messenger", fb_payload(text))
    handler = h.get("X-Handler") or h.get("x-handler") or ("AI" if "advice" in str(body).lower() else "Unknown")
    rl = h.get("X-Rate-Limited") or h.get("x-rate-limited")
    return {"text":text, "status":code, "handler":handler, "rate_limited":rl, "excerpt":clip(body)}

print("\n[3] Router/Intent Tests")
tests = [
    "recommend where to save money",
    "how can I cut costs this week?",
    "give me ideas to reduce food and ride spend",
    "summary"
]
results = [routed_test(t) for t in tests]
for r in results:
    print(f"- '{r['text']}' -> {r['status']} | handler={r['handler']} | RL={r['rate_limited']} | {r['excerpt']}")

# 4) Deterministic fallback check (logger)
print("\n[4] Deterministic Logger Check")
log_res = routed_test("log 20 on snacks")
print(f"- 'log 20 on snacks' -> {log_res['status']} | handler={log_res['handler']} | {log_res['excerpt']}")

# 5) Rate-limit burst (send 6 AI-like asks)
print("\n[5] Rate Limit Burst (6 asks in <60s)")
burst_prompts = [f"quick tip #{i}: where to save money?" for i in range(1,7)]
burst = [routed_test(p) for p in burst_prompts]
ai_count = sum(1 for b in burst if (b["handler"] or "").lower().startswith("ai"))
fb_count = len(burst) - ai_count
print("AI responses:", ai_count, "| Fallbacks:", fb_count)
for b in burst:
    print(f"  • {b['handler'] or 'Unknown'} | RL={b['rate_limited']} | {clip(b['excerpt'],120)}")
    
# 6) PASS/FAIL + Root Cause hint
print("\n[6] Summary")
ai_ok = any((r["handler"] or "").lower().startswith("ai") for r in results)
summary_ok = any("Last 7 days" in r["excerpt"] or "summary" in r["excerpt"].lower() for r in results)
fallback_ok = "log" in log_res["text"] and not (log_res["handler"] or "").lower().startswith("ai")

print("PASS health:", (code==200))
print("PASS router→AI:", ai_ok)
print("PASS summary:", summary_ok)
print("PASS logger deterministic:", fallback_ok)
print("PASS rate-limit sane:", ai_count>=1 and fb_count>=1)

hint = "If router→AI is FAIL but direct AI is OK → intent mapping or AI flag."
if ai_ok and fb_count>0 and not os.environ.get("IGNORE_RATE_LIMITS"):
    hint = "Rate limiter working; tune thresholds if too aggressive."
if not fallback_ok:
    hint = "Logger route misclassified—adjust intent patterns."
print("Root Cause Hint:", hint)