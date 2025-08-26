
-- Performance indexes for overlay tables
-- Run this migration to optimize precedence queries

-- Index for user corrections lookup
CREATE INDEX IF NOT EXISTS idx_user_corrections_lookup 
ON user_corrections(user_id, tx_id, created_at DESC);

-- Index for user rules matching
CREATE INDEX IF NOT EXISTS idx_user_rules_active
ON user_rules(user_id, active, created_at DESC);

-- Index for transactions effective precedence
CREATE INDEX IF NOT EXISTS idx_transactions_effective_precedence
ON transactions_effective(user_id, tx_id, decided_at DESC);

-- Composite index for fast precedence resolution
CREATE INDEX IF NOT EXISTS idx_precedence_composite
ON transactions_effective(user_id, tx_id, status, decided_at DESC);

-- Rule pattern matching optimization
CREATE INDEX IF NOT EXISTS idx_user_rules_pattern
ON user_rules(user_id, rule_type, priority DESC);
