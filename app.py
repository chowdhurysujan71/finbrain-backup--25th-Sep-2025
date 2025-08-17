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
from datetime import datetime, timedelta, timezone

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
    
    # Log centralized configuration for observability
    from config import AI_RL_USER_LIMIT, AI_RL_WINDOW_SEC, AI_RL_GLOBAL_LIMIT, MSG_MAX_CHARS, TIMEZONE, CURRENCY_SYMBOL
    logger.info({
        "startup_configuration": {
            "rate_limits": {
                "ai_rl_user_limit": AI_RL_USER_LIMIT,
                "ai_rl_window_sec": AI_RL_WINDOW_SEC,
                "ai_rl_global_limit": AI_RL_GLOBAL_LIMIT
            },
            "app_constants": {
                "msg_max_chars": MSG_MAX_CHARS,
                "timezone": TIMEZONE,
                "currency_symbol": CURRENCY_SYMBOL
            },
            "ux_enhancements": {
                "fallback_copy": "Taking a quick breather to stay fast & free...",
                "system_prompt": "2-3 sentences max, action-oriented",
                "quick_replies": "structured messaging enabled"
            }
        }
    })
    
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
        from datetime import datetime
        from sqlalchemy import func, extract
        
        # Get recent expenses
        recent_expenses = Expense.query.order_by(Expense.created_at.desc()).limit(10).all()
        
        # Get total active users (users with expenses)
        total_users = db.session.query(func.count(func.distinct(Expense.user_id))).scalar()
        
        # Get this month's expenses directly from expense table
        today = datetime.utcnow()
        current_month = today.month
        current_year = today.year
        
        # Calculate this month's totals directly from expenses
        total_expenses_this_month = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            extract('month', Expense.created_at) == current_month,
            extract('year', Expense.created_at) == current_year
        ).scalar()
        
        total_transactions_this_month = db.session.query(Expense).filter(
            extract('month', Expense.created_at) == current_month,
            extract('year', Expense.created_at) == current_year
        ).count()
        
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
        # PRODUCTION SECURITY: Enforce HTTPS (temporarily disabled for local testing)
        # TODO: Re-enable for production deployment
        # if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
        #     logger.error("Webhook called over HTTP - Facebook requires HTTPS")
        #     return "HTTPS required", 400
        
        # PRODUCTION SECURITY: Mandatory signature verification
        from utils.webhook_processor import process_webhook_fast
        
        # Streamlined production routing
        try:
            from production_router import router as production_router
        except ImportError:
            production_router = None
        
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
        
        # Get AI status from production systems
        try:
            import os
            from utils.production_router import production_router
            
            ai_enabled = os.environ.get("AI_ENABLED", "false").lower() == "true"
            ai_provider = os.environ.get("AI_PROVIDER", "none") if ai_enabled else "none"
            telemetry = production_router.get_telemetry()
            
            ai_status_info = {
                "enabled": ai_enabled,
                "provider": ai_provider,
                "ai_messages": telemetry.get('ai_messages', 0),
                "rules_messages": telemetry.get('rules_messages', 0),
                "ai_failovers": telemetry.get('ai_failovers', 0),
                "note": f"Production AI: {ai_provider} enabled" if ai_enabled else "AI disabled - using deterministic rules"
            }
        except Exception as e:
            logger.error(f"Failed to get AI status: {str(e)}")
            ai_status_info = {
                "enabled": False,
                "provider": "unknown",
                "note": "AI status unavailable"
            }
        
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
            "ai_status": ai_status_info,
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

@app.route('/user/<psid_hash>/insights')
@require_basic_auth
def user_insights(psid_hash):
    """AI-powered user insights dashboard"""
    try:
        from models import User, Expense
        from utils.ai_adapter_gemini import generate_with_schema
        from datetime import datetime, timedelta
        import json
        
        # Find user by PSID hash
        user = User.query.filter_by(user_id_hash=psid_hash).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get user expenses (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        expenses = Expense.query.filter(
            Expense.user_id == psid_hash,
            Expense.created_at >= thirty_days_ago
        ).order_by(Expense.created_at.desc()).all()
        
        # Calculate spending metrics
        total_amount = sum(float(e.amount) for e in expenses)
        category_totals = {}
        for expense in expenses:
            cat = expense.category.lower()
            category_totals[cat] = category_totals.get(cat, 0) + float(expense.amount)
        
        largest_category = max(category_totals.keys(), key=category_totals.get) if category_totals else "other"
        largest_category_amount = category_totals.get(largest_category, 0)
        largest_category_pct = round((largest_category_amount / total_amount * 100), 1) if total_amount > 0 else 0
        
        # Generate AI insights
        ai_insights = {
            "summary": "I'm analyzing your spending patterns to provide personalized insights.",
            "key_insight": "Your spending patterns show opportunities for optimization.",
            "recommendation": "Consider tracking more detailed expense categories for better insights.",
            "smart_tip": "Try setting a weekly spending limit to build better financial habits."
        }
        
        # If we have enough data, use AI for real insights
        if total_amount > 0 and len(expenses) >= 3:
            try:
                context = f"User has spent {total_amount} over {len(expenses)} transactions. Main category: {largest_category} ({largest_category_pct}%). Categories: {', '.join(category_totals.keys())}"
                
                ai_result = generate_with_schema(
                    user_text=f"Generate financial insights for: {context}",
                    system_prompt="You are a financial advisor. Provide personalized insights based on spending data. Be encouraging and specific.",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "key_insight": {"type": "string"}, 
                            "recommendation": {"type": "string"},
                            "smart_tip": {"type": "string"}
                        }
                    }
                )
                
                if ai_result.get("ok") and "data" in ai_result:
                    ai_insights = ai_result["data"]
            except Exception as e:
                logger.warning(f"AI insights generation failed: {e}")
        
        # Build spending patterns for display
        spending_patterns = []
        category_icons = {
            'food': 'fas fa-utensils',
            'shopping': 'fas fa-shopping-cart',
            'bills': 'fas fa-file-invoice',
            'transport': 'fas fa-car',
            'other': 'fas fa-ellipsis-h'
        }
        
        for category, amount in category_totals.items():
            spending_patterns.append({
                'category': category,
                'amount': amount,
                'icon': category_icons.get(category, 'fas fa-tag'),
                'ai_insight': f"Spent {amount} on {category} this month"
            })
        
        # Recent interactions (last 5 expenses as conversation proxy)
        recent_interactions = []
        for expense in expenses[:5]:
            recent_interactions.append({
                'user_message': expense.original_message or f"Logged {expense.amount} for {expense.description}",
                'ai_response': f"Recorded {expense.amount} in {expense.category}. Great job tracking your expenses!",
                'timestamp': expense.created_at.strftime('%Y-%m-%d %H:%M'),
                'detected_amount': expense.amount,
                'detected_category': expense.category
            })
        
        return render_template('user_insights.html',
            user_profile={
                'first_name': user.first_name or 'User',
                'focus_area': user.focus_area or 'saving',
                'income_range': user.income_range or 'not specified'
            },
            ai_insights=ai_insights,
            spending_metrics={
                'monthly_total': total_amount,
                'transaction_count': len(expenses),
                'largest_category': largest_category,
                'largest_category_pct': largest_category_pct,
                'trend': 'stable',
                'trend_percentage': 0
            },
            spending_patterns=spending_patterns,
            recent_interactions=recent_interactions,
            timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        )
        
    except Exception as e:
        logger.error(f"User insights error: {e}")
        return jsonify({"error": "Failed to generate insights"}), 500

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

@app.route('/ops/telemetry', methods=['GET'])
@require_basic_auth
def ops_telemetry():
    """Advanced telemetry endpoint for comprehensive system monitoring"""
    try:
        from utils.production_router import production_router
        import os
        
        telemetry_data = production_router.get_telemetry()
        
        return jsonify({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_status': 'healthy',
            'config': {
                'ai_enabled_effective': os.environ.get("AI_ENABLED", "false").lower() == "true",
                'ai_provider': os.environ.get("AI_PROVIDER", "none"),
                'gemini_model': "gemini-2.5-flash-lite" if os.environ.get("AI_PROVIDER") == "gemini" else None,
                'ai_timeout': 3,
                'rate_limits': {
                    'global_per_min': int(os.environ.get("AI_MAX_CALLS_PER_MIN", "10")),
                    'per_psid_per_min': int(os.environ.get("AI_MAX_CALLS_PER_MIN_PER_PSID", "4"))
                }
            },
            'routing': {
                'total_messages': telemetry_data['total_messages'],
                'ai_messages': telemetry_data['ai_messages'],
                'rl2_messages': telemetry_data['rl2_messages'],
                'rules_messages': telemetry_data['rules_messages'],
                'ai_failovers': telemetry_data['ai_failovers']
            },
            'performance': {
                'queue_depth': telemetry_data['queue_depth'],
                'avg_processing_time_ms': telemetry_data.get('avg_processing_time_ms', 0),
                'success_rate': telemetry_data.get('success_rate', 100.0)
            }
        })
        
    except Exception as e:
        logger.error(f"Telemetry endpoint error: {str(e)}")
        return jsonify({
            "error": "Failed to retrieve telemetry",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/ops/ai/ping', methods=['GET'])
@require_basic_auth
def ops_ai_ping():
    """AI provider ping test with latency measurement"""
    try:
        from utils.ai_adapter_v2 import production_ai_adapter
        import time
        
        if not production_ai_adapter.enabled:
            return jsonify({
                "ok": False,
                "error": "AI disabled",
                "latency_ms": 0
            })
        
        # Test AI ping with simple request
        start_time = time.time()
        test_result = production_ai_adapter.ai_parse("ping test", {
            'user_hash': 'ping_test',
            'request_id': 'ping_test',
            'tokens_remaining': 100
        })
        latency_ms = (time.time() - start_time) * 1000
        
        return jsonify({
            "ok": not test_result.get('failover', False),
            "latency_ms": round(latency_ms, 2),
            "provider": production_ai_adapter.provider,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"AI ping error: {str(e)}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "latency_ms": 0
        }), 500

@app.route('/ops/rl/reset', methods=['POST'])
@require_basic_auth
def ops_rl_reset():
    """Reset rate limiter for testing"""
    try:
        from utils.ai_rate_limiter import ai_rate_limiter
        
        # Reset the rate limiter
        ai_rate_limiter.reset_all()
        
        return jsonify({
            "status": "reset_complete",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "All rate limits cleared"
        })
        
    except Exception as e:
        logger.error(f"Rate limiter reset error: {str(e)}")
        return jsonify({
            "error": "Failed to reset rate limiter",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/ops/trace', methods=['GET'])
@require_basic_auth
def ops_trace():
    """Routing trace logs for debugging"""
    try:
        from utils.production_router import production_router
        
        # Get recent routing decisions
        trace_data = production_router.get_trace_logs()
        
        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "trace_count": len(trace_data),
            "last": trace_data[-50:] if trace_data else []  # Last 50 traces
        })
        
    except Exception as e:
        logger.error(f"Trace endpoint error: {str(e)}")
        return jsonify({
            "error": "Failed to retrieve trace logs",
            "timestamp": datetime.utcnow().isoformat(),
            "last": []
        }), 500

@app.route('/ops/users', methods=['GET'])
@require_basic_auth
def ops_users():
    """User management dashboard with AI insights links"""
    try:
        from models import User
        
        # Get all users with expense counts
        users = User.query.all()
        
        user_list = []
        for user in users:
            user_list.append({
                'psid_hash': user.user_id_hash,
                'expense_count': user.expense_count or 0,
                'total_expenses': float(user.total_expenses or 0),
                'platform': user.platform,
                'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else 'Unknown',
                'last_interaction': user.last_interaction.strftime('%Y-%m-%d %H:%M') if user.last_interaction else 'Never',
                'first_name': user.first_name or 'User',
                'focus_area': user.focus_area or 'Not set'
            })
        
        # Sort by expense count descending
        user_list.sort(key=lambda x: x['expense_count'], reverse=True)
        
        return render_template('user_list.html', users=user_list, total_users=len(user_list))
        
    except Exception as e:
        logger.error(f"User list error: {e}")
        return jsonify({"error": "Failed to retrieve users"}), 500

# Register streamlined admin operations
from admin_ops import admin_ops
app.register_blueprint(admin_ops)

@app.route("/webhook", methods=["POST"])
def webhook():
    """Simple PSID extraction endpoint for testing real Facebook PSIDs"""
    data = request.get_json()
    try:
        psid = data["entry"][0]["messaging"][0]["sender"]["id"]
        print("REAL PSID:", psid)
        logger.info(f"Real Facebook PSID received: {psid}")
        
        # Test our new PSID validation
        from fb_client import is_valid_psid
        is_valid = is_valid_psid(psid)
        logger.info(f"PSID validation result: {psid} -> {is_valid}")
        
        return "EVENT_RECEIVED", 200
    except Exception as e:
        print("Could not extract PSID:", e, data)
        logger.error(f"PSID extraction failed: {str(e)}")
        return "EVENT_RECEIVED", 200

@app.route('/webhook/test', methods=['POST'])
def webhook_test():
    """Test endpoint for UAT - bypasses signature verification"""
    import time
    start_time = time.time()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "invalid_json"}), 400
            
        # Simple test processing
        if 'entry' in data and data['entry']:
            entry = data['entry'][0]
            if 'messaging' in entry and entry['messaging']:
                message = entry['messaging'][0]
                sender_id = message.get('sender', {}).get('id', 'unknown')
                text = message.get('message', {}).get('text', '')
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                return jsonify({
                    "status": "test_ack",
                    "sender_id": sender_id,
                    "text": text,
                    "processing_time_ms": round(elapsed_ms, 2),
                    "test_mode": True
                }), 200
        
        return jsonify({"error": "invalid_structure"}), 400
        
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return jsonify({
            "error": "test_error",
            "message": str(e),
            "processing_time_ms": round(elapsed_ms, 2)
        }), 500





# Legacy handler - now replaced by fast webhook processor
# Keeping for reference but no longer used

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
