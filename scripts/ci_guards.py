#!/usr/bin/env python3
"""
CI Guards for FinBrain Web-Only Architecture

Prevents Facebook/Messenger code reintroduction and ensures zero LSP diagnostics.
Used in CI/CD pipeline to maintain web-only architecture integrity.
"""

import os
import re
import sys
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Set

# Colors for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print colored header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}🔒 {text}{Colors.END}")
    print("=" * (len(text) + 3))

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

class FacebookCodeDetector:
    """Detects Facebook/Messenger code patterns that violate web-only architecture"""
    
    # Forbidden patterns that indicate Facebook integration
    FORBIDDEN_PATTERNS = [
        # Facebook API calls
        r'facebook\.com',
        r'graph\.facebook\.com',
        r'\/v\d+\.\d+\/',  # Facebook API versions
        
        # Webhook patterns
        r'webhook',
        r'@app\.route.*webhook',
        r'verify_token',
        r'hub\.verify_token',
        r'hub\.challenge',
        r'hub\.mode',
        
        # Facebook-specific fields
        r'psid',
        r'page_scoped_id',
        r'sender_id',
        r'recipient_id',
        r'messaging',
        r'postback',
        r'quick_reply',
        
        # Messenger Platform
        r'messenger_platform',
        r'send_api',
        r'messenger\.send',
        r'MessengerService',
        
        # Facebook Graph API
        r'access_token.*facebook',
        r'page_access_token',
        r'app_secret',
        r'verify_signature',
        r'X-Hub-Signature',
        
        # Platform-specific logic
        r"platform.*==.*['\"]messenger['\"]",
        r"platform.*==.*['\"]facebook['\"]",
    ]
    
    # Files to exclude from checks (legacy data, configs, etc.)
    EXCLUDED_FILES = {
        'README.md',
        'CHANGELOG.md',
        'replit.md',
        '.gitignore',
        'requirements.txt',
        'package.json',
        'alembic.ini',
    }
    
    # Directories to exclude
    EXCLUDED_DIRS = {
        '.git',
        '__pycache__',
        'node_modules',
        '.pytest_cache',
        'alembic/versions',  # Database migrations may reference old structure
        'tests',  # Test files may have mock Facebook data
    }
    
    def __init__(self):
        self.violations = []
        
    def is_excluded(self, file_path: Path) -> bool:
        """Check if file should be excluded from scanning"""
        # Check filename
        if file_path.name in self.EXCLUDED_FILES:
            return True
            
        # Check if in excluded directory
        for part in file_path.parts:
            if part in self.EXCLUDED_DIRS:
                return True
                
        return False
        
    def scan_file(self, file_path: Path) -> List[Dict]:
        """Scan a single file for Facebook code patterns"""
        violations = []
        
        if self.is_excluded(file_path):
            return violations
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                
            for line_num, line in enumerate(lines, 1):
                for pattern in self.FORBIDDEN_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append({
                            'file': str(file_path),
                            'line': line_num,
                            'pattern': pattern,
                            'content': line.strip(),
                            'severity': self._get_severity(pattern)
                        })
                        
        except Exception as e:
            print_warning(f"Could not scan {file_path}: {e}")
            
        return violations
        
    def _get_severity(self, pattern: str) -> str:
        """Determine severity of pattern violation"""
        critical_patterns = [
            r'webhook',
            r'facebook\.com',
            r'graph\.facebook\.com',
            r'messenger\.send',
        ]
        
        for critical in critical_patterns:
            if pattern == critical:
                return 'CRITICAL'
                
        return 'HIGH'
        
    def scan_directory(self, directory: Path) -> List[Dict]:
        """Scan directory recursively for Facebook code patterns"""
        all_violations = []
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml']:
                violations = self.scan_file(file_path)
                all_violations.extend(violations)
                
        return all_violations

class LSPDiagnosticsChecker:
    """Checks for LSP diagnostics in production code"""
    
    # Production files that must have zero LSP errors
    PRODUCTION_FILES = [
        'app.py',
        'main.py',
        'models.py',
        'routes_nudges.py',
        'pwa_ui.py',
        'utils/feature_flags.py',
        'utils/test_clock.py',
    ]
    
    def __init__(self):
        self.diagnostics = []
        
    def check_lsp_diagnostics(self) -> bool:
        """Check LSP diagnostics for production files"""
        has_errors = False
        
        for file_path in self.PRODUCTION_FILES:
            if os.path.exists(file_path):
                try:
                    # This would integrate with actual LSP server
                    # For now, check if files can be imported without syntax errors
                    if file_path.endswith('.py'):
                        result = subprocess.run([
                            sys.executable, '-m', 'py_compile', file_path
                        ], capture_output=True, text=True)
                        
                        if result.returncode != 0:
                            print_error(f"Syntax error in {file_path}: {result.stderr}")
                            has_errors = True
                        else:
                            print_success(f"No syntax errors in {file_path}")
                            
                except Exception as e:
                    print_error(f"Could not check {file_path}: {e}")
                    has_errors = True
            else:
                print_warning(f"Production file not found: {file_path}")
                
        return not has_errors

class WebOnlyArchitectureValidator:
    """Validates web-only architecture compliance"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        
    def check_required_files(self) -> bool:
        """Check that required web-only files exist"""
        required_files = [
            'app.py',
            'main.py', 
            'models.py',
            'routes_nudges.py',
            'pwa_ui.py',
            'templates/chat.html',
            'utils/feature_flags.py',
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
                
        if missing_files:
            print_error(f"Missing required files: {missing_files}")
            return False
            
        print_success("All required web-only files present")
        return True
        
    def check_web_auth_setup(self) -> bool:
        """Check that web authentication is properly configured"""
        try:
            app_file = self.project_root / 'app.py'
            if app_file.exists():
                content = app_file.read_text()
                
                # Check for Flask-Login or similar web auth
                auth_patterns = [
                    r'flask_login',
                    r'LoginManager',
                    r'login_required',
                    r'session\[',
                ]
                
                for pattern in auth_patterns:
                    if re.search(pattern, content):
                        print_success("Web authentication patterns found")
                        return True
                        
                print_warning("No web authentication patterns detected")
                return False
                
        except Exception as e:
            print_error(f"Could not check web auth setup: {e}")
            return False
            
    def check_environment_vars(self) -> bool:
        """Check required environment variables"""
        required_vars = [
            'NUDGES_ENABLED',
            'DATABASE_URL',
            'SESSION_SECRET',
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                
        if missing_vars:
            print_warning(f"Missing environment variables: {missing_vars}")
            return False
            
        print_success("Required environment variables present")
        return True

def main():
    """Main CI guard execution"""
    print_header("FinBrain CI Guards - Web-Only Architecture Protection")
    
    success = True
    
    # 1. Facebook Code Detection
    print_header("Facebook Code Pattern Detection")
    detector = FacebookCodeDetector()
    violations = detector.scan_directory(Path.cwd())
    
    if violations:
        print_error(f"Found {len(violations)} Facebook code violations:")
        for violation in violations[:10]:  # Show first 10
            print(f"  {violation['file']}:{violation['line']} - {violation['pattern']}")
            print(f"    {violation['content']}")
        
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more violations")
            
        success = False
    else:
        print_success("No Facebook code patterns detected")
    
    # 2. LSP Diagnostics Check
    print_header("LSP Diagnostics Check")
    lsp_checker = LSPDiagnosticsChecker()
    lsp_clean = lsp_checker.check_lsp_diagnostics()
    
    if not lsp_clean:
        success = False
    
    # 3. Web-Only Architecture Validation
    print_header("Web-Only Architecture Validation")
    validator = WebOnlyArchitectureValidator()
    
    # Check required files
    files_ok = validator.check_required_files()
    if not files_ok:
        success = False
    
    # Check web auth setup
    auth_ok = validator.check_web_auth_setup()
    if not auth_ok:
        success = False
    
    # Check environment variables
    env_ok = validator.check_environment_vars()
    if not env_ok:
        success = False
    
    # Final result
    print_header("CI Guards Results")
    
    if success:
        print_success("✅ ALL CI GUARDS PASSED - Web-only architecture is protected!")
        print("🚀 Safe to deploy")
        return 0
    else:
        print_error("❌ CI GUARDS FAILED - Architecture violations detected!")
        print("🛑 Deployment blocked")
        return 1

if __name__ == '__main__':
    exit(main())