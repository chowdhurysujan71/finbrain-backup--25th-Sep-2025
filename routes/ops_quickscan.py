"""
Diagnostic endpoint for tracing write/read path inconsistencies
"""
from flask import Blueprint, request

from models import Expense, User
from utils.identity import ensure_hashed

bp = Blueprint("quickscan", __name__)

@bp.route("/ops/quickscan")
def quickscan():
    """Diagnostic endpoint to check user data consistency - ADMIN ACCESS REQUIRED"""
    # Check authentication
    from flask import jsonify

    from app import check_basic_auth
    
    if not check_basic_auth():
        return jsonify({"error": "Authentication required"}), 401
    psid = request.args.get("psid")
    psid_hash = request.args.get("psid_hash")
    
    if not (psid or psid_hash):
        return jsonify({"error": "provide psid or psid_hash"}), 400
    
    user_id = ensure_hashed(psid or psid_hash or "")
    
    # Check expenses table
    expenses = Expense.query.filter_by(user_id=user_id).all()
    expense_total = sum(float(expense.amount) for expense in expenses)
    
    # Check users table  
    user = User.query.filter_by(user_id_hash=user_id).first()
    
    # Sample expenses
    sample_expenses = [
        {
            "id": exp.id,
            "description": exp.description,
            "amount": float(exp.amount),
            "category": exp.category,
            "created_at": exp.created_at.isoformat() if exp.created_at else None
        }
        for exp in expenses[:3]
    ]
    
    return jsonify({
        "resolved_user_id": user_id,
        "expenses_table": {
            "count": len(expenses),
            "total": expense_total,
            "sample": sample_expenses
        },
        "users_table": {
            "exists": user is not None,
            "total_expenses": float(user.total_expenses) if user else 0,
            "expense_count": user.expense_count if user else 0
        },
        "consistency_check": {
            "field_names": {
                "expenses_uses": "user_id",
                "users_uses": "user_id_hash"
            },
            "counts_match": len(expenses) == (user.expense_count if user else 0),
            "totals_match": abs(expense_total - (float(user.total_expenses) if user else 0)) < 0.01
        }
    }), 200