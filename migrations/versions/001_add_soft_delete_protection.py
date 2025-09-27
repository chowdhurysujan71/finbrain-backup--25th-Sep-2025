"""Add soft delete protection to expenses and users tables

Revision ID: 001_soft_delete
Revises: 
Create Date: 2025-09-27 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_soft_delete'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add soft delete columns to critical tables"""
    
    # Add soft delete columns to expenses table
    op.add_column('expenses', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('expenses', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add index for performance on soft-delete queries
    op.create_index('ix_expenses_is_deleted', 'expenses', ['is_deleted'])
    op.create_index('ix_expenses_deleted_at', 'expenses', ['deleted_at'])
    
    # Add soft delete columns to users table
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add index for performance on soft-delete queries
    op.create_index('ix_users_is_deleted', 'users', ['is_deleted'])
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'])


def downgrade():
    """Remove soft delete columns"""
    
    # Remove indexes
    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_index('ix_users_is_deleted', table_name='users')
    op.drop_index('ix_expenses_deleted_at', table_name='expenses')
    op.drop_index('ix_expenses_is_deleted', table_name='expenses')
    
    # Remove columns
    op.drop_column('users', 'is_deleted')
    op.drop_column('users', 'deleted_at')
    op.drop_column('expenses', 'is_deleted')
    op.drop_column('expenses', 'deleted_at')