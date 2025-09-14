"""
Migration helpers for safe concurrent index operations in Alembic.

This module provides utility functions for creating database indexes safely
in production environments using PostgreSQL's CONCURRENTLY option.

Key principles:
- Never wrap concurrent operations in transactions
- Use IF NOT EXISTS for idempotent operations
- Provide graceful error handling
- Support both creation and replacement patterns
"""

import logging
from typing import List, Optional, Dict, Any
from alembic import op
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, InternalError, OperationalError, DatabaseError

logger = logging.getLogger(__name__)

class ConcurrentIndexError(Exception):
    """Raised when concurrent index operations fail"""
    pass

def create_index_concurrently(
    index_name: str,
    table_name: str,
    columns: List[str],
    where_clause: Optional[str] = None,
    unique: bool = False,
    if_not_exists: bool = True,
    index_type: str = "btree"
) -> bool:
    """
    Create an index using CONCURRENTLY to avoid table locks.
    
    Args:
        index_name: Name of the index to create
        table_name: Target table name
        columns: List of column names for the index
        where_clause: Optional WHERE clause for partial indexes
        unique: Whether to create a unique index
        if_not_exists: Use IF NOT EXISTS for idempotent creation
        index_type: Index type (btree, gin, gist, etc.)
    
    Returns:
        bool: True if index was created/exists, False if creation failed
    
    Example:
        create_index_concurrently(
            "ix_expenses_user_created",
            "expenses",
            ["user_id", "created_at DESC"],
            where_clause="superseded_by IS NULL"
        )
    """
    try:
        # Check if running inside a transaction
        if _is_in_transaction():
            logger.warning(
                f"Cannot create index {index_name} concurrently inside transaction. "
                "Consider using configure_alembic_for_concurrent() in env.py"
            )
            return False
        
        # Build the CREATE INDEX statement
        unique_clause = "UNIQUE " if unique else ""
        if_not_exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        columns_str = ", ".join(columns)
        where_clause_str = f" WHERE {where_clause}" if where_clause else ""
        
        sql = f"""
        CREATE {unique_clause}INDEX CONCURRENTLY {if_not_exists_clause}{index_name}
        ON {table_name} USING {index_type} ({columns_str}){where_clause_str}
        """
        
        logger.info(f"Creating index concurrently: {index_name}")
        logger.debug(f"SQL: {sql.strip()}")
        
        op.execute(text(sql))
        logger.info(f"✓ Index {index_name} created successfully")
        return True
        
    except ProgrammingError as e:
        error_msg = str(e).lower()
        
        # Handle "already exists" case gracefully
        if "already exists" in error_msg and if_not_exists:
            logger.info(f"✓ Index {index_name} already exists")
            return True
        
        # Handle concurrent creation conflicts
        if "deadlock detected" in error_msg or "lock timeout" in error_msg:
            logger.warning(f"⚠ Concurrent conflict creating {index_name}: {e}")
            return False
        
        logger.error(f"✗ Failed to create index {index_name}: {e}")
        raise ConcurrentIndexError(f"Failed to create index {index_name}: {e}")
    
    except Exception as e:
        logger.error(f"✗ Unexpected error creating index {index_name}: {e}")
        raise ConcurrentIndexError(f"Unexpected error creating index {index_name}: {e}")

def drop_index_concurrently(
    index_name: str,
    if_exists: bool = True
) -> bool:
    """
    Drop an index using CONCURRENTLY to avoid table locks.
    
    Args:
        index_name: Name of the index to drop
        if_exists: Use IF EXISTS for idempotent dropping
    
    Returns:
        bool: True if index was dropped/doesn't exist, False if drop failed
    """
    try:
        if _is_in_transaction():
            logger.warning(
                f"Cannot drop index {index_name} concurrently inside transaction. "
                "Consider using configure_alembic_for_concurrent() in env.py"
            )
            return False
        
        if_exists_clause = "IF EXISTS " if if_exists else ""
        sql = f"DROP INDEX CONCURRENTLY {if_exists_clause}{index_name}"
        
        logger.info(f"Dropping index concurrently: {index_name}")
        logger.debug(f"SQL: {sql}")
        
        op.execute(text(sql))
        logger.info(f"✓ Index {index_name} dropped successfully")
        return True
        
    except ProgrammingError as e:
        error_msg = str(e).lower()
        
        # Handle "does not exist" case gracefully
        if "does not exist" in error_msg and if_exists:
            logger.info(f"✓ Index {index_name} does not exist")
            return True
        
        logger.error(f"✗ Failed to drop index {index_name}: {e}")
        raise ConcurrentIndexError(f"Failed to drop index {index_name}: {e}")
    
    except Exception as e:
        logger.error(f"✗ Unexpected error dropping index {index_name}: {e}")
        raise ConcurrentIndexError(f"Unexpected error dropping index {index_name}: {e}")

def replace_index_concurrently(
    old_index_name: str,
    new_index_name: str,
    table_name: str,
    columns: List[str],
    where_clause: Optional[str] = None,
    unique: bool = False,
    index_type: str = "btree"
) -> bool:
    """
    Replace an existing index with a new one using concurrent operations.
    
    This performs the safe replacement pattern:
    1. Create new index concurrently
    2. Drop old index concurrently
    
    Args:
        old_index_name: Name of the existing index to replace
        new_index_name: Name of the new index to create
        table_name: Target table name
        columns: List of column names for the new index
        where_clause: Optional WHERE clause for partial indexes
        unique: Whether to create a unique index
        index_type: Index type (btree, gin, gist, etc.)
    
    Returns:
        bool: True if replacement successful, False otherwise
    """
    logger.info(f"Replacing index {old_index_name} with {new_index_name}")
    
    # Step 1: Create new index
    if not create_index_concurrently(
        new_index_name, table_name, columns, where_clause, unique, True, index_type
    ):
        logger.error(f"✗ Failed to create new index {new_index_name}")
        return False
    
    # Step 2: Drop old index
    if not drop_index_concurrently(old_index_name, if_exists=True):
        logger.warning(f"⚠ Failed to drop old index {old_index_name}, but new index exists")
        # Don't fail the migration - new index is in place
    
    logger.info(f"✓ Index replacement complete: {old_index_name} → {new_index_name}")
    return True

def batch_create_indexes_concurrently(
    indexes: List[Dict[str, Any]],
    continue_on_error: bool = True
) -> Dict[str, bool]:
    """
    Create multiple indexes concurrently with optional error tolerance.
    
    Args:
        indexes: List of index specifications, each containing:
            - name: str (required)
            - table: str (required)
            - columns: List[str] (required)
            - where: Optional[str]
            - unique: bool (default False)
            - type: str (default "btree")
        continue_on_error: Whether to continue if individual indexes fail
    
    Returns:
        Dict[str, bool]: Mapping of index names to success status
    
    Example:
        batch_create_indexes_concurrently([
            {
                "name": "ix_expenses_user_created",
                "table": "expenses",
                "columns": ["user_id", "created_at DESC"]
            },
            {
                "name": "ix_expenses_category_partial",
                "table": "expenses", 
                "columns": ["category", "created_at DESC"],
                "where": "superseded_by IS NULL"
            }
        ])
    """
    results = {}
    
    for idx_spec in indexes:
        name = idx_spec["name"]
        table = idx_spec["table"]
        columns = idx_spec["columns"]
        where = idx_spec.get("where")
        unique = idx_spec.get("unique", False)
        index_type = idx_spec.get("type", "btree")
        
        try:
            success = create_index_concurrently(
                name, table, columns, where, unique, True, index_type
            )
            results[name] = success
            
            if not success and not continue_on_error:
                logger.error(f"Stopping batch operation due to failure on {name}")
                break
                
        except Exception as e:
            logger.error(f"Error creating index {name}: {e}")
            results[name] = False
            
            if not continue_on_error:
                logger.error(f"Stopping batch operation due to error on {name}")
                break
    
    success_count = sum(1 for success in results.values() if success)
    logger.info(f"Batch index creation: {success_count}/{len(indexes)} successful")
    
    return results

def check_index_exists(index_name: str) -> bool:
    """
    Check if an index exists in the database.
    
    Args:
        index_name: Name of the index to check
    
    Returns:
        bool: True if index exists, False otherwise
    """
    try:
        sql = """
        SELECT 1 FROM pg_indexes 
        WHERE indexname = :index_name
        LIMIT 1
        """
        
        result = op.get_bind().execute(text(sql), {"index_name": index_name})
        return result.fetchone() is not None
        
    except Exception as e:
        logger.error(f"Error checking if index {index_name} exists: {e}")
        return False

def get_index_definition(index_name: str) -> Optional[str]:
    """
    Get the CREATE INDEX statement for an existing index.
    
    Args:
        index_name: Name of the index
    
    Returns:
        Optional[str]: The CREATE INDEX statement, or None if not found
    """
    try:
        sql = """
        SELECT indexdef FROM pg_indexes 
        WHERE indexname = :index_name
        """
        
        result = op.get_bind().execute(text(sql), {"index_name": index_name})
        row = result.fetchone()
        return row[0] if row else None
        
    except Exception as e:
        logger.error(f"Error getting definition for index {index_name}: {e}")
        return None

def _is_in_transaction() -> bool:
    """
    Check if we're currently inside a transaction.
    
    Uses PostgreSQL's txid_current_if_assigned() function to detect active transactions.
    This is critical for concurrent index operations which cannot run inside transactions.
    
    Returns:
        bool: True if inside a transaction, False otherwise
        
    Note:
        Returns True (safe default) if transaction status cannot be determined
    """
    try:
        # Use PostgreSQL's txid_current_if_assigned() to check transaction status
        # This returns NULL if no transaction is active, or the transaction ID if one exists
        result = op.get_bind().execute(text("SELECT txid_current_if_assigned()"))
        row = result.fetchone()
        if row is None:
            logger.debug("No result from txid_current_if_assigned() - assuming in transaction")
            return True  # Safe default
        
        tx_id = row[0] 
        is_in_tx = tx_id is not None
        
        if is_in_tx:
            logger.debug(f"Transaction detected: txid={tx_id}")
        else:
            logger.debug("No active transaction detected")
            
        return is_in_tx
        
    except OperationalError as e:
        error_msg = str(e).lower()
        
        # Handle specific PostgreSQL errors
        if "function txid_current_if_assigned() does not exist" in error_msg:
            logger.warning("txid_current_if_assigned() not available - assuming in transaction for safety")
        elif "connection" in error_msg:
            logger.warning(f"Database connection error checking transaction status: {e}")
        else:
            logger.warning(f"Operational error checking transaction status: {e}")
        return True  # Safe default
        
    except ProgrammingError as e:
        error_msg = str(e).lower()
        
        # Handle SQL syntax or permission errors
        if "permission denied" in error_msg:
            logger.warning("Permission denied checking transaction status - assuming in transaction")
        else:
            logger.warning(f"Programming error checking transaction status: {e}")
        return True  # Safe default
        
    except DatabaseError as e:
        logger.warning(f"Database error checking transaction status: {e}")
        return True  # Safe default
        
    except Exception as e:
        # Catch any other unexpected errors
        logger.warning(f"Unexpected error checking transaction status: {type(e).__name__}: {e}")
        return True  # Safe default - assume we're in a transaction for safety

def configure_alembic_for_concurrent():
    """
    Configure Alembic for concurrent operations by disabling transactions.
    
    This should be called in alembic/env.py when concurrent operations are needed.
    """
    # This is a placeholder - actual configuration happens in env.py
    # This function serves as documentation for the required configuration
    pass

# Common index patterns for convenience
def create_user_temporal_index(
    index_name: str,
    table_name: str,
    user_column: str = "user_id_hash",
    time_column: str = "created_at",
    where_clause: Optional[str] = None
) -> bool:
    """
    Create a common user+temporal index pattern.
    
    Args:
        index_name: Name of the index
        table_name: Target table
        user_column: User identifier column (default: user_id_hash)
        time_column: Temporal column (default: created_at)
        where_clause: Optional WHERE clause
    
    Returns:
        bool: True if successful
    """
    return create_index_concurrently(
        index_name,
        table_name,
        [user_column, f"{time_column} DESC"],
        where_clause=where_clause
    )

def create_category_index(
    index_name: str,
    table_name: str,
    category_column: str = "category",
    time_column: str = "created_at"
) -> bool:
    """
    Create a category+time index for analytical queries.
    
    Args:
        index_name: Name of the index
        table_name: Target table
        category_column: Category column name
        time_column: Temporal column for ordering
    
    Returns:
        bool: True if successful
    """
    return create_index_concurrently(
        index_name,
        table_name,
        [category_column, f"{time_column} DESC"]
    )

# Usage examples and documentation
EXAMPLES = {
    "basic_index": """
# Create a simple concurrent index
create_index_concurrently(
    "ix_expenses_user_id_hash",
    "expenses", 
    ["user_id_hash"]
)
""",
    
    "composite_index": """
# Create a composite index with ordering
create_index_concurrently(
    "ix_expenses_user_created", 
    "expenses",
    ["user_id_hash", "created_at DESC"]
)
""",
    
    "partial_index": """
# Create a partial index with WHERE clause
create_index_concurrently(
    "ix_expenses_recent_user",
    "expenses",
    ["user_id_hash", "created_at DESC"],
    where_clause="created_at >= '2024-01-01'"
)
""",
    
    "unique_index": """
# Create a unique index
create_index_concurrently(
    "ux_expenses_psid_mid",
    "expenses",
    ["user_id", "mid"],
    where_clause="mid IS NOT NULL AND mid != ''",
    unique=True
)
""",
    
    "index_replacement": """
# Replace an existing index
replace_index_concurrently(
    "old_ix_expenses_user",
    "new_ix_expenses_user_optimized",
    "expenses",
    ["user_id_hash", "created_at DESC", "category"]
)
""",
    
    "batch_creation": """
# Create multiple indexes at once
batch_create_indexes_concurrently([
    {
        "name": "ix_expenses_category_time",
        "table": "expenses", 
        "columns": ["category", "created_at DESC"]
    },
    {
        "name": "ix_expenses_amount_range",
        "table": "expenses",
        "columns": ["amount"],
        "where": "amount > 0"
    }
])
"""
}