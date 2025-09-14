#!/usr/bin/env python3
"""
Migration script with PostgreSQL advisory lock to prevent race conditions.
Ensures only one process can run migrations at a time during concurrent startup.
"""

import os
import sys
import logging
import time
import subprocess
from typing import Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Advisory lock ID for migrations - use a unique number
MIGRATION_LOCK_ID = 919191

class MigrationLockError(Exception):
    """Raised when migration lock operations fail"""
    pass

class AdvisoryLockManager:
    """Manages PostgreSQL advisory locks for migration coordination"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection: Optional[psycopg2.extensions.connection] = None
        self.lock_acquired = False
    
    def connect(self) -> None:
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(self.database_url)
            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("✓ Connected to PostgreSQL for migration lock")
        except Exception as e:
            raise MigrationLockError(f"Failed to connect to database: {e}")
    
    def acquire_lock(self, timeout_seconds: int = 300) -> bool:
        """
        Acquire advisory lock with timeout.
        Returns True if lock acquired, False if timeout.
        """
        if not self.connection:
            raise MigrationLockError("Not connected to database")
        
        start_time = time.time()
        
        while True:
            try:
                with self.connection.cursor() as cursor:
                    # Try to acquire lock without blocking
                    cursor.execute("SELECT pg_try_advisory_lock(%s);", (MIGRATION_LOCK_ID,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        self.lock_acquired = True
                        logger.info(f"✓ Acquired migration advisory lock ({MIGRATION_LOCK_ID})")
                        return True
                    
                    # Check timeout
                    elapsed = time.time() - start_time
                    if elapsed >= timeout_seconds:
                        logger.error(f"✗ Timeout waiting for migration lock after {elapsed:.1f}s")
                        return False
                    
                    # Log that we're waiting and sleep
                    if elapsed > 5:  # Only log after 5 seconds to avoid spam
                        logger.info("waiting for migration lock...")
                    
                    time.sleep(1)
                    
            except Exception as e:
                raise MigrationLockError(f"Failed to acquire advisory lock: {e}")
    
    def release_lock(self) -> None:
        """Release the advisory lock"""
        if not self.connection or not self.lock_acquired:
            return
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s);", (MIGRATION_LOCK_ID,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    logger.info(f"✓ Released migration advisory lock ({MIGRATION_LOCK_ID})")
                else:
                    logger.warning(f"Advisory lock ({MIGRATION_LOCK_ID}) was not held by this session")
                
                self.lock_acquired = False
                
        except Exception as e:
            logger.error(f"Error releasing advisory lock: {e}")
    
    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            try:
                self.connection.close()
                logger.debug("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_lock()
        self.close()

def run_alembic_upgrade() -> bool:
    """
    Run alembic upgrade head command.
    Returns True if successful, False otherwise.
    """
    try:
        logger.info("Running alembic upgrade head...")
        
        # Change to project root directory for alembic
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout for migrations
        )
        
        if result.returncode == 0:
            logger.info("✓ Alembic migration completed successfully")
            if result.stdout.strip():
                logger.info(f"Alembic output: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"✗ Alembic migration failed with exit code {result.returncode}")
            if result.stderr.strip():
                logger.error(f"Alembic error: {result.stderr.strip()}")
            if result.stdout.strip():
                logger.error(f"Alembic output: {result.stdout.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("✗ Alembic migration timed out after 120 seconds")
        return False
    except Exception as e:
        logger.error(f"✗ Error running alembic migration: {e}")
        return False

def main() -> int:
    """
    Main migration function with advisory lock.
    Returns 0 on success, non-zero on failure.
    """
    # Validate environment
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.critical("DATABASE_URL environment variable is required")
        return 1
    
    logger.info("=== MIGRATION WITH ADVISORY LOCK ===")
    
    try:
        with AdvisoryLockManager(database_url) as lock_manager:
            # Try to acquire lock with 5 minute timeout
            if not lock_manager.acquire_lock(timeout_seconds=300):
                logger.critical("Failed to acquire migration lock within timeout")
                logger.critical("Another migration process may be stuck or taking too long")
                return 1
            
            # Run migrations while holding the lock
            if run_alembic_upgrade():
                logger.info("✓ Migration completed successfully")
                return 0
            else:
                logger.error("✗ Migration failed")
                return 1
                
    except MigrationLockError as e:
        logger.critical(f"Migration lock error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
        return 1
    except Exception as e:
        logger.critical(f"Unexpected error during migration: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)