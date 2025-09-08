#!/usr/bin/env python3
"""
Deduplicate requirements.txt - Critical reliability fix
Removes duplicate packages that cause pip conflicts
"""
from collections import OrderedDict
import sys

def dedupe_requirements():
    """Remove duplicate packages from requirements.txt"""
    try:
        with open("requirements.txt", "r") as f:
            lines = f.readlines()
        
        # Track seen packages (case-insensitive)
        seen = OrderedDict()
        deduped = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                deduped.append(line)
                continue
                
            # Extract package name (before ==, >=, etc.)
            pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip().lower()
            
            if pkg_name not in seen:
                seen[pkg_name] = line
                deduped.append(line)
            else:
                print(f"REMOVED DUPLICATE: {line} (keeping {seen[pkg_name]})")
        
        # Write deduplicated requirements
        with open("requirements.txt", "w") as f:
            f.write("\n".join(deduped) + "\n")
            
        print(f"✓ Deduplication complete. Removed {len(lines) - len(deduped)} duplicates")
        return True
        
    except Exception as e:
        print(f"✗ Error deduplicating requirements: {e}")
        return False

if __name__ == "__main__":
    success = dedupe_requirements()
    sys.exit(0 if success else 1)