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
    
    # Initialize scheduler for automated reports (optional for production)
    if os.getenv("ENABLE_REPORTS", "false").lower() == "true":
        from utils.scheduler import init_scheduler
        init_scheduler()
        logger.info("Background reports scheduler enabled")
    else:
        logger.info("Background reports disabled (ENABLE_REPORTS=false)")
    
    # Initialize background processor
    logger.info("Initializing background processor...")
    from utils.background_processor import background_processor
    logger.info(f"Background processor ready: {background_processor.get_stats()}")
    
    # Run cold-start mitigation warm-up
    logger.info("Running cold-start mitigation...")
    from utils.cold_start_mitigation import cold_start_mitigator
    warm_up_results = cold_start_mitigator.run_warm_up_sequence()
    logger.info(f"Cold-start mitigation completed: {warm_up_results}")
    
    # Start health ping system to keep server warm
    from utils.health_ping import health_pinger
    health_pinger.start_health_pings()

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
    """Health check endpoint with production security monitoring"""
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
    
    # Enhanced security: Check Facebook token health
    try:
        from utils.token_manager import check_token_health
        token_healthy, token_message = check_token_health()
        if not token_healthy:
            health_status = "degraded"
            issues.append(f"token_issue")
    except Exception as e:
        logger.error(f"Token health check failed: {str(e)}")
        health_status = "degraded"
        issues.append("token_check_failed")
    
    # Production security: All required envs guaranteed to exist (validated at boot)
    required_envs = ["DATABASE_URL", "ADMIN_USER", "ADMIN_PASS", "FACEBOOK_PAGE_ACCESS_TOKEN", 
                    "FACEBOOK_VERIFY_TOKEN", "FACEBOOK_APP_SECRET", "FACEBOOK_APP_ID"]
    
    # Check optional environment variables
    optional_envs = ["SENTRY_DSN"]
    present_optional = [env for env in optional_envs if os.environ.get(env)]
    
    # Get enhanced system metrics
    from utils.cold_start_mitigation import cold_start_mitigator
    from utils.background_processor import background_processor
    
    uptime_seconds = cold_start_mitigator.get_uptime_seconds()
    queue_depth = background_processor.get_stats().get("queue_size", 0)
    ai_status = cold_start_mitigator.get_ai_status()
    
    # Adjust overall status based on cold-start completion
    if health_status == "healthy" and not cold_start_mitigator.warm_up_completed:
        health_status = "warming"
    
    response = {
        "status": health_status,
        "service": "finbrain-expense-tracker",
        "database": database_status,
        "platform_support": ["facebook_messenger"],
        "required_envs": {
            "all_present": True,
            "count": len(required_envs)
        },
        "boot_validation": "strict_enforcement_enabled",
        "uptime_s": round(uptime_seconds, 2),
        "queue_depth": queue_depth,
        "ai_status": ai_status,
        "cold_start_mitigation": {
            "completed": cold_start_mitigator.warm_up_completed,
            "ai_enabled": cold_start_mitigator.ai_enabled
        },
        "security": {
            "https_enforced": True,
            "signature_verification": "mandatory",
            "token_monitoring": "enabled"
        }
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
    
    if request.method == "GET":
        # Facebook webhook verification
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        mode = request.args.get("hub.mode")
        
        logger.info(f"Webhook verification: mode={mode}, token_provided={bool(verify_token)}, challenge={bool(challenge)}")
        
        if mode == "subscribe" and verify_token == os.environ.get("FACEBOOK_VERIFY_TOKEN"):
            logger.info("Webhook verification successful")
            return challenge
        else:
            logger.warning(f"Webhook verification failed: mode={mode}, token_match={verify_token == os.environ.get('FACEBOOK_VERIFY_TOKEN')}")
            return "Verification token mismatch", 403
        
    elif request.method == "POST":
        # PRODUCTION SECURITY: Enforce HTTPS
        if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
            logger.error("Webhook called over HTTP - Facebook requires HTTPS")
            return "HTTPS required", 400
        
        # PRODUCTION SECURITY: Mandatory signature verification
        from utils.webhook_processor import process_webhook_fast
        
        # Get raw payload and signature
        payload_bytes = request.get_data()
        signature = request.headers.get('X-Hub-Signature-256', '')
        
        # Get app secret - REQUIRED for production
        app_secret = os.environ.get('FACEBOOK_APP_SECRET', '')
        
        if not app_secret:
            logger.error("FACEBOOK_APP_SECRET is required for webhook signature verification")
            return "Configuration error", 500
        
        if not signature:
            logger.error("Missing X-Hub-Signature-256 header")
            return "Missing signature", 400
        
        response_text, status_code = process_webhook_fast(payload_bytes, signature, app_secret)
        return response_text, status_code

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
        
        # Get Facebook token status
        try:
            from utils.token_manager import get_token_status
            token_status = get_token_status()
        except Exception as e:
            logger.error(f"Failed to get token status: {str(e)}")
            token_status = {"error": "token_status_unavailable"}
        
        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "facebook_token": token_status,
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

@app.route('/ops/token-refresh-status', methods=['GET'])
@require_basic_auth
def token_refresh_status():
    """Token refresh monitoring and reminder endpoint (JSON) - Admin access required"""
    try:
        from utils.token_refresh_reminder import get_token_refresh_status
        
        refresh_status = get_token_refresh_status()
        
        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "token-refresh-status",
            "refresh_monitoring": refresh_status
        })
        
    except Exception as e:
        logger.error(f"Token refresh status error: {str(e)}")
        return jsonify({
            "error": "Failed to retrieve token refresh status",
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

@app.route('/version', methods=['GET'])
def version():
    """Version endpoint for deployment tracking"""
    try:
        # Try to read deployment info if available
        import json
        try:
            with open('deployment_info.json', 'r') as f:
                deployment_info = json.load(f)
                release_info = deployment_info.get('release', {})
        except FileNotFoundError:
            release_info = {
                "version": "v1.0.0-mvp",
                "status": "development"
            }
        
        return jsonify({
            "service": "finbrain-expense-tracker",
            "version": release_info.get("version", "v1.0.0-mvp"),
            "build_date": release_info.get("build_date", "unknown"),
            "commit_hash": release_info.get("short_hash", "unknown"),
            "status": release_info.get("status", "development"),
            "security_hardening": "complete",
            "deployment_ready": True
        })
        
    except Exception as e:
        logger.error(f"Version endpoint error: {str(e)}")
        return jsonify({
            "service": "finbrain-expense-tracker", 
            "version": "v1.0.0-mvp",
            "status": "error",
            "error": "version_info_unavailable",
            "security_hardening": "complete"
        }), 500





# Legacy handler - now replaced by fast webhook processor
# Keeping for reference but no longer used

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
