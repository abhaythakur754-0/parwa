-- ═══════════════════════════════════════════════════════════════════════════════
-- PARWA — Interaction Table Indexes
-- Week 26 Day 1 (Builder 1 Task)
-- Target: Query time < 10ms for indexed queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- Sessions Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 1: Session lookup by tenant and customer
-- Purpose: Fast lookup of customer sessions for tenant isolation
-- Query: SELECT * FROM sessions WHERE tenant_id = ? AND customer_id = ?
-- Note: Already exists in schema.sql as idx_sessions_tenant_customer
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'sessions' AND indexname = 'idx_sessions_tenant_customer'
    ) THEN
        CREATE INDEX idx_sessions_tenant_customer ON sessions(tenant_id, customer_id);
    END IF;
END $$;

-- Index 2: Session status filtering
-- Purpose: Fast filtering by session status (active, closed, escalated)
-- Query: SELECT * FROM sessions WHERE status = 'active'
CREATE INDEX IF NOT EXISTS idx_sessions_status
ON sessions(tenant_id, status);

-- Index 3: Session channel filtering
-- Purpose: Fast filtering by communication channel
-- Query: SELECT * FROM sessions WHERE channel = 'chat'
CREATE INDEX IF NOT EXISTS idx_sessions_channel
ON sessions(tenant_id, channel);

-- Index 4: Active sessions index
-- Purpose: Fast lookup of active sessions
-- Query: SELECT * FROM sessions WHERE tenant_id = ? AND status = 'active'
CREATE INDEX IF NOT EXISTS idx_sessions_active
ON sessions(tenant_id, created_at DESC)
WHERE status = 'active';

-- Index 5: Session time-based queries
-- Purpose: Time-based analytics on sessions
-- Query: SELECT * FROM sessions WHERE tenant_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_sessions_created_at
ON sessions(tenant_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Interactions Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 6: Interaction lookup by session
-- Purpose: Fast retrieval of all interactions in a session
-- Query: SELECT * FROM interactions WHERE session_id = ?
-- Note: Already exists in schema.sql as idx_interactions_session_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'interactions' AND indexname = 'idx_interactions_session_id'
    ) THEN
        CREATE INDEX idx_interactions_session_id ON interactions(session_id);
    END IF;
END $$;

-- Index 7: Interaction role filtering
-- Purpose: Fast filtering by role (user, assistant, system)
-- Query: SELECT * FROM interactions WHERE session_id = ? AND role = 'user'
CREATE INDEX IF NOT EXISTS idx_interactions_role
ON interactions(session_id, role);

-- Index 8: Interaction time ordering
-- Purpose: Fast ordering of interactions by time within a session
-- Query: SELECT * FROM interactions WHERE session_id = ? ORDER BY created_at
CREATE INDEX IF NOT EXISTS idx_interactions_session_time
ON interactions(session_id, created_at);

-- Index 9: Model usage analytics
-- Purpose: Analytics on which AI models are used
-- Query: SELECT * FROM interactions WHERE model_used = 'gpt-4'
CREATE INDEX IF NOT EXISTS idx_interactions_model
ON interactions(model_used);

-- Index 10: Token usage analytics
-- Purpose: Analytics on token usage patterns
-- Query: SELECT * FROM interactions WHERE tokens_prompt > 1000
CREATE INDEX IF NOT EXISTS idx_interactions_tokens
ON interactions(session_id, tokens_prompt + tokens_completion DESC);

-- Index 11: Recent interactions lookup
-- Purpose: Fast lookup of recent interactions across all sessions
-- Query: SELECT * FROM interactions ORDER BY created_at DESC LIMIT 100
CREATE INDEX IF NOT EXISTS idx_interactions_recent
ON interactions(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Customers Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 12: Customer lookup by tenant and email
-- Purpose: Fast customer lookup by email within tenant
-- Query: SELECT * FROM customers WHERE tenant_id = ? AND email = ?
-- Note: Already exists in schema.sql as idx_customers_tenant_email
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'customers' AND indexname = 'idx_customers_tenant_email'
    ) THEN
        CREATE INDEX idx_customers_tenant_email ON customers(tenant_id, email);
    END IF;
END $$;

-- Index 13: Customer lookup by phone
-- Purpose: Fast customer lookup by phone within tenant
-- Note: Already exists in schema.sql as idx_customers_tenant_phone
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'customers' AND indexname = 'idx_customers_tenant_phone'
    ) THEN
        CREATE INDEX idx_customers_tenant_phone ON customers(tenant_id, phone);
    END IF;
END $$;

-- Index 14: Customer external ID lookup
-- Purpose: Fast customer lookup by external ID (e.g., Shopify customer ID)
-- Query: SELECT * FROM customers WHERE tenant_id = ? AND external_id = ?
CREATE INDEX IF NOT EXISTS idx_customers_external_id
ON customers(tenant_id, external_id)
WHERE external_id IS NOT NULL;

-- Index 15: Customer name search
-- Purpose: Fast search by customer name
-- Query: SELECT * FROM customers WHERE tenant_id = ? AND name ILIKE '%john%'
CREATE INDEX IF NOT EXISTS idx_customers_name
ON customers(tenant_id, name);

-- ─────────────────────────────────────────────────────────────────────────────
-- Human Corrections Table Indexes (Agent Lightning Training Data)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 16: Corrections for training export
-- Purpose: Fast lookup of corrections not yet exported for training
-- Query: SELECT * FROM human_corrections WHERE exported_for_training = false
-- Note: Already exists in schema.sql as idx_corrections_training
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'human_corrections' AND indexname = 'idx_corrections_training'
    ) THEN
        CREATE INDEX idx_corrections_training ON human_corrections(tenant_id, exported_for_training);
    END IF;
END $$;

-- Index 17: Corrections by interaction
-- Purpose: Fast lookup of corrections for a specific interaction
-- Query: SELECT * FROM human_corrections WHERE interaction_id = ?
CREATE INDEX IF NOT EXISTS idx_corrections_interaction
ON human_corrections(interaction_id);

-- Index 18: Corrections by user
-- Purpose: Analytics on which users provide corrections
-- Query: SELECT * FROM human_corrections WHERE corrected_by_user_id = ?
CREATE INDEX IF NOT EXISTS idx_corrections_user
ON human_corrections(corrected_by_user_id)
WHERE corrected_by_user_id IS NOT NULL;

-- Index 19: Recent corrections for training pipeline
-- Purpose: Fast lookup of recent corrections for training
-- Query: SELECT * FROM human_corrections WHERE exported_for_training = false ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_corrections_recent_unexported
ON human_corrections(tenant_id, created_at DESC)
WHERE exported_for_training = false;

-- ─────────────────────────────────────────────────────────────────────────────
-- Index Statistics and Monitoring
-- ─────────────────────────────────────────────────────────────────────────────

-- Analyze tables after index creation
ANALYZE sessions;
ANALYZE interactions;
ANALYZE customers;
ANALYZE human_corrections;

-- Comments for documentation
COMMENT ON INDEX idx_sessions_status IS 'Session status filtering per tenant';
COMMENT ON INDEX idx_sessions_channel IS 'Session channel filtering per tenant';
COMMENT ON INDEX idx_sessions_active IS 'Active sessions lookup (partial)';
COMMENT ON INDEX idx_sessions_created_at IS 'Session time-based analytics';
COMMENT ON INDEX idx_interactions_role IS 'Interaction role filtering per session';
COMMENT ON INDEX idx_interactions_session_time IS 'Interaction time ordering per session';
COMMENT ON INDEX idx_interactions_model IS 'AI model usage analytics';
COMMENT ON INDEX idx_interactions_tokens IS 'Token usage analytics per session';
COMMENT ON INDEX idx_interactions_recent IS 'Recent interactions across all sessions';
COMMENT ON INDEX idx_customers_external_id IS 'Customer external ID lookup (partial)';
COMMENT ON INDEX idx_customers_name IS 'Customer name search per tenant';
COMMENT ON INDEX idx_corrections_interaction IS 'Corrections by interaction';
COMMENT ON INDEX idx_corrections_user IS 'Corrections by user (partial)';
COMMENT ON INDEX idx_corrections_recent_unexported IS 'Unexported corrections for training (partial)';
