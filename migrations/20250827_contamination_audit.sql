-- AI Contamination Prevention & Audit Migration
-- Safe, idempotent migration for contamination monitoring
-- Created: 2025-08-27

-- Create audit table for AI request tracking (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ai_request_audit') THEN
        CREATE TABLE ai_request_audit (
            id BIGSERIAL PRIMARY KEY,
            request_id VARCHAR(255) UNIQUE NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            request_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expense_data JSONB NOT NULL,
            response_data JSONB,
            contamination_detected BOOLEAN DEFAULT FALSE,
            contamination_issues JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Index for user isolation queries
        CREATE INDEX IF NOT EXISTS idx_ai_request_audit_user_id 
        ON ai_request_audit(user_id, request_timestamp);
        
        -- Index for contamination detection
        CREATE INDEX IF NOT EXISTS idx_ai_request_audit_contamination 
        ON ai_request_audit(contamination_detected, created_at) 
        WHERE contamination_detected = true;
        
        RAISE NOTICE 'Created ai_request_audit table with indexes';
    ELSE
        RAISE NOTICE 'ai_request_audit table already exists, skipping creation';
    END IF;
END $$;

-- Add missing indexes for user isolation on expenses table (idempotent)
DO $$ 
BEGIN
    -- Index for user_id + created_at (insights queries)
    IF NOT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_expenses_user_insights') THEN
        CREATE INDEX idx_expenses_user_insights 
        ON expenses(user_id, created_at DESC);
        RAISE NOTICE 'Created idx_expenses_user_insights index';
    END IF;
    
    -- Index for user_id + category (category breakdown queries)
    IF NOT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_expenses_user_category') THEN
        CREATE INDEX idx_expenses_user_category 
        ON expenses(user_id, category, created_at DESC);
        RAISE NOTICE 'Created idx_expenses_user_category index';
    END IF;
END $$;

-- Add soft delete support (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns 
                   WHERE table_name = 'expenses' AND column_name = 'deleted_at') THEN
        ALTER TABLE expenses ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE NULL;
        
        -- Index for non-deleted records
        CREATE INDEX IF NOT EXISTS idx_expenses_not_deleted 
        ON expenses(user_id, created_at DESC) 
        WHERE deleted_at IS NULL;
        
        RAISE NOTICE 'Added soft delete support to expenses table';
    ELSE
        RAISE NOTICE 'Soft delete column already exists, skipping';
    END IF;
END $$;

-- Create function for data version calculation (idempotent)
CREATE OR REPLACE FUNCTION calculate_user_data_version(p_user_id VARCHAR(255), p_window_start TIMESTAMP, p_window_end TIMESTAMP)
RETURNS VARCHAR(32) AS $$
DECLARE
    data_hash VARCHAR(32);
BEGIN
    -- Calculate hash of user's expense data in time window
    SELECT MD5(
        COALESCE(
            STRING_AGG(
                category || ':' || amount::text || ':' || EXTRACT(EPOCH FROM created_at)::text,
                '|' ORDER BY created_at, id
            ),
            'empty'
        )
    ) INTO data_hash
    FROM expenses 
    WHERE user_id = p_user_id 
      AND created_at >= p_window_start 
      AND created_at < p_window_end
      AND deleted_at IS NULL;
    
    RETURN COALESCE(data_hash, MD5('empty'));
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (idempotent)
DO $$ 
BEGIN
    -- Grant select on audit table to application user if exists
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = current_user) THEN
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON ai_request_audit TO %I', current_user);
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE ai_request_audit_id_seq TO %I', current_user);
        RAISE NOTICE 'Granted permissions on ai_request_audit to current user';
    END IF;
END $$;

-- Create contamination alert function
CREATE OR REPLACE FUNCTION alert_contamination()
RETURNS TRIGGER AS $$
BEGIN
    -- Log contamination detection
    IF NEW.contamination_detected = true THEN
        RAISE WARNING 'AI_CONTAMINATION_DETECTED: request_id=% user_id=% issues=%', 
                     NEW.request_id, NEW.user_id, NEW.contamination_issues;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for contamination alerts (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'trigger_contamination_alert') THEN
        CREATE TRIGGER trigger_contamination_alert
        AFTER INSERT OR UPDATE ON ai_request_audit
        FOR EACH ROW
        WHEN (NEW.contamination_detected = true)
        EXECUTE FUNCTION alert_contamination();
        
        RAISE NOTICE 'Created contamination alert trigger';
    END IF;
END $$;