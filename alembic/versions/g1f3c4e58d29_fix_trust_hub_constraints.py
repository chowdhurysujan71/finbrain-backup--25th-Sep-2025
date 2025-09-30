"""fix_trust_hub_constraints

Revision ID: g1f3c4e58d29
Revises: f9e2b3d47c18
Create Date: 2025-09-30 05:22:30.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'g1f3c4e58d29'
down_revision: str | Sequence[str] | None = 'f9e2b3d47c18'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fix uniqueness constraints and remove redundant indexes."""
    
    # Fix deletion_requests: Replace global unique with partial unique (active only)
    op.drop_constraint('deletion_requests_user_id_hash_key', 'deletion_requests', type_='unique')
    op.drop_index('ix_deletion_requests_user_id_hash', table_name='deletion_requests')
    
    # Create partial unique index for one active request per user
    op.execute("""
        CREATE UNIQUE INDEX ux_active_deletion_request 
        ON deletion_requests(user_id_hash) 
        WHERE canceled_at IS NULL
    """)
    
    # Re-create non-unique index for general user lookups
    op.create_index('ix_deletion_requests_user_id_hash', 'deletion_requests', ['user_id_hash'], unique=False)
    
    # Fix password_resets: Remove redundant unique index (keep column unique constraint)
    op.drop_index('ix_password_resets_token_hash', table_name='password_resets')
    
    # Re-create as non-unique index (uniqueness enforced by column constraint)
    op.create_index('ix_password_resets_token_hash', 'password_resets', ['token_hash'], unique=False)
    
    # Add CHECK constraints for data integrity
    op.create_check_constraint(
        'ck_password_resets_expires_after_created',
        'password_resets',
        'expires_at > created_at'
    )
    
    op.create_check_constraint(
        'ck_password_resets_used_after_created',
        'password_resets',
        'used_at IS NULL OR used_at >= created_at'
    )
    
    op.create_check_constraint(
        'ck_deletion_requests_scheduled_after_created',
        'deletion_requests',
        'scheduled_delete_at > created_at'
    )
    
    op.create_check_constraint(
        'ck_deletion_requests_canceled_after_created',
        'deletion_requests',
        'canceled_at IS NULL OR canceled_at >= created_at'
    )


def downgrade() -> None:
    """Revert constraint fixes."""
    
    # Remove CHECK constraints
    op.drop_constraint('ck_deletion_requests_canceled_after_created', 'deletion_requests', type_='check')
    op.drop_constraint('ck_deletion_requests_scheduled_after_created', 'deletion_requests', type_='check')
    op.drop_constraint('ck_password_resets_used_after_created', 'password_resets', type_='check')
    op.drop_constraint('ck_password_resets_expires_after_created', 'password_resets', type_='check')
    
    # Revert password_resets index
    op.drop_index('ix_password_resets_token_hash', table_name='password_resets')
    op.create_index('ix_password_resets_token_hash', 'password_resets', ['token_hash'], unique=True)
    
    # Revert deletion_requests indexes and constraints
    op.drop_index('ix_deletion_requests_user_id_hash', table_name='deletion_requests')
    op.execute('DROP INDEX IF EXISTS ux_active_deletion_request')
    
    op.create_index('ix_deletion_requests_user_id_hash', 'deletion_requests', ['user_id_hash'], unique=True)
    op.create_unique_constraint('deletion_requests_user_id_hash_key', 'deletion_requests', ['user_id_hash'])
