"""
🎯 CI INVARIANT ENFORCEMENT
Advanced static analysis and CI enforcement for unbreakable single writer invariants

This module provides CI-level enforcement that prevents architectural violations
from being introduced into the codebase.
"""

import re
import os
import sys
from typing import List, Dict, Tuple, Set
from pathlib import Path

class InvariantViolationDetector:
    """
    🔍 STATIC ANALYSIS FOR SINGLE WRITER VIOLATIONS
    Detects patterns that could bypass the single writer architecture
    """
    
    # Patterns that indicate potential bypasses
    BYPASS_PATTERNS = [
        # Direct database writes
        r'db\.session\.add\s*\(\s*Expense\s*\(',
        r'Expense\s*\(\s*.*\)\.save\s*\(',
        r'INSERT\s+INTO\s+expenses',
        r'expenses\.insert\s*\(',
        
        # Source validation bypasses
        r'source\s*=\s*["\'](?!chat)[^"\']+["\']',  # Any source other than 'chat'
        r'ALLOWED_SOURCES\s*=.*(?!.*\{[^}]*["\']chat["\'][^}]*\})',  # Modified ALLOWED_SOURCES
        
        # Hardcoded deprecated sources
        r'["\']messenger["\'].*source',
        r'["\']form["\'].*source',
        r'source.*["\']messenger["\']',
        r'source.*["\']form["\']',
        
        # Backend assistant bypasses
        r'def\s+(?:create|save|upsert|insert)_expense.*(?!.*add_expense)',
        r'expense\s*=\s*Expense\s*\([^)]*\)(?!\s*#.*canonical)',
        
        # Import bypasses
        r'from\s+models\s+import.*Expense(?!.*#.*read-only)',
        r'import.*sqlite3|import.*psycopg2(?!.*#.*monitoring)',
    ]
    
    # Files that are allowed to have bypass patterns (with justification)
    EXEMPT_FILES = {
        'models.py': 'Model definitions',
        'utils/unbreakable_invariants.py': 'Monitoring system',
        'backend_assistant.py': 'Canonical writer',
        'ci_invariant_enforcement.py': 'This file',
        'test_': 'Test files',
        'migration': 'Database migrations'
    }
    
    def __init__(self, project_root: str = '.'):
        self.project_root = Path(project_root)
        self.violations: List[Dict] = []
        
    def scan_codebase(self) -> List[Dict]:
        """
        🔍 COMPREHENSIVE CODEBASE SCAN
        Scans all Python files for single writer invariant violations
        """
        self.violations = []
        
        for file_path in self._get_python_files():
            if self._is_exempt_file(file_path):
                continue
                
            violations = self._scan_file(file_path)
            self.violations.extend(violations)
            
        return self.violations
    
    def _get_python_files(self) -> List[Path]:
        """Get all Python files in the project"""
        python_files = []
        for pattern in ['**/*.py']:
            python_files.extend(self.project_root.glob(pattern))
        return python_files
    
    def _is_exempt_file(self, file_path: Path) -> bool:
        """Check if file is exempt from invariant checks"""
        file_str = str(file_path)
        for exempt_pattern in self.EXEMPT_FILES.keys():
            if exempt_pattern in file_str:
                return True
        return False
    
    def _scan_file(self, file_path: Path) -> List[Dict]:
        """Scan a single file for violations"""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            for i, line in enumerate(lines, 1):
                for pattern in self.BYPASS_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append({
                            'file': str(file_path),
                            'line': i,
                            'pattern': pattern,
                            'content': line.strip(),
                            'severity': 'HIGH'
                        })
                        
        except Exception as e:
            violations.append({
                'file': str(file_path),
                'line': 0,
                'pattern': 'FILE_READ_ERROR',
                'content': f'Error reading file: {e}',
                'severity': 'ERROR'
            })
            
        return violations
    
    def check_allowed_sources_integrity(self) -> List[Dict]:
        """
        🔒 VERIFY ALLOWED_SOURCES INTEGRITY
        Ensures ALLOWED_SOURCES contains only 'chat'
        """
        violations = []
        constants_file = self.project_root / 'constants.py'
        
        if not constants_file.exists():
            violations.append({
                'file': 'constants.py',
                'line': 0,
                'pattern': 'MISSING_CONSTANTS_FILE',
                'content': 'constants.py file missing',
                'severity': 'CRITICAL'
            })
            return violations
            
        try:
            with open(constants_file, 'r') as f:
                content = f.read()
                
            # Check if ALLOWED_SOURCES only contains 'chat'
            allowed_sources_match = re.search(r'ALLOWED_SOURCES\s*=\s*\{([^}]+)\}', content)
            if allowed_sources_match:
                sources_content = allowed_sources_match.group(1)
                # Should only contain 'chat'
                if not re.match(r"^\s*['\"]chat['\"]\s*$", sources_content):
                    violations.append({
                        'file': 'constants.py',
                        'line': content[:allowed_sources_match.start()].count('\n') + 1,
                        'pattern': 'INVALID_ALLOWED_SOURCES',
                        'content': f'ALLOWED_SOURCES contains: {sources_content}',
                        'severity': 'CRITICAL'
                    })
            else:
                violations.append({
                    'file': 'constants.py',
                    'line': 0,
                    'pattern': 'MISSING_ALLOWED_SOURCES',
                    'content': 'ALLOWED_SOURCES not found',
                    'severity': 'CRITICAL'
                })
                
        except Exception as e:
            violations.append({
                'file': 'constants.py',
                'line': 0,
                'pattern': 'CONSTANTS_READ_ERROR',
                'content': f'Error reading constants.py: {e}',
                'severity': 'ERROR'
            })
            
        return violations
    
    def generate_report(self) -> str:
        """Generate formatted violation report"""
        if not self.violations:
            return "✅ NO SINGLE WRITER INVARIANT VIOLATIONS DETECTED"
            
        report = ["🚨 SINGLE WRITER INVARIANT VIOLATIONS DETECTED", "=" * 50]
        
        critical_count = len([v for v in self.violations if v['severity'] == 'CRITICAL'])
        high_count = len([v for v in self.violations if v['severity'] == 'HIGH'])
        
        report.append(f"CRITICAL: {critical_count}, HIGH: {high_count}")
        report.append("")
        
        for violation in self.violations:
            report.append(f"🚨 {violation['severity']}: {violation['file']}:{violation['line']}")
            report.append(f"   Pattern: {violation['pattern']}")
            report.append(f"   Content: {violation['content']}")
            report.append("")
            
        return "\n".join(report)

def run_ci_invariant_check() -> bool:
    """
    🎯 CI ENTRY POINT
    Run invariant checks and return True if all checks pass
    """
    detector = InvariantViolationDetector()
    
    # Run comprehensive scan
    violations = detector.scan_codebase()
    
    # Check ALLOWED_SOURCES integrity
    source_violations = detector.check_allowed_sources_integrity()
    violations.extend(source_violations)
    
    # Generate report
    report = detector.generate_report()
    print(report)
    
    # Return success/failure
    critical_violations = [v for v in violations if v['severity'] in ['CRITICAL', 'ERROR']]
    return len(critical_violations) == 0

if __name__ == "__main__":
    """CI Script Entry Point"""
    success = run_ci_invariant_check()
    sys.exit(0 if success else 1)