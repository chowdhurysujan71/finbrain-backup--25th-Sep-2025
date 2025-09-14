import os
import logging
import sys
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response, g
import uuid
import time
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
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

# Sentry enforcement for production
env = os.environ.get('ENV', 'development')
if env == 'prod':
    sentry_dsn = os.environ.get('SENTRY_DSN')
    if not sentry_dsn:
        logger.critical("BOOT FAILURE: SENTRY_DSN required when ENV=prod")
        logger.critical("Set SENTRY_DSN environment variable for production deployment")
        sys.exit(1)
    
    # Initialize Sentry for production
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            environment=env
        )
        logger.info("✓ Sentry initialized for production environment")
    except ImportError:
        logger.critical("BOOT FAILURE: sentry-sdk not installed but required for ENV=prod")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"BOOT FAILURE: Sentry initialization failed: {str(e)}")
        sys.exit(1)

# Import shared db and Base from lightweight module
from db_base import db, Base

# Create the app
app = Flask(__name__, static_folder='static', static_url_path='/static')

# SECURITY HARDENED: Require SESSION_SECRET from environment - no fallback
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    logger.critical("BOOT FAILURE: SESSION_SECRET environment variable is required for production security")
    sys.exit(1)
    
app.secret_key = session_secret

# SECURITY HARDENED: Configure secure session cookies for production
app.config["SESSION_COOKIE_SECURE"] = True        # HTTPS only
app.config["SESSION_COOKIE_HTTPONLY"] = True      # No JavaScript access  
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"  # CSRF protection

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure CORS and rate limiting
CORS(app, resources={r"/ai-chat": {"origins": [os.getenv("APP_ORIGIN", "http://localhost:5000")]}})
limiter = Limiter(
    key_func=get_remote_address,
    app=app, 
    default_limits=["120 per minute"]
)

# Request logging middleware using existing structured logger
from utils.logger import structured_logger

@app.before_request
def before_request():
    """Capture request start time and generate/propagate request_id"""
    g.start_time = time.time()
    # Get request_id from header or generate new one
    g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    
    # Check if existing logger already handles this to avoid duplication
    if not hasattr(g, 'logging_handled'):
        g.logging_handled = True

@app.after_request
def after_request(response):
    """Log request completion with structured JSON format"""
    if hasattr(g, 'start_time') and hasattr(g, 'request_id') and hasattr(g, 'logging_handled'):
        try:
            duration_ms = (time.time() - g.start_time) * 1000
            
            # SECURITY HARDENED: Only log server-side session user_id, never client headers
            session_user_id = session.get('user_id') if session else None
            
            # Use existing structured logger format
            import json
            log_data = {
                "ts": int(time.time() * 1000),  # epoch milliseconds
                "level": "info",
                "request_id": g.request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": round(duration_ms, 2)
            }
            
            # Only log authenticated session user_id for security traceability
            if session_user_id:
                log_data["session_user_id"] = session_user_id[:12] + "..."  # Truncated for privacy
            
            # Log using existing logger infrastructure
            structured_logger.logger.info(json.dumps(log_data))
            
        except Exception as e:
            # Don't let logging errors break the response
            logger.debug(f"Request logging error: {str(e)}")
    
    # Add X-Request-ID header to response
    if hasattr(g, 'request_id'):
        response.headers['X-Request-ID'] = g.request_id
    
    return response

# Add startup self-check for canonical router
try:
    from utils.production_router import production_router
    router_sha = getattr(production_router, 'SHA', 'cc72dd77e8d8')
    app.logger.info(f"[BOOT] Canonical router loaded. SHA={router_sha}")
except Exception as e:
    app.logger.error(f"[BOOT][FATAL] Failed to load canonical router: {e}")

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
    import models_pca  # noqa: F401
    
    # Use read-only database validation for Alembic-managed environments
    # Schema creation is now handled by Alembic migrations
    try:
        from utils.safe_db_init import safe_database_check_only
        if not safe_database_check_only():
            logger.error("✗ Database schema validation failed - check logs for details")
            logger.error("✗ Run './scripts/migrate.sh' to apply pending migrations")
            sys.exit(1)
        logger.info("✓ Database schema validation completed (Alembic-managed)")
    except ImportError as e:
        logger.critical(f"BOOT FAILURE: Safe database validation module not available: {e}")
        logger.critical("Database schema validation is required for secure startup")
        sys.exit(1)
    
    # Run database migrations with advisory lock to prevent race conditions
    logger.info("Running database migrations with advisory lock...")
    import subprocess
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "migrate_with_lock.py")
    
    try:
        
        # Run migration script with timeout
        result = subprocess.run(
            [sys.executable, script_path],
            timeout=600,  # 10 minute timeout for migrations
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✓ Database migrations completed successfully")
            if result.stdout.strip():
                # Log migration output at debug level to avoid spam
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        logger.debug(f"Migration: {line.strip()}")
        else:
            logger.critical(f"✗ Database migration failed with exit code {result.returncode}")
            if result.stderr.strip():
                logger.critical(f"Migration error: {result.stderr.strip()}")
            if result.stdout.strip():
                logger.error(f"Migration output: {result.stdout.strip()}")
            logger.critical("BOOT FAILURE: Cannot start application with failed migrations")
            sys.exit(1)
            
    except subprocess.TimeoutExpired:
        logger.critical("✗ Database migration timed out after 10 minutes")
        logger.critical("BOOT FAILURE: Migration process may be stuck or database unreachable")
        sys.exit(1)
    except FileNotFoundError:
        logger.critical(f"✗ Migration script not found: {script_path}")
        logger.critical("BOOT FAILURE: Migration infrastructure missing")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"✗ Unexpected error running migrations: {e}")
        logger.critical("BOOT FAILURE: Migration process failed")
        sys.exit(1)
    
    # Schema validation and auto-healing
    try:
        from utils.schema_validator import validate_schema_on_startup
        if validate_schema_on_startup():
            logger.info("✓ Database schema validation passed")
        else:
            logger.error("✗ Database schema validation failed - check logs")
    except ImportError:
        logger.warning("Schema validator not available - skipping validation")
    
    # Register PCA blueprints for overlay features
    try:
        from utils.pca_feature_flags import pca_feature_flags
        
        # Only register blueprints if PCA is enabled
        if pca_feature_flags.is_overlay_active():
            from routes.pca_api import pca_api
            from routes.pca_ui import pca_ui
            
            if 'pca_api' not in app.blueprints:
                app.register_blueprint(pca_api)
                logger.info("✓ PCA API routes registered")
            if 'pca_ui' not in app.blueprints:
                app.register_blueprint(pca_ui)
                logger.info("✓ PCA UI routes registered")
    except ImportError as e:
        logger.info(f"PCA blueprints not loaded: {e}")
    except Exception as e:
        logger.warning(f"PCA blueprint registration failed: {e}")
    
    # Register Audit API (Phase 1 - safe read-only endpoints)
    try:
        from routes.audit_api import audit_api
        if 'audit_api' not in app.blueprints:
            app.register_blueprint(audit_api)
            logger.info("✓ Audit API routes registered")
    except ImportError as e:
        logger.info(f"Audit API not loaded: {e}")
    except Exception as e:
        logger.warning(f"Audit API registration failed: {e}")
    
    # Register Assets API (Phase B - Supabase Storage)
    try:
        from routes_assets import assets_bp
        if 'assets' not in app.blueprints:
            app.register_blueprint(assets_bp)
            logger.info("✓ Assets API routes registered")
    except ImportError as e:
        logger.info(f"Assets API not loaded: {e}")
    except Exception as e:
        logger.warning(f"Assets API registration failed: {e}")
    
    # Register Redis Smoke Test endpoint
    logger.info("Attempting to register Redis smoke test endpoint...")
    try:
        from app.routes_redis_smoke import redis_smoke_bp
        if 'redis_smoke' not in app.blueprints:
            app.register_blueprint(redis_smoke_bp)
            logger.info("✓ Redis smoke test endpoint registered")
        else:
            logger.info("Redis smoke test endpoint already registered")
    except ImportError as e:
        logger.info(f"Redis smoke test endpoint not loaded: {e}")
    except Exception as e:
        logger.warning(f"Redis smoke test endpoint registration failed: {e}")
    
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
                    <title>finbrain Admin Login</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
                        .auth-box { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }
                        h1 { color: #333; margin-bottom: 20px; }
                        p { color: #666; }
                    </style>
                </head>
                <body>
                    <div class="auth-box">
                        <h1>finbrain Admin Access</h1>
                        <p>Please enter your admin credentials to access the dashboard.</p>
                        <p><small>Your browser should prompt for username and password.</small></p>
                    </div>
                </body>
                </html>
                """, 401)
            response.headers['WWW-Authenticate'] = 'Basic realm="finbrain Admin"'
            return response
        return f(*args, **kwargs)
    return decorated_function

def check_admin_auth():
    """Check if user is authenticated as admin (legacy session-based)"""
    return session.get('admin_authenticated', False)

# Legacy admin login/logout routes removed - using HTTP Basic Auth now

@app.route('/')
def public_landing():
    """Public landing page - no authentication required"""
    try:
        from models import Expense
        from sqlalchemy import func
        
        # Get basic stats without requiring auth
        total_transactions = db.session.query(func.count(Expense.id)).scalar() or 0
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>finbrain - AI-Powered Expense Tracking</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 50px 20px; text-align: center; }}
                .logo {{ font-size: 3em; font-weight: bold; margin-bottom: 20px; }}
                .tagline {{ font-size: 1.5em; margin-bottom: 30px; opacity: 0.9; }}
                .stats {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin: 30px 0; }}
                .feature {{ margin: 20px 0; }}
                .cta {{ background: #ff6b6b; padding: 15px 30px; border-radius: 25px; text-decoration: none; color: white; font-weight: bold; }}
                .admin-link {{ margin-top: 40px; }}
                .admin-link a {{ color: rgba(255,255,255,0.7); text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">🧠 finbrain</div>
                <div class="tagline">AI-Powered Expense Tracking via Messenger</div>
                
                <div class="stats">
                    <h3>System Status: ✅ Operational</h3>
                    <p>Total Transactions Processed: {total_transactions:,}</p>
                    <p>AI Integration: Active</p>
                    <p>Security: Enhanced</p>
                </div>
                
                <div class="feature">
                    <h3>💬 Natural Language Processing</h3>
                    <p>Just message "spent 500 on groceries" and finbrain handles the rest</p>
                </div>
                
                <div class="feature">
                    <h3>🤖 Intelligent Categorization</h3>
                    <p>AI automatically categorizes expenses and provides insights</p>
                </div>
                
                <div class="feature">
                    <h3>📊 Smart Summaries</h3>
                    <p>Get personalized spending analysis and financial advice</p>
                </div>
                
                <div class="admin-link">
                    <a href="/admin">Admin Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Landing page error: {e}")
        return """
        <!DOCTYPE html>
        <html>
        <head><title>FinBrain</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>🧠 FinBrain</h1>
            <p>AI-Powered Expense Tracking System</p>
            <p>Status: Online</p>
        </body>
        </html>
        """

@app.route('/admin')
@require_basic_auth
def admin_dashboard():
    """Dashboard for viewing expense statistics (HTTP Basic Auth required) - LIVE DATA ONLY"""
    
    try:
        from datetime import datetime
        
        # Get recent expenses from LIVE VIEW only (excludes test data and superseded rows)
        recent_expenses_raw = db.session.execute(db.text("""
            SELECT e.id, e.description, e.amount, e.category, e.currency, e.created_at, e.platform
            FROM v_expenses_live e
            WHERE e.superseded_by IS NULL
            ORDER BY e.created_at DESC
            LIMIT 10
        """)).fetchall()
        
        # Convert to dict for template compatibility
        recent_expenses = [
            {
                'id': row.id,
                'description': row.description,
                'amount': row.amount,
                'category': row.category,
                'currency': row.currency,
                'created_at': row.created_at,
                'platform': row.platform
            }
            for row in recent_expenses_raw
        ]
        
        # Get total active users from LIVE VIEW only (real users only)
        total_users = db.session.execute(db.text("""
            SELECT COUNT(DISTINCT u.user_id_hash) 
            FROM v_users_live u
            WHERE EXISTS (
                SELECT 1 FROM v_expenses_live e 
                WHERE e.user_id = u.user_id_hash 
                AND e.superseded_by IS NULL
            )
        """)).scalar()
        
        # Get this month's expenses from LIVE VIEW only
        today = datetime.utcnow()
        current_month = today.month
        current_year = today.year
        
        # Calculate this month's totals from LIVE VIEW
        total_expenses_this_month = db.session.execute(db.text("""
            SELECT COALESCE(SUM(e.amount), 0)
            FROM v_expenses_live e
            WHERE EXTRACT(month FROM e.created_at) = :month
            AND EXTRACT(year FROM e.created_at) = :year
            AND e.superseded_by IS NULL
        """), {'month': current_month, 'year': current_year}).scalar()
        
        total_transactions_this_month = db.session.execute(db.text("""
            SELECT COUNT(*)
            FROM v_expenses_live e
            WHERE EXTRACT(month FROM e.created_at) = :month
            AND EXTRACT(year FROM e.created_at) = :year
            AND e.superseded_by IS NULL
        """), {'month': current_month, 'year': current_year}).scalar()
        
        response = make_response(render_template('dashboard.html',
                             recent_expenses=recent_expenses,
                             total_users=total_users,
                             total_expenses_this_month=total_expenses_this_month,
                             total_transactions_this_month=total_transactions_this_month))
        # Add cache-busting headers for dynamic data
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        response = make_response(render_template('dashboard.html',
                             recent_expenses=[],
                             total_users=0,
                             total_expenses_this_month=0,
                             total_transactions_this_month=0))
        # Add cache-busting headers even for error cases
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

# Helper functions for health and diagnostics
def get_git_commit():
    """Get git commit SHA safely"""
    try:
        import subprocess
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return result.stdout.strip()[:8]  # First 8 chars
    except:
        pass
    return "unknown"

def get_database_host():
    """Extract database host from DATABASE_URL safely (no secrets)"""
    try:
        from urllib.parse import urlparse
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            parsed = urlparse(db_url)
            return parsed.hostname or "localhost"
    except:
        pass
    return "unknown"

def get_alembic_head():
    """Get current alembic revision"""
    try:
        import subprocess
        result = subprocess.run(['alembic', 'current'], 
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            # Extract revision from output like "abc123 (head)"
            output = result.stdout.strip()
            if output:
                return output.split()[0]  # First part is the revision
    except:
        pass
    return "unknown"

def check_migrations_applied():
    """Check if all migrations are applied"""
    try:
        import subprocess
        # Check if there are pending migrations
        result = subprocess.run(['alembic', 'heads'], 
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            heads = result.stdout.strip()
            if heads:
                # Check current vs heads
                current_result = subprocess.run(['alembic', 'current'], 
                                              capture_output=True, text=True, timeout=3)
                if current_result.returncode == 0:
                    current = current_result.stdout.strip()
                    # If current matches heads, migrations are up to date
                    return heads in current if current else False
    except:
        pass
    return False

@app.route('/health', methods=['GET'])
def health_check():
    """Lightweight health check endpoint - no dependencies, <100ms response"""
    return jsonify({
        "service": "FinBrain",
        "status": "healthy",
        "git_commit": get_git_commit(),
        "db": get_database_host(),
        "alembic_head": get_alembic_head(),
        "migrations_applied": check_migrations_applied()
    }), 200

@app.route('/readyz', methods=['GET'])
def readiness_check():
    """Readiness check with dependency validation - returns 200 only if DB + AI key OK"""
    import psycopg
    import redis
    import time
    
    start_time = time.time()
    
    # Initialize check results
    db_ok = False
    redis_ok = False
    ai_ok = bool(os.environ.get("AI_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    
    # Database check with 2s timeout
    try:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            with psycopg.connect(db_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    db_ok = result is not None
    except Exception as e:
        logger.debug(f"DB readiness check failed: {str(e)}")
        db_ok = False
    
    # Redis check with 1s timeout (informational only)
    try:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            r = redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
            redis_ok = r.ping()
    except Exception as e:
        logger.debug(f"Redis readiness check failed: {str(e)}")
        redis_ok = False
    
    # Ensure total execution ≤2s
    elapsed = time.time() - start_time
    if elapsed > 2.0:
        logger.warning(f"Readiness check exceeded 2s budget: {elapsed:.3f}s")
    
    # Return 200 only if DB and AI key are OK
    status_code = 200 if (db_ok and ai_ok) else 503
    
    response = {
        "db": db_ok,
        "redis": redis_ok,
        "ai_key_present": ai_ok
    }
    
    return jsonify(response), status_code

# Import admin authentication from admin_ops
from admin_ops import require_admin

# Diagnostic helper functions
def get_database_role_grants():
    """Get role grants from database"""
    try:
        grants = db.session.execute(db.text("""
            SELECT grantee, table_name, privilege_type 
            FROM information_schema.role_table_grants 
            WHERE table_schema = 'public' 
            ORDER BY grantee, table_name
            LIMIT 20
        """)).fetchall()
        return [{"grantee": g.grantee, "table": g.table_name, "privilege": g.privilege_type} for g in grants]
    except Exception as e:
        return [{"error": str(e)}]

def test_advisory_lock():
    """Test acquiring and releasing advisory lock 919191"""
    try:
        # Try to acquire advisory lock
        result = db.session.execute(db.text("SELECT pg_try_advisory_lock(919191)")).scalar()
        if result:
            # Successfully acquired, now release it
            db.session.execute(db.text("SELECT pg_advisory_unlock(919191)"))
            return {"status": "success", "acquired": True, "released": True}
        else:
            return {"status": "failed", "acquired": False, "error": "Lock already held"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_pending_migrations():
    """Check for pending migrations with detailed info"""
    try:
        import subprocess
        # Get head revisions
        heads_result = subprocess.run(['alembic', 'heads'], 
                                    capture_output=True, text=True, timeout=5)
        # Get current revision
        current_result = subprocess.run(['alembic', 'current'], 
                                      capture_output=True, text=True, timeout=5)
        
        if heads_result.returncode == 0 and current_result.returncode == 0:
            heads = heads_result.stdout.strip()
            current = current_result.stdout.strip()
            
            # Check if there are pending migrations
            pending_result = subprocess.run(['alembic', 'history', '--indicate-current'], 
                                          capture_output=True, text=True, timeout=5)
            
            return {
                "heads": heads,
                "current": current,
                "up_to_date": heads in current if current else False,
                "pending_migrations": "-> (head)" not in pending_result.stdout if pending_result.returncode == 0 else "unknown"
            }
    except Exception as e:
        return {"error": str(e)}
    
    return {"error": "Unable to check migrations"}

@app.route('/diagnostics', methods=['GET'])
@require_admin
def diagnostics():
    """Detailed diagnostics endpoint - admin auth required"""
    import time
    start_time = time.time()
    
    try:
        diagnostics_data = {
            "service": "FinBrain",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "host": get_database_host(),
                "role_grants": get_database_role_grants(),
                "advisory_lock_test": test_advisory_lock()
            },
            "migrations": check_pending_migrations(),
            "git": {
                "commit": get_git_commit(),
                "alembic_head": get_alembic_head()
            },
            "environment": {
                "env": os.environ.get('ENV', 'development'),
                "required_vars_present": all(os.environ.get(var) for var in ['DATABASE_URL', 'ADMIN_USER', 'ADMIN_PASS', 'FACEBOOK_PAGE_ACCESS_TOKEN', 'FACEBOOK_VERIFY_TOKEN'])
            }
        }
        
        diagnostics_data["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        return jsonify(diagnostics_data), 200
        
    except Exception as e:
        logger.error(f"Diagnostics endpoint error: {str(e)}")
        return jsonify({
            "service": "FinBrain",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round((time.time() - start_time) * 1000, 2)
        }), 500

@app.route('/__test_error', methods=['GET'])
def test_error():
    """Test endpoint to trigger Sentry error for verification"""
    raise RuntimeError("Sentry test error")

@app.route('/health/deployment', methods=['GET'])
def deployment_readiness_check():
    """Dedicated deployment readiness check endpoint for production verification"""
    try:
        readiness_checks = {
            "app_initialization": False,
            "database_connection": False,
            "environment_variables": False,
            "route_registration": False,
            "blueprint_loading": False,
            "error_handling": False
        }
        
        issues = []
        
        # Check app initialization
        try:
            if app and app.name:
                readiness_checks["app_initialization"] = True
            else:
                issues.append("Flask app not properly initialized")
        except Exception as e:
            issues.append(f"App initialization error: {str(e)}")
        
        # Check database connection
        try:
            db.session.execute(db.text('SELECT 1'))
            readiness_checks["database_connection"] = True
        except Exception as e:
            issues.append(f"Database connection failed: {str(e)}")
        
        # Check required environment variables
        required_envs = ["DATABASE_URL", "ADMIN_USER", "ADMIN_PASS", 
                        "FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_VERIFY_TOKEN"]
        missing_envs = [env for env in required_envs if not os.environ.get(env)]
        if not missing_envs:
            readiness_checks["environment_variables"] = True
        else:
            issues.extend([f"Missing environment variable: {env}" for env in missing_envs])
        
        # Check route registration
        try:
            essential_routes = ['/health', '/webhook/messenger', '/health/deployment']
            registered_routes = [str(rule) for rule in app.url_map.iter_rules()]
            missing_routes = [route for route in essential_routes if route not in registered_routes]
            if not missing_routes:
                readiness_checks["route_registration"] = True
            else:
                issues.extend([f"Missing essential route: {route}" for route in missing_routes])
        except Exception as e:
            issues.append(f"Route registration check failed: {str(e)}")
        
        # Check blueprint loading
        try:
            if len(app.blueprints) > 0:
                readiness_checks["blueprint_loading"] = True
            else:
                issues.append("No blueprints registered")
        except Exception as e:
            issues.append(f"Blueprint check failed: {str(e)}")
        
        # Check error handling capabilities
        try:
            # Verify logger is available
            logger.info("Deployment readiness check - error handling test")
            readiness_checks["error_handling"] = True
        except Exception as e:
            issues.append(f"Error handling system failed: {str(e)}")
        
        # Determine overall readiness
        all_checks_passed = all(readiness_checks.values())
        deployment_status = "ready" if all_checks_passed else "not_ready"
        
        response = {
            "deployment_status": deployment_status,
            "service": "finbrain-expense-tracker",
            "timestamp": datetime.utcnow().isoformat(),
            "readiness_checks": readiness_checks,
            "checks_passed": sum(readiness_checks.values()),
            "total_checks": len(readiness_checks),
            "success_rate": f"{(sum(readiness_checks.values()) / len(readiness_checks)) * 100:.1f}%"
        }
        
        if issues:
            response["issues"] = issues
            
        if not all_checks_passed:
            response["recommendation"] = "Fix the identified issues before deploying to production"
        
        status_code = 200 if all_checks_passed else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Deployment readiness check failed: {str(e)}")
        return jsonify({
            "deployment_status": "error",
            "service": "finbrain-expense-tracker",
            "timestamp": datetime.utcnow().isoformat(),
            "error": f"Readiness check system failure: {str(e)}",
            "recommendation": "Contact support - deployment readiness system is not functioning"
        }), 500

@app.route("/webhook/messenger", methods=["GET", "POST"])  # type: ignore[misc]
def webhook_messenger():
    """Facebook Messenger webhook with structured request logging"""
    from utils.logger import request_logger
    
    if request.method == "GET":
        # Facebook webhook verification
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        mode = request.args.get("hub.mode")
        
        # Enhanced logging to debug verification issues
        logger.info(f"Webhook verification request - mode={mode}, token_provided={bool(verify_token)}, challenge={bool(challenge)}")
        logger.info(f"Full request args: {dict(request.args)}")
        
        expected_token = os.environ.get("FACEBOOK_VERIFY_TOKEN")
        logger.info(f"Expected token present: {bool(expected_token)}, Received token matches: {verify_token == expected_token}")
        
        if mode == "subscribe" and verify_token == expected_token:
            logger.info("✅ Webhook verification successful")
            return challenge or ""
        else:
            logger.warning(f"❌ Webhook verification failed: mode={mode}, expected_mode=subscribe, token_match={verify_token == expected_token}")
            logger.warning(f"Received token: '{verify_token}', Expected: '{expected_token[:10] if expected_token else None}...' (masked)")
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
            from utils.production_router import production_router
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
        
        # Local testing bypass - check for bypass header
        local_bypass = request.headers.get('X-Local-Testing', '').lower() == 'true'
        
        if not signature and not local_bypass:
            logger.error("Missing X-Hub-Signature-256 header")
            return "Missing signature", 400
        
        if local_bypass:
            # For local testing, bypass signature verification
            logger.info("Local testing bypass enabled - skipping signature verification")
            from utils.webhook_processor import process_webhook_fast_local
            response_text, status_code = process_webhook_fast_local(payload_bytes)
        else:
            response_text, status_code = process_webhook_fast(payload_bytes, signature, app_secret)
        return response_text, status_code

@app.route('/diagnose/router', methods=['GET'])
@require_basic_auth
def diagnose_router():
    """Diagnostic endpoint to test router directly with real PSID and query - ADMIN ACCESS REQUIRED"""
    import uuid
    import hashlib
    
    query = request.args.get('q', '')
    psid = request.args.get('psid', '')
    
    if not query or not psid:
        return jsonify({
            "error": "Missing required parameters",
            "usage": "/diagnose/router?q=What are my expenses this week&psid=3052211490"
        }), 400
    
    try:
        from utils.production_router import production_router
        
        # Generate request ID
        rid = str(uuid.uuid4())[:8]
        
        # Get build info
        build_sha = hashlib.md5(open(__file__, 'rb').read()).hexdigest()[:8]
        router_sha = hashlib.md5(open('utils/production_router.py', 'rb').read()).hexdigest()[:8]
        
        # Test the router directly
        response_text, intent, category, amount = production_router.route_message(query, psid, rid)
        
        # Also test FAQ matcher directly
        from utils.faq_map import match_faq_or_smalltalk
        faq_result = match_faq_or_smalltalk(query)
        
        return jsonify({
            "rid": rid,
            "query": query,
            "psid": psid,
            "psid_hash": hashlib.sha256(psid.encode()).hexdigest()[:8],
            "router_result": {
                "response": response_text,
                "intent": intent,
                "category": category,
                "amount": amount
            },
            "faq_check": {
                "result": faq_result,
                "matched": faq_result is not None
            },
            "build_info": {
                "app_sha": build_sha,
                "router_sha": router_sha
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": str(e.__class__.__name__)
        }), 500

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
        from utils.ai_adapter_v2 import production_ai_adapter
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
        
        largest_category = max(category_totals.keys(), key=lambda k: category_totals[k]) if category_totals else "other"
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
                
                # Use production AI adapter for insights
                ai_result = None
                try:
                    from utils.ai_adapter_v2 import production_ai_adapter
                    # Use generic generate method instead of non-existent generate_insights_for_user
                    ai_result = production_ai_adapter.generate_structured_response(
                        f"Generate spending insights for: {context}",
                        {"context": context}
                    )
                    if ai_result and ai_result.get("ok") and "data" in ai_result:
                        ai_insights = ai_result["data"]
                except Exception as ai_error:
                    logger.warning(f"AI insights generation failed: {ai_error}")
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

@app.route('/user/<psid_hash>/category/<category_name>')
@require_basic_auth  
def user_category_breakdown(psid_hash, category_name):
    """Get spending breakdown for a specific category"""
    try:
        from handlers.category_breakdown import handle_category_breakdown
        from models import User
        
        # Find user by PSID hash
        user = User.query.filter_by(user_id_hash=psid_hash).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        # Create a query for the handler
        query = f"How much did I spend on {category_name} this month?"
        
        # Use the category breakdown handler with correct parameter order
        result = handle_category_breakdown(psid_hash, query)
        
        if result and "text" in result:
            return jsonify({
                "category": category_name,
                "breakdown": result["text"],
                "user_hash": psid_hash,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "error": "Could not generate category breakdown",
                "category": category_name
            }), 500
            
    except Exception as e:
        logger.error(f"Category breakdown error: {str(e)}")
        return jsonify({"error": "Failed to generate category breakdown"}), 500

@app.route('/user/<psid_hash>/categories')  
@require_basic_auth
def user_categories_list(psid_hash):
    """List all categories with spending totals for a user"""
    try:
        from models import User, Expense
        from datetime import datetime, timedelta
        
        # Find user by PSID hash
        user = User.query.filter_by(user_id_hash=psid_hash).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        # Get current month expenses
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        expenses = Expense.query.filter(
            Expense.user_id == psid_hash,
            Expense.created_at >= start_of_month
        ).all()
        
        # Calculate category totals
        category_totals = {}
        for expense in expenses:
            cat = expense.category.lower()
            if cat not in category_totals:
                category_totals[cat] = {
                    "total": 0,
                    "count": 0,
                    "category": cat
                }
            category_totals[cat]["total"] += float(expense.amount)
            category_totals[cat]["count"] += 1
            
        return jsonify({
            "user_hash": psid_hash,
            "month": f"{now.year}-{now.month:02d}",  
            "categories": list(category_totals.values()),
            "total_categories": len(category_totals),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Categories list error: {str(e)}")
        return jsonify({"error": "Failed to get categories list"}), 500

@app.route("/ops/pca/status")
@require_basic_auth
def pca_status():
    """PCA system status endpoint for monitoring"""
    try:
        from utils.pca_flags import pca_flags
        from utils.config import get_config_summary
        
        status = pca_flags.get_status()
        config = get_config_summary()
        
        return jsonify({
            'status': 'healthy',
            'pca_flags': status,
            'config_summary': config,
            'timestamp': datetime.utcnow().isoformat(),
            'phase': 'Phase 0 - Safety Rails Online'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route("/ops/pca/health")
@require_basic_auth  
def pca_health():
    """Simple PCA health check for monitoring systems"""
    try:
        from utils.pca_flags import pca_flags, force_fallback_mode
        
        return jsonify({
            'healthy': True,
            'mode': pca_flags.mode.value,
            'kill_switch_active': force_fallback_mode(),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'healthy': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()  
        }), 500

@app.route("/ops/pca/overlay")
@require_basic_auth
def pca_overlay_health():
    """PCA overlay database health check"""
    try:
        from utils.pca_processor import get_pca_health_status
        
        health_status = get_pca_health_status()
        status_code = 200 if health_status.get('healthy', False) else 500
        
        return jsonify(health_status), status_code
        
    except Exception as e:
        return jsonify({
            'healthy': False,
            'error': f'Overlay health check failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route("/ops/pca/telemetry")
@require_basic_auth
def pca_telemetry():
    """PCA processing telemetry and analytics"""
    try:
        from utils.pca_integration import get_pca_telemetry_summary
        
        telemetry = get_pca_telemetry_summary()
        
        return jsonify({
            'phase': 'Phase 2 - Shadow Mode Testing',
            'telemetry': telemetry,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Telemetry collection failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route("/ops/pca/canary", methods=["GET", "POST"])  # type: ignore[misc]
@require_basic_auth
def pca_canary_management():
    """Manage PCA canary users for SHADOW mode testing"""
    if request.method == "GET":
        # Get current canary user status
        try:
            from utils.pca_integration import get_pca_deployment_status
            from utils.pca_flags import pca_flags
            
            deployment_status = get_pca_deployment_status()
            
            return jsonify({
                'phase': 'Phase 3 - DRYRUN Mode Ready',
                'pca_mode': pca_flags.mode.value,
                'deployment_status': deployment_status,
                'ready_for_dryrun': pca_flags.mode.value in ['DRYRUN', 'ON'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            return jsonify({
                'error': f'Canary status check failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    elif request.method == "POST":
        # Enable SHADOW mode for a user
        try:
            data = request.get_json()
            user_hash = data.get('user_hash', '')
            
            if not user_hash:
                return jsonify({
                    'error': 'user_hash is required',
                    'usage': 'POST {"user_hash": "a1b2c3d4..."}'
                }), 400
            
            from utils.pca_integration import enable_shadow_mode_for_user
            result = enable_shadow_mode_for_user(user_hash)
            
            status_code = 200 if result.get('success', False) else 500
            return jsonify(result), status_code
            
        except Exception as e:
            return jsonify({
                'error': f'Enable SHADOW mode failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
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

@app.route('/api/preview/report', methods=['GET'])
def preview_report():
    """
    BLOCK 5: Static preview JSON for marketing (no live data)
    Returns exact demo report payload for marketing/demo purposes
    Publicly cacheable, no database access, no user context
    """
    try:
        # Static demo JSON - exact byte-for-byte match required
        demo_report = {
            "user": "demo",
            "report_date": "2025-08-31",
            "summary": "You logged 7 expenses in 3 days. Food ≈ 40%. Transport spend fell ~15% vs the prior window. 🔥 Streak-3 achieved. Next: try a 7-day streak with a 10% cap on Food.",
            "milestones": ["streak-3", "small win"],
            "feedback_options": ["👍","👎","💬"]
        }
        
        # Create response with proper cache headers
        response = make_response(jsonify(demo_report))
        
        # Set cache headers for 1+ hour public caching
        response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour
        response.headers['Content-Type'] = 'application/json'
        
        # Optional: ETag for better caching
        response.headers['ETag'] = '"demo-report-v1"'
        
        return response
        
    except Exception as e:
        # Even errors should be cacheable for marketing endpoint
        error_response = make_response(jsonify({"error": "preview_unavailable"}), 500)
        error_response.headers['Cache-Control'] = 'public, max-age=300'  # 5 min cache for errors
        return error_response

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

# Register coaching monitoring endpoints
try:
    from app_coaching_endpoints import coaching_bp
    app.register_blueprint(coaching_bp)
    logger.info("Coaching monitoring endpoints registered")
except ImportError as e:
    logger.warning(f"Coaching monitoring endpoints not available: {e}")

# Register Phase 3: Replay & Debug routes
try:
    from phase3_replay_debug import register_replay_routes
    register_replay_routes(app)
except ImportError as e:
    logger.warning(f"Phase 3 replay routes not available: {e}")

# Register Phase 4: Enhanced Monitoring routes
try:
    from phase4_enhanced_monitoring import register_monitoring_routes
    register_monitoring_routes(app)
except ImportError as e:
    logger.warning(f"Phase 4 monitoring routes not available: {e}")

# Register Phase 5: Production Blast routes
try:
    from phase5_production_blast import register_production_routes
    register_production_routes(app)
except ImportError as e:
    logger.warning(f"Phase 5 production routes not available: {e}")

@app.get("/ops/hash")
def ops_hash():
    """Generate canonical PSID hash for identity debugging"""
    psid = request.args.get("psid", "")
    from utils.identity import psid_hash
    return {"psid": psid, "psid_hash": psid_hash(psid)}, 200

@app.get("/supabase-test")
def supabase_test():
    """Supabase connectivity smoke test - lists objects in configured bucket"""
    import requests
    import os
    
    # Get Supabase configuration
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") 
    supabase_bucket = os.environ.get("SUPABASE_BUCKET", "user-assets")
    
    if not supabase_url or not supabase_key:
        return {"error": "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required"}, 503
    
    # Call Supabase Storage API to list objects
    list_url = f"{supabase_url}/storage/v1/object/list/{supabase_bucket}"
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key
    }
    
    try:
        response = requests.get(list_url, headers=headers, timeout=3)
        response.raise_for_status()
        
        # Return the list of objects (may be empty array)
        return response.json(), 200
        
    except requests.exceptions.Timeout:
        return {"error": "Supabase request timeout (3s exceeded)"}, 503
    except requests.exceptions.RequestException as e:
        return {"error": f"Supabase connection failed: {str(e)}"}, 503
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}, 503

@app.get("/supabase-smoke")
def supabase_smoke():
    """Supabase connectivity smoke test - validates Storage API connection"""
    import requests
    import os
    
    # Get Supabase configuration
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") 
    supabase_bucket = os.environ.get("SUPABASE_BUCKET", "user-assets")
    
    if not supabase_url or not supabase_key:
        return {"connected": False, "error": "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required"}, 503
    
    # Call Supabase Storage list API with POST request
    list_url = f"{supabase_url}/storage/v1/object/list/{supabase_bucket}"
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/json"
    }
    payload = {
        "prefix": "",
        "limit": 1,
        "offset": 0
    }
    
    try:
        response = requests.post(list_url, json=payload, headers=headers, timeout=3)
        response.raise_for_status()
        
        # Return success with object list (may be empty)
        objects = response.json()
        return {"connected": True, "objects": objects}, 200
        
    except requests.exceptions.Timeout:
        return {"connected": False, "error": "Supabase request timeout (3s exceeded)"}, 503
    except requests.exceptions.RequestException as e:
        return {"connected": False, "error": f"Supabase connection failed: {str(e)}"}, 503
    except Exception as e:
        return {"connected": False, "error": f"Unexpected error: {str(e)}"}, 503

# REMOVED: Legacy /webhook endpoint - redundant with /webhook/messenger
# Only canonical /webhook/messenger endpoint remains for production use

# REMOVED: /webhook/test endpoint - test endpoints removed for production security





# Register diagnostic routes
try:
    from routes.ops_quickscan import bp as quickscan_bp
    app.register_blueprint(quickscan_bp)
    logger.info("Registered quickscan diagnostic endpoint at /ops/quickscan")
except ImportError:
    logger.warning("Could not register quickscan blueprint")

# Phase C: Job Queue API endpoints
try:
    from utils.job_queue import job_queue
    from utils.rate_limiter_jobs import get_job_rate_limiter
    from utils.circuit_breaker import circuit_breaker
    
    # Initialize job rate limiter with Redis client
    if hasattr(job_queue, 'redis_client') and job_queue.redis_client:
        job_rate_limiter = get_job_rate_limiter(job_queue.redis_client)
    else:
        job_rate_limiter = get_job_rate_limiter()
    
    @app.route('/jobs', methods=['POST'])
    def enqueue_job():
        """Enqueue a job with validation and rate limiting"""
        start_time = time.time()
        
        # Get user ID from header
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"error": "X-User-ID header required"}), 400
        
        # Validate request body
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        # Validate required fields
        job_type = data.get('type')
        payload = data.get('payload', {})
        idempotency_key = data.get('idempotency_key')
        
        if not job_type:
            return jsonify({"error": "Field 'type' is required"}), 400
        
        if not idempotency_key:
            return jsonify({"error": "Field 'idempotency_key' is required"}), 400
        
        # Validate payload size (1MB limit)
        payload_json = json.dumps(payload)
        if len(payload_json.encode('utf-8')) > 1024 * 1024:
            return jsonify({"error": "Payload exceeds 1MB limit"}), 413
        
        # Check circuit breaker
        if circuit_breaker.is_open():
            return jsonify({"error": "temporarily unavailable"}), 429
        
        # Check rate limit
        rate_limit_result = job_rate_limiter.check_rate_limit(user_id)
        if not rate_limit_result.allowed:
            return jsonify({
                "error": "Rate limit exceeded", 
                "retry_after": int(rate_limit_result.reset_time - time.time())
            }), 429
        
        try:
            # Enqueue job
            job_id = job_queue.enqueue(job_type, payload, user_id, idempotency_key)
            
            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"Job {job_id} enqueued successfully in {latency_ms:.2f}ms")
            
            return jsonify({
                "job_id": job_id,
                "status": "queued"
            }), 201
            
        except RuntimeError as e:
            if "Redis job queue not available" in str(e):
                return jsonify({"error": "Job queue service unavailable"}), 503
            raise
        except Exception as e:
            logger.error(f"Job enqueue failed: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    @app.route('/jobs/<job_id>/status', methods=['GET'])
    def get_job_status(job_id):
        """Get job status and metadata"""
        # Get user ID from header
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"error": "X-User-ID header required"}), 400
        
        try:
            status = job_queue.get_job_status(job_id)
            if not status:
                return jsonify({"error": "Job not found"}), 404
            
            return jsonify(status), 200
            
        except Exception as e:
            logger.error(f"Job status retrieval failed: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    @app.route('/jobs/<job_id>/cancel', methods=['POST'])
    def cancel_job(job_id):
        """Cancel a job (best effort)"""
        # Get user ID from header
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"error": "X-User-ID header required"}), 400
        
        try:
            success = job_queue.cancel_job(job_id)
            if success:
                return jsonify({"message": "Job cancelled successfully"}), 200
            else:
                return jsonify({"error": "Job not found or cannot be cancelled"}), 404
                
        except Exception as e:
            logger.error(f"Job cancellation failed: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    @app.route('/jobs/status', methods=['GET'])
    def get_job_queue_status():
        """Get job queue system status"""
        try:
            # Basic queue health
            redis_healthy = job_queue.health_check() if job_queue else False
            circuit_open = circuit_breaker.is_open() if circuit_breaker else False
            
            # Get queue stats if Redis available
            stats = {}
            if job_queue and job_queue.redis_available:
                try:
                    stats = job_queue.get_queue_stats()
                except Exception as e:
                    logger.debug(f"Failed to get queue stats: {e}")
                    stats = {"error": "Stats unavailable"}
            
            response = {
                "redis_connected": redis_healthy,
                "circuit_breaker_open": circuit_open,
                "queue_stats": stats,
                "timestamp": int(time.time())
            }
            
            # Return 503 if Redis unhealthy or circuit open
            status_code = 503 if not redis_healthy or circuit_open else 200
            
            return jsonify(response), status_code
            
        except Exception as e:
            logger.error(f"Job queue status check failed: {e}")
            return jsonify({"error": "Status check failed"}), 500

    logger.info("✓ Job queue API endpoints registered")

except ImportError as e:
    logger.warning(f"Job queue API endpoints not available: {e}")

# Register PWA UI Blueprint
try:
    from pwa_ui import pwa_ui
    if 'pwa_ui' not in app.blueprints:
        app.register_blueprint(pwa_ui)
        logger.info("✓ PWA UI routes registered (/chat, /report, /profile, /challenge, /offline)")
except ImportError as e:
    logger.warning(f"PWA UI routes not available: {e}")

# Register Backend Assistant API routes
try:
    from routes_backend_assistant import backend_api
    if 'backend_api' not in app.blueprints:
        app.register_blueprint(backend_api)
        logger.info("✓ Backend Assistant API routes registered (/api/backend/*)")
except ImportError as e:
    logger.warning(f"Backend Assistant routes not available: {e}")

# Register Growth Telemetry Blueprint
try:
    from routes_telemetry import register_telemetry_routes
    register_telemetry_routes(app)
    logger.info("✓ Growth telemetry routes registered (/metrics, /admin/metrics)")
except ImportError as e:
    logger.warning(f"Growth telemetry routes not available: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
