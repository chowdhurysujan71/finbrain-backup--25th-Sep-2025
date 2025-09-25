#!/usr/bin/env python3
"""
🔒 FinBrain Security Scanner
Comprehensive security hygiene checks for secret scanning and vulnerability detection
"""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SecurityScanner:
    """Comprehensive security scanner for FinBrain codebase"""
    
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.violations = []
        self.scan_stats = {
            'files_scanned': 0,
            'secrets_found': 0,
            'vulnerabilities_found': 0,
            'excluded_files': 0
        }
        
        # Common secret patterns to detect
        self.secret_patterns = [
            # API Keys
            (r'api[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9]{20,}["\']?', 'API Key'),
            (r'secret[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9]{20,}["\']?', 'Secret Key'),
            
            # Database credentials
            (r'password\s*[=:]\s*["\'][^"\']{8,}["\']', 'Hard-coded Password'),
            (r'db[_-]?password\s*[=:]\s*["\'][^"\']{6,}["\']', 'DB Password'),
            
            # Authentication tokens
            (r'token\s*[=:]\s*["\']?[a-zA-Z0-9]{30,}["\']?', 'Auth Token'),
            (r'bearer\s+[a-zA-Z0-9]{20,}', 'Bearer Token'),
            
            # Cloud service keys
            (r'aws[_-]?access[_-]?key[_-]?id\s*[=:]\s*["\']?[A-Z0-9]{20}["\']?', 'AWS Access Key'),
            (r'aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9/+]{40}["\']?', 'AWS Secret Key'),
            
            # Private keys
            (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', 'Private Key'),
            (r'private[_-]?key\s*[=:]\s*["\'][^"\']{20,}["\']', 'Private Key'),
            
            # Database URLs with credentials
            (r'[a-zA-Z]+://[^:]+:[^@]+@[^/]+', 'Database URL with credentials'),
            
            # Generic secrets
            (r'["\'][a-zA-Z0-9]{32,}["\']', 'Potential Secret'),
        ]
        
        # Files and directories to exclude
        self.exclude_patterns = [
            r'\.git/',
            r'node_modules/',
            r'\.pytest_cache/',
            r'__pycache__/',
            r'\.pyc$',
            r'\.log$',
            r'\.tmp$',
            r'\.DS_Store$',
            r'security_scanner\.py$',  # Don't scan this file
            r'test_.*\.py$',  # Test files might have dummy secrets
        ]
        
        # Safe patterns that are not real secrets
        self.safe_patterns = [
            r'YOUR_API_KEY_HERE',
            r'example\.com',
            r'localhost',
            r'127\.0\.0\.1',
            r'placeholder',
            r'dummy',
            r'test[_-]?key',
            r'mock[_-]?secret',
            r'fake[_-]?token',
        ]
    
    def should_exclude_file(self, file_path: str) -> bool:
        """Check if file should be excluded from scanning"""
        for pattern in self.exclude_patterns:
            if re.search(pattern, file_path):
                return True
        return False
    
    def is_safe_pattern(self, content: str) -> bool:
        """Check if content matches safe/dummy patterns"""
        content_lower = content.lower()
        for pattern in self.safe_patterns:
            if re.search(pattern, content_lower):
                return True
        return False
    
    def scan_file_for_secrets(self, file_path: Path) -> list[dict]:
        """Scan a single file for potential secrets"""
        violations = []
        
        try:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            for pattern, secret_type in self.secret_patterns:
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        matched_text = match.group(0)
                        
                        # Skip if it's a safe pattern
                        if self.is_safe_pattern(matched_text):
                            continue
                        
                        # Skip if it's in a comment explaining what NOT to do
                        if any(comment in line.lower() for comment in ['# never', '# don\'t', '# avoid', '# example']):
                            continue
                        
                        violations.append({
                            'type': 'secret',
                            'file': str(file_path),
                            'line': line_num,
                            'column': match.start() + 1,
                            'secret_type': secret_type,
                            'pattern': pattern,
                            'context': line.strip(),
                            'severity': 'HIGH'
                        })
                        
        except Exception as e:
            logger.warning(f"Could not scan {file_path}: {e}")
            
        return violations
    
    def scan_dependencies(self) -> list[dict]:
        """Scan dependencies for known vulnerabilities"""
        vulnerabilities = []
        
        # Check Python dependencies
        if (self.root_path / 'requirements.txt').exists():
            try:
                result = subprocess.run([
                    sys.executable, '-m', 'pip', 'list', '--format=json'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    packages = json.loads(result.stdout)
                    
                    # Known vulnerable patterns (simplified check)
                    vulnerable_packages = {
                        'requests': ['2.25.0', '2.25.1'],  # Example vulnerable versions
                        'flask': ['1.0.0', '1.0.1'],
                        'sqlalchemy': ['1.3.0']
                    }
                    
                    for package in packages:
                        name = package['name'].lower()
                        version = package['version']
                        
                        if name in vulnerable_packages:
                            if version in vulnerable_packages[name]:
                                vulnerabilities.append({
                                    'type': 'vulnerability',
                                    'package': name,
                                    'version': version,
                                    'severity': 'MEDIUM',
                                    'description': f'Package {name} {version} has known vulnerabilities'
                                })
                                
            except Exception as e:
                logger.warning(f"Could not check Python dependencies: {e}")
        
        # Check Node.js dependencies
        if (self.root_path / 'package.json').exists():
            try:
                result = subprocess.run([
                    'npm', 'audit', '--json'
                ], cwd=self.root_path, capture_output=True, text=True)
                
                if result.returncode == 0:
                    audit_data = json.loads(result.stdout)
                    if 'vulnerabilities' in audit_data:
                        for vuln_name, vuln_data in audit_data['vulnerabilities'].items():
                            vulnerabilities.append({
                                'type': 'vulnerability',
                                'package': vuln_name,
                                'severity': vuln_data.get('severity', 'UNKNOWN').upper(),
                                'description': vuln_data.get('title', 'Unknown vulnerability')
                            })
                            
            except Exception as e:
                logger.warning(f"Could not check Node.js dependencies: {e}")
        
        return vulnerabilities
    
    def check_environment_security(self) -> list[dict]:
        """Check environment variable security practices"""
        violations = []
        
        # Check for .env files
        env_files = list(self.root_path.glob('**/.env*'))
        for env_file in env_files:
            if env_file.name != '.env.example':
                violations.append({
                    'type': 'environment',
                    'file': str(env_file),
                    'severity': 'HIGH',
                    'description': 'Environment file should not be committed to repository'
                })
        
        # Check for hardcoded environment variables
        py_files = list(self.root_path.glob('**/*.py'))
        for py_file in py_files:
            if self.should_exclude_file(str(py_file)):
                continue
                
            try:
                with open(py_file, encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                # Look for os.environ assignments with hardcoded values
                env_assign_pattern = r'os\.environ\[["\']([^"\']+)["\']\]\s*=\s*["\']([^"\']+)["\']'
                matches = re.finditer(env_assign_pattern, content)
                
                for match in matches:
                    env_var = match.group(1)
                    env_value = match.group(2)
                    
                    # Skip safe assignments
                    if any(safe in env_value.lower() for safe in ['test', 'dev', 'localhost', 'example']):
                        continue
                        
                    violations.append({
                        'type': 'environment',
                        'file': str(py_file),
                        'severity': 'MEDIUM',
                        'description': f'Hardcoded environment variable assignment: {env_var}={env_value}'
                    })
                    
            except Exception as e:
                logger.warning(f"Could not check {py_file}: {e}")
        
        return violations
    
    def scan_all(self) -> dict:
        """Run comprehensive security scan"""
        logger.info("🔒 Starting comprehensive security scan...")
        
        all_violations = []
        
        # 1. Scan for secrets in files
        logger.info("📝 Scanning files for secrets...")
        file_extensions = ['.py', '.js', '.ts', '.json', '.yaml', '.yml', '.txt', '.md']
        
        for ext in file_extensions:
            files = list(self.root_path.glob(f'**/*{ext}'))
            for file_path in files:
                if self.should_exclude_file(str(file_path)):
                    self.scan_stats['excluded_files'] += 1
                    continue
                    
                self.scan_stats['files_scanned'] += 1
                file_violations = self.scan_file_for_secrets(file_path)
                all_violations.extend(file_violations)
                
        self.scan_stats['secrets_found'] = len([v for v in all_violations if v['type'] == 'secret'])
        
        # 2. Scan dependencies
        logger.info("📦 Scanning dependencies for vulnerabilities...")
        dep_violations = self.scan_dependencies()
        all_violations.extend(dep_violations)
        self.scan_stats['vulnerabilities_found'] = len(dep_violations)
        
        # 3. Check environment security
        logger.info("🌍 Checking environment variable security...")
        env_violations = self.check_environment_security()
        all_violations.extend(env_violations)
        
        self.violations = all_violations
        
        return {
            'total_violations': len(all_violations),
            'violations': all_violations,
            'stats': self.scan_stats,
            'summary': self.generate_summary()
        }
    
    def generate_summary(self) -> dict:
        """Generate scan summary"""
        violations_by_type = {}
        violations_by_severity = {}
        
        for violation in self.violations:
            # Count by type
            v_type = violation['type']
            violations_by_type[v_type] = violations_by_type.get(v_type, 0) + 1
            
            # Count by severity
            severity = violation.get('severity', 'UNKNOWN')
            violations_by_severity[severity] = violations_by_severity.get(severity, 0) + 1
        
        return {
            'by_type': violations_by_type,
            'by_severity': violations_by_severity,
            'scan_stats': self.scan_stats
        }
    
    def generate_report(self, output_file: str = None) -> str:
        """Generate comprehensive security report"""
        report_lines = [
            "🔒 FINBRAIN SECURITY SCAN REPORT",
            "=" * 50,
            "",
            "📊 SCAN STATISTICS:",
            f"  Files Scanned: {self.scan_stats['files_scanned']}",
            f"  Files Excluded: {self.scan_stats['excluded_files']}",
            f"  Secrets Found: {self.scan_stats['secrets_found']}",
            f"  Vulnerabilities Found: {self.scan_stats['vulnerabilities_found']}",
            "",
            f"🎯 TOTAL VIOLATIONS: {len(self.violations)}",
            ""
        ]
        
        if not self.violations:
            report_lines.extend([
                "✅ NO SECURITY VIOLATIONS FOUND!",
                "🎉 Your codebase follows security best practices.",
                ""
            ])
        else:
            # Group violations by severity
            high_violations = [v for v in self.violations if v.get('severity') == 'HIGH']
            medium_violations = [v for v in self.violations if v.get('severity') == 'MEDIUM']
            low_violations = [v for v in self.violations if v.get('severity') == 'LOW']
            
            if high_violations:
                report_lines.extend([
                    "🚨 HIGH SEVERITY VIOLATIONS:",
                    "-" * 30
                ])
                for violation in high_violations:
                    report_lines.append(f"  {violation.get('description', violation['type'])}")
                    if 'file' in violation:
                        report_lines.append(f"    File: {violation['file']}")
                    if 'line' in violation:
                        report_lines.append(f"    Line: {violation['line']}")
                    report_lines.append("")
            
            if medium_violations:
                report_lines.extend([
                    "⚠️  MEDIUM SEVERITY VIOLATIONS:",
                    "-" * 30
                ])
                for violation in medium_violations:
                    report_lines.append(f"  {violation.get('description', violation['type'])}")
                    if 'file' in violation:
                        report_lines.append(f"    File: {violation['file']}")
                    report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        if output_file:
            output_path = Path(output_file)
            with open(output_path, 'w') as f:
                f.write(report_text)
            logger.info(f"📄 Report saved to {output_path}")
        
        return report_text

def main():
    """Main security scanner entry point"""
    scanner = SecurityScanner()
    results = scanner.scan_all()
    
    # Generate and display report
    report = scanner.generate_report('security_scan_report.txt')
    print(report)
    
    # Return exit code based on violations
    high_violations = [v for v in scanner.violations if v.get('severity') == 'HIGH']
    if high_violations:
        logger.error(f"❌ {len(high_violations)} high severity violations found")
        return 1
    elif scanner.violations:
        logger.warning(f"⚠️  {len(scanner.violations)} violations found")
        return 0  # Don't fail CI for medium/low severity
    else:
        logger.info("✅ No security violations found")
        return 0

if __name__ == "__main__":
    sys.exit(main())