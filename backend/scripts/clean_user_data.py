"""
PARWA — Clean User Data Script

Keeps: Account structure (companies, users with email/password, agents,
       variant_instances, company_settings, channels, channel_configs,
       sla_policies, technique_configurations, ai_token_budgets)

Deletes: All user-generated data (tickets, customers, messages,
          sessions, logs, etc.)

Usage:
    python scripts/clean_user_data.py

Set DATABASE_URL env var, or it defaults to the alembic.ini value.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Get DATABASE_URL from env or fall back to alembic.ini default."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    # Default from alembic.ini
    return "postgresql://parwa:parwa@localhost:5432/parwa"


# Tables to PRESERVE (account structure + system config)
KEEP_TABLES = {
    # Core structure (companies kept, users cleaned)
    "companies",
    "agents",
    "variant_instances",
    "company_settings",
    # System config / seed data
    "channels",
    "channel_configs",
    "sla_policies",
    "technique_configurations",
    "ai_token_budgets",
    "variant_ai_capabilities",
    "variant_workload_distribution",
    "shadow_mode_configs",
    "notification_templates",
    "canned_responses",
    "response_templates",
    "feature_flags",
    "confidence_thresholds",
    "auto_approve_rules",
    "prompt_templates",
    "service_configs",
    "api_providers",
    "guardrail_rules",
    "sms_channel_configs",
    "voice_channel_configs",
    "chat_widget_configs",
    "custom_fields",
    "assignment_rules",
    "ooo_detection_rules",
    "variant_limits",
}

# Tables to CLEAN (user-generated data, session data, logs)
# We derive these from ALL tables minus KEEP_TABLES
CLEAN_TABLES = {
    # Tickets & customer data
    "tickets",
    "ticket_messages",
    "ticket_attachments",
    "ticket_internal_notes",
    "ticket_status_changes",
    "ticket_assignments",
    "ticket_merges",
    "ticket_feedbacks",
    "ticket_intents",
    "ticket_collisions",
    "ticket_triggers",
    "bulk_action_logs",
    "bulk_action_failures",
    "customers",
    "customer_channels",
    "customer_merge_audits",
    "identity_match_logs",
    "classification_corrections",
    # Jarvis / onboarding sessions
    "jarvis_sessions",
    "jarvis_messages",
    "jarvis_knowledge_used",
    "jarvis_action_tickets",
    "jarvis_awareness_snapshots",
    "jarvis_commands",
    "jarvis_proactive_alerts",
    "jarvis_activity_events",
    "onboarding_sessions",
    "consent_records",
    "demo_sessions",
    "knowledge_documents",
    "document_chunks",
    # Chat widget sessions
    "chat_widget_sessions",
    "chat_widget_messages",
    # Users / login accounts (wrongly created, clean them all)
    "users",
    # Auth / tokens (session data)
    "refresh_tokens",
    "mfa_secrets",
    "backup_codes",
    "verification_tokens",
    "password_reset_tokens",
    "oauth_accounts",
    "phone_otps",
    "business_email_otps",
    # User preferences
    "user_notification_preferences",
    "notification_preferences",
    "user_details",
    # Emergency states
    "emergency_states",
    # API keys (user-created)
    "api_keys",
    "api_key_audit_log",
    # Email data
    "inbound_emails",
    "email_threads",
    "outbound_emails",
    "email_delivery_events",
    "email_bounces",
    "customer_email_status",
    "email_deliverability_alerts",
    "email_logs",
    # SMS data
    "sms_messages",
    "sms_conversations",
    # Voice data
    "voice_calls",
    "voice_conversations",
    # Billing / transactions
    "subscriptions",
    "invoices",
    "overage_charges",
    "transactions",
    "cancellation_requests",
    "client_refunds",
    "payment_methods",
    "usage_records",
    "idempotency_keys",
    "webhook_sequences",
    "proration_audits",
    "payment_failures",
    "paddle_webhook_events",
    "paddle_reconciliation_reports",
    # AI pipeline data
    "ai_agent_assignments",
    "technique_caches",
    "technique_executions",
    "technique_versions",
    "prompt_injection_attempts",
    "ai_performance_variant_metrics",
    "pipeline_state_snapshots",
    "gsd_sessions",
    "confidence_scores",
    "guardrail_blocks",
    "model_usage_logs",
    "classification_log",
    "guardrails_audit_log",
    "guardrails_blocked_queue",
    "ai_response_feedback",
    "human_corrections",
    "langgraph_dlq_entries",
    # Analytics / metrics
    "metric_aggregates",
    "roi_snapshots",
    "drift_reports",
    "qa_scores",
    "training_runs",
    "training_datasets",
    "training_checkpoints",
    "agent_mistakes",
    "agent_performance",
    # Approval / action data
    "approval_queues",
    "approval_batches",
    "executed_actions",
    "undo_log",
    # Webhooks / integrations (user-configured)
    "webhook_events",
    "integrations",
    "rest_connectors",
    "webhook_integrations",
    "mcp_connections",
    "db_connections",
    "event_buffer",
    "error_log",
    "audit_trail",
    "outgoing_webhooks",
    # Shadow mode results
    "shadow_mode_results",
    # OOO detection logs
    "ooo_detection_log",
    "ooo_sender_profiles",
    # Activity / notifications
    "activity_log",
    "notifications",
    "notification_logs",
    "first_victories",
    # Rate limiting
    "rate_limit_counters",
    "rate_limit_events",
    # Newsletter
    "newsletter_subscribers",
}


def clean_database(database_url: str, dry_run: bool = False):
    """Clean all user data from the database, keeping account structure."""
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all existing tables
        result = session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        ))
        existing_tables = {row[0] for row in result.fetchall()}

        # Determine which tables to clean (only existing ones)
        tables_to_clean = CLEAN_TABLES & existing_tables
        tables_kept = KEEP_TABLES & existing_tables

        print("=" * 60)
        print("  PARWA — Clean User Data Script")
        print("=" * 60)
        print(f"\n  Database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
        print(f"  Dry run: {dry_run}")
        print(f"\n  Tables PRESERVED ({len(tables_kept)}):")
        for t in sorted(tables_kept):
            print(f"    ✅ {t}")
        print(f"\n  Tables TO CLEAN ({len(tables_to_clean)}):")
        for t in sorted(tables_to_clean):
            print(f"    🗑️  {t}")

        if not tables_to_clean:
            print("\n  No tables to clean. Done.")
            return

        # Disable foreign key checks temporarily for clean deletion
        # Clean in order that respects most foreign keys
        # First, disable triggers
        if not dry_run:
            session.execute(text("SET session_replication_role = 'replica'"))

        total_rows = 0
        for table in sorted(tables_to_clean):
            # Count rows
            count_result = session.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            count = count_result.scalar()
            total_rows += count

            if count > 0:
                action = "WOULD DELETE" if dry_run else "DELETING"
                print(f"\n    {action}: {table} ({count} rows)")
                if not dry_run:
                    session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
            else:
                print(f"\n    SKIP: {table} (0 rows)")

        # Re-enable triggers
        if not dry_run:
            session.execute(text("SET session_replication_role = 'origin'"))
            session.commit()

        print(f"\n{'=' * 60}")
        if dry_run:
            print(f"  DRY RUN: Would delete {total_rows} rows across {len(tables_to_clean)} tables")
        else:
            print(f"  ✅ Cleaned {total_rows} rows across {len(tables_to_clean)} tables")
            print(f"  ✅ Preserved {len(tables_kept)} account/config tables")
        print(f"{'=' * 60}")

    except Exception as e:
        session.rollback()
        print(f"\n  ❌ Error: {e}")
        raise
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    db_url = get_database_url()

    # Check for --dry-run flag
    dry_run = "--dry-run" in sys.argv or "--dry" in sys.argv
    force = "--force" in sys.argv or "-y" in sys.argv

    if not dry_run and not force:
        print("⚠️  This will PERMANENTLY delete all user data!")
        print("   Use --dry-run to preview, or --force to skip confirmation.")
        confirm = input("\n   Type 'yes' to proceed: ")
        if confirm.lower() != "yes":
            print("   Cancelled.")
            sys.exit(0)

    clean_database(db_url, dry_run=dry_run)
