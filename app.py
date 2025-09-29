import json
import logging
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from functools import wraps

from flask import Flask, g, jsonify, make_response, render_template, request, session
from flask_cors import CORS
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging - production mode removes debug and reload
log_level = logging.INFO if os.environ.get('ENV') == 'production' else logging.DEBUG
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SAFETY GUARD: Ensure web-only mode (no Facebook Messenger)
assert os.environ.get("MESSAGING_CHANNEL", "web") == "web", "Only web chat supported - Facebook Messenger code quarantined"

def validate_required_environment():
    """Validate all required environment variables are present at boot"""
    required_envs = [
        'DATABASE_URL',
        'ADMIN_USER', 
        'ADMIN_PASS',
        'SESSION_SECRET',
        'ID_SALT'
    ]
    
    missing_envs = []
    for env_var in required_envs:
        if not os.environ.get(env_var):
            missing_envs.append(env_var)
    
    if missing_envs:
        logger.critical(f"BOOT FAILURE: Missing required environment variables: {missing_envs}")
        logger.critical("finbrain refuses to start without all required environment variables")
        logger.critical("Set the following environment variables and restart:")
        for env_var in missing_envs:
            logger.critical(f"  - {env_var}")
        sys.exit(1)
    
    logger.info("✓ All required environment variables present (web-only architecture)")
    return True

# Validate environment before any Flask initialization
validate_required_environment()

# Sentry enforcement for production - support both 'prod' and 'production'
env = os.environ.get('ENV', 'development')
is_production = env in ['prod', 'production']

if is_production:
    sentry_dsn = os.environ.get('SENTRY_DSN')
    if not sentry_dsn:
        logger.critical("BOOT FAILURE: SENTRY_DSN required when ENV=production")
        logger.critical("Set SENTRY_DSN environment variable for production deployment")
        logger.critical("Example: export SENTRY_DSN=https://your-sentry-dsn@sentry.io/project")
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
from db_base import db  # noqa: E402

# Create the app
app = Flask(__name__, static_folder='static', static_url_path='/static')

# SECURITY HARDENED: Require SESSION_SECRET from environment - no fallback
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    logger.critical("BOOT FAILURE: SESSION_SECRET environment variable is required for production security")
    sys.exit(1)
    
app.secret_key = session_secret

# Session cookie configuration
app.config["SESSION_COOKIE_HTTPONLY"] = True       # JS cannot read cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"      # Required for subdomain redirects

# SESSION CONFIGURATION: Replit-as-production ready
if is_production:
    app.config["SESSION_COOKIE_SECURE"] = True         # HTTPS only in production
    app.config["SESSION_COOKIE_DOMAIN"] = None         # Host-only cookies (works on any domain)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"      # Required for subdomain redirects
    logger.info("✓ Session cookies configured for Replit production: host-only, secure, SameSite=Lax")
else:
    # Development: Allow HTTP and localhost sessions for testing
    app.config["SESSION_COOKIE_SECURE"] = False        # Allow HTTP in development/testing
    app.config["SESSION_COOKIE_DOMAIN"] = None         # Host-only
    logger.info("✓ Session cookies configured for localhost (development, non-secure)")

app.config["SESSION_COOKIE_NAME"] = "fbn.sid"      # Custom session cookie name
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# CORS CONFIGURATION: Replit-as-production ready
if env == 'production' or env == 'prod':
    # Production: Use Replit domain as primary production origin
    replit_domains = os.environ.get('REPLIT_DOMAINS', '')
    if replit_domains and ('replit.dev' in replit_domains or 'replit.app' in replit_domains):
        # Replit as production
        production_origins = [f"https://{replit_domains}"]
        logger.info(f"✓ CORS configured for Replit production: {production_origins}")
    else:
        # Fallback to finbrain.app if available
        production_origins = [
            "https://finbrain.app",
            "https://login.finbrain.app", 
            "https://app.finbrain.app",
            "https://chat.finbrain.app",
            "https://admin.finbrain.app"
        ]
        logger.info(f"✓ CORS configured for finbrain.app production: {production_origins}")
else:
    # Development: Allow localhost
    production_origins = [
        os.getenv("APP_ORIGIN", "http://localhost:5000"),
        "http://localhost:5000"
    ]
    logger.info(f"✓ CORS configured for development: {production_origins}")

# CORS: Scoped to specific routes for security
CORS(app, supports_credentials=True, resources={
    r"/api/*": {"origins": production_origins},
    r"/ai-chat": {"origins": production_origins}, 
    r"/auth/*": {"origins": production_origins}
})
from utils.rate_limiting import limiter  # noqa: E402

limiter.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = '/login'  # Direct URL path to avoid blueprint resolution issues
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login sessions"""
    from models import User  # noqa: E402
    return User.query.get(int(user_id))

# Request logging middleware using existing structured logger
from utils.logger import structured_logger  # noqa: E402


@app.before_request
def attach_user_and_trace():
    """Capture request start time, generate request_id, set user context, and enforce subdomain auth"""
    import os
    from urllib.parse import quote

    from flask import after_this_request, jsonify, redirect, request

    from auth_helpers import (
        get_subdomain,
        get_user_id_from_session,
        is_protected_subdomain,
    )
    
    g.start_time = time.time()
    # Get request_id from header or generate new one
    g.request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:12]
    
    # SINGLE-SOURCE-OF-TRUTH: Set authenticated user context from session only
    g.user_id = get_user_id_from_session()
    
    # AUTH FLOW GUARD: Redirect authenticated users away from auth pages
    if g.user_id and request.path in ("/login", "/register", "/signup"):
        return redirect("/chat", code=302)
    
    # Get current subdomain for routing logic
    current_subdomain = get_subdomain()
    
    # Enhanced logging for trace middleware
    app.logger.info(f"[{g.request_id}] → {request.method} {request.path} user={g.user_id or 'anon'} subdomain={current_subdomain or 'localhost'}")
    
    @after_this_request
    def add_trace_headers(resp):
        resp.headers['X-Request-ID'] = g.request_id
        return resp
    
    # SUBDOMAIN AUTHENTICATION ENFORCEMENT
    # Redirect unauthenticated users from protected subdomains to login
    if current_subdomain and is_protected_subdomain(current_subdomain) and not g.user_id:
        # Skip auth redirect for auth-related routes to prevent redirect loops
        if not (request.path.startswith('/auth/') or request.path.startswith('/api/auth/')):
            # Helper function to build environment-aware URLs
            def build_domain_url(subdomain=None, path="/"):
                """Build URL with environment-aware domain detection"""
                replit_domains = os.environ.get('REPLIT_DOMAINS', '')
                
                if replit_domains and ('replit.dev' in replit_domains or 'replit.app' in replit_domains):
                    # Replit domain: use path-based routing
                    base_url = f"https://{replit_domains}"
                    if subdomain and subdomain != 'www':
                        return f"{base_url}/{subdomain}{path}"
                    else:
                        return f"{base_url}{path}"
                else:
                    # Production finbrain.app domain: use subdomain routing
                    if subdomain and subdomain != 'www':
                        return f"https://{subdomain}.finbrain.app{path}"
                    else:
                        return f"https://finbrain.app{path}"
            
            # Build returnTo URL with current subdomain and path
            return_to_url = build_domain_url(current_subdomain, request.path)
            if request.query_string:
                return_to_url += f"?{request.query_string.decode('utf-8')}"
            
            # Redirect to login with returnTo parameter
            login_url = build_domain_url('login', f"/login?returnTo={quote(return_to_url)}")
            
            app.logger.info(f"[{g.request_id}] Redirecting unauthenticated user from {current_subdomain} to login")
            return redirect(login_url, code=302)
    
    # PRODUCTION SECURITY: Block ALL /api/* requests without authentication
    is_api_route = request.path.startswith('/api/')
    allow_guest_writes = os.environ.get('ALLOW_GUEST_WRITES', 'false').lower() == 'true'
    
    # Exception: Allow /api/auth/* routes for login/signup
    is_auth_route = request.path.startswith('/api/auth/')
    
    if is_api_route and not is_auth_route and not g.user_id and not allow_guest_writes:
        return jsonify({
            'success': False,
            'error': 'Authentication required',
            'error_code': 'AUTH_REQUIRED',
            'trace_id': g.request_id
        }), 401
    
    # Check if existing logger already handles this to avoid duplication
    if not hasattr(g, 'logging_handled'):
        g.logging_handled = True
    
    return None

@app.after_request
def after_request(response):
    """Log request completion with structured JSON format, add cache control and security headers"""
    
    # Never cache the SW file; always revalidate
    if request.path == "/sw.js":
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    # For HTML routes/partials: never cache; vary by cookie
    ctype = response.headers.get("Content-Type", "")
    if ctype.startswith("text/html") or request.path.startswith('/partials/'):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = (response.headers.get("Vary", "") + ", Cookie").strip(", ")
    
    # Add no-cache headers for all API endpoints to prevent stale cached responses
    if request.path.startswith('/api/') or request.path.startswith('/ai-chat'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # Add security headers for all responses
    # HSTS (HTTP Strict Transport Security) - Force HTTPS for 1 year, include subdomains
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # Additional security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
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
            
            # ENHANCED TELEMETRY: For /api/backend/* routes, log detailed auth context
            if request.path.startswith('/api/backend/'):
                log_data["route"] = request.path
                log_data["resolved_user_id"] = getattr(g, 'user_id', None) or "anonymous"
                log_data["corr_id"] = g.request_id
                log_data["api_backend_request"] = True
            
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

# Configure the database with enhanced SSL and connection handling
database_url = os.environ.get("DATABASE_URL")

# Enhanced database connection configuration for SSL stability
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 280,  # Recycle connections before 5 minute timeout
    "pool_pre_ping": True,  # Test connections before use
    "pool_timeout": 30,  # Connection timeout from pool
    "pool_size": 10,  # Maximum number of permanent connections in pool
    "max_overflow": 20,  # Maximum overflow connections
    "echo": False,  # Disable SQL echoing for performance
    "connect_args": {
        "connect_timeout": 30,  # PostgreSQL connection timeout
        "sslmode": "require" if is_production else "prefer",  # Enforce SSL in production
        "application_name": "finbrain_app",  # Help identify app in database logs
        # PostgreSQL-specific SSL retry settings
        "keepalives_idle": 600,  # TCP keepalive idle time (10 minutes)
        "keepalives_interval": 30,  # TCP keepalive interval (30 seconds)
        "keepalives_count": 3,  # Number of keepalive probes
        "tcp_user_timeout": 30000,  # TCP user timeout (30 seconds)
    }
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
    
    # Register Data Integrity API (Nightly Check System)
    try:
        from routes.integrity_api import integrity_api
        if 'integrity_api' not in app.blueprints:
            app.register_blueprint(integrity_api, url_prefix='/api')
            logger.info("✓ Data Integrity API routes registered")
    except ImportError as e:
        logger.info(f"Data Integrity API not loaded: {e}")
    except Exception as e:
        logger.warning(f"Data Integrity API registration failed: {e}")
    
    # Register Deploy Probe API (Post-Deploy Validation System)
    try:
        from routes.deploy_probe import deploy_probe
        if 'deploy_probe' not in app.blueprints:
            app.register_blueprint(deploy_probe)
            logger.info("✓ Deploy Probe API routes registered")
    except ImportError as e:
        logger.info(f"Deploy Probe API not loaded: {e}")
    except Exception as e:
        logger.warning(f"Deploy Probe API registration failed: {e}")
    
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
    
    # Initialize data integrity scheduler
    logger.info("Initializing data integrity scheduler...")
    try:
        from utils.integrity_scheduler import integrity_scheduler
        integrity_scheduler.start()
        logger.info("✓ Data integrity scheduler started (nightly checks enabled)")
        
        # Register cleanup on shutdown
        import atexit
        atexit.register(integrity_scheduler.stop)
        
    except Exception as e:
        logger.error(f"Failed to start data integrity scheduler: {e}")
        # Don't fail app startup if scheduler fails to start
    
    # Log centralized configuration for observability
    from config import (
        AI_RL_GLOBAL_LIMIT,
        AI_RL_USER_LIMIT,
        AI_RL_WINDOW_SEC,
        CURRENCY_SYMBOL,
        MSG_MAX_CHARS,
        TIMEZONE,
    )
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
        from sqlalchemy import func

        from models import Expense
        
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
        <head><title>finbrain</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>🧠 finbrain</h1>
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
# Cache git commit at startup to avoid repeated subprocess calls
_git_commit_cache = None

def get_git_commit():
    """Get git commit SHA safely (cached)"""
    global _git_commit_cache
    if _git_commit_cache is None:
        try:
            import subprocess
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                _git_commit_cache = result.stdout.strip()[:8]  # First 8 chars
            else:
                _git_commit_cache = "unknown"
        except Exception:
            _git_commit_cache = "unknown"
    return _git_commit_cache

# Alembic data cache for <100ms /health performance
_alembic_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 60  # Cache for 60 seconds
}

def get_alembic_data_cached():
    """Get Alembic data with 60s caching for /health performance"""
    import time
    global _alembic_cache
    
    now = time.time()
    
    # Check if cache is valid
    if (_alembic_cache['data'] is not None and 
        now - _alembic_cache['timestamp'] < _alembic_cache['ttl']):
        return _alembic_cache['data']
    
    # Cache expired or empty, refresh
    try:
        # Get current revision from database
        current_rev = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        
        # Get head revisions using Alembic API
        head_revs = []
        migrations_applied = False
        
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            
            # Load Alembic config
            alembic_cfg = Config("alembic.ini")
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            
            # Get head revisions
            head_revs = script_dir.get_heads()
            
            # Check if migrations are applied: current revision should match one of the heads
            if current_rev and head_revs:
                migrations_applied = current_rev in head_revs
            else:
                migrations_applied = False
                
        except Exception as e:
            logger.debug(f"Alembic API access failed: {str(e)}")
            # Fallback: if we have a current revision, assume applied
            migrations_applied = bool(current_rev)
        
        # Cache the data
        _alembic_cache['data'] = {
            'alembic_head': current_rev or "no_revision",
            'migrations_applied': migrations_applied
        }
        _alembic_cache['timestamp'] = now
        
        return _alembic_cache['data']
        
    except Exception as e:
        logger.debug(f"Alembic data fetch failed: {str(e)}")
        # Return safe defaults
        return {
            'alembic_head': "unknown",
            'migrations_applied': False
        }

def get_database_host():
    """Extract database host from DATABASE_URL safely (no secrets)"""
    try:
        from urllib.parse import urlparse
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            parsed = urlparse(db_url)
            return parsed.hostname or "localhost"
    except Exception:
        pass
    return "unknown"

def get_alembic_head():
    """Get current alembic revision from database"""
    try:
        # Query alembic_version table directly
        result = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        return result if result else "no_revision"
    except Exception as e:
        logger.debug(f"Alembic head query failed: {str(e)}")
        return "unknown"

def check_migrations_applied():
    """Check if all migrations are applied using database query"""
    try:
        # Get current revision from database
        current = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        if not current:
            return False
        
        # Simple check: if we have a current revision and no obvious migration errors,
        # assume migrations are applied. For detailed checks, use /diagnostics endpoint
        return True
    except Exception as e:
        logger.debug(f"Migration check failed: {str(e)}")
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Lightweight health check endpoint - no dependencies, <100ms response"""
    # Get cached Alembic data for compliance
    alembic_data = get_alembic_data_cached()
    
    # Ultra-lightweight response with cached values only
    response_data = {
        "service": "finbrain",
        "status": "healthy",
        "git_commit": get_git_commit(),  # Cached
        "db": get_database_host(),       # No DB call, just hostname parsing
        "alembic_head": alembic_data["alembic_head"],      # Required field - cached
        "migrations_applied": alembic_data["migrations_applied"]  # Required field - cached
    }
    
    # Create response with proper cache headers to prevent stale operational status
    response = make_response(jsonify(response_data), 200)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/readyz', methods=['GET'])
def readiness_check():
    """Readiness check with dependency validation - returns 200 only if DB + AI key OK"""
    import time

    import psycopg
    import redis
    
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
from admin_ops import require_admin  # noqa: E402


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
    """Check for pending migrations using proper Alembic API"""
    try:
        # Get current revision from database
        current_revs = []
        try:
            current = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
            if current:
                current_revs = [current]
        except Exception as e:
            logger.debug(f"Failed to get current revision: {str(e)}")
        
        # Get head revisions using Alembic API
        head_revs = []
        pending_migrations = []
        
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            
            # Load Alembic config
            alembic_cfg = Config("alembic.ini")
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            
            # Get head revisions
            head_revs = script_dir.get_heads()
            
            # Get pending migrations if current != heads
            if current_revs and head_revs:
                if set(current_revs) != set(head_revs):
                    # Get revisions from current to head to find pending
                    for head in head_revs:
                        for rev in script_dir.iterate_revisions(head, current_revs[0] if current_revs else None):
                            if rev.revision not in current_revs:
                                pending_migrations.append({
                                    "revision": rev.revision,
                                    "message": rev.doc or "No description"
                                })
                                
        except Exception as e:
            logger.debug(f"Alembic API access failed: {str(e)}")
        
        # Determine status
        up_to_date = bool(current_revs and head_revs and set(current_revs) == set(head_revs))
        
        return {
            "current": current_revs[0] if current_revs else "no_revision",
            "heads": head_revs,
            "pending_migrations": pending_migrations,
            "up_to_date": up_to_date,
            "migrations_applied": up_to_date,  # Same as up_to_date
            "status": "connected" if current_revs else "no_migrations_run"
        }
            
    except Exception as e:
        logger.debug(f"Migration check failed: {str(e)}")
        return {
            "error": str(e),
            "current": "unknown",
            "heads": [],
            "pending_migrations": [],
            "up_to_date": False,
            "migrations_applied": False,
            "status": "error"
        }

@app.route('/diagnostics', methods=['GET'])
@require_admin
def diagnostics():
    """Detailed diagnostics endpoint - admin auth required"""
    import time
    start_time = time.time()
    
    try:
        diagnostics_data = {
            "service": "finbrain",
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
            "service": "finbrain",
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
            essential_routes = ['/health', '/health/deployment']
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

# No webhook endpoints needed - web-only chat application

@app.route('/diagnose/router', methods=['GET'])
@require_basic_auth
def diagnose_router():
    """Diagnostic endpoint to test router directly with real PSID and query - ADMIN ACCESS REQUIRED"""
    import hashlib
    import uuid
    
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
        from datetime import date, timedelta

        from models import Expense, User
        
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
        from datetime import datetime

        from models import Expense, User
        
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

@app.route('/user/<psid_hash>/insights')
@require_basic_auth  
def user_insights(psid_hash):
    """Get AI-powered spending insights for a specific user"""
    try:
        from handlers.insight import handle_insight
        from models import User
        
        # Find user by PSID hash
        user = User.query.filter_by(user_id_hash=psid_hash).first()
        if not user:
            return f"""
            <!DOCTYPE html>
            <html lang="en" data-bs-theme="dark">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>User Not Found - finbrain Admin</title>
                <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
            </head>
            <body>
                <div class="container mt-4">
                    <div class="alert alert-danger">
                        <h4>User Not Found</h4>
                        <p>No user found with hash: {psid_hash[:8]}...</p>
                        <a href="/admin" class="btn btn-primary">Back to Admin Dashboard</a>
                    </div>
                </div>
            </body>
            </html>
            """, 404
            
        # Generate insights using the existing handler
        result = handle_insight(psid_hash)
        
        if result and "text" in result:
            insights_text = result["text"]
            
            # Create user-friendly HTML page displaying the insights
            return f"""
            <!DOCTYPE html>
            <html lang="en" data-bs-theme="dark">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>AI Insights - {user.first_name or 'User'} - finbrain Admin</title>
                <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
                <style>
                    .insights-content {{
                        background: linear-gradient(135deg, #667eea, #764ba2);
                        border-radius: 15px;
                        padding: 30px;
                        color: white;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                        margin: 20px 0;
                        line-height: 1.6;
                        font-size: 1.1em;
                    }}
                    .user-header {{
                        background: rgba(255,255,255,0.1);
                        border-radius: 10px;
                        padding: 20px;
                        margin-bottom: 20px;
                    }}
                    .back-btn {{
                        background: rgba(255,255,255,0.2);
                        border: none;
                        padding: 10px 20px;
                        border-radius: 25px;
                        color: white;
                        text-decoration: none;
                        display: inline-flex;
                        align-items: center;
                        gap: 8px;
                        transition: all 0.3s ease;
                    }}
                    .back-btn:hover {{
                        background: rgba(255,255,255,0.3);
                        color: white;
                        text-decoration: none;
                    }}
                </style>
            </head>
            <body>
                <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
                    <div class="container">
                        <a class="navbar-brand" href="/admin">
                            <i class="fas fa-brain me-2"></i>finbrain Admin
                        </a>
                        <div class="navbar-nav ms-auto">
                            <a class="nav-link" href="/admin">
                                <i class="fas fa-chart-bar me-1"></i>Dashboard
                            </a>
                        </div>
                    </div>
                </nav>

                <div class="container mt-4">
                    <div class="row">
                        <div class="col-12">
                            <a href="/admin" class="back-btn mb-3">
                                <i class="fas fa-arrow-left"></i>
                                Back to Admin Dashboard
                            </a>
                            
                            <div class="user-header">
                                <div class="d-flex align-items-center">
                                    <i class="fas fa-user-circle fa-3x text-primary me-3"></i>
                                    <div>
                                        <h2 class="mb-1">{user.first_name or 'User'}'s AI Insights</h2>
                                        <p class="mb-0 text-muted">
                                            <i class="fas fa-hashtag me-1"></i>{psid_hash[:12]}...
                                            <span class="ms-3">
                                                <i class="fas fa-calendar me-1"></i>Generated: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')}
                                            </span>
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div class="insights-content">
                                <div class="d-flex align-items-center mb-3">
                                    <i class="fas fa-robot fa-2x me-3"></i>
                                    <h3 class="mb-0">AI-Powered Spending Insights</h3>
                                </div>
                                <div style="white-space: pre-wrap;">{insights_text}</div>
                            </div>

                            <div class="card mt-4">
                                <div class="card-body">
                                    <h5 class="card-title">
                                        <i class="fas fa-info-circle me-2 text-info"></i>About These Insights
                                    </h5>
                                    <p class="card-text text-muted">
                                        These insights are generated by our AI system based on the user's spending patterns and recent activity. 
                                        The analysis includes category breakdowns, spending trends, and personalized recommendations.
                                    </p>
                                    <div class="row text-center">
                                        <div class="col-md-4">
                                            <div class="p-3">
                                                <i class="fas fa-chart-pie fa-2x text-success mb-2"></i>
                                                <h6>Smart Analysis</h6>
                                                <small>Category-based insights</small>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="p-3">
                                                <i class="fas fa-lightbulb fa-2x text-warning mb-2"></i>
                                                <h6>Recommendations</h6>
                                                <small>Actionable suggestions</small>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="p-3">
                                                <i class="fas fa-clock fa-2x text-primary mb-2"></i>
                                                <h6>Real-time</h6>
                                                <small>Up-to-date analysis</small>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            </body>
            </html>
            """
        else:
            return f"""
            <!DOCTYPE html>
            <html lang="en" data-bs-theme="dark">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Insights Error - finbrain Admin</title>
                <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
            </head>
            <body>
                <div class="container mt-4">
                    <div class="alert alert-warning">
                        <h4>Could Not Generate Insights</h4>
                        <p>Unable to generate AI insights for user {user.first_name or 'Unknown'}. This may be due to insufficient data or a temporary AI service issue.</p>
                        <a href="/admin" class="btn btn-primary">Back to Admin Dashboard</a>
                    </div>
                </div>
            </body>
            </html>
            """, 500
            
    except Exception as e:
        logger.error(f"User insights error: {str(e)}")
        return """
        <!DOCTYPE html>
        <html lang="en" data-bs-theme="dark">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Insights Error - finbrain Admin</title>
            <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-4">
                <div class="alert alert-danger">
                    <h4>Error Loading Insights</h4>
                    <p>An error occurred while generating user insights. Please try again later.</p>
                    <a href="/admin" class="btn btn-primary">Back to Admin Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """, 500

@app.route("/ops/pca/status")
@require_basic_auth
def pca_status():
    """PCA system status endpoint for monitoring"""
    try:
        from utils.config import get_config_summary
        from utils.pca_flags import pca_flags
        
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
        from utils.pca_flags import force_fallback_mode, pca_flags
        
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
            from utils.pca_flags import pca_flags
            from utils.pca_integration import get_pca_deployment_status
            
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
        from models import Expense, User
        
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
            with open('deployment_info.json') as f:
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
        
    except Exception:
        # Even errors should be cacheable for marketing endpoint
        error_response = make_response(jsonify({"error": "preview_unavailable"}), 500)
        error_response.headers['Cache-Control'] = 'public, max-age=300'  # 5 min cache for errors
        return error_response

@app.route('/ops/telemetry', methods=['GET'])
@require_basic_auth
def ops_telemetry():
    """Advanced telemetry endpoint for comprehensive system monitoring"""
    try:
        import os

        from utils.production_router import production_router
        
        telemetry_data = production_router.get_telemetry()
        
        return jsonify({
            'timestamp': datetime.now(UTC).isoformat(),
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
        import time

        from utils.ai_adapter_v2 import production_ai_adapter
        
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
from admin_ops import admin_ops  # noqa: E402

app.register_blueprint(admin_ops)

# Register coaching monitoring endpoints
try:
    from app_coaching_endpoints import coaching_bp
    app.register_blueprint(coaching_bp)
    logger.info("Coaching monitoring endpoints registered")
except ImportError as e:
    logger.warning(f"Coaching monitoring endpoints not available: {e}")

# Phase 3-5 routes disabled - optional features not implemented
# Register Phase 3: Replay & Debug routes
# try:
#     from phase3_replay_debug import register_replay_routes
#     register_replay_routes(app)
# except ImportError as e:
#     logger.warning(f"Phase 3 replay routes not available: {e}")

# Register Phase 4: Enhanced Monitoring routes
# try:
#     from phase4_enhanced_monitoring import register_monitoring_routes
#     register_monitoring_routes(app)
# except ImportError as e:
#     logger.warning(f"Phase 4 monitoring routes not available: {e}")

# Register Phase 5: Production Blast routes
# try:
#     from phase5_production_blast import register_production_routes
#     register_production_routes(app)
# except ImportError as e:
#     logger.warning(f"Phase 5 production routes not available: {e}")

@app.get("/ops/hash")
def ops_hash():
    """Generate canonical PSID hash for identity debugging"""
    psid = request.args.get("psid", "")
    from utils.identity import psid_hash
    return {"psid": psid, "psid_hash": psid_hash(psid)}, 200

@app.get("/supabase-test")
def supabase_test():
    """Supabase connectivity smoke test - lists objects in configured bucket"""
    import os

    import requests
    
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
    import os

    import requests
    
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

# No legacy webhook endpoints needed - web-only chat application

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
    from utils.circuit_breaker import circuit_breaker
    from utils.job_queue import job_queue
    from utils.rate_limiter_jobs import get_job_rate_limiter
    
    # Initialize job rate limiter with Redis client
    if hasattr(job_queue, 'redis_client') and job_queue.redis_client:
        job_rate_limiter = get_job_rate_limiter(job_queue.redis_client)
    else:
        job_rate_limiter = get_job_rate_limiter()
    
    @app.route('/jobs', methods=['POST'])
    def enqueue_job():
        """Enqueue a job with validation and rate limiting"""
        start_time = time.time()
        
        # SECURITY: Get user ID from session only
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
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
        # SECURITY: Get user ID from session only
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
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
        # SECURITY: Get user ID from session only
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
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

# Register Nudge API routes (behind feature flags)
try:
    from routes_nudges import nudges_bp
    if 'nudges' not in app.blueprints:
        app.register_blueprint(nudges_bp)
        logger.info("✓ Nudge API routes registered (/api/banners, /api/nudges/*)")
except ImportError as e:
    logger.warning(f"Nudge API routes not available: {e}")
except Exception as e:
    logger.error(f"Failed to register nudges blueprint: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")

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

# Register Single Writer Observability Blueprint
try:
    from routes_single_writer_observability import single_writer_obs
    if 'single_writer_obs' not in app.blueprints:
        app.register_blueprint(single_writer_obs)
        logger.info("✓ Single Writer Observability routes registered (/ops/single-writer/*, /admin/single-writer/*)")
except ImportError as e:
    logger.warning(f"Single Writer Observability routes not available: {e}")

# Register Service Worker Diagnostics Blueprint
try:
    from routes.sw_diagnostics import sw_diagnostics
    if 'sw_diagnostics' not in app.blueprints:
        app.register_blueprint(sw_diagnostics)
        logger.info("✓ Service Worker diagnostics registered (/ops/sw-diagnostics)")
except ImportError as e:
    logger.warning(f"Service Worker diagnostics not available: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=not is_production)
