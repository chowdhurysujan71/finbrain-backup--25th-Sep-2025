"""baseline_migration

Revision ID: 5b555895a514
Revises: 
Create Date: 2025-09-14 05:27:57.349712

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '5b555895a514'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
