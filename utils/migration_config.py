"""
Shared migration configuration constants.

This module centralizes all migration-related configuration to prevent
drift between migration scripts and ensure consistency across the system.
"""

import os
from typing import Optional

# Advisory lock ID for migration coordination
# This MUST be the same across all migration scripts to prevent race conditions
MIGRATION_ADVISORY_LOCK_ID = 919191

# Migration timeouts (seconds)
MIGRATION_LOCK_TIMEOUT = 300  # 5 minutes
MIGRATION_COMMAND_TIMEOUT = 120  # 2 minutes

# Migration directories and paths
MIGRATION_BACKUP_DIR = "migration_backups"

def get_safe_database_info(database_url: str) -> str:
    """
    Extract safe database connection information for logging.
    
    This function extracts only non-sensitive information from the DATABASE_URL:
    - Database name
    - Host (if not localhost)
    - Port (if not default)
    
    SECURITY: This function explicitly excludes usernames, passwords, and
    connection parameters that could contain sensitive information.
    
    Args:
        database_url: The full database URL
        
    Returns:
        str: Safe connection info for logging (format: "database@host:port")
        
    Examples:
        >>> get_safe_database_info("postgresql://user:pass@localhost:5432/mydb")
        "mydb@localhost:5432"
        
        >>> get_safe_database_info("postgresql://user:pass@prod-db.example.com/app_db")
        "app_db@prod-db.example.com"
    """
    try:
        from urllib.parse import urlparse
        
        parsed = urlparse(database_url)
        
        # Extract safe components
        database = parsed.path.lstrip('/') if parsed.path else 'unknown'
        host = parsed.hostname or 'unknown'
        port = parsed.port
        
        # Build safe connection string
        if port and port != 5432:  # Only include port if non-default
            return f"{database}@{host}:{port}"
        else:
            return f"{database}@{host}"
            
    except Exception:
        # If parsing fails, return generic info
        return "database@unknown_host"

def get_migration_lock_id() -> int:
    """
    Get the migration advisory lock ID.
    
    This can be overridden via environment variable for testing,
    but defaults to the standard production lock ID.
    
    Returns:
        int: The advisory lock ID to use for migration coordination
    """
    env_lock_id = os.environ.get('MIGRATION_ADVISORY_LOCK_ID')
    if env_lock_id:
        try:
            return int(env_lock_id)
        except ValueError:
            # Invalid environment variable, use default
            pass
    
    return MIGRATION_ADVISORY_LOCK_ID

def get_migration_backup_dir() -> str:
    """
    Get the directory for migration backups.
    
    Returns:
        str: Path to migration backup directory
    """
    project_root = os.environ.get('PROJECT_ROOT', os.getcwd())
    return os.path.join(project_root, MIGRATION_BACKUP_DIR)

# Export commonly used values for easy importing
__all__ = [
    'MIGRATION_ADVISORY_LOCK_ID',
    'MIGRATION_LOCK_TIMEOUT', 
    'MIGRATION_COMMAND_TIMEOUT',
    'MIGRATION_BACKUP_DIR',
    'get_safe_database_info',
    'get_migration_lock_id',
    'get_migration_backup_dir'
]