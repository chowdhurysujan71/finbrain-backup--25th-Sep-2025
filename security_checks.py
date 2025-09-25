#!/usr/bin/env python3
"""
🔒 Security Checks for CI/CD Pipeline
Prevents security vulnerabilities from being committed
"""

import re
import subprocess
import sys
from pathlib import Path


def check_environment_files():
    """Check for committed environment files"""
    violations = []
    
    # Find all .env files
    result = subprocess.run(
        ['find', '.', '-name', '.env*', '-type', 'f'],
        capture_output=True, text=True
    )
    
    env_files = [f.strip() for f in result.stdout.split('\n') if f.strip()]
    
    for env_file in env_files:
        # Allow .env.example
        if env_file.endswith('.env.example'):
            continue
            
        violations.append({
            'type': 'environment_file',
            'file': env_file,
            'severity': 'CRITICAL',
            'message': 'Environment files must not be committed to repository'
        })
    
    return violations

def check_hardcoded_secrets():
    """Check for hardcoded secrets in code"""
    violations = []
    
    # Secret patterns to detect
    patterns = [
        (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API Key'),
        (r'["\'][A-Za-z0-9]{32,}["\']', 'Potential Secret Token'),
        (r'password\s*=\s*["\'][^"\']{8,}["\']', 'Hardcoded Password'),
        (r'secret\s*=\s*["\'][^"\']{10,}["\']', 'Hardcoded Secret'),
    ]
    
    # Scan Python files
    py_files = list(Path('.').glob('**/*.py'))
    
    for py_file in py_files:
        # Skip certain directories
        if any(skip in str(py_file) for skip in ['.cache', '__pycache__', '.git', 'node_modules']):
            continue
            
        try:
            with open(py_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            for pattern, secret_type in patterns:
                for line_num, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        # Skip safe patterns
                        if any(safe in line.lower() for safe in ['example', 'test', 'placeholder', 'your_key_here']):
                            continue
                        
                        violations.append({
                            'type': 'hardcoded_secret',
                            'file': str(py_file),
                            'line': line_num,
                            'secret_type': secret_type,
                            'severity': 'HIGH',
                            'message': f'Potential hardcoded {secret_type} detected'
                        })
                        
        except Exception as e:
            print(f"Warning: Could not scan {py_file}: {e}")
    
    return violations

def check_database_credentials():
    """Check for hardcoded database credentials"""
    violations = []
    
    # Database URL patterns
    db_patterns = [
        r'postgres://[^:]+:[^@]+@[^/]+',
        r'mysql://[^:]+:[^@]+@[^/]+',
        r'mongodb://[^:]+:[^@]+@[^/]+',
    ]
    
    py_files = list(Path('.').glob('**/*.py'))
    
    for py_file in py_files:
        if any(skip in str(py_file) for skip in ['.cache', '__pycache__', '.git']):
            continue
            
        try:
            with open(py_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            for pattern in db_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Skip example URLs
                    if any(safe in match.group(0).lower() for safe in ['localhost', 'example', 'test']):
                        continue
                        
                    violations.append({
                        'type': 'database_credential',
                        'file': str(py_file),
                        'severity': 'CRITICAL',
                        'message': 'Hardcoded database credentials detected'
                    })
                    
        except Exception as e:
            print(f"Warning: Could not scan {py_file}: {e}")
    
    return violations

def main():
    """Run all security checks"""
    print("🔒 SECURITY CHECKS - Scanning for vulnerabilities...")
    print("=" * 60)
    
    all_violations = []
    
    # 1. Check environment files
    print("📁 Checking for committed environment files...")
    env_violations = check_environment_files()
    all_violations.extend(env_violations)
    
    if env_violations:
        print(f"❌ Found {len(env_violations)} environment file violations")
    else:
        print("✅ No environment files found")
    
    # 2. Check hardcoded secrets
    print("\n🔑 Checking for hardcoded secrets...")
    secret_violations = check_hardcoded_secrets()
    all_violations.extend(secret_violations)
    
    if secret_violations:
        print(f"❌ Found {len(secret_violations)} potential hardcoded secrets")
    else:
        print("✅ No hardcoded secrets detected")
    
    # 3. Check database credentials
    print("\n🗃️ Checking for hardcoded database credentials...")
    db_violations = check_database_credentials()
    all_violations.extend(db_violations)
    
    if db_violations:
        print(f"❌ Found {len(db_violations)} database credential violations")
    else:
        print("✅ No hardcoded database credentials found")
    
    # Summary
    print("\n🎯 SECURITY SCAN RESULTS:")
    print(f"Total violations: {len(all_violations)}")
    
    if all_violations:
        print("\n🚨 VIOLATIONS FOUND:")
        
        critical_violations = [v for v in all_violations if v['severity'] == 'CRITICAL']
        high_violations = [v for v in all_violations if v['severity'] == 'HIGH']
        
        if critical_violations:
            print(f"\n💀 CRITICAL ({len(critical_violations)}):")
            for violation in critical_violations[:5]:  # Show first 5
                print(f"  {violation['message']}")
                print(f"    File: {violation['file']}")
        
        if high_violations:
            print(f"\n⚠️  HIGH ({len(high_violations)}):")
            for violation in high_violations[:5]:  # Show first 5
                print(f"  {violation['message']}")
                print(f"    File: {violation['file']}")
        
        # Return error code for CI
        if critical_violations:
            print("\n❌ CRITICAL VIOLATIONS FOUND - BUILD SHOULD FAIL")
            return 1
        elif high_violations:
            print("\n⚠️ HIGH SEVERITY VIOLATIONS - REVIEW REQUIRED")
            return 0  # Don't fail CI for high severity
    else:
        print("✅ NO SECURITY VIOLATIONS FOUND!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())