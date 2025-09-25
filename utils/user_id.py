# utils/user_id.py
from functools import wraps

from flask import jsonify, session


def get_canonical_user_id():
    return session.get("user_id")

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        uid = get_canonical_user_id()
        if not uid:
            return jsonify({"error": "Please log in to track expenses"}), 401
        return fn(*args, **kwargs, user_id=uid)
    return wrapper