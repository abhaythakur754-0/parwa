-- ============================================================
-- JARVIS Wave 1 — Database Schema
-- All tables for Jarvis Operating System
-- Run this in Supabase SQL Editor
--
-- Design principles:
--   1. Every table has tenant_id for multi-tenant isolation
--   2. RLS enabled on every table
--   3. TEXT tenant_id (matches existing PARWA auth system)
--   4. UUID primary keys (except audit_trail which is SERIAL for immutability)
--   5. No duplicate data — foreign keys reference, never copy
--   6. 30-day retention on notifications (GDPR)
-- ============================================================

-- ============================================================
-- 1. NOTIFICATIONS (replaces in-memory notification_center.py)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    notification_key TEXT NOT NULL UNIQUE,          -- PARWA-NFY-XXX
    type            TEXT NOT NULL,                   -- stuck_ticket, quota_low, integration_down, accuracy_drop, sla_risk, policy_change
    priority        TEXT NOT NULL DEFAULT 'MEDIUM',  -- CRITICAL, HIGH, MEDIUM, LOW
    priority_score  DECIMAL(4,4) NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    related_tickets TEXT[] DEFAULT '{}',
    batch_key       TEXT,
    source_data     JSONB DEFAULT '{}',
    is_read         BOOLEAN DEFAULT FALSE,
    is_resolved     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'
);

CREATE INDEX idx_jn_tenant_status ON jarvis_notifications(tenant_id, is_resolved);
CREATE INDEX idx_jn_priority ON jarvis_notifications(tenant_id, priority, created_at DESC);
CREATE INDEX idx_jn_batch ON jarvis_notifications(tenant_id, batch_key) WHERE NOT is_resolved;

-- ============================================================
-- 2. SYSTEM FLAGS (Jarvis → PARWA communication)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_system_flags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    flag_type       TEXT NOT NULL,
    flag_value      TEXT NOT NULL,
    scope           TEXT NOT NULL DEFAULT 'global',  -- global, per_ticket, per_channel, per_variant
    target_id       TEXT,                             -- ticket_id, channel_name, variant_id
    set_by          TEXT NOT NULL,                    -- email or 'jarvis_auto'
    reason          TEXT,
    expires_at      TIMESTAMPTZ,                      -- NULL = permanent
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_jsf_tenant_type ON jarvis_system_flags(tenant_id, flag_type, revoked_at);
CREATE INDEX idx_jsf_active ON jarvis_system_flags(tenant_id)
    WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > NOW());

-- ============================================================
-- 3. AUDIT TRAIL (immutable append-only — no UPDATE/DELETE)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_audit_trail (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    action          TEXT NOT NULL,
    actor_email     TEXT NOT NULL,
    target_type     TEXT,              -- ticket, flag, notification, agent, skill
    target_id       TEXT,
    payload         JSONB DEFAULT '{}',
    previous_hash   TEXT,
    current_hash    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jat_tenant ON jarvis_audit_trail(tenant_id, created_at DESC);
CREATE INDEX idx_jat_action ON jarvis_audit_trail(tenant_id, action);
CREATE INDEX idx_jat_target ON jarvis_audit_trail(tenant_id, target_type, target_id);

-- Immutable trigger — prevent any UPDATE or DELETE
CREATE OR REPLACE FUNCTION jarvis_audit_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'jarvis_audit_trail is immutable — no UPDATE or DELETE allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS jarvis_audit_no_modify ON jarvis_audit_trail;
CREATE TRIGGER jarvis_audit_no_modify
    BEFORE UPDATE OR DELETE ON jarvis_audit_trail
    FOR EACH ROW EXECUTE FUNCTION jarvis_audit_immutable();

-- ============================================================
-- 4. QUALITY SCORES (written by PARWA Node 6, read by Jarvis)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_quality_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    agent_id        TEXT,
    ticket_id       TEXT,
    overall_score   DECIMAL(3,2),
    confidence_score DECIMAL(3,2),
    sentiment_score DECIMAL(3,2),
    resolution_path TEXT,              -- simple, complex, escalated, stuck
    nodes_reached   TEXT[] DEFAULT '{}',
    llm_calls       INT DEFAULT 0,
    tokens_used     INT DEFAULT 0,
    model_used      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jqs_tenant_date ON jarvis_quality_scores(tenant_id, created_at DESC);
CREATE INDEX idx_jqs_score ON jarvis_quality_scores(tenant_id, overall_score);

-- ============================================================
-- 5. QUALITY ALERTS
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_quality_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    alert_type      TEXT NOT NULL,       -- quality_drop, recurring_error, confidence_drift, csat_decline
    severity        TEXT NOT NULL DEFAULT 'medium',
    message         TEXT NOT NULL,
    metric_name     TEXT,
    metric_value    DECIMAL(5,2),
    threshold_value DECIMAL(5,2),
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jqa_tenant ON jarvis_quality_alerts(tenant_id, resolved, created_at DESC);

-- ============================================================
-- 6. TRAINING SUGGESTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_training_suggestions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,      -- new_knowledge, policy_update, skill_gap, kb_gap
    description     TEXT NOT NULL,
    priority        INT DEFAULT 0,
    related_tickets TEXT[] DEFAULT '{}',
    implemented     BOOLEAN DEFAULT FALSE,
    implemented_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jts_tenant ON jarvis_training_suggestions(tenant_id, implemented, priority);

-- ============================================================
-- 7. AGENT CONFIGS (virtual agent registry)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_agent_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    variant_type    TEXT NOT NULL,       -- parwa, mini, trivya, high
    status          TEXT NOT NULL DEFAULT 'active',
    capabilities    TEXT[] DEFAULT '{}',
    config          JSONB DEFAULT '{}',
    created_by      TEXT NOT NULL,
    provisioning_id TEXT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jac_tenant ON jarvis_agent_configs(tenant_id, status);

-- ============================================================
-- 8. CLIENT SKILLS (taught via chat)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_client_skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    skill_name      TEXT NOT NULL,
    description     TEXT,
    steps_json      JSONB NOT NULL,
    source          TEXT DEFAULT 'chat',
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_jcs_name ON jarvis_client_skills(tenant_id, skill_name);

-- ============================================================
-- 9. FEATURE FLAGS
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_feature_flags (
    tenant_id       TEXT NOT NULL,
    feature_name    TEXT NOT NULL,
    enabled         BOOLEAN DEFAULT FALSE,
    rollout_percentage INT DEFAULT 100,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (tenant_id, feature_name)
);

-- ============================================================
-- 10. CLIENT LEGAL CONFIG
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_client_legal (
    tenant_id       TEXT PRIMARY KEY,
    allows_data_sharing BOOLEAN DEFAULT FALSE,
    custom_sla_uptime DECIMAL(5,2) DEFAULT 99.50,
    custom_sla_credit_pct INT DEFAULT 10,
    compliance_framework TEXT DEFAULT 'GDPR',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 11. AGENT PROVISIONING LOGS
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_provisioning_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    variant_type    TEXT NOT NULL,
    count           INT NOT NULL,
    agent_ids       UUID[] DEFAULT '{}',
    expires_at      TIMESTAMPTZ,
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 12. TRAINING DATA (from approvals/rejections)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_training_data (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    ticket_id       TEXT,
    interaction_type TEXT NOT NULL,     -- approved, rejected, edited, corrected
    original_prompt TEXT,
    corrected_prompt TEXT,
    user_feedback   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jtd_tenant ON jarvis_training_data(tenant_id, interaction_type, created_at DESC);

-- ============================================================
-- 13. BATCH QUEUE (replaces in-memory batch buffer)
-- ============================================================

CREATE TABLE IF NOT EXISTS jarvis_batch_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    batch_key       TEXT NOT NULL,
    ticket_ids      TEXT[] NOT NULL,
    confidence_min  DECIMAL(3,2),
    confidence_max  DECIMAL(3,2),
    risk_level      TEXT,
    total_amount    DECIMAL(10,2) DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ DEFAULT NOW() + INTERVAL '5 minutes'
);

CREATE INDEX idx_jbq_tenant ON jarvis_batch_queue(tenant_id, status, created_at DESC);

-- ============================================================
-- ROW-LEVEL SECURITY — All Jarvis tables
-- ============================================================

ALTER TABLE jarvis_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_system_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_audit_trail ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_quality_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_quality_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_training_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_agent_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_client_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_client_legal ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_provisioning_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_training_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_batch_queue ENABLE ROW LEVEL SECURITY;

-- Tenant isolation policy — applied to ALL jarvis tables
-- NULL tenant_id context = superuser access (for admin operations)
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT table_name FROM information_schema.tables
             WHERE table_schema = 'public' AND table_name LIKE 'jarvis_%'
    LOOP
        EXECUTE format(
            'CREATE POLICY jarvis_tenant_isolation ON %I
             USING (tenant_id = current_setting(''app.tenant_id'', TRUE)
                    OR current_setting(''app.tenant_id'', TRUE) IS NULL)',
            t
        );
    END LOOP;
END;
$$;

-- ============================================================
-- AUTO-CLEANUP: Expire old notifications (run as daily cron)
-- ============================================================

CREATE OR REPLACE FUNCTION jarvis_expire_notifications()
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM jarvis_notifications WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- HELPER: Get active flags for a tenant (used by PARWA)
-- ============================================================

CREATE OR REPLACE FUNCTION jarvis_get_active_flags(p_tenant_id TEXT)
RETURNS TABLE (
    id UUID, flag_type TEXT, flag_value TEXT, scope TEXT,
    target_id TEXT, set_by TEXT, reason TEXT, expires_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT f.id, f.flag_type, f.flag_value, f.scope,
           f.target_id, f.set_by, f.reason, f.expires_at
    FROM jarvis_system_flags f
    WHERE f.tenant_id = p_tenant_id
      AND f.revoked_at IS NULL
      AND (f.expires_at IS NULL OR f.expires_at > NOW());
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;