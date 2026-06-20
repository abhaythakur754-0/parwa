-- ============================================================
-- PARWA Phase 1 — Database Schema
-- Key-based access + Multi-tenant isolation
-- ============================================================

-- 1. Tenants (companies using PARWA)
CREATE TABLE IF NOT EXISTS tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) NOT NULL UNIQUE,        -- e.g. "acme-corp"
    tier            VARCHAR(20) NOT NULL DEFAULT 'mini', -- mini, parwa, high
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    settings        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    -- Multi-tenant: every query filters by tenant_id
    CONSTRAINT valid_tier CHECK (tier IN ('mini', 'parwa', 'high')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'suspended', 'trial'))
);

-- 2. Users (admin users within a tenant)
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'admin',  -- admin, viewer
    password_hash   VARCHAR(255),                           -- optional, key-based auth primary
    is_active       BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (tenant_id, email),
    CONSTRAINT valid_role CHECK (role IN ('admin', 'viewer'))
);

-- 3. Access Keys (API keys for programmatic access)
CREATE TABLE IF NOT EXISTS access_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    key_prefix      VARCHAR(12) NOT NULL,        -- first 12 chars for display: "pk_live_abc1..."
    key_hash        VARCHAR(255) NOT NULL UNIQUE, -- SHA-256 hash of full key
    key_type        VARCHAR(20) NOT NULL DEFAULT 'live',  -- live, test
    name            VARCHAR(100) NOT NULL,        -- e.g. "Production Key"
    permissions     JSONB DEFAULT '[]',           -- allowed scopes
    is_active       BOOLEAN DEFAULT TRUE,
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,                  -- NULL = no expiry
    rate_limit_rpm  INT DEFAULT 40,               -- requests per minute
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_key_type CHECK (key_type IN ('live', 'test'))
);

-- 4. Key Usage Audit (every API call logged)
CREATE TABLE IF NOT EXISTS key_usage_audit (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    key_id          UUID REFERENCES access_keys(id),
    session_id      VARCHAR(255),
    endpoint        VARCHAR(255) NOT NULL,
    method          VARCHAR(10) NOT NULL,
    status_code     INT,
    ip_address      INET,
    user_agent      TEXT,
    duration_ms     INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Failed Auth Attempts (for lockout)
CREATE TABLE IF NOT EXISTS failed_auth_attempts (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    identifier      VARCHAR(255) NOT NULL,   -- IP or key_prefix used
    attempt_count   INT DEFAULT 1,
    locked_until    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_access_keys_tenant_id ON access_keys(tenant_id);
CREATE INDEX idx_access_keys_key_hash ON access_keys(key_hash);
CREATE INDEX idx_access_keys_key_prefix ON access_keys(key_prefix);
CREATE INDEX idx_key_usage_audit_tenant_id ON key_usage_audit(tenant_id);
CREATE INDEX idx_key_usage_audit_key_id ON key_usage_audit(key_id);
CREATE INDEX idx_key_usage_audit_created_at ON key_usage_audit(created_at);
CREATE INDEX idx_failed_auth_tenant_id ON failed_auth_attempts(tenant_id);
CREATE INDEX idx_failed_auth_identifier ON failed_auth_attempts(identifier);

-- ============================================================
-- Row-Level Security (PostgreSQL RLS) — Multi-tenant isolation
-- Every table with tenant_id gets RLS enabled
-- ============================================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE key_usage_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE failed_auth_attempts ENABLE ROW LEVEL SECURITY;

-- Tenant members can only see their own tenant
-- Superuser bypasses RLS for cross-tenant admin operations
CREATE POLICY tenant_isolation ON tenants
    USING (id = current_setting('app.tenant_id', TRUE)::UUID OR current_setting('app.tenant_id', TRUE) IS NULL);

CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID OR current_setting('app.tenant_id', TRUE) IS NULL);

CREATE POLICY tenant_isolation ON access_keys
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID OR current_setting('app.tenant_id', TRUE) IS NULL);

CREATE POLICY tenant_isolation ON key_usage_audit
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID OR current_setting('app.tenant_id', TRUE) IS NULL);

CREATE POLICY tenant_isolation ON failed_auth_attempts
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID OR current_setting('app.tenant_id', TRUE) IS NULL);

-- ============================================================
-- Helper: set_tenant_context function
-- Call at the start of every request to set the tenant scope
-- ============================================================

CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.tenant_id', p_tenant_id::TEXT, TRUE);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Helper: clear_tenant_context
-- Call at the end of every request
-- ============================================================

CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.tenant_id', '', TRUE);
END;
$$ LANGUAGE plpgsql;