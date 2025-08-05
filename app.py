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
app = Flask(__name__)
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
        "platform_support": ["whatsapp", "facebook_messenger"]
    })

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Unified webhook for WhatsApp and Facebook Messenger"""
    try:
        if request.method == 'GET':
            # Facebook webhook verification
            return handle_facebook_verification(request)
        
        elif request.method == 'POST':
            # Detect platform based on content type
            content_type = request.content_type
            
            if 'application/x-www-form-urlencoded' in content_type:
                # WhatsApp via Twilio (form data)
                logger.debug("Processing WhatsApp message")
                return handle_whatsapp_request(request)
            
            elif 'application/json' in content_type:
                # Facebook Messenger (JSON)
                logger.debug("Processing Facebook Messenger message")
                return handle_facebook_request(request)
            
            else:
                logger.warning(f"Unknown content type: {content_type}")
                return jsonify({"error": "Unsupported content type"}), 400
                
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        # Always return 200 to prevent platform retries
        return jsonify({"status": "error", "message": "Internal error"}), 200

def handle_facebook_verification(request):
    """Handle Facebook webhook verification"""
    try:
        verify_token = os.environ.get("FACEBOOK_VERIFY_TOKEN", "default_verify_token")
        
        if request.args.get('hub.verify_token') == verify_token:
            return request.args.get('hub.challenge')
        else:
            logger.warning("Facebook verification failed - invalid token")
            return "Verification failed", 403
            
    except Exception as e:
        logger.error(f"Facebook verification error: {str(e)}")
        return "Verification failed", 403

def handle_whatsapp_request(request):
    """Handle WhatsApp message processing with rate limiting"""
    try:
        # Extract message data
        from_number = request.form.get('From', '')
        message_body = request.form.get('Body', '')
        message_sid = request.form.get('SmsMessageSid', '')
        
        if not from_number or not message_body:
            logger.warning("Missing WhatsApp message data")
            return "", 200
        
        # Check rate limits
        from utils.rate_limiter import check_rate_limit
        if not check_rate_limit(from_number, 'whatsapp'):
            logger.warning(f"Rate limit exceeded for WhatsApp user: {from_number}")
            return "", 200
        
        # Process the message
        from utils.whatsapp_handler import handle_whatsapp_message
        response = handle_whatsapp_message(from_number, message_body, message_sid)
        
        return response, 200
        
    except Exception as e:
        logger.error(f"WhatsApp processing error: {str(e)}")
        return "", 200

def handle_facebook_request(request):
    """Handle Facebook Messenger message processing with rate limiting"""
    try:
        data = request.get_json()
        
        if not data or data.get('object') != 'page':
            logger.warning("Invalid Facebook webhook data")
            return jsonify({"status": "ok"}), 200
        
        for entry in data.get('entry', []):
            for messaging in entry.get('messaging', []):
                sender_id = messaging.get('sender', {}).get('id')
                message = messaging.get('message', {})
                message_text = message.get('text', '')
                
                if sender_id and message_text:
                    # Check rate limits
                    from utils.rate_limiter import check_rate_limit
                    if not check_rate_limit(sender_id, 'facebook'):
                        logger.warning(f"Rate limit exceeded for Facebook user: {sender_id}")
                        continue
                    
                    # Process the message
                    from utils.facebook_handler import handle_facebook_message
                    handle_facebook_message(sender_id, message_text)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Facebook processing error: {str(e)}")
        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
