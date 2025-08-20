"""
Guardrail test to prevent regressions in router canonicality
Ensures all imports use utils.production_router instead of non-canonical paths
"""

import os
import re
from pathlib import Path

NON_CANON_PATTERN = re.compile(r'(^|\s)from\s+production_router\s+import|(^|\s)import\s+production_router\b')

def test_no_noncanonical_router_imports():
    """Ensure no file imports production_router without utils. prefix"""
    repo_root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in repo_root.rglob("*.py"):
        if "venv" in str(path) or ".pythonlibs" in str(path) or ".cache" in str(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if NON_CANON_PATTERN.search(text):
                offenders.append(str(path.relative_to(repo_root)))
        except Exception:
            continue
    assert not offenders, f"Found non-canonical router imports: {offenders}"

def test_canonical_router_importable():
    """Ensure canonical router path is valid and importable"""
    from utils.production_router import production_router, ProductionRouter
    assert production_router is not None
    assert ProductionRouter is not None

def test_canonical_router_sha_verification():
    """Verify canonical router has expected SHA"""
    import hashlib
    from pathlib import Path
    
    canonical_path = Path(__file__).resolve().parent.parent / "utils" / "production_router.py"
    if canonical_path.exists():
        sha = hashlib.sha256(canonical_path.read_bytes()).hexdigest()[:12]
        expected_sha = "cc72dd77e8d8"
        assert sha == expected_sha, f"Canonical router SHA mismatch: got {sha}, expected {expected_sha}"
    else:
        assert False, "Canonical router file utils/production_router.py not found"