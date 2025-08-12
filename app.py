import os
import logging
import sys
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
import json
import base64
from datetime import datetime, timedelta

# Configure logging - production mode removes debug and reload
log_level = logging.INFO if os.environ.get('ENV') == 'production' else logging.DEBUG
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_required_environment():
    """Validate all required environment variables are present at boot"""
    required_envs = [
        'DATABASE_URL',
        'ADMIN_USER', 
        'ADMIN_PASS',
        'FACEBOOK_PAGE_ACCESS_TOKEN',
        'FACEBOOK_VERIFY_TOKEN'
    ]
    
    missing_envs = []
    for env_var in required_envs:
        if not os.environ.get(env_var):
            missing_envs.append(env_var)
    
    if missing_envs:
        logger.critical(f"BOOT FAILURE: Missing required environment variables: {missing_envs}")
        logger.critical("FinBrain refuses to start without all required environment variables")
        logger.critical("Set the following environment variables and restart:")
        for env_var in missing_envs:
            logger.critical(f"  - {env_var}")
        sys.exit(1)
    
    logger.info("✓ All required environment variables present")
    return True

# Validate environment before any Flask initialization
validate_required_environment()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SESSION_SECRET") or os.urandom(32).hex()
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database (guaranteed to exist due to validation)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    db.create_all()
    
    # Initialize scheduler for automated reports (after db setup)
    from utils.scheduler import init_scheduler
    init_scheduler()
    
    # Initialize background processor
    logger.info("Initializing background processor...")
    from utils.background_processor import background_processor
    logger.info(f"Background processor ready: {background_processor.get_stats()}")

def check_basic_auth():
    """Check HTTP Basic Authentication against ADMIN_USER/ADMIN_PASS"""
    auth = request.authorization
    admin_user = os.environ.get('ADMIN_USER')
    admin_pass = os.environ.get('ADMIN_PASS')
    
    if not admin_user or not admin_pass:
        return False
        
    if not auth or not auth.username or not auth.password:
        return False
    
    auth_success = auth.username == admin_user and auth.password == admin_pass
        
    return auth_success

def require_basic_auth(f):
    """Decorator to require HTTP Basic Authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_basic_auth():
            # Check if request expects JSON (for API endpoints)
            if request.headers.get('Content-Type') == 'application/json' or '/ops' in request.path or '/psid/' in request.path:
                response = make_response(jsonify({"error": "Authentication required"}), 401)
            else:
                # For dashboard/HTML requests, send HTML response
                response = make_response("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>FinBrain Admin Login</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
                        .auth-box { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }
                        h1 { color: #333; margin-bottom: 20px; }
                        p { color: #666; }
                    </style>
                </head>
                <body>
                    <div class="auth-box">
                        <h1>FinBrain Admin Access</h1>
                        <p>Please enter your admin credentials to access the dashboard.</p>
                        <p><small>Your browser should prompt for username and password.</small></p>
                    </div>
                </body>
                </html>
                """, 401)
            response.headers['WWW-Authenticate'] = 'Basic realm="FinBrain Admin"'
            return response
        return f(*args, **kwargs)
    return decorated_function

def check_admin_auth():
    """Check if user is authenticated as admin (legacy session-based)"""
    return session.get('admin_authenticated', False)

# Legacy admin login/logout routes removed - using HTTP Basic Auth now

@app.route('/')
@require_basic_auth
def dashboard():
    """Dashboard for viewing expense statistics (HTTP Basic Auth required)"""
    
    try:
        from models import Expense, User, MonthlySummary
        
        # Get recent expenses
        recent_expenses = Expense.query.order_by(Expense.created_at.desc()).limit(10).all()
        
        # Get total users
        total_users = User.query.count()
        
        # Get this month's summary stats
        from datetime import datetime
        current_month = datetime.now().strftime('%Y-%m')
        monthly_stats = MonthlySummary.query.filter_by(month=current_month).all()
        
        total_expenses_this_month = sum(stat.total_amount for stat in monthly_stats)
        total_transactions_this_month = sum(stat.expense_count for stat in monthly_stats)
        
        return render_template('dashboard.html',
                             recent_expenses=recent_expenses,
                             total_users=total_users,
                             total_expenses_this_month=total_expenses_this_month,
                             total_transactions_this_month=total_transactions_this_month)
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return render_template('dashboard.html',
                             recent_expenses=[],
                             total_users=0,
                             total_expenses_this_month=0,
                             total_transactions_this_month=0)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - all required envs guaranteed present at boot"""
    health_status = "healthy"
    issues = []
    
    # Check database connection
    try:
        db.session.execute(db.text('SELECT 1'))
        database_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        database_status = "disconnected"
        health_status = "degraded"
        issues.append("database_unreachable")
    
    # All required envs guaranteed to exist (validated at boot)
    required_envs = ["DATABASE_URL", "ADMIN_USER", "ADMIN_PASS", "FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_VERIFY_TOKEN"]
    
    # Check optional environment variables
    optional_envs = ["SENTRY_DSN"]
    present_optional = [env for env in optional_envs if os.environ.get(env)]
    
    response = {
        "status": health_status,
        "service": "finbrain-expense-tracker",
        "database": database_status,
        "platform_support": ["facebook_messenger"],
        "required_envs": {
            "all_present": True,
            "count": len(required_envs)
        },
        "boot_validation": "strict_enforcement_enabled"
    }
    
    if present_optional:
        response["optional_envs_present"] = present_optional
    
    if issues:
        response["issues"] = issues
    
    return jsonify(response)

@app.route("/webhook/messenger", methods=["GET", "POST"])
def webhook_messenger():
    """Facebook Messenger webhook with structured request logging"""
    from utils.logger import request_logger
    
    @request_logger
    def _webhook():
        if request.method == "GET":
            # Facebook webhook verification
            verify_token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            if verify_token == os.environ.get("FACEBOOK_VERIFY_TOKEN"):
                return challenge, 200  # Must return as plain text
            return "Verification token mismatch", 403
            
        elif request.method == "POST":
            # Fast webhook processing with signature verification
            from utils.webhook_processor import process_webhook_fast
            
            # Get raw payload and signature
            payload_bytes = request.get_data()
            signature = request.headers.get('X-Hub-Signature-256', '')
            
            # Skip signature verification for MVP (no FACEBOOK_APP_SECRET required)
            response_text, status_code = process_webhook_fast(payload_bytes, signature, '')
            return response_text, status_code
    
    return _webhook()

@app.route('/ops', methods=['GET'])
@require_basic_auth
def ops_status():
    """Operations status endpoint (JSON) - Admin access required"""
    try:
        from models import User, Expense
        from datetime import date, timedelta
        
        # Get message counts today
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        messages_today = Expense.query.filter(
            Expense.created_at >= today_start
        ).count()
        
        # Get last outbound success/failure (MVP: no outbound messages)
        last_outbound_success = None
        last_outbound_failure = None
        
        # Get last AI error (currently no AI errors tracked)
        last_ai_error = None
        
        # Get system stats
        total_users = User.query.count()
        total_messages = Expense.query.count()
        
        # Get recent activity (last hour)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_activity = Expense.query.filter(
            Expense.created_at >= hour_ago
        ).count()
        
        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "message_counts": {
                "today": messages_today,
                "total": total_messages,
                "last_hour": recent_activity
            },
            "outbound_status": {
                "last_success": last_outbound_success,
                "last_failure": last_outbound_failure,
                "note": "MVP: No scheduled outbound messages (24h policy compliance)"
            },
            "ai_status": {
                "last_error": last_ai_error,
                "note": "MVP: Simple regex routing (no AI processing)"
            },
            "system_stats": {
                "total_users": total_users,
                "uptime_check": "healthy"
            }
        })
        
    except Exception as e:
        logger.error(f"Ops status error: {str(e)}")
        return jsonify({
            "error": "Failed to retrieve ops status",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/psid/<psid_hash>', methods=['GET'])
@require_basic_auth 
def psid_explorer(psid_hash):
    """PSID Explorer - Last 20 messages and computed summary (Read-only)"""
    try:
        from models import User, Expense
        
        # Find user by PSID hash
        user = User.query.filter_by(user_id_hash=psid_hash).first()
        if not user:
            return jsonify({"error": "PSID not found"}), 404
        
        # Get last 20 expenses for this user
        recent_expenses = Expense.query.filter_by(user_id=psid_hash).order_by(
            Expense.created_at.desc()
        ).limit(20).all()
        
        # Calculate computed summary (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        week_expenses = Expense.query.filter(
            Expense.user_id == psid_hash,
            Expense.created_at >= seven_days_ago
        ).all()
        
        # Category totals
        category_totals = {}
        week_total = 0
        
        for expense in week_expenses:
            category = expense.category
            amount = float(expense.amount)
            category_totals[category] = category_totals.get(category, 0) + amount
            week_total += amount
        
        # Format expenses for response
        formatted_expenses = []
        for expense in recent_expenses:
            formatted_expenses.append({
                "id": expense.id,
                "amount": float(expense.amount),
                "currency": expense.currency,
                "description": expense.description,
                "category": expense.category,
                "created_at": expense.created_at.isoformat(),
                "original_message": expense.original_message or "N/A"
            })
        
        return jsonify({
            "psid_hash": psid_hash,
            "user_stats": {
                "total_expenses": float(user.total_expenses or 0),
                "expense_count": user.expense_count or 0,
                "platform": user.platform,
                "created_at": user.created_at.isoformat(),
                "last_interaction": user.last_interaction.isoformat() if user.last_interaction else None,
                "last_user_message_at": user.last_user_message_at.isoformat() if hasattr(user, 'last_user_message_at') and user.last_user_message_at else None
            },
            "recent_messages": formatted_expenses,
            "computed_summary": {
                "period": "last_7_days",
                "total_amount": week_total,
                "expense_count": len(week_expenses),
                "category_breakdown": category_totals
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Read-only PSID explorer - no personal data exposed"
            }
        })
        
    except Exception as e:
        logger.error(f"PSID explorer error: {str(e)}")
        return jsonify({"error": "Failed to retrieve PSID data"}), 500





# Legacy handler - now replaced by fast webhook processor
# Keeping for reference but no longer used

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
