"""
Alembic Revision Checker
Provides functions to check if the database is at the current Alembic migration head
"""

import logging
import os
import sys
from typing import Optional, Tuple
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

def get_alembic_current_revision(database_url: str) -> Optional[str]:
    """
    Get the current Alembic revision from the database
    Returns None if unable to determine
    """
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """))
            
            row = result.fetchone()
            if not row or not row[0]:
                logger.warning("Alembic version table does not exist - database not initialized with Alembic")
                return None
            
            # Get current revision
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1;"))
            row = result.fetchone()
            
            if row:
                current_revision = row[0]
                logger.debug(f"Current database revision: {current_revision}")
                return current_revision
            else:
                logger.warning("No revision found in alembic_version table")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get current Alembic revision: {e}")
        return None

def get_alembic_head_revision() -> Optional[str]:
    """
    Get the head revision from Alembic configuration
    Returns None if unable to determine
    """
    try:
        # Add project root to path for Alembic imports
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        # Load Alembic config
        alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        
        # Get head revision
        head_revision = script_dir.get_current_head()
        logger.debug(f"Head revision from Alembic: {head_revision}")
        return head_revision
        
    except Exception as e:
        logger.error(f"Failed to get Alembic head revision: {e}")
        return None

def check_alembic_revision_status(database_url: str) -> Tuple[bool, str]:
    """
    Check if database is at the current Alembic head revision
    
    Returns:
        Tuple of (is_current, status_message)
    """
    logger.info("Checking Alembic revision status...")
    
    current_revision = get_alembic_current_revision(database_url)
    head_revision = get_alembic_head_revision()
    
    if current_revision is None:
        return False, "Unable to determine current database revision - Alembic not initialized"
    
    if head_revision is None:
        return False, "Unable to determine head revision from Alembic configuration"
    
    if current_revision == head_revision:
        logger.info(f"✓ Database is at current revision: {current_revision}")
        return True, f"Database at head revision: {current_revision}"
    else:
        logger.error(f"✗ Database revision mismatch - Current: {current_revision}, Head: {head_revision}")
        return False, f"Database revision mismatch - Current: {current_revision}, Head: {head_revision}"

def verify_alembic_status_or_fail(database_url: str) -> None:
    """
    Verify Alembic status and exit application if not at head revision
    Used during application startup to enforce schema consistency
    """
    is_current, status_message = check_alembic_revision_status(database_url)
    
    if not is_current:
        logger.critical(f"ALEMBIC REVISION CHECK FAILED: {status_message}")
        logger.critical("Database schema is not at the required revision")
        logger.critical("Run './scripts/migrate.sh' to apply pending migrations")
        logger.critical("Refusing to start application with outdated database schema")
        sys.exit(1)
    
    logger.info(f"✓ Alembic revision check passed: {status_message}")