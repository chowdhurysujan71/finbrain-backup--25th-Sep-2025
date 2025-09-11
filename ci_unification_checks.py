#!/usr/bin/env python3
"""
CI: Automated Database Unification Regression Checks
Blocks any build that violates the unified single-path architecture
"""

import os
import sys
import subprocess
import psycopg2
from urllib.parse import urlparse

def run_command(cmd, description):
    """Run shell command and return output"""
    print(f"🔍 {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return 1, "", str(e)

def run_sql_check(query, description, max_allowed=0):
    """Run SQL query and check if result exceeds threshold"""
    print(f"🔍 {description}")
    
    try:
        # Parse DATABASE_URL
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return False
            
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        cur.execute(query)
        result = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print(f"   Result: {result} (max allowed: {max_allowed})")
        
        if result > max_allowed:
            print(f"❌ FAIL: {description} returned {result}, expected <= {max_allowed}")
            return False
        else:
            print(f"✅ PASS: {description}")
            return True
            
    except Exception as e:
        print(f"❌ SQL check failed: {e}")
        return False

def main():
    """Run all unification regression checks"""
    print("🚀 Starting Database Unification CI Checks")
    print("=" * 60)
    
    all_passed = True
    
    # A) Check for fragmented reads in codebase
    print("\n📁 A) Code Pattern Checks - No fragmented reads")
    
    # Check for inference_snapshots reads in UI-facing code (exclude backend handlers)
    code, stdout, stderr = run_command(
        "grep -r 'FROM inference_snapshots' --include='*.py' pwa_ui.py routes/pwa* templates/ static/ || true",
        "Scanning for inference_snapshots reads in UI-facing code"
    )
    
    if stdout.strip():
        print(f"❌ FAIL: Found forbidden inference_snapshots reads:")
        print(stdout)
        all_passed = False
    else:
        print("✅ PASS: No inference_snapshots reads in user-facing code")
    
    # Check for monthly_summaries reads in UI-facing code  
    code, stdout, stderr = run_command(
        "grep -r 'FROM monthly_summaries' --include='*.py' pwa_ui.py routes/pwa* templates/ static/ || true",
        "Scanning for monthly_summaries reads in UI-facing code"
    )
    
    if stdout.strip():
        print(f"❌ FAIL: Found forbidden monthly_summaries reads:")
        print(stdout)
        all_passed = False
    else:
        print("✅ PASS: No monthly_summaries reads in user-facing code")
    
    # C) UI Guardrail Checks - Frontend must only call backend APIs
    print("\n🛡️  C) UI Guardrail Checks - Frontend API enforcement")
    
    # Check for direct database access in UI components
    code, stdout, stderr = run_command(
        "grep -r 'db\\.session\\|execute.*text\\|\.fetchall\\|\.first()' --include='*.py' pwa_ui.py routes/pwa*.py || true",
        "Scanning for direct database access in UI components"
    )
    
    if stdout.strip():
        print(f"❌ FAIL: Found direct database access in UI components (must use API endpoints only):")
        print(stdout)
        all_passed = False
    else:
        print("✅ PASS: No direct database access in UI components")
    
    # Check for prepared statement calls outside backend
    code, stdout, stderr = run_command(
        "grep -r 'EXECUTE.*recent_expenses\\|EXECUTE.*weekly_totals' --include='*.py' --exclude='backend_assistant.py' --exclude='routes_backend_assistant.py' handlers/ routes/ pwa_ui.py || true",
        "Scanning for prepared statement calls outside backend layer"
    )
    
    if stdout.strip():
        print(f"❌ FAIL: Found prepared statement calls outside backend layer:")
        print(stdout)
        all_passed = False
    else:
        print("✅ PASS: Prepared statements only used in backend layer")
    
    # B) Check for orphan snapshots (adapted to actual schema)
    print("\n🗃️  B) Database State Checks")
    
    orphan_check = run_sql_check(
        """
        SELECT COUNT(*) FROM inference_snapshots s
        LEFT JOIN expenses e ON e.mid = s.cc_id
        WHERE e.id IS NULL AND s.intent = 'LOG_EXPENSE'
        """,
        "Checking for orphan LOG_EXPENSE snapshots",
        max_allowed=0
    )
    all_passed = all_passed and orphan_check
    
    # C) Check for duplicate idempotency keys
    duplicate_check = run_sql_check(
        """
        SELECT COUNT(*) FROM (
          SELECT idempotency_key FROM expenses GROUP BY 1 HAVING COUNT(*)>1
        ) d
        """,
        "Checking for duplicate idempotency keys",
        max_allowed=0
    )
    all_passed = all_passed and duplicate_check
    
    # D) Check for app write permissions on legacy tables (adapted to actual user)
    print("\n🔒 D) Permission Checks")
    
    permission_check = run_sql_check(
        """
        SELECT COUNT(*) FROM information_schema.role_table_grants
        WHERE grantee = 'neondb_owner' 
        AND table_name IN ('inference_snapshots', 'transactions_effective', 'messages', 'expense_edits', 'ai_request_audit', 'user_corrections')
        AND privilege_type IN ('INSERT','UPDATE','DELETE')
        """,
        "Checking for write permissions on legacy tables",
        max_allowed=0
    )
    all_passed = all_passed and permission_check
    
    # E) UI Guardrails Check
    print("\n🔒 E) UI Guardrails - Frontend can only use approved endpoints")
    
    ui_code, ui_stdout, ui_stderr = run_command(
        "python3 ui_guardrails_validation.py",
        "Running UI guardrails validation"
    )
    
    if ui_code != 0:
        print(f"❌ FAIL: UI guardrails validation failed")
        print(ui_stdout)
        all_passed = False
    else:
        print("✅ PASS: UI guardrails enforced")
    
    # F) Verify unified read path is active
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM expenses")
        expense_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print(f"🔍 Verifying expenses table is accessible (unified read path)")
        print(f"   Result: {expense_count} expenses found")
        
        if expense_count > 0:
            print("✅ PASS: Expenses table accessible with data")
        else:
            print("❌ FAIL: Expenses table returned 0 records - unified read path broken")
            all_passed = False
    except Exception as e:
        print(f"❌ FAIL: Could not access expenses table: {e}")
        all_passed = False
    
    # Final result
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED - Database unification intact")
        sys.exit(0)
    else:
        print("💥 CHECKS FAILED - Database unification regression detected")
        print("🚫 BUILD BLOCKED - Fix violations before deployment")
        sys.exit(1)

if __name__ == "__main__":
    main()