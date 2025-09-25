"""
Database Schema Validator - Prevents schema drift by validating expected columns
"""
import logging

from sqlalchemy import text

from db_base import db

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Validates that database schema matches application expectations"""
    
    REQUIRED_COLUMNS = {
        'expenses': {
            'user_id_hash': 'character varying',
            'amount': 'numeric', 
            'category': 'character varying',
            'created_at': 'timestamp without time zone'
        },
        'users': {
            'user_id_hash': 'character varying',
            'platform': 'character varying',
            'created_at': 'timestamp without time zone'
        }
    }
    
    def __init__(self):
        self.validation_errors = []
    
    def validate_all_tables(self) -> bool:
        """Validate all critical tables have required columns"""
        self.validation_errors = []
        
        for table_name, required_cols in self.REQUIRED_COLUMNS.items():
            if not self._validate_table(table_name, required_cols):
                return False
        
        logger.info("Schema validation passed - all tables have required columns")
        return True
    
    def _validate_table(self, table_name: str, required_columns: dict) -> bool:
        """Validate a specific table has all required columns"""
        try:
            # Get actual table columns from database
            result = db.session.execute(text(
                """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = :table_name
                """
            ), {'table_name': table_name}).fetchall()
            
            actual_columns = {row[0]: row[1] for row in result}
            
            # Check each required column exists
            for col_name, expected_type in required_columns.items():
                if col_name not in actual_columns:
                    error = f"CRITICAL: Table '{table_name}' missing required column '{col_name}'"
                    self.validation_errors.append(error)
                    logger.error(error)
                    return False
                
                # Optional: validate data type matches
                actual_type = actual_columns[col_name]
                if expected_type not in actual_type:
                    warning = f"WARNING: Table '{table_name}' column '{col_name}' type mismatch: expected {expected_type}, got {actual_type}"
                    logger.warning(warning)
            
            logger.debug(f"Table '{table_name}' validation passed")
            return True
            
        except Exception as e:
            error = f"Schema validation failed for table '{table_name}': {e}"
            self.validation_errors.append(error)
            logger.error(error)
            return False
    
    def get_validation_errors(self) -> list:
        """Get list of validation errors"""
        return self.validation_errors
    
    def auto_fix_missing_columns(self) -> bool:
        """Attempt to auto-fix missing critical columns"""
        try:
            # Check if expenses.user_id_hash is missing
            result = db.session.execute(text(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'expenses' AND column_name = 'user_id_hash'
                """
            )).fetchone()
            
            if not result:
                logger.info("Auto-fixing: Adding user_id_hash column to expenses table")
                
                # Add the missing column
                db.session.execute(text("ALTER TABLE expenses ADD COLUMN user_id_hash VARCHAR(255)"))
                
                # Populate with user_id values
                db.session.execute(text("UPDATE expenses SET user_id_hash = user_id WHERE user_id_hash IS NULL"))
                
                # Create index for performance
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_expenses_user_id_hash ON expenses(user_id_hash)"))
                
                db.session.commit()
                logger.info("Auto-fix completed successfully")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Auto-fix failed: {e}")
            db.session.rollback()
            return False

# Global validator instance
schema_validator = SchemaValidator()

def validate_schema_on_startup():
    """Run schema validation during application startup"""
    try:
        if not schema_validator.validate_all_tables():
            logger.error("Schema validation failed - attempting auto-fix")
            if schema_validator.auto_fix_missing_columns():
                logger.info("Auto-fix successful - re-validating schema")
                return schema_validator.validate_all_tables()
            else:
                logger.error("Auto-fix failed - manual intervention required")
                return False
        return True
    except Exception as e:
        logger.error(f"Schema validation startup check failed: {e}")
        return False