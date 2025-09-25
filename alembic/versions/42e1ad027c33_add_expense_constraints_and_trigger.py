"""add_expense_constraints_and_trigger

Revision ID: 42e1ad027c33
Revises: ad086f28445a
Create Date: 2025-09-20 08:18:08.798486

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '42e1ad027c33'
down_revision: Union[str, Sequence[str], None] = 'ad086f28445a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add critical database constraints and trigger for single-writer enforcement."""
    
    # 1. Add UNIQUE constraint on (user_id_hash, idempotency_key) for proper idempotency
    # This prevents duplicate expenses with same user and request ID
    op.create_unique_constraint(
        'ux_expenses_user_idempotency', 
        'expenses', 
        ['user_id_hash', 'idempotency_key']
    )
    
    # 2. Add CHECK constraint to prevent negative amounts
    # This ensures data integrity at the database level
    op.create_check_constraint(
        'ck_expenses_amount_minor_positive',
        'expenses',
        'amount_minor >= 0'
    )
    
    # 3. Create trigger function to block direct INSERT attempts
    # This enforces the single-writer principle at the database level
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_direct_expense_inserts()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Allow inserts only if they come from the canonical writer
            -- Canonical writer must set idempotency_key with 'api:' prefix
            IF NEW.idempotency_key IS NULL OR NOT NEW.idempotency_key LIKE 'api:%' THEN
                RAISE EXCEPTION 'Direct INSERT to expenses table blocked. Use backend_assistant.add_expense() instead.'
                    USING ERRCODE = 'check_violation',
                          HINT = 'All expense writes must go through the canonical single writer function.';
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 4. Create trigger to enforce single-writer principle
    op.execute("""
        CREATE TRIGGER trg_prevent_direct_expense_inserts
            BEFORE INSERT ON expenses
            FOR EACH ROW
            EXECUTE FUNCTION prevent_direct_expense_inserts();
    """)


def downgrade() -> None:
    """Remove constraints and trigger."""
    
    # Remove trigger first
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_direct_expense_inserts ON expenses;")
    
    # Remove trigger function
    op.execute("DROP FUNCTION IF EXISTS prevent_direct_expense_inserts();")
    
    # Remove constraints
    op.drop_constraint('ck_expenses_amount_minor_positive', 'expenses', type_='check')
    op.drop_constraint('ux_expenses_user_idempotency', 'expenses', type_='unique')
