import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost/finbrain")
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

@app.route('/')
def dashboard():
    """Dashboard for viewing expense statistics"""
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
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        database_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        database_status = "disconnected"
    
    return jsonify({
        "status": "healthy",
        "service": "finbrain-expense-tracker",
        "database": database_status,
        "platform_support": ["facebook_messenger"]
    })

@app.route("/webhook/messenger", methods=["GET", "POST"])
def webhook_messenger():
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
        app_secret = os.environ.get('FACEBOOK_APP_SECRET', '')
        
        # Process with fast handler
        response_text, status_code = process_webhook_fast(payload_bytes, signature, app_secret)
        return response_text, status_code





# Legacy handler - now replaced by fast webhook processor
# Keeping for reference but no longer used

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
