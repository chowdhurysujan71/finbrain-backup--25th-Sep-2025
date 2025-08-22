-- FinBrain Expense Corrections Migration
-- Adds backwards-compatible correction tracking to expenses table
-- All columns are nullable to ensure zero impact on existing data

-- Add correction tracking columns
ALTER TABLE expenses
  ADD COLUMN IF NOT EXISTS superseded_by BIGINT NULL,
  ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS corrected_reason TEXT NULL;

-- Add comments for clarity
COMMENT ON COLUMN expenses.superseded_by IS 'ID of expense that supersedes this one (for corrections)';
COMMENT ON COLUMN expenses.corrected_at IS 'Timestamp when this expense was corrected';
COMMENT ON COLUMN expenses.corrected_reason IS 'Short reason for the correction (e.g., "meant 500")';

-- Performance index for finding uncorrected expenses by user
-- This helps quickly find the latest uncorrected expense for a user
CREATE INDEX IF NOT EXISTS ix_expenses_user_created_uncorrected
  ON expenses (user_id, created_at DESC)
  WHERE superseded_by IS NULL;

-- Index for correction lookup performance
CREATE INDEX IF NOT EXISTS ix_expenses_superseded_by
  ON expenses (superseded_by)
  WHERE superseded_by IS NOT NULL;

-- Verify the migration worked
SELECT 
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns 
WHERE table_name = 'expenses' 
  AND column_name IN ('superseded_by', 'corrected_at', 'corrected_reason')
ORDER BY column_name;