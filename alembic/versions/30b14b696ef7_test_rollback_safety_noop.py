"""test_rollback_safety_noop

Revision ID: 30b14b696ef7
Revises: cf6afe03b206
Create Date: 2025-09-14 06:34:29.210395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30b14b696ef7'
down_revision: Union[str, Sequence[str], None] = 'cf6afe03b206'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
