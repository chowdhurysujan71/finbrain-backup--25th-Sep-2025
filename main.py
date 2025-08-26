import os
# Phase 4: Limited Production - Enable actual transaction creation
os.environ['PCA_MODE'] = 'ON'

from app import app  # noqa: F401
