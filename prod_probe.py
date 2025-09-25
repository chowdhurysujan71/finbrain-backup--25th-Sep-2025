# prod_probe.py
import hashlib
import hmac
import json
import os
import time

import requests

PROD_URL        = os.environ.get("PROD_URL", "https://<your-deploy-domain>/webhook/messenger")
FB_APP_SECRET   = os.environ["FACEBOOK_APP_SECRET"]     # set in Replit Secrets
PSID            = os.environ.get("PSID", "TEST_PSID")
PAGE_ID         = os.environ.get("PAGE_ID", "PAGE_ID")

def fb_payload(text):
    now = int(time.time()*1000)
    return {
        "object":"page",
        "entry":[{"id":PAGE_ID,"time":now,"messaging":[
            {"sender":{"id":PSID},"recipient":{"id":PAGE_ID},"timestamp":now,
             "message":{"mid":f"m_{now}", "text":text}}
        ]}]
    }

def sign(body_bytes):
    mac = hmac.new(FB_APP_SECRET.encode(), msg=body_bytes, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()

def send(text):
    body = fb_payload(text)
    raw  = json.dumps(body, separators=(",",":")).encode()
    sig  = sign(raw)
    r = requests.post(PROD_URL, data=raw, headers={
        "Content-Type":"application/json",
        "X-Hub-Signature-256": sig
    }, timeout=12)
    ct = r.headers.get("content-type","")
    data = r.json() if ct.startswith("application/json") else r.text
    handler = r.headers.get("X-Handler") or "unknown"
    rl = r.headers.get("X-Rate-Limited")
    print(f"\n> {text}\n{r.status_code} | handler={handler} | RL={rl}\n{str(data)[:200]}")

tests = [
  "recommend where to save money",
  "how can I cut costs this week?",
  "give me ideas to reduce food and ride spend",
  "summary",
  "log 20 on snacks"
]

print("PROD URL:", PROD_URL)
for t in tests: send(t)