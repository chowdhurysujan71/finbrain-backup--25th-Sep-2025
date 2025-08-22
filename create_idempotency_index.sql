-- Migration: Add unique index for idempotency protection
-- Prevents duplicate expense logging using Facebook message ID

-- Add mid column if it doesn't exist (for Facebook message ID)
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS mid VARCHAR(255);

-- Add currency column if it doesn't exist
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'BDT';

-- Create unique index on (user_id, mid) for idempotency protection
-- This prevents the same Facebook message from creating duplicate expenses
CREATE UNIQUE INDEX IF NOT EXISTS ux_expenses_psid_mid 
ON expenses(user_id, mid) 
WHERE mid IS NOT NULL AND mid != '';

-- Create index on user_id and created_at for performance
CREATE INDEX IF NOT EXISTS ix_expenses_user_created 
ON expenses(user_id, created_at DESC);

-- Create index on month for monthly summaries
CREATE INDEX IF NOT EXISTS ix_expenses_month 
ON expenses(month);

-- Verify the indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'expenses' 
  AND indexname IN ('ux_expenses_psid_mid', 'ix_expenses_user_created', 'ix_expenses_month')
ORDER BY indexname;