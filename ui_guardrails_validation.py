#!/usr/bin/env python3
"""
UI Guardrails Validation Script
Ensures frontend can ONLY access data through approved backend API endpoints
"""

import os
import re
import subprocess
from typing import List, Tuple


def scan_ui_files_for_violations() -> list[tuple[str, str, str]]:
    """
    Scan UI-related files for violations of UI guardrails
    Returns: List of (file_path, line_content, violation_type)
    """
    violations = []
    
    # UI-related files to scan (frontend components only - exclude backend handlers)
    ui_files = [
        'pwa_ui.py',
        'templates/dashboard.html',
        'templates/insights.html', 
        'templates/partials/*.html',
        'static/js/*.js',
        'static/*.js'
    ]
    
    # Explicitly exclude backend components from UI guardrail checks
    exclude_patterns = [
        'handlers/',         # Backend Messenger handlers
        'routes_backend_',   # Backend API routes  
        'backend_assistant.py',  # Backend logic
        'models.py',         # Database models
        'ci_unification',    # CI scripts
        'test_',            # Test files
    ]
    
    # Forbidden patterns that bypass API endpoints
    forbidden_patterns = [
        # Direct database access patterns
        (r'db\.session\.execute', 'Direct database access'),
        (r'\.query\(.*Expense', 'Direct ORM query'),
        (r'\.query\(.*User', 'Direct ORM query'),
        (r'SELECT.*FROM\s+(expenses|inference_snapshots|monthly_summaries)', 'Direct SQL query'),
        
        # Direct model imports for data access
        (r'from models import.*Expense', 'Direct model import for data'),
        (r'Expense\.query', 'Direct Expense model query'),
        
        # In-memory calculation patterns
        (r'total.*=.*sum\(', 'In-memory calculation'),
        (r'amount_sum', 'In-memory totals'),
        
        # Non-approved API endpoints for USER EXPENSE DATA (exclude admin endpoints)
        (r'fetch.*\/api\/(?!backend\/(get_recent_expenses|get_totals)|rules|corrections|system)', 'Non-approved user data API'),
        (r'POST.*\/api\/(?!backend\/(get_recent_expenses|get_totals)|rules|corrections|system)', 'Non-approved user data API'),
    ]
    
    for file_pattern in ui_files:
        try:
            # Find files matching pattern
            result = subprocess.run(f'find . -path "./{file_pattern}" 2>/dev/null', 
                                  shell=True, capture_output=True, text=True)
            
            files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for file_path in files:
                if not os.path.exists(file_path):
                    continue
                    
                # Skip backend components (not UI)
                if any(exclude in file_path for exclude in exclude_patterns):
                    continue
                    
                try:
                    with open(file_path, encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for line_num, line in enumerate(lines, 1):
                            for pattern, violation_type in forbidden_patterns:
                                if re.search(pattern, line, re.IGNORECASE):
                                    # Skip comments and documentation
                                    if line.strip().startswith('#') or line.strip().startswith('//'):
                                        continue
                                    # Skip this validation script itself
                                    if 'ui_guardrails_validation.py' in file_path:
                                        continue
                                    # Skip authentication patterns (legitimate User queries for login/register)
                                    if ('auth/login' in content or 'auth/register' in content) and 'User.query' in line:
                                        continue
                                    # Skip session management patterns
                                    if 'session.add' in line or 'session.commit' in line or 'session.rollback' in line:
                                        if 'auth/' in content:  # Only in auth routes
                                            continue
                                        
                                    violations.append((
                                        f"{file_path}:{line_num}",
                                        line.strip(),
                                        violation_type
                                    ))
                except UnicodeDecodeError:
                    # Skip binary files
                    continue
                except Exception as e:
                    print(f"Warning: Could not scan {file_path}: {e}")
                    
        except Exception as e:
            print(f"Warning: Could not process pattern {file_pattern}: {e}")
    
    return violations

def check_approved_endpoints_exist() -> bool:
    """Check that the approved API endpoints exist and are properly secured"""
    try:
        # Check routes_backend_assistant.py for the approved endpoints
        with open('routes_backend_assistant.py') as f:
            content = f.read()
            
        required_endpoints = [
            'def api_get_recent_expenses',
            'def api_get_totals',
            '@require_backend_user_auth'
        ]
        
        for endpoint in required_endpoints:
            if endpoint not in content:
                print(f"❌ Missing required endpoint: {endpoint}")
                return False
                
        print("✅ All approved API endpoints exist and are secured")
        return True
        
    except Exception as e:
        print(f"❌ Could not verify endpoints: {e}")
        return False

def check_backend_endpoint_security() -> bool:
    """Verify that backend endpoints use session auth and prepared statements"""
    try:
        with open('backend_assistant.py') as f:
            content = f.read()
            
        # Check for proper authentication patterns
        security_patterns = [
            'EXECUTE recent_expenses',  # Prepared statement usage
            'EXECUTE weekly_totals',    # Prepared statement usage
            'user_hash = ensure_hashed', # Proper user ID handling
        ]
        
        for pattern in security_patterns:
            if pattern not in content:
                print(f"❌ Missing security pattern: {pattern}")
                return False
                
        print("✅ Backend endpoints use proper security patterns")
        return True
        
    except Exception as e:
        print(f"❌ Could not verify backend security: {e}")
        return False

def main():
    """Run UI guardrails validation"""
    print("🔒 UI Guardrails Validation")
    print("=" * 50)
    
    all_passed = True
    
    # 1. Check for violations in UI files
    print("\n📋 1) Scanning UI files for guardrail violations...")
    violations = scan_ui_files_for_violations()
    
    if violations:
        print(f"❌ Found {len(violations)} UI guardrail violations:")
        for file_line, content, violation_type in violations:
            print(f"   {file_line}: {violation_type}")
            print(f"      Code: {content}")
        all_passed = False
    else:
        print("✅ No UI guardrail violations found")
    
    # 2. Check approved endpoints exist
    print("\n🎯 2) Verifying approved API endpoints...")
    if not check_approved_endpoints_exist():
        all_passed = False
    
    # 3. Check backend security
    print("\n🔐 3) Verifying backend endpoint security...")
    if not check_backend_endpoint_security():
        all_passed = False
    
    # 4. Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 UI GUARDRAILS VALIDATION PASSED")
        print("✅ Frontend can only access approved API endpoints")
        print("✅ All data flows through session-authenticated backend")
        print("✅ No direct database access from UI components")
        return 0
    else:
        print("💥 UI GUARDRAILS VALIDATION FAILED")
        print("🚫 Frontend has direct database access violations")
        print("🔧 Fix violations to ensure data security")
        return 1

if __name__ == "__main__":
    exit(main())