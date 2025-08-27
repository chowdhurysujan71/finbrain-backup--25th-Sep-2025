import os
import sys
import logging

# Configure logging before importing app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Phase 4: Limited Production - Enable actual transaction creation
os.environ['PCA_MODE'] = 'ON'

try:
    logger.info("Starting FinBrain application initialization...")
    from app import app
    logger.info("✓ Flask application imported successfully")
    
    # Verify the app is properly configured
    if not app:
        logger.error("Flask app instance is None")
        sys.exit(1)
    
    # Test database connection on startup
    with app.app_context():
        from app import db
        try:
            db.session.execute(db.text('SELECT 1'))
            logger.info("✓ Database connection verified")
        except Exception as e:
            logger.error(f"✗ Database connection failed: {str(e)}")
            sys.exit(1)
    
    logger.info("✓ FinBrain application ready for deployment")
    
except ImportError as e:
    logger.error(f"✗ Failed to import app module: {str(e)}")
    sys.exit(1)
except Exception as e:
    logger.error(f"✗ Application initialization failed: {str(e)}")
    sys.exit(1)
