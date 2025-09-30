"""add_expense_performance_indexes

Revision ID: h2g4d5f69e3a
Revises: g1f3c4e58d29
Create Date: 2025-09-30 05:26:00.000000

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'h2g4d5f69e3a'
down_revision: str | Sequence[str] | None = 'g1f3c4e58d29'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add performance indexes for common query patterns."""
    
    # Index for category-filtered chronological lists
    # Supports: SELECT * FROM transactions_effective WHERE user_id=? AND category=? ORDER BY transaction_date DESC
    op.create_index(
        'idx_expenses_user_category_date',
        'transactions_effective',
        ['user_id', 'category', 'transaction_date'],
        unique=False
    )
    
    # Index for amount-based queries and filtering
    # Supports: SELECT * FROM transactions_effective WHERE user_id=? AND amount BETWEEN ? AND ?
    op.create_index(
        'idx_expenses_user_amount',
        'transactions_effective',
        ['user_id', 'amount'],
        unique=False
    )
    
    # Optimize the existing user_date index with DESC ordering for chronological queries
    # Drop and recreate with DESC for better reverse-chronological performance
    op.drop_index('idx_transactions_effective_user_date', table_name='transactions_effective')
    
    op.execute("""
        CREATE INDEX idx_transactions_effective_user_date 
        ON transactions_effective(user_id, transaction_date DESC)
    """)


def downgrade() -> None:
    """Remove performance indexes."""
    
    # Restore original user_date index without DESC
    op.drop_index('idx_transactions_effective_user_date', table_name='transactions_effective')
    op.create_index(
        'idx_transactions_effective_user_date',
        'transactions_effective',
        ['user_id', 'transaction_date'],
        unique=False
    )
    
    # Remove amount index
    op.drop_index('idx_expenses_user_amount', table_name='transactions_effective')
    
    # Remove category index
    op.drop_index('idx_expenses_user_category_date', table_name='transactions_effective')
