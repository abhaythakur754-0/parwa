-- ════════════════════════════════════════════════════════════════
-- PARWA — PostgreSQL Row Level Security (RLS) Policies
-- Week 3 Day 3 (Agent 2 Task)
-- ════════════════════════════════════════════════════════════════

-- Enable Row Level Security for all core tables
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_trails ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────────
-- Policies for 'companies'
-- ─────────────────────────────────────────────────────────────────
-- A company can only see its own record
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'company_isolation_policy' AND tablename = 'companies') THEN
        CREATE POLICY company_isolation_policy ON companies
        USING (id = current_setting('app.current_company_id', TRUE)::uuid);
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Policies for 'users'
-- ─────────────────────────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'user_isolation_policy' AND tablename = 'users') THEN
        CREATE POLICY user_isolation_policy ON users
        USING (company_id = current_setting('app.current_company_id', TRUE)::uuid);
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Policies for 'licenses'
-- ─────────────────────────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'license_isolation_policy' AND tablename = 'licenses') THEN
        CREATE POLICY license_isolation_policy ON licenses
        USING (company_id = current_setting('app.current_company_id', TRUE)::uuid);
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Policies for 'subscriptions'
-- ─────────────────────────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'subscription_isolation_policy' AND tablename = 'subscriptions') THEN
        CREATE POLICY subscription_isolation_policy ON subscriptions
        USING (company_id = current_setting('app.current_company_id', TRUE)::uuid);
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Policies for 'support_tickets'
-- ─────────────────────────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'ticket_isolation_policy' AND tablename = 'support_tickets') THEN
        CREATE POLICY ticket_isolation_policy ON support_tickets
        USING (company_id = current_setting('app.current_company_id', TRUE)::uuid);
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Policies for 'audit_trails'
-- ─────────────────────────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'audit_isolation_policy' AND tablename = 'audit_trails') THEN
        CREATE POLICY audit_isolation_policy ON audit_trails
        USING (company_id = current_setting('app.current_company_id', TRUE)::uuid);
    END IF;
END $$;

-- Note: In a real environment, we would also grant specific permissions (ALL, SELECT, etc.)
-- to a restricted database user that doesn't bypass RLS.
