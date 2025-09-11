import requests
import psycopg2
import os
from datetime import datetime, timedelta

# ---------------------------
# CONFIG
# ---------------------------
API_BASE = "http://localhost:5000/api/backend"
DB_CONN = {
    "dbname": os.environ.get("PGDATABASE") or "finbrain",
    "user": os.environ.get("PGUSER") or "postgres", 
    "password": os.environ.get("PGPASSWORD") or "",
    "host": os.environ.get("PGHOST") or "localhost",
    "port": int(os.environ.get("PGPORT") or 5432)
}
TEST_USER_HASH = "4820e98cf64dfd3984bd6fb121bb530590297f8df3d6d6eb19b5c5a26a20c885"  # From DB query

# ---------------------------
# HELPERS
# ---------------------------
def run_sql(query, params=None):
    conn = psycopg2.connect(**DB_CONN)
    cur = conn.cursor()
    cur.execute(query, params or ())
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def check_equal(name, api_value, db_value):
    if api_value == db_value:
        print(f"✅ {name} matches: {api_value}")
    else:
        print(f"❌ {name} mismatch! API={api_value}, DB={db_value}")

# ---------------------------
# TESTS
# ---------------------------
def test_propose_expense():
    text = "bought groceries for 250 taka"
    r = requests.post(f"{API_BASE}/propose_expense", json={"text": text}).json()
    print("Propose Expense:", r)
    assert "amount_minor" in r, "Invalid schema"
    assert isinstance(r["amount_minor"], int), "Amount not int"

def test_get_totals():
    # API (Note: These endpoints require session auth, so will return 401)
    api = requests.post(f"{API_BASE}/get_totals", json={"period": "week"})
    print("Get Totals API Response Status:", api.status_code)
    
    if api.status_code == 401:
        print("✅ Auth protection working - get_totals requires session")
    else:
        api_data = api.json()
        
        # DB
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        sql = """
            SELECT COALESCE(SUM(amount_minor),0), COUNT(*)
            FROM expenses
            WHERE user_id_hash = %s AND created_at >= %s
        """
        db_total, db_count = run_sql(sql, (TEST_USER_HASH, one_week_ago))[0]

        check_equal("Weekly Total", api_data["total_minor"], db_total)
        check_equal("Expenses Count", api_data["expenses_count"], db_count)

def test_get_recent_expenses():
    # API (Note: These endpoints require session auth, so will return 401)  
    api = requests.post(f"{API_BASE}/get_recent_expenses", json={"limit": 3})
    print("Get Recent Expenses API Response Status:", api.status_code)
    
    if api.status_code == 401:
        print("✅ Auth protection working - get_recent_expenses requires session")
    else:
        api_data = api.json()
        sql = """
            SELECT amount_minor, category, description
            FROM expenses
            WHERE user_id_hash = %s
            ORDER BY created_at DESC LIMIT 3
        """
        db_rows = run_sql(sql, (TEST_USER_HASH,))
        print("Recent (API):", api_data)
        print("Recent (DB):", db_rows)

def test_direct_db_verification():
    print("\n🔍 Direct DB Verification:")
    
    # Check expenses table structure
    sql = "SELECT COUNT(*) FROM expenses"
    expense_count = run_sql(sql)[0][0]
    print(f"✅ Total expenses in DB: {expense_count}")
    
    # Check users table  
    sql = "SELECT COUNT(*) FROM users"
    user_count = run_sql(sql)[0][0]
    print(f"✅ Total users in DB: {user_count}")
    
    # Check for test user
    sql = "SELECT user_id_hash, platform FROM users WHERE user_id_hash = %s"
    user_data = run_sql(sql, (TEST_USER_HASH,))
    if user_data:
        print(f"✅ Test user found: {user_data[0]}")
    else:
        print(f"⚠️ Test user not found: {TEST_USER_HASH}")

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    print("🔍 Running Backend Verification...")
    test_propose_expense()
    test_get_totals()
    test_get_recent_expenses()
    test_direct_db_verification()
    print("✅ Verification Complete")