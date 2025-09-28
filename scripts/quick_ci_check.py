#!/usr/bin/env python3
"""
Quick CI Check for FinBrain Web-Only Architecture
Fast validation to prevent Facebook code and ensure basic compliance.
"""

import os
import re
import sys
from pathlib import Path

def check_facebook_patterns():
    """Quick check for Facebook patterns in key files"""
    critical_files = [
        'app.py',
        'main.py', 
        'routes_nudges.py',
        'pwa_ui.py'
    ]
    
    facebook_patterns = [
        r'webhook',
        r'facebook\.com',
        r'messenger',
        r'psid',
        r'hub\.verify',
    ]
    
    violations = 0
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                for pattern in facebook_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        print(f"❌ Facebook pattern '{pattern}' found in {file_path}")
                        violations += 1
                        
            except Exception as e:
                print(f"⚠️  Could not check {file_path}: {e}")
    
    if violations == 0:
        print("✅ No Facebook patterns detected in critical files")
        
    return violations == 0

def check_syntax():
    """Check syntax of critical Python files"""
    critical_files = [
        'app.py',
        'main.py',
        'models.py',
        'routes_nudges.py',
        'pwa_ui.py'
    ]
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    compile(f.read(), file_path, 'exec')
                print(f"✅ {file_path} syntax OK")
            except SyntaxError as e:
                print(f"❌ Syntax error in {file_path}: {e}")
                return False
            except Exception as e:
                print(f"⚠️  Could not check {file_path}: {e}")
                
    return True

def check_required_features():
    """Check that required web-only features exist"""
    checks = [
        ('routes_nudges.py', 'Banner system routes'),
        ('utils/feature_flags.py', 'Feature flags'),
        ('utils/test_clock.py', 'Test clock'),
        ('templates/chat.html', 'Chat template'),
    ]
    
    all_present = True
    
    for file_path, description in checks:
        if os.path.exists(file_path):
            print(f"✅ {description} present")
        else:
            print(f"❌ {description} missing: {file_path}")
            all_present = False
            
    return all_present

def main():
    """Quick CI validation"""
    print("🔒 FinBrain Quick CI Check")
    print("=" * 30)
    
    # Run checks
    facebook_clean = check_facebook_patterns()
    syntax_clean = check_syntax()
    features_present = check_required_features()
    
    # Check environment
    nudges_enabled = os.getenv('NUDGES_ENABLED', 'false').lower() == 'true'
    if nudges_enabled:
        print("✅ NUDGES_ENABLED flag is set")
    else:
        print("⚠️  NUDGES_ENABLED flag not set")
    
    # Final result
    print("\n📊 Results:")
    success = facebook_clean and syntax_clean and features_present
    
    if success:
        print("✅ Quick CI check PASSED")
        return 0
    else:
        print("❌ Quick CI check FAILED")
        return 1

if __name__ == '__main__':
    exit(main())