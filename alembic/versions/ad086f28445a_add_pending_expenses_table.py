"""add_pending_expenses_table

Revision ID: ad086f28445a
Revises: cf6afe03b206
Create Date: 2025-09-17 13:07:33.463310

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ad086f28445a'
down_revision: str | Sequence[str] | None = 'cf6afe03b206'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pending_expenses table for temporary expense clarifications."""
    # Create the pending_expenses table
    op.create_table('pending_expenses',
        sa.Column('pending_id', sa.String(255), nullable=False, primary_key=True),
        sa.Column('user_id_hash', sa.String(255), nullable=False, index=True),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False, default='BDT'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('suggested_category', sa.String(50), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('item', sa.String(255), nullable=False),
        sa.Column('mid', sa.String(255), nullable=True),
        sa.Column('options_json', sa.Text(), nullable=False),  # JSON serialized options
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create index for efficient TTL cleanup and user lookups
    op.create_index('ix_pending_expenses_expires_at', 'pending_expenses', ['expires_at'])
    op.create_index('ix_pending_expenses_user_expires', 'pending_expenses', ['user_id_hash', 'expires_at'])


def downgrade() -> None:
    """Remove pending_expenses table."""
    op.drop_index('ix_pending_expenses_user_expires', table_name='pending_expenses')
    op.drop_index('ix_pending_expenses_expires_at', table_name='pending_expenses')
    op.drop_table('pending_expenses')
