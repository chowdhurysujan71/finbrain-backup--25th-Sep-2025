-- Critical performance indexes for FinBrain
-- Composite index for user expense queries (hot path)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_uid_created
ON expenses (user_id_hash, created_at DESC);

-- Index for PCA expense tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pca_expenses_uid_date  
ON pca_expenses (user_id, transaction_date DESC);

-- Index for monthly summaries lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monthly_summaries_uid_month
ON monthly_summaries (user_id_hash, month, year);

-- Index for expense categories (for analytics)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_category
ON expenses (category, created_at DESC);