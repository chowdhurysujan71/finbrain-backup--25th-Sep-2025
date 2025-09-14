#!/usr/bin/env python3
import os, sys
import requests
from datetime import datetime, timedelta

# ----------------------------
# CONFIG (override via ENV)
# ----------------------------
BASE = os.getenv("BASE_URL", "http://localhost:5000/api/backend")
SESSION_COOKIE = os.getenv("SESSION_COOKIE", "session=PASTE_COOKIE")
CANARY_PREFIX = os.getenv("CANARY_PREFIX", "uat canary")
AGE_HOURS = int(os.getenv("AGE_HOURS", "24"))

HDRS_AUTH = {"Content-Type": "application/json", "Cookie": SESSION_COOKIE}

def fail(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)

def cleanup_canaries():
    cutoff = datetime.utcnow() - timedelta(hours=AGE_HOURS)
    print(f"🧹 Cleaning canary expenses (prefix='{CANARY_PREFIX}', since {cutoff.isoformat()} UTC)…")

    # 1) Get recent expenses (broad pull)
    r = requests.post(f"{BASE}/get_recent_expenses",
                      json={"limit": 1000},
                      headers=HDRS_AUTH,
                      timeout=30)
    if r.status_code != 200:
        fail(f"Failed to fetch recent expenses: {r.status_code} {r.text}")
    
    response_data = r.json()
    expenses = response_data.get("data", response_data) if isinstance(response_data, dict) else response_data
    if not isinstance(expenses, list):
        expenses = []

    # 2) Filter canaries
    to_delete = []
    for e in expenses:
        desc = e.get("description", "")
        created_at = e.get("created_at")
        if CANARY_PREFIX in desc:
            if not created_at or created_at >= cutoff.isoformat():
                to_delete.append(e)

    if not to_delete:
        print("✅ No canary expenses found to delete.")
        return

    print(f"Found {len(to_delete)} canary expenses to delete:")
    for e in to_delete[:5]:
        print(f" - {e.get('id')} | {e.get('description')} | {e.get('created_at')}")
    if len(to_delete) > 5:
        print(f"   … and {len(to_delete)-5} more")

    # 3) Call delete endpoint if exists, else warn
    for e in to_delete:
        expense_id = e.get("id")
        if not expense_id:
            continue
        # Assumes you have /api/backend/delete_expense
        del_url = f"{BASE}/delete_expense"
        r = requests.post(del_url, json={"expense_id": expense_id}, headers=HDRS_AUTH, timeout=30)
        if r.status_code == 200:
            print(f"   ✅ Deleted expense {expense_id}")
        else:
            print(f"   ⚠️ Could not delete {expense_id} (HTTP {r.status_code}) — maybe no delete endpoint implemented.")

    print("🧹 Cleanup finished.")

if __name__ == "__main__":
    try:
        cleanup_canaries()
    except requests.exceptions.RequestException as e:
        fail(f"Network error: {e}")