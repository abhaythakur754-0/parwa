-- ═══════════════════════════════════════════════════════════════════════════════
-- PARWA — Client/Company Table Indexes
-- Week 26 Day 1 (Builder 1 Task)
-- Target: Query time < 10ms for indexed queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- Companies Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 1: Primary company lookup by ID
-- Purpose: Fast company lookup by ID (primary key already indexed, this is explicit)
-- Query: SELECT * FROM companies WHERE id = ?
-- Note: Primary key is automatically indexed, but we add this for documentation
-- CREATE INDEX IF NOT EXISTS idx_companies_id ON companies(id);  -- Already exists via PK

-- Index 2: Company name search
-- Purpose: Fast lookup of companies by name
-- Query: SELECT * FROM companies WHERE name = ?
CREATE INDEX IF NOT EXISTS idx_companies_name
ON companies(name);

-- Index 3: Industry filtering index
-- Purpose: Fast filtering of clients by industry
-- Query: SELECT * FROM companies WHERE industry = 'ecommerce'
CREATE INDEX IF NOT EXISTS idx_companies_industry
ON companies(industry);

-- Index 4: Plan tier filtering index
-- Purpose: Fast filtering by subscription tier (mini, parwa, parwa_high)
-- Query: SELECT * FROM companies WHERE plan_tier = 'parwa_high'
CREATE INDEX IF NOT EXISTS idx_companies_plan_tier
ON companies(plan_tier);

-- Index 5: Active clients index
-- Purpose: Fast lookup of active clients
-- Query: SELECT * FROM companies WHERE is_active = true
CREATE INDEX IF NOT EXISTS idx_companies_active
ON companies(is_active)
WHERE is_active = true;

-- Index 6: Created at index for analytics
-- Purpose: Time-based analytics on client onboarding
-- Query: SELECT * FROM companies ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_companies_created_at
ON companies(created_at DESC);

-- Index 7: Composite index for active clients by tier
-- Purpose: Fast filtering of active clients by subscription tier
-- Query: SELECT * FROM companies WHERE is_active = true AND plan_tier = ?
CREATE INDEX IF NOT EXISTS idx_companies_active_tier
ON companies(plan_tier, created_at DESC)
WHERE is_active = true;

-- ─────────────────────────────────────────────────────────────────────────────
-- Tenants Table Indexes (from schema.sql)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 8: Tenant tier index
-- Purpose: Fast filtering by tenant tier
-- Query: SELECT * FROM tenants WHERE tier = 'mini'
-- Note: Already exists in schema.sql, verify
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'tenants' AND indexname = 'idx_tenants_tier'
    ) THEN
        CREATE INDEX idx_tenants_tier ON tenants(tier);
    END IF;
END $$;

-- Index 9: Active tenants index
-- Purpose: Fast lookup of active tenants
-- Query: SELECT * FROM tenants WHERE is_active = true
CREATE INDEX IF NOT EXISTS idx_tenants_active
ON tenants(is_active)
WHERE is_active = true;

-- Index 10: Tenant name search
-- Purpose: Fast lookup by tenant name
-- Query: SELECT * FROM tenants WHERE name = ?
CREATE INDEX IF NOT EXISTS idx_tenants_name
ON tenants(name);

-- ─────────────────────────────────────────────────────────────────────────────
-- Users Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 11: User email lookup
-- Purpose: Fast authentication lookup by email
-- Query: SELECT * FROM users WHERE email = ?
CREATE INDEX IF NOT EXISTS idx_users_email
ON users(email);

-- Index 12: User role filtering
-- Purpose: Fast filtering by user role (admin, manager, agent)
-- Query: SELECT * FROM users WHERE role = 'admin'
CREATE INDEX IF NOT EXISTS idx_users_role
ON users(tenant_id, role);

-- Index 13: Active users by tenant
-- Purpose: Fast lookup of active users per tenant
-- Query: SELECT * FROM users WHERE tenant_id = ? AND is_active = true
CREATE INDEX IF NOT EXISTS idx_users_tenant_active
ON users(tenant_id)
WHERE is_active = true;

-- ─────────────────────────────────────────────────────────────────────────────
-- API Keys Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 14: Active API keys by tenant
-- Purpose: Fast lookup of active API keys per tenant
-- Query: SELECT * FROM api_keys WHERE tenant_id = ? AND is_active = true
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_active
ON api_keys(tenant_id)
WHERE is_active = true;

-- Index 15: API key hash lookup
-- Purpose: Fast authentication by API key hash
-- Query: SELECT * FROM api_keys WHERE key_hash = ?
CREATE INDEX IF NOT EXISTS idx_api_keys_hash
ON api_keys(key_hash)
WHERE is_active = true;

-- ─────────────────────────────────────────────────────────────────────────────
-- Index Statistics and Monitoring
-- ─────────────────────────────────────────────────────────────────────────────

-- Analyze tables after index creation
ANALYZE companies;
ANALYZE tenants;
ANALYZE users;
ANALYZE api_keys;

-- Comments for documentation
COMMENT ON INDEX idx_companies_name IS 'Company name search';
COMMENT ON INDEX idx_companies_industry IS 'Industry filtering for analytics';
COMMENT ON INDEX idx_companies_plan_tier IS 'Subscription tier filtering';
COMMENT ON INDEX idx_companies_active IS 'Active clients lookup (partial)';
COMMENT ON INDEX idx_companies_created_at IS 'Client onboarding analytics';
COMMENT ON INDEX idx_companies_active_tier IS 'Active clients by tier (composite, partial)';
COMMENT ON INDEX idx_tenants_active IS 'Active tenants lookup (partial)';
COMMENT ON INDEX idx_tenants_name IS 'Tenant name search';
COMMENT ON INDEX idx_users_email IS 'User authentication lookup';
COMMENT ON INDEX idx_users_role IS 'User role filtering per tenant';
COMMENT ON INDEX idx_users_tenant_active IS 'Active users per tenant (partial)';
COMMENT ON INDEX idx_api_keys_tenant_active IS 'Active API keys per tenant (partial)';
COMMENT ON INDEX idx_api_keys_hash IS 'API key authentication (partial)';
