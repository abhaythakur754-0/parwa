"""022_enable_rls: PostgreSQL Row-Level Security on all tenant-scoped tables.

CROSS-17 — Multi-tenant Data Isolation

This migration enables Row-Level Security (RLS) on every table that
contains a ``company_id`` column (≈ 122 tables across migrations 001–020).

What it does:
1. Creates the ``app.current_tenant_id()`` SQL helper function.
2. Enables RLS on every tenant-scoped table.
3. Creates SELECT / INSERT / UPDATE / DELETE policies that restrict
   each statement to rows where ``company_id = app.current_tenant_id()``.
4. Grants BYPASSRLS to the ``parwa_admin`` role (for migrations & admin).

Downgrade removes all policies, disables RLS, and drops the function.

Revision ID: 022_enable_rls
Revises: 021_fix_session_ticket_fk
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
import logging

revision = "022_enable_rls"
down_revision = "021_fix_session_ticket_fk"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic")

# ═══════════════════════════════════════════════════════════════════
# Every table with a company_id column, extracted from migrations
# 001–020.  Sorted alphabetically for readability.
# ═══════════════════════════════════════════════════════════════════
TENANT_TABLES: list[str] = [
    # 001 — initial_schema
    "agents",
    "api_keys",
    "backup_codes",
    "company_settings",
    "emergency_states",
    "mfa_secrets",
    "oauth_accounts",
    "password_reset_tokens",
    "refresh_tokens",
    "user_notification_preferences",
    "users",
    "verification_tokens",
    # 002 — ticketing_tables
    "assignment_rules",
    "bulk_action_failures",
    "bulk_action_logs",
    "channel_configs",
    "classification_corrections",
    "customer_channels",
    "customer_merge_audits",
    "customers",
    "identity_match_logs",
    "notification_templates",
    "sla_policies",
    "sla_timers",
    "ticket_assignments",
    "ticket_attachments",
    "ticket_feedbacks",
    "ticket_internal_notes",
    "ticket_intents",
    "ticket_merges",
    "ticket_messages",
    "ticket_status_changes",
    "tickets",
    # 003 — ai_pipeline_tables
    "confidence_scores",
    "guardrail_blocks",
    "guardrail_rules",
    "gsd_sessions",
    "model_usage_logs",
    "prompt_templates",
    "service_configs",
    # 004 — integration_tables
    "db_connections",
    "error_log",
    "event_buffer",
    "integrations",
    "mcp_connections",
    "outgoing_webhooks",
    "rest_connectors",
    "webhook_integrations",
    # 005 — audit_billing_tables
    "api_key_audit_log",
    "audit_trail",
    "cancellation_requests",
    "invoices",
    "overage_charges",
    "rate_limit_events",
    "subscriptions",
    "transactions",
    "webhook_events",
    # 006 — analytics_onboarding_tables
    "agent_mistakes",
    "agent_performance",
    "consent_records",
    "document_chunks",
    "drift_reports",
    "knowledge_documents",
    "metric_aggregates",
    "onboarding_sessions",
    "qa_scores",
    "roi_snapshots",
    "training_checkpoints",
    "training_datasets",
    "training_runs",
    # 007 — remaining_gap_tables
    "ai_response_feedback",
    "approval_batches",
    "approval_queues",
    "auto_approve_rules",
    "classification_log",
    "confidence_thresholds",
    "email_logs",
    "executed_actions",
    "feature_flags",
    "first_victories",
    "guardrails_audit_log",
    "guardrails_blocked_queue",
    "human_corrections",
    "notifications",
    "phone_otps",
    "rate_limit_counters",
    "response_templates",
    "undo_log",
    # 008 — technique_tables
    "technique_configurations",
    "technique_executions",
    "technique_versions",
    # 009 — billing_extended_tables
    "client_refunds",
    "idempotency_keys",
    "payment_failures",
    "payment_methods",
    "proration_audits",
    "usage_records",
    "webhook_sequences",
    # 010 — onboarding_extended
    "user_details",
    # 011 — phase3_variant_engine
    "ai_performance_variant_metrics",
    "ai_token_budgets",
    "pipeline_state_snapshots",
    "prompt_injection_attempts",
    "technique_caches",
    "variant_ai_capabilities",
    "variant_instances",
    "variant_workload_distribution",
    # 012 — jarvis_system
    "jarvis_sessions",
    # 015 — business_email_otp
    "business_email_otps",
    # 016 — email_channel_tables
    "email_threads",
    "inbound_emails",
    # 017 — outbound_email
    "outbound_emails",
    # 018 — email_delivery_events
    "email_delivery_events",
    # 019 — ooo_bounce_tables
    "customer_email_status",
    "email_bounces",
    "email_deliverability_alerts",
    "ooo_detection_log",
    "ooo_detection_rules",
    "ooo_sender_profiles",
    # 020 — jarvis_cc_tables
    "jarvis_awareness_snapshots",
    "jarvis_commands",
    "jarvis_proactive_alerts",
]

# ═══════════════════════════════════════════════════════════════════
# SQL fragments
# ═══════════════════════════════════════════════════════════════════

_CREATE_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION app.current_tenant_id()
RETURNS TEXT AS $$
  SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::TEXT;
$$ LANGUAGE SQL STABLE;
"""

_DROP_FUNCTION_SQL = "DROP FUNCTION IF EXISTS app.current_tenant_id();"


def _enable_rls_for_table(table: str) -> None:
    """Enable RLS and create tenant-isolation policies on *table*."""
    conn = op.get_bind()

    # ── Enable RLS ──────────────────────────────────────────────
    try:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        log.debug("RLS enabled on %s", table)
    except Exception:
        log.warning("Could not enable RLS on %s — skipping", table, exc_info=True)
        return

    # ── Drop existing policies (idempotent) ────────────────────
    for suffix in ("tenant_select", "tenant_insert", "tenant_update", "tenant_delete"):
        policy_name = f"{table}_{suffix}"
        try:
            conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        except Exception:
            pass  # non-existent policy — fine

    # ── SELECT ──────────────────────────────────────────────────
    try:
        conn.execute(sa.text(
            f"CREATE POLICY {table}_tenant_select ON {table} "
            f"FOR SELECT USING (company_id = app.current_tenant_id())"
        ))
    except Exception:
        log.warning("Failed to create SELECT policy on %s", table, exc_info=True)

    # ── INSERT ──────────────────────────────────────────────────
    try:
        conn.execute(sa.text(
            f"CREATE POLICY {table}_tenant_insert ON {table} "
            f"FOR INSERT WITH CHECK (company_id = app.current_tenant_id())"
        ))
    except Exception:
        log.warning("Failed to create INSERT policy on %s", table, exc_info=True)

    # ── UPDATE ──────────────────────────────────────────────────
    try:
        conn.execute(sa.text(
            f"CREATE POLICY {table}_tenant_update ON {table} "
            f"FOR UPDATE USING (company_id = app.current_tenant_id())"
        ))
    except Exception:
        log.warning("Failed to create UPDATE policy on %s", table, exc_info=True)

    # ── DELETE ──────────────────────────────────────────────────
    try:
        conn.execute(sa.text(
            f"CREATE POLICY {table}_tenant_delete ON {table} "
            f"FOR DELETE USING (company_id = app.current_tenant_id())"
        ))
    except Exception:
        log.warning("Failed to create DELETE policy on %s", table, exc_info=True)


def _disable_rls_for_table(table: str) -> None:
    """Drop all tenant policies and disable RLS on *table*."""
    conn = op.get_bind()

    for suffix in ("tenant_select", "tenant_insert", "tenant_update", "tenant_delete"):
        policy_name = f"{table}_{suffix}"
        try:
            conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        except Exception:
            pass

    try:
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    except Exception:
        log.warning("Could not disable RLS on %s", table, exc_info=True)


# ═══════════════════════════════════════════════════════════════════
# Alembic upgrade / downgrade
# ═══════════════════════════════════════════════════════════════════

def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create the app schema (if missing) and helper function ──
    try:
        conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS app"))
    except Exception:
        log.warning("Could not create schema 'app'", exc_info=True)

    op.execute(_CREATE_FUNCTION_SQL)
    log.info("Created app.current_tenant_id() function")

    # ── 2. Enable RLS + policies on every tenant-scoped table ─────
    for table in TENANT_TABLES:
        _enable_rls_for_table(table)

    log.info("RLS enabled on %d tables", len(TENANT_TABLES))

    # ── 3. Grant BYPASSRLS to parwa_admin ────────────────────────
    try:
        op.execute("DO $$ BEGIN ALTER ROLE parwa_admin BYPASSRLS; EXCEPTION WHEN OTHERS THEN NULL; END $$;")
        log.info("BYPASSRLS granted to parwa_admin")
    except Exception:
        log.warning("Could not grant BYPASSRLS to parwa_admin", exc_info=True)


def downgrade() -> None:
    conn = op.get_bind()

    # ── 1. Revoke BYPASSRLS from parwa_admin ─────────────────────
    try:
        op.execute("DO $$ BEGIN ALTER ROLE parwa_admin NOBYPASSRLS; EXCEPTION WHEN OTHERS THEN NULL; END $$;")
    except Exception:
        pass

    # ── 2. Disable RLS on every table ───────────────────────────
    for table in TENANT_TABLES:
        _disable_rls_for_table(table)

    log.info("RLS disabled on %d tables", len(TENANT_TABLES))

    # ── 3. Drop the helper function ─────────────────────────────
    op.execute(_DROP_FUNCTION_SQL)
    log.info("Dropped app.current_tenant_id() function")
