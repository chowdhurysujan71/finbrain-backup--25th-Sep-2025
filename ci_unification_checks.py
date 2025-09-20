#!/usr/bin/env python3
"""
CI: Automated Database Unification Regression Checks
Blocks any build that violates the unified single-path architecture
"""

import os
import sys
import subprocess
import psycopg2
import re
import glob
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
        fetch_result = cur.fetchone()
        result = fetch_result[0] if fetch_result else 0
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

def run_security_checks():
    """Run security vulnerability checks"""
    print("\n🔒 SECURITY CHECKS")
    print("=" * 60)
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, 'security_checks.py'
        ], capture_output=True, text=True, cwd='.')
        
        print(result.stdout)
        if result.stderr:
            print("Security check warnings:", result.stderr)
        
        if result.returncode != 0:
            print("❌ FAIL: Security violations detected")
            return False
        else:
            print("✅ PASS: No security violations found")
            return True
    except Exception as e:
        print(f"❌ Security checks failed to run: {e}")
        return False

def check_hardcoded_sources():
    """Check for hardcoded deprecated source values"""
    print("\n🎯 F) Source Validation - No hardcoded deprecated sources")
    
    violations = []
    
    # Find Python files
    py_files = [f for f in glob.glob('**/*.py', recursive=True) if not f.startswith('.')]
    
    forbidden_patterns = [
        r"source.*in.*{.*['\"]form['\"]",      # {'form'} or similar
        r"source.*in.*{.*['\"]messenger['\"]", # {'messenger'} or similar  
        r"['\"]form['\"].*,.*['\"]chat['\"]",  # hardcoded lists with deprecated sources
        r"['\"]messenger['\"].*,.*['\"]chat['\"]"
    ]
    
    for file_path in py_files:
        # Skip generated files and archives
        if any(skip in file_path for skip in ['_quarantine', '_attic', '__pycache__', 'alembic/versions']):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            for pattern in forbidden_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(f"Hardcoded deprecated source in {file_path}")
                    
        except Exception as e:
            print(f"Warning: Could not scan {file_path}: {e}")
    
    if violations:
        print("❌ FAIL: Hardcoded deprecated sources found")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ PASS: No hardcoded deprecated sources")
        return True

def main():
    """Run all unification regression checks"""
    print("🚀 Starting Database Unification CI Checks")
    print("=" * 60)
    
    all_passed = True
    
    # Run security checks first
    security_passed = run_security_checks()
    if not security_passed:
        all_passed = False
    
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
    
    # GHOST CODE PROTECTION: Check for deprecated expense writers
    print("\n👻 GHOST CODE PROTECTION: Single Writer Principle Enforcement")
    
    # Check for forbidden deprecated function imports
    forbidden_imports = [
        'save_expense',
        'create_expense', 
        'upsert_expense_idempotent',
        'save_expense_idempotent'
    ]
    
    for func_name in forbidden_imports:
        code, stdout, stderr = run_command(
            f"grep -r 'from utils\.db import.*{func_name}\|import.*{func_name}' --include='*.py' --exclude-dir='_attic' --exclude-dir='_quarantine' --exclude-dir='artifacts' --exclude-dir='results' --exclude-dir='tests' app/ routes/ handlers/ utils/ services/ ai/ parsers/ finbrain/ || true",
            f"Scanning for forbidden import: {func_name}"
        )
        
        if stdout.strip():
            print(f"❌ FAIL: Found forbidden import of {func_name}:")
            print(stdout)
            all_passed = False
        else:
            print(f"✅ PASS: No forbidden {func_name} imports")
    
    # Check for direct expense table inserts (bypass canonical writer)
    code, stdout, stderr = run_command(
        "grep -ri '\\binsert\\s\\+into\\s\\+expenses\\b' --include='*.py' --exclude-dir='_attic' --exclude-dir='_quarantine' --exclude-dir='artifacts' --exclude-dir='alembic' app/ routes/ handlers/ utils/ services/ ai/ parsers/ finbrain/ || true",
        "Scanning for direct expense table inserts (must use backend_assistant.add_expense)"
    )
    
    if stdout.strip():
        print(f"❌ FAIL: Found direct expense table inserts (violates single writer principle):")
        print(stdout)
        all_passed = False
    else:
        print(f"✅ PASS: No direct expense table inserts detected")
    
    # Check for non-canonical expense writers
    code, stdout, stderr = run_command(
        "grep -r 'add_expense\\s*(' --include='*.py' --exclude-dir='_attic' --exclude-dir='_quarantine' --exclude-dir='artifacts' --exclude-dir='tests' app/ routes/ handlers/ utils/ services/ ai/ parsers/ finbrain/ | grep -v 'backend_assistant\\|import backend_assistant\\|from backend_assistant' || true",
        "Scanning for non-canonical expense writers (must import from backend_assistant)"
    )
    
    if stdout.strip():
        print(f"❌ FAIL: Found add_expense calls not imported from backend_assistant:")
        print(stdout)
        all_passed = False
    else:
        print(f"✅ PASS: All add_expense calls use canonical backend_assistant import")
    
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
    
    # F) Source Validation Check
    source_passed = check_hardcoded_sources()
    if not source_passed:
        all_passed = False
    
    # G) Verify unified read path is active
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM expenses")
        fetch_result = cur.fetchone()
        expense_count = fetch_result[0] if fetch_result else 0
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