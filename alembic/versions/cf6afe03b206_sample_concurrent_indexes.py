"""sample_concurrent_indexes

Revision ID: cf6afe03b206
Revises: 5b555895a514
Create Date: 2025-09-14 06:01:28.658532

This migration demonstrates safe concurrent index operations.

To run this migration in concurrent mode:
1. Set environment variable: export CONCURRENT_MIGRATION=true
2. Run migration: alembic upgrade head
   
The migration will run without transactions, allowing CREATE INDEX CONCURRENTLY.

Examples demonstrated:
- Basic concurrent index creation
- Composite indexes for performance
- Partial indexes with WHERE clauses
- Unique constraints with concurrent creation
- Index replacement patterns
- Batch operations with error handling

Safety features:
- Uses IF NOT EXISTS for idempotent operations
- Graceful error handling for existing indexes
- No table locking during index creation
- Fail-safe behavior for production environments
"""
from typing import Sequence, Union
import logging

from utils.migrations import (
    create_index_concurrently,
    replace_index_concurrently, 
    batch_create_indexes_concurrently,
    check_index_exists,
    create_user_temporal_index,
    create_category_index
)

# Setup logging
logger = logging.getLogger('alembic.sample_concurrent_indexes')

# revision identifiers, used by Alembic.
revision: str = 'cf6afe03b206'
down_revision: Union[str, Sequence[str], None] = '5b555895a514'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Demonstrate safe concurrent index operations.
    
    This migration shows various patterns for creating indexes without table locks.
    All operations use CREATE INDEX CONCURRENTLY for production safety.
    """
    logger.info("=== CONCURRENT INDEX CREATION DEMO ===")
    
    # Example 1: Basic concurrent index
    logger.info("1. Creating basic concurrent index...")
    create_index_concurrently(
        "demo_ix_expenses_hash_lookup",
        "expenses",
        ["user_id_hash"],
        if_not_exists=True
    )
    
    # Example 2: Composite index for analytical queries
    logger.info("2. Creating composite analytical index...")
    create_index_concurrently(
        "demo_ix_expenses_analytics",
        "expenses", 
        ["user_id_hash", "category", "created_at DESC"],
        if_not_exists=True
    )
    
    # Example 3: Partial index for recent data
    logger.info("3. Creating partial index for recent data...")
    create_index_concurrently(
        "demo_ix_expenses_recent_90d",
        "expenses",
        ["user_id_hash", "amount", "created_at DESC"],
        where_clause="created_at >= '2024-01-01'::date",
        if_not_exists=True
    )
    
    # Example 4: Unique constraint with WHERE clause
    logger.info("4. Creating unique constraint concurrently...")
    create_index_concurrently(
        "demo_ux_expenses_external_id",
        "expenses", 
        ["user_id_hash", "mid"],
        where_clause="mid IS NOT NULL AND mid != ''",
        unique=True,
        if_not_exists=True
    )
    
    # Example 5: Index replacement pattern (if old index exists)
    logger.info("5. Demonstrating index replacement...")
    if check_index_exists("ix_expenses_user_id_hash"):
        replace_index_concurrently(
            "ix_expenses_user_id_hash",  # old index
            "demo_ix_expenses_user_hash_optimized",  # new index
            "expenses",
            ["user_id_hash", "created_at DESC"],  # enhanced with ordering
            where_clause="superseded_by IS NULL"  # only active records
        )
    else:
        logger.info("   Old index not found, creating new optimized index...")
        create_index_concurrently(
            "demo_ix_expenses_user_hash_optimized",
            "expenses",
            ["user_id_hash", "created_at DESC"],
            where_clause="superseded_by IS NULL",
            if_not_exists=True
        )
    
    # Example 6: Using convenience functions
    logger.info("6. Using convenience helper functions...")
    create_user_temporal_index(
        "demo_ix_monthly_summaries_user_time",
        "monthly_summaries",
        user_column="user_id_hash",
        time_column="created_at"
    )
    
    create_category_index(
        "demo_ix_expenses_category_performance", 
        "expenses",
        category_column="category",
        time_column="created_at"
    )
    
    # Example 7: Batch creation with error handling
    logger.info("7. Demonstrating batch index creation...")
    batch_indexes = [
        {
            "name": "demo_ix_telemetry_event_lookup",
            "table": "telemetry_events",
            "columns": ["event_type", "timestamp DESC"]
        },
        {
            "name": "demo_ix_telemetry_user_events", 
            "table": "telemetry_events",
            "columns": ["user_id_hash", "event_type", "timestamp DESC"],
            "where": "user_id_hash IS NOT NULL"
        },
        {
            "name": "demo_ix_report_feedback_context",
            "table": "report_feedback", 
            "columns": ["report_context_id", "signal", "created_at DESC"]
        }
    ]
    
    results = batch_create_indexes_concurrently(batch_indexes, continue_on_error=True)
    
    # Report results
    successful = [name for name, success in results.items() if success]
    failed = [name for name, success in results.items() if not success]
    
    logger.info(f"Batch creation complete: {len(successful)} successful, {len(failed)} failed")
    if failed:
        logger.warning(f"Failed indexes: {', '.join(failed)}")
    
    logger.info("=== CONCURRENT INDEX CREATION COMPLETE ===")


def downgrade() -> None:
    """
    Remove demonstration indexes created in upgrade().
    
    Uses DROP INDEX CONCURRENTLY for safe removal without table locks.
    """
    logger.info("=== CONCURRENT INDEX REMOVAL DEMO ===")
    
    from utils.migrations import drop_index_concurrently
    
    # List of demo indexes to remove
    demo_indexes = [
        "demo_ix_expenses_hash_lookup",
        "demo_ix_expenses_analytics", 
        "demo_ix_expenses_recent_90d",
        "demo_ux_expenses_external_id",
        "demo_ix_expenses_user_hash_optimized",
        "demo_ix_monthly_summaries_user_time",
        "demo_ix_expenses_category_performance",
        "demo_ix_telemetry_event_lookup",
        "demo_ix_telemetry_user_events",
        "demo_ix_report_feedback_context"
    ]
    
    for index_name in demo_indexes:
        logger.info(f"Removing demo index: {index_name}")
        drop_index_concurrently(index_name, if_exists=True)
    
    logger.info("=== CONCURRENT INDEX REMOVAL COMPLETE ===")


# Migration metadata for concurrent operations
def requires_concurrent_operations() -> bool:
    """
    Indicate this migration requires concurrent operations.
    
    This is checked by alembic/env.py to enable concurrent mode.
    """
    return True
