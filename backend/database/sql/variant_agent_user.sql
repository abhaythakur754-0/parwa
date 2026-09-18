-- ═══════════════════════════════════════════════════════════════════
-- variant_agent — limited DB user for the z.ai SPACE worker
-- ═══════════════════════════════════════════════════════════════════
-- Run ONCE as the MASTER database owner (e.g. in the Supabase SQL editor
-- or psql as postgres). The space worker then connects ONLY as
-- variant_agent and refuses to boot if the grants are wrong.
--
-- What this user CAN do:
--   SELECT/INSERT/UPDATE on the tables the 8-node pipeline touches
--   (claim tickets, write AI replies, wiki write-back, checkpoints)
-- What this user can NEVER do:
--   DELETE anything, change the schema, touch auth/billing/secret
--   tables, or see Jarvis's own queue (two systems, fully separate).
-- ═══════════════════════════════════════════════════════════════════

-- 1 ── Create the user. CHANGE THE PASSWORD before running. ─────────
CREATE ROLE variant_agent LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';

GRANT CONNECT ON DATABASE postgres TO variant_agent;  -- change db name if different
GRANT USAGE ON SCHEMA public TO variant_agent;

-- 2 ── Broad working grants (the pipeline reads/writes many tables;
--      a missed table would crash tickets mid-run). ─────────────────
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO variant_agent;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO variant_agent;

-- Future tables created by alembic get the same grants automatically.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO variant_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO variant_agent;

-- 3 ── Hard denylist: REVOKE everything on secrets, money, auth. ────
REVOKE ALL ON public.users, public.user_details,
  public.mfa_secrets, public.backup_codes, public.refresh_tokens,
  public.oauth_accounts, public.password_reset_tokens,
  public.verification_tokens, public.business_email_otps, public.phone_otps,
  public.api_keys, public.api_key_audit_log, public.provider_configurations,
  public.db_connections, public.audit_trail,
  public.transactions, public.invoices, public.payment_methods,
  public.payment_failures, public.subscriptions, public.overage_charges,
  public.proration_audits, public.paddle_webhook_events,
  public.paddle_reconciliation_reports, public.client_refunds,
  public.flexpay_plans, public.flexpay_installments,
  public.cancellation_requests, public.newsletter_subscribers,
  public.demo_sessions, public.onboarding_sessions
FROM variant_agent;

-- Integration configs are readable (Node 5 executes integration actions)
-- but NEVER writable by the worker:
REVOKE INSERT, UPDATE ON public.rest_connectors, public.mcp_connections,
  public.superglue_action_safety
FROM variant_agent;

-- Jarvis is a SEPARATE system (P-001): the worker must never touch
-- Jarvis's queue, sessions, or messages.
DO $$
DECLARE t text;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables
           WHERE schemaname = 'public' AND tablename LIKE 'jarvis_%'
  LOOP
    EXECUTE format('REVOKE ALL ON public.%I FROM variant_agent', t);
  END LOOP;
END $$;

-- 4 ── Heartbeat table (Jarvis awareness Domain 12 reads this). ─────
CREATE TABLE IF NOT EXISTS public.space_worker_heartbeat (
  worker_id          TEXT PRIMARY KEY,
  hostname           TEXT,
  concurrency        INTEGER NOT NULL DEFAULT 0,
  status             TEXT NOT NULL DEFAULT 'running',  -- running | stopped
  tickets_in_progress INTEGER NOT NULL DEFAULT 0,
  started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_beat_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  version            TEXT
);
GRANT SELECT, INSERT, UPDATE ON public.space_worker_heartbeat TO variant_agent;

-- 5 ── LangGraph checkpoint tables (used by the pipeline checkpointer).
--      They already exist in production (Render uses PostgresSaver).
--      The broad grants in step 2 cover them. If a fresh database has
--      none yet, let Render boot once (it creates them), then re-run
--      step 2 grants.

-- ═══════════════════════════════════════════════════════════════════
-- VERIFY (run as variant_agent — every DELETE must FAIL):
--   DELETE FROM tickets WHERE false;   -- expect: permission denied ✅
--   SELECT count(*) FROM users;        -- expect: permission denied ✅
--   SELECT count(*) FROM jarvis_message_queue;  -- permission denied ✅
-- ═══════════════════════════════════════════════════════════════════
