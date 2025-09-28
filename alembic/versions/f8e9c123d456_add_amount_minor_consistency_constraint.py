"""add_amount_minor_consistency_constraint

Revision ID: f8e9c123d456
Revises: 42e1ad027c33
Create Date: 2025-09-28 08:02:00.000000

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f8e9c123d456'
down_revision: str | Sequence[str] | None = '42e1ad027c33'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add amount/amount_minor consistency constraint to prevent data drift."""
    
    # Add CHECK constraint to ensure amount_minor = amount * 100
    # This prevents inconsistency between the two currency fields
    op.create_check_constraint(
        'ck_expenses_amount_minor_consistent',
        'expenses',
        'amount_minor = (amount * 100)::bigint'
    )


def downgrade() -> None:
    """Remove amount/amount_minor consistency constraint."""
    
    op.drop_constraint('ck_expenses_amount_minor_consistent', 'expenses', type_='check')