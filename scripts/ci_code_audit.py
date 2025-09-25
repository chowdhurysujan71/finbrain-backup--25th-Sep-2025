#!/usr/bin/env python3
"""
Code References Audit - Evidence-Driven Release Assurance
Scans for banned references that would cause runtime failures
"""
import os
import re
import sys
import subprocess
from pathlib import Path

def scan_banned_references():
    """Scan for banned code references that would cause runtime failures"""
    print("🔍 Code References Audit - Evidence Generation")
    print("=" * 50)
    
    # Create artifacts directory
    artifacts_dir = Path("artifacts/static")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Define banned patterns and exclusions
    banned_patterns = [
        (r'\bget_completion\(', "get_completion() calls (deprecated AI adapter method)"),
        (r'\blocalhost\b', "localhost hardcoding (should use config)"),
        (r'^\s*print\(', "bare print() statements (should use logging)")
    ]
    
    exclude_patterns = [
        "_quarantine/**",
        "_attic/**", 
        "tests/**",
        "docs/**",
        "scripts/**",
        "*.pyc",
        "__pycache__/**"
    ]
    
    # Build ripgrep command with exclusions
    rg_cmd = ["rg", "-n", "--type", "py"]
    for exclude in exclude_patterns:
        rg_cmd.extend(["-g", f"!{exclude}"])
    
    results = []
    total_violations = 0
    
    for pattern, description in banned_patterns:
        print(f"\n🔍 Scanning for: {description}")
        
        try:
            # Run ripgrep for this pattern
            cmd = rg_cmd + [pattern, "."]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:  # Found matches
                matches = result.stdout.strip().split('\n')
                violation_count = len([m for m in matches if m.strip()])
                total_violations += violation_count
                
                print(f"  ❌ FOUND: {violation_count} violations")
                results.append(f"VIOLATIONS: {description}")
                results.append(f"Count: {violation_count}")
                results.extend([f"  {match}" for match in matches if match.strip()])
                results.append("")
            else:
                print(f"  ✅ CLEAN: No violations found")
                results.append(f"CLEAN: {description}")
                results.append("")
                
        except FileNotFoundError:
            print(f"  ⚠️  ripgrep not found, falling back to grep")
            # Fallback to basic grep
            try:
                result = subprocess.run(
                    ["grep", "-r", "-n", "--include=*.py", pattern, "."], 
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    matches = result.stdout.strip().split('\n')
                    violation_count = len([m for m in matches if m.strip() and not any(excl.replace("**", "") in m for excl in exclude_patterns)])
                    total_violations += violation_count
                    print(f"  ❌ FOUND: {violation_count} violations (grep fallback)")
                else:
                    print(f"  ✅ CLEAN: No violations found (grep fallback)")
            except Exception as e:
                print(f"  💥 ERROR: Could not scan for {description}: {e}")
    
    # Write detailed audit results
    audit_file = artifacts_dir / "import_check.txt"
    with open(audit_file, "w") as f:
        f.write("Code References Audit Results\n")
        f.write("=" * 35 + "\n\n")
        f.write(f"Total Violations Found: {total_violations}\n\n")
        f.write("\n".join(results))
    
    # Generate summary
    print(f"\n📊 Code Audit Summary")
    print("=" * 25)
    print(f"Total Violations: {total_violations}")
    
    if total_violations == 0:
        print("✅ AUDIT: PASS (no banned references)")
        audit_status = "PASS"
        exit_code = 0
    else:
        print("❌ AUDIT: FAIL (banned references found)")
        audit_status = "FAIL"
        exit_code = 1
    
    # Write summary
    summary_file = artifacts_dir / "code_audit_summary.txt"
    with open(summary_file, "w") as f:
        f.write(f"Code Audit Status: {audit_status}\n")
        f.write(f"Total Violations: {total_violations}\n")
        f.write(f"Audit File: {audit_file}\n")
    
    print(f"\n📁 Audit results saved to: {audit_file}")
    return exit_code

if __name__ == "__main__":
    exit_code = scan_banned_references()
    sys.exit(exit_code)