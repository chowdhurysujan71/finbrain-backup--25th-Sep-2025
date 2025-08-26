import os
# Force DRYRUN mode for Phase 3 testing
os.environ['PCA_MODE'] = 'DRYRUN'

from app import app  # noqa: F401
