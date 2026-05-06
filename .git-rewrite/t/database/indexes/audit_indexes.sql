-- ═══════════════════════════════════════════════════════════════════════════════
-- PARWA — Audit Table Indexes
-- Week 26 Day 1 (Builder 1 Task)
-- Target: Query time < 10ms for indexed queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- Audit Logs Table Indexes (from schema.sql)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 1: Audit logs by tenant and action type
-- Purpose: Fast filtering of audit logs by action type within tenant
-- Query: SELECT * FROM audit_logs WHERE tenant_id = ? AND action_type = 'refund_issued'
-- Note: Already exists in schema.sql as idx_audit_logs_tenant_action
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'audit_logs' AND indexname = 'idx_audit_logs_tenant_action'
    ) THEN
        CREATE INDEX idx_audit_logs_tenant_action ON audit_logs(tenant_id, action_type);
    END IF;
END $$;

-- Index 2: Audit logs time-based queries
-- Purpose: Time-based queries on audit logs
-- Query: SELECT * FROM audit_logs WHERE created_at > ?
-- Note: Already exists in schema.sql as idx_audit_logs_created_at
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'audit_logs' AND indexname = 'idx_audit_logs_created_at'
    ) THEN
        CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
    END IF;
END $$;

-- Index 3: Audit logs by actor
-- Purpose: Fast filtering by actor type (ai, human, system)
-- Query: SELECT * FROM audit_logs WHERE actor_type = 'ai'
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_type
ON audit_logs(tenant_id, actor_type);

-- Index 4: Audit logs by user
-- Purpose: Fast lookup of audit logs for specific user
-- Query: SELECT * FROM audit_logs WHERE user_id = ?
CREATE INDEX IF NOT EXISTS idx_audit_logs_user
ON audit_logs(actor_id)
WHERE actor_type = 'human';

-- Index 5: Composite index for time-range queries
-- Purpose: Fast time-range queries within tenant
-- Query: SELECT * FROM audit_logs WHERE tenant_id = ? AND created_at BETWEEN ? AND ?
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_time
ON audit_logs(tenant_id, created_at DESC);

-- Index 6: Resource lookup index
-- Purpose: Fast lookup of audit logs by resource
-- Query: SELECT * FROM audit_logs WHERE resource_type = 'ticket' AND resource_id = ?
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource
ON audit_logs(tenant_id, resource_type, resource_id);

-- Index 7: Recent audit logs per tenant
-- Purpose: Fast lookup of recent audit logs for dashboard
-- Query: SELECT * FROM audit_logs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 50
CREATE INDEX IF NOT EXISTS idx_audit_logs_recent
ON audit_logs(tenant_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Audit Trails Table Indexes (Immutable Audit Trail)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 8: Audit trail by company
-- Purpose: Fast filtering by company for multi-tenant isolation
-- Query: SELECT * FROM audit_trails WHERE company_id = ?
CREATE INDEX IF NOT EXISTS idx_audit_trails_company
ON audit_trails(company_id);

-- Index 9: Audit trail by ticket
-- Purpose: Fast lookup of audit trail for a specific ticket
-- Query: SELECT * FROM audit_trails WHERE ticket_id = ?
CREATE INDEX IF NOT EXISTS idx_audit_trails_ticket
ON audit_trails(ticket_id)
WHERE ticket_id IS NOT NULL;

-- Index 10: Audit trail by actor
-- Purpose: Fast filtering by actor type
-- Query: SELECT * FROM audit_trails WHERE actor = 'ai_agent'
CREATE INDEX IF NOT EXISTS idx_audit_trails_actor
ON audit_trails(company_id, actor);

-- Index 11: Audit trail by action
-- Purpose: Fast filtering by action type
-- Query: SELECT * FROM audit_trails WHERE action = 'refund_approved'
CREATE INDEX IF NOT EXISTS idx_audit_trails_action
ON audit_trails(company_id, action);

-- Index 12: Audit trail time-based queries
-- Purpose: Fast time-based queries
-- Query: SELECT * FROM audit_trails WHERE company_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_audit_trails_time
ON audit_trails(company_id, created_at DESC);

-- Index 13: Hash chain verification index
-- Purpose: Fast lookup for hash chain verification
-- Query: SELECT * FROM audit_trails WHERE previous_hash = ?
CREATE INDEX IF NOT EXISTS idx_audit_trails_hash
ON audit_trails(previous_hash)
WHERE previous_hash IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- Financial Audit Trail Table Indexes (Week 25)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 14: Financial audit by customer
-- Purpose: Fast lookup of financial actions by customer
-- Query: SELECT * FROM financial_audit_trail WHERE customer_id = ?
-- Note: Already exists in migration 008 as ix_financial_audit_trail_customer
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'financial_audit_trail' AND indexname = 'ix_financial_audit_trail_customer'
    ) THEN
        CREATE INDEX ix_financial_audit_trail_customer
        ON financial_audit_trail(customer_id, timestamp DESC);
    END IF;
END $$;

-- Index 15: Financial audit by actor
-- Purpose: Fast lookup of financial actions by actor
-- Note: Already exists in migration 008 as ix_financial_audit_trail_actor
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'financial_audit_trail' AND indexname = 'ix_financial_audit_trail_actor'
    ) THEN
        CREATE INDEX ix_financial_audit_trail_actor
        ON financial_audit_trail(actor, timestamp DESC);
    END IF;
END $$;

-- Index 16: Financial audit by tenant and time
-- Purpose: Fast time-range queries within tenant
-- Query: SELECT * FROM financial_audit_trail WHERE tenant_id = ? ORDER BY timestamp DESC
CREATE INDEX IF NOT EXISTS ix_financial_audit_trail_tenant_time
ON financial_audit_trail(tenant_id, timestamp DESC);

-- Index 17: Financial audit by action type
-- Purpose: Fast filtering by action type
-- Query: SELECT * FROM financial_audit_trail WHERE action_type = 'refund'
CREATE INDEX IF NOT EXISTS ix_financial_audit_trail_action
ON financial_audit_trail(tenant_id, action_type, timestamp DESC);

-- Index 18: Financial audit by account
-- Purpose: Fast lookup by account ID
-- Query: SELECT * FROM financial_audit_trail WHERE account_id = ?
CREATE INDEX IF NOT EXISTS ix_financial_audit_trail_account
ON financial_audit_trail(account_id)
WHERE account_id IS NOT NULL;

-- Index 19: Financial audit by transaction
-- Purpose: Fast lookup by transaction ID
-- Query: SELECT * FROM financial_audit_trail WHERE transaction_id = ?
CREATE INDEX IF NOT EXISTS ix_financial_audit_trail_transaction
ON financial_audit_trail(transaction_id)
WHERE transaction_id IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- Compliance Records Table Indexes (Week 25)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 20: Compliance records by tenant
-- Purpose: Fast filtering by tenant
-- Query: SELECT * FROM compliance_records WHERE tenant_id = ?
CREATE INDEX IF NOT EXISTS ix_compliance_records_tenant
ON compliance_records(tenant_id, timestamp DESC);

-- Index 21: Compliance records by check type
-- Purpose: Fast filtering by check type (sox, finra, hipaa, pci_dss)
-- Query: SELECT * FROM compliance_records WHERE check_type = 'sox'
CREATE INDEX IF NOT EXISTS ix_compliance_records_check_type
ON compliance_records(tenant_id, check_type, timestamp DESC);

-- Index 22: Compliance records by status
-- Purpose: Fast filtering by status (passed, failed, warning)
-- Query: SELECT * FROM compliance_records WHERE passed = false
CREATE INDEX IF NOT EXISTS ix_compliance_records_passed
ON compliance_records(tenant_id, passed, timestamp DESC)
WHERE passed = false;

-- ─────────────────────────────────────────────────────────────────────────────
-- Fraud Alerts Table Indexes (Week 25)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 23: Fraud alerts by status
-- Purpose: Fast filtering by investigation status
-- Query: SELECT * FROM fraud_alerts WHERE investigation_status = 'pending'
-- Note: Already exists in migration 008 as ix_fraud_alerts_status
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'fraud_alerts' AND indexname = 'ix_fraud_alerts_status'
    ) THEN
        CREATE INDEX ix_fraud_alerts_status
        ON fraud_alerts(investigation_status, risk_level);
    END IF;
END $$;

-- Index 24: Fraud alerts by tenant
-- Purpose: Fast filtering by tenant
-- Query: SELECT * FROM fraud_alerts WHERE tenant_id = ?
CREATE INDEX IF NOT EXISTS ix_fraud_alerts_tenant
ON fraud_alerts(tenant_id, detected_at DESC);

-- Index 25: Fraud alerts by customer
-- Purpose: Fast lookup of fraud alerts by customer
-- Query: SELECT * FROM fraud_alerts WHERE customer_id = ?
CREATE INDEX IF NOT EXISTS ix_fraud_alerts_customer
ON fraud_alerts(tenant_id, customer_id);

-- Index 26: High-risk alerts index
-- Purpose: Fast lookup of high-risk pending alerts
-- Query: SELECT * FROM fraud_alerts WHERE risk_level = 'high' AND investigation_status = 'pending'
CREATE INDEX IF NOT EXISTS ix_fraud_alerts_high_risk
ON fraud_alerts(tenant_id, detected_at DESC)
WHERE risk_level = 'high' AND investigation_status = 'pending';

-- ─────────────────────────────────────────────────────────────────────────────
-- Complaint Tracking Table Indexes (Week 25)
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 27: Complaints by status
-- Purpose: Fast filtering by status
-- Query: SELECT * FROM complaint_tracking WHERE status = 'open'
-- Note: Already exists in migration 008 as ix_complaint_tracking_status
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'complaint_tracking' AND indexname = 'ix_complaint_tracking_status'
    ) THEN
        CREATE INDEX ix_complaint_tracking_status
        ON complaint_tracking(status, receipt_date DESC);
    END IF;
END $$;

-- Index 28: Complaints by tenant
-- Purpose: Fast filtering by tenant
-- Query: SELECT * FROM complaint_tracking WHERE tenant_id = ?
CREATE INDEX IF NOT EXISTS ix_complaint_tracking_tenant
ON complaint_tracking(tenant_id, complaint_date DESC);

-- Index 29: Complaints by customer
-- Purpose: Fast lookup of complaints by customer
-- Query: SELECT * FROM complaint_tracking WHERE customer_id = ?
CREATE INDEX IF NOT EXISTS ix_complaint_tracking_customer
ON complaint_tracking(tenant_id, customer_id);

-- Index 30: Complaints by type
-- Purpose: Fast filtering by complaint type
-- Query: SELECT * FROM complaint_tracking WHERE complaint_type = 'service'
CREATE INDEX IF NOT EXISTS ix_complaint_tracking_type
ON complaint_tracking(tenant_id, complaint_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- Index Statistics and Monitoring
-- ─────────────────────────────────────────────────────────────────────────────

-- Analyze tables after index creation
ANALYZE audit_logs;
ANALYZE audit_trails;
ANALYZE financial_audit_trail;
ANALYZE compliance_records;
ANALYZE fraud_alerts;
ANALYZE complaint_tracking;

-- Comments for documentation
COMMENT ON INDEX idx_audit_logs_actor_type IS 'Audit logs by actor type (ai/human/system)';
COMMENT ON INDEX idx_audit_logs_user IS 'Audit logs by user (partial, human actors only)';
COMMENT ON INDEX idx_audit_logs_tenant_time IS 'Time-range queries within tenant';
COMMENT ON INDEX idx_audit_logs_resource IS 'Resource lookup by type and ID';
COMMENT ON INDEX idx_audit_logs_recent IS 'Recent audit logs per tenant for dashboard';
COMMENT ON INDEX idx_audit_trails_company IS 'Audit trail by company';
COMMENT ON INDEX idx_audit_trails_ticket IS 'Audit trail by ticket (partial)';
COMMENT ON INDEX idx_audit_trails_actor IS 'Audit trail by actor';
COMMENT ON INDEX idx_audit_trails_action IS 'Audit trail by action';
COMMENT ON INDEX idx_audit_trails_time IS 'Audit trail time-based queries';
COMMENT ON INDEX idx_audit_trails_hash IS 'Hash chain verification (partial)';
COMMENT ON INDEX ix_financial_audit_trail_tenant_time IS 'Financial audit by tenant and time';
COMMENT ON INDEX ix_financial_audit_trail_action IS 'Financial audit by action type';
COMMENT ON INDEX ix_financial_audit_trail_account IS 'Financial audit by account (partial)';
COMMENT ON INDEX ix_financial_audit_trail_transaction IS 'Financial audit by transaction (partial)';
COMMENT ON INDEX ix_compliance_records_tenant IS 'Compliance records by tenant';
COMMENT ON INDEX ix_compliance_records_check_type IS 'Compliance records by check type';
COMMENT ON INDEX ix_compliance_records_passed IS 'Failed compliance checks (partial)';
COMMENT ON INDEX ix_fraud_alerts_tenant IS 'Fraud alerts by tenant';
COMMENT ON INDEX ix_fraud_alerts_customer IS 'Fraud alerts by customer';
COMMENT ON INDEX ix_fraud_alerts_high_risk IS 'High-risk pending alerts (partial)';
COMMENT ON INDEX ix_complaint_tracking_tenant IS 'Complaints by tenant';
COMMENT ON INDEX ix_complaint_tracking_customer IS 'Complaints by customer';
COMMENT ON INDEX ix_complaint_tracking_type IS 'Complaints by type';
