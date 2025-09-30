"""add_trust_hub_tables

Revision ID: f9e2b3d47c18
Revises: 42e1ad027c33
Create Date: 2025-09-30 05:11:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9e2b3d47c18'
down_revision: str | Sequence[str] | None = '42e1ad027c33'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create trust hub tables for password resets and account deletion."""
    
    # Create password_resets table
    op.create_table('password_resets',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('user_id_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),  # IPv6 max length
        sa.Column('user_agent', sa.Text(), nullable=True)
    )
    
    # Create indexes for password_resets
    op.create_index('ix_password_resets_token_hash', 'password_resets', ['token_hash'], unique=True)
    op.create_index('ix_password_resets_user_id_hash', 'password_resets', ['user_id_hash'])
    op.create_index('ix_password_resets_expires_at', 'password_resets', ['expires_at'])
    
    # Create deletion_requests table
    op.create_table('deletion_requests',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('user_id_hash', sa.String(255), nullable=False, unique=True),  # One active request per user
        sa.Column('scheduled_delete_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True)
    )
    
    # Create indexes for deletion_requests
    op.create_index('ix_deletion_requests_user_id_hash', 'deletion_requests', ['user_id_hash'], unique=True)
    op.create_index('ix_deletion_requests_scheduled_delete_at', 'deletion_requests', ['scheduled_delete_at'])


def downgrade() -> None:
    """Remove trust hub tables."""
    
    # Drop deletion_requests table and indexes
    op.drop_index('ix_deletion_requests_scheduled_delete_at', table_name='deletion_requests')
    op.drop_index('ix_deletion_requests_user_id_hash', table_name='deletion_requests')
    op.drop_table('deletion_requests')
    
    # Drop password_resets table and indexes
    op.drop_index('ix_password_resets_expires_at', table_name='password_resets')
    op.drop_index('ix_password_resets_user_id_hash', table_name='password_resets')
    op.drop_index('ix_password_resets_token_hash', table_name='password_resets')
    op.drop_table('password_resets')
