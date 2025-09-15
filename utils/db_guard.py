# utils/db_guard.py
import warnings
from db_base import db as canonical_db

def assert_single_db_instance(db_candidate):
    if id(db_candidate) != id(canonical_db):
        warnings.warn(
            f"[DB GUARD] Multiple DB objects detected! "
            f"candidate={id(db_candidate)} canonical={id(canonical_db)}",
            RuntimeWarning,
        )