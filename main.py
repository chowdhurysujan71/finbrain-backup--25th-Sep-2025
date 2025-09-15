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
        from db_base import db
        try:
            db.session.execute(db.text('SELECT 1'))
            logger.info("✓ Database connection verified")
            
            # ARCHITECT RECOMMENDED: Verify users table has auth columns
            result = db.session.execute(db.text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name IN ('email', 'password_hash', 'name')
                ORDER BY column_name
            """))
            auth_columns = [row[0] for row in result.fetchall()]
            logger.info(f"✓ Users table auth columns found: {auth_columns}")
            
            required_auth_columns = ['email', 'name', 'password_hash']
            missing_columns = [col for col in required_auth_columns if col not in auth_columns]
            if missing_columns:
                logger.error(f"✗ CRITICAL: Missing auth columns in users table: {missing_columns}")
                logger.error("This explains the 500 errors! Auth columns missing from database.")
                # Don't exit - let it run but log the issue
            else:
                logger.info("✓ All required auth columns present in users table")
                
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
