-- ════════════════════════════════════════════════════════════════
-- PARWA — PostgreSQL Initial Schema
-- Week 2 Day 1 (Agent 4 Task)
-- ════════════════════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────
-- Tenants (Organizations)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(50) NOT NULL DEFAULT 'mini', -- 'mini', 'standard', 'high'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_tenants_tier ON tenants(tier);

-- ─────────────────────────────────────────────────────────────────
-- Users (Dashboard Access)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'agent', -- 'admin', 'manager', 'agent'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id);

-- ─────────────────────────────────────────────────────────────────
-- API Keys (External Integrations like Shopify, Twilio)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    permissions JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_api_keys_tenant_id ON api_keys(tenant_id);

-- ─────────────────────────────────────────────────────────────────
-- Customers (End-Users interacting with PARWA)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    external_id VARCHAR(255), -- E.g., Shopify Customer ID
    email VARCHAR(255),
    phone VARCHAR(50),
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, external_id)
);

CREATE INDEX idx_customers_tenant_email ON customers(tenant_id, email);
CREATE INDEX idx_customers_tenant_phone ON customers(tenant_id, phone);

-- ─────────────────────────────────────────────────────────────────
-- Sessions (Conversations)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    channel VARCHAR(50) NOT NULL, -- 'web', 'sms', 'voice'
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'closed', 'escalated'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_tenant_customer ON sessions(tenant_id, customer_id);

-- ─────────────────────────────────────────────────────────────────
-- Interactions (Chat/Voice logs)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    model_used VARCHAR(100), -- Which tier of AI handled this
    tokens_prompt INTEGER DEFAULT 0,
    tokens_completion INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_interactions_session_id ON interactions(session_id);

-- ─────────────────────────────────────────────────────────────────
-- Human Corrections (Agent Lightning Loop)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS human_corrections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    interaction_id UUID REFERENCES interactions(id) ON DELETE CASCADE,
    corrected_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    original_prompt TEXT NOT NULL,
    ai_draft_response TEXT NOT NULL,
    human_approved_response TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    exported_for_training BOOLEAN DEFAULT FALSE,
    exported_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_corrections_training ON human_corrections(tenant_id, exported_for_training);

-- ─────────────────────────────────────────────────────────────────
-- Audit Logs (Financial & Security Actions)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    actor_type VARCHAR(50) NOT NULL, -- 'ai', 'human', 'system'
    actor_id UUID, -- References users(id) or ai model
    action_type VARCHAR(100) NOT NULL, -- 'refund_issued', 'discount_applied', 'pii_scrubbed'
    resource_type VARCHAR(100), 
    resource_id VARCHAR(255),
    details JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

CREATE INDEX idx_audit_logs_tenant_action ON audit_logs(tenant_id, action_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Update triggers for timestamp columns
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenant_modtime
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TRIGGER update_user_modtime
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TRIGGER update_customer_modtime
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TRIGGER update_session_modtime
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
