#!/usr/bin/env python3
"""
Validates that AI/brain outputs (amount/category) are actually persisted for the same user,
and that users are isolated in storage. Exits nonzero on mismatch.
"""
import os, sys, json, time, hashlib
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
import psycopg2, psycopg2.extras

APP = os.environ.get("APP_ORIGIN","http://localhost:5000")
DB  = os.environ["DATABASE_URL"]
OUTBASE = f"results/{datetime.utcnow().isoformat()}Z"
COMMIT  = os.popen("git rev-parse --short HEAD 2>/dev/null").read().strip() or "no-git"
OUTDIR  = f"{OUTBASE}/{COMMIT}"
os.makedirs(OUTDIR, exist_ok=True)

def post(uid, msg):
    req = Request(APP+"/ai-chat", data=json.dumps({"message":msg}).encode(),
                  headers={"Content-Type":"application/json","X-User-ID":uid})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def psid_hash(uid):
    return hashlib.sha256(uid.encode()).hexdigest()

def die(msg, path=None):
    print(f"FAIL: {msg}")
    if path: print(f"See: {path}")
    sys.exit(2)

cx = psycopg2.connect(DB)
cx.autocommit = True
cur = cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# 1) Log an expense via chat
uid = "db-truth-uid"
resp = post(uid, "Groceries 1450 at Shwapno")
open(f"{OUTDIR}/dbtruth_chat_resp.json","w").write(json.dumps(resp, indent=2))

amount = (resp.get("data") or {}).get("amount")
category = (resp.get("data") or {}).get("category")
if not amount or not category:
    die("Chat did not return structured amount/category", f"{OUTDIR}/dbtruth_chat_resp.json")

# 2) Query DB for most recent row for this user
uid_hash = psid_hash(uid)
cur.execute("""
    SELECT id, user_id_hash, amount, category, created_at
    FROM expenses
    WHERE user_id_hash=%s
    ORDER BY created_at DESC
    LIMIT 1
""", (uid_hash,))
row = cur.fetchone()
open(f"{OUTDIR}/dbtruth_db_row.json","w").write(json.dumps({k:str(v) for k,v in (row or {}).items()}, indent=2))

if not row: die("No expense row found for user after chat insert")

# 3) Compare values
if float(row["amount"]) != float(amount):
    die(f"Amount mismatch: DB {row['amount']} vs Chat {amount}", f"{OUTDIR}/dbtruth_db_row.json")
if str(row["category"]).lower() != str(category).lower():
    die(f"Category mismatch: DB {row['category']} vs Chat {category}", f"{OUTDIR}/dbtruth_db_row.json")

# 4) Isolation: ensure another user does not see this
other = "db-truth-other"
resp2 = post(other, "What did I just log?")
open(f"{OUTDIR}/dbtruth_other_resp.json","w").write(json.dumps(resp2, indent=2))
if "1450" in json.dumps(resp2).lower() or "groc" in json.dumps(resp2).lower():
    die("Cross-user leak: other user response appears to reference A's data", f"{OUTDIR}/dbtruth_other_resp.json")

print("DB truth checks passed. Artifacts in", OUTDIR)