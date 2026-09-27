"""020_jarvis_cc_tables: Jarvis Customer Care persistence

Revision ID: 020
Revises: 019_ooo_bounce_tables
Create Date: 2026-05-11

Jarvis Customer Care — awareness snapshots, command audit log,
and proactive alerts. These 3 tables persist the GROUP 14
(JARVIS_AWARENESS) and GROUP 20 (JARVIS_COMMAND) fields from
ParwaGraphState that currently exist only in-memory.

Also extends jarvis_messages CHECK constraint to include
CC message types (variant_pipeline, ai_generated, direct_ai,
proactive_alert, command_response).

Tables:
- jarvis_awareness_snapshots: Periodic snapshots of the 21-field
  awareness state per CC session
- jarvis_commands: Full audit log of every command Jarvis receives
  and executes
- jarvis_proactive_alerts: Proactive alerts from awareness engine
  to dashboard

BC-001: company_id indexed on every table.
BC-008: Null-safe columns for graceful degradation.
BC-012: All timestamps UTC.
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019_ooo_bounce_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── Extend jarvis_messages CHECK constraint for CC types ──
    # Must drop and recreate because CHECK constraints can't be ALTERed
    op.drop_constraint("ck_jarvis_message_type", "jarvis_messages", type_="check")
    op.create_check_constraint(
        "ck_jarvis_message_type",
        "jarvis_messages",
        sa.column("message_type").in_(
            [
                "text", "bill_summary", "payment_card", "otp_card",
                "handoff_card", "demo_call_card", "action_ticket",
                "call_summary", "recharge_cta",
                "limit_reached", "pack_expired", "error",
                # Phase 1.3: Customer Care message types
                "variant_pipeline", "ai_generated", "direct_ai",
                "proactive_alert", "command_response",
            ]
        ),
    )

    # ════════════════════════════════════════════════════════════════
    # JARVIS AWARENESS SNAPSHOTS
    # ════════════════════════════════════════════════════════════════

    op.create_table(
        "jarvis_awareness_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id", sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        # Snapshot metadata
        sa.Column(
            "snapshot_type", sa.String(20),
            nullable=False, server_default="periodic",
        ),
        sa.Column("tick_number", sa.Integer, nullable=True),
        # Plan & subscription (GROUP 14)
        sa.Column("current_plan", sa.String(20), nullable=True),
        sa.Column("plan_usage_today", sa.Numeric(5, 2), nullable=True),
        sa.Column("subscription_status", sa.String(20), nullable=True),
        sa.Column("days_until_renewal", sa.Integer, nullable=True),
        # System health
        sa.Column("system_health", sa.String(20), nullable=True),
        sa.Column("channel_health_json", sa.Text, server_default="{}"),
        # Alerts summary
        sa.Column("active_alerts_count", sa.Integer, server_default="0"),
        sa.Column("active_alerts_json", sa.Text, server_default="[]"),
        # Ticket volume
        sa.Column("ticket_volume_today", sa.Integer, server_default="0"),
        sa.Column("ticket_volume_avg", sa.Numeric(10, 2), nullable=True),
        sa.Column("ticket_volume_spike", sa.Boolean, server_default="0"),
        # Agent pool
        sa.Column("active_agents", sa.Integer, server_default="0"),
        sa.Column("agent_pool_capacity", sa.Integer, server_default="0"),
        sa.Column("agent_pool_utilization", sa.Numeric(5, 2), nullable=True),
        # Training (Agent Lightning)
        sa.Column("training_running", sa.Boolean, server_default="0"),
        sa.Column("training_mistake_count", sa.Integer, server_default="0"),
        sa.Column("training_model_version", sa.String(50), nullable=True),
        # Drift & quality
        sa.Column("drift_status", sa.String(20), nullable=True),
        sa.Column("drift_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("quality_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("quality_alerts_json", sa.Text, server_default="[]"),
        # Recent errors
        sa.Column("last_5_errors_json", sa.Text, server_default="[]"),
        # Raw state dump
        sa.Column("raw_state_json", sa.Text, server_default="{}"),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        # CHECK constraints
        sa.CheckConstraint(
            "snapshot_type IN ('periodic','on_change','manual','emergency')",
            name="ck_jarvis_aware_snapshot_type",
        ),
    )
    # Composite indexes for common query patterns
    op.create_index(
        "ix_jarvis_aware_comp_created",
        "jarvis_awareness_snapshots",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_jarvis_aware_session_created",
        "jarvis_awareness_snapshots",
        ["session_id", "created_at"],
    )

    # ════════════════════════════════════════════════════════════════
    # JARVIS COMMANDS
    # ════════════════════════════════════════════════════════════════

    op.create_table(
        "jarvis_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id", sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        # Raw input
        sa.Column("raw_input", sa.Text, nullable=False),
        sa.Column(
            "source", sa.String(20),
            nullable=False, server_default="chat",
        ),
        # Parsed command (GROUP 20 mapping)
        sa.Column("command_parsed", sa.Text, nullable=True),
        sa.Column("command_intent", sa.String(20), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        # Co-Pilot context
        sa.Column("co_pilot_suggestion", sa.Text, nullable=True),
        sa.Column("co_pilot_suggestion_type", sa.String(50), nullable=True),
        # Execution
        sa.Column(
            "status", sa.String(15),
            nullable=False, server_default="received",
        ),
        sa.Column("result_json", sa.Text, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        # Metadata
        sa.Column("command_metadata_json", sa.Text, server_default="{}"),
        sa.Column("undo_available", sa.Boolean, server_default="0"),
        sa.Column("undone_by_command_id", sa.String(36), nullable=True),
        # Timestamps
        sa.Column("received_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("parsed_at", sa.DateTime, nullable=True),
        sa.Column("executed_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        # CHECK constraints
        sa.CheckConstraint(
            "command_intent IN ('query','control','configure','report','override')",
            name="ck_jarvis_cmd_intent",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'received','parsing','parsed','executing',"
            "'completed','failed','cancelled','undone'"
            ")",
            name="ck_jarvis_cmd_status",
        ),
        sa.CheckConstraint(
            "source IN ('chat','api','co_pilot','proactive','scheduled')",
            name="ck_jarvis_cmd_source",
        ),
    )
    # Composite indexes
    op.create_index(
        "ix_jarvis_cmd_comp_created",
        "jarvis_commands",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_jarvis_cmd_session_created",
        "jarvis_commands",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_jarvis_cmd_comp_status",
        "jarvis_commands",
        ["company_id", "status"],
    )

    # ════════════════════════════════════════════════════════════════
    # JARVIS PROACTIVE ALERTS
    # ════════════════════════════════════════════════════════════════

    op.create_table(
        "jarvis_proactive_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id", sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        # Alert identification
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column(
            "severity", sa.String(15),
            nullable=False, server_default="info",
        ),
        sa.Column(
            "category", sa.String(30),
            nullable=False, server_default="system_health",
        ),
        # Alert content
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details_json", sa.Text, server_default="{}"),
        # Alert lifecycle
        sa.Column(
            "status", sa.String(15),
            nullable=False, server_default="active",
        ),
        sa.Column("acknowledged_by", sa.String(36), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime, nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        # Dashboard behavior
        sa.Column("action_required", sa.Boolean, server_default="0"),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("ttl_seconds", sa.Integer, server_default="0"),
        # Related resources
        sa.Column("related_snapshot_id", sa.String(36), nullable=True),
        sa.Column("related_command_id", sa.String(36), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        # CHECK constraints
        sa.CheckConstraint(
            "severity IN ('info','warning','critical','emergency')",
            name="ck_jarvis_alert_severity",
        ),
        sa.CheckConstraint(
            "category IN ("
            "'system_health','ticket_volume','agent_pool',"
            "'quality','drift','billing','security','integration'"
            ")",
            name="ck_jarvis_alert_category",
        ),
        sa.CheckConstraint(
            "status IN ('active','acknowledged','dismissed','resolved','expired')",
            name="ck_jarvis_alert_status",
        ),
    )
    # Composite indexes
    op.create_index(
        "ix_jarvis_alert_comp_created",
        "jarvis_proactive_alerts",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_jarvis_alert_comp_severity",
        "jarvis_proactive_alerts",
        ["company_id", "severity"],
    )
    op.create_index(
        "ix_jarvis_alert_session_created",
        "jarvis_proactive_alerts",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_jarvis_alert_comp_status",
        "jarvis_proactive_alerts",
        ["company_id", "status"],
    )


def downgrade() -> None:
    # Drop in reverse creation order (FK dependencies)
    op.drop_table("jarvis_proactive_alerts")
    op.drop_table("jarvis_commands")
    op.drop_table("jarvis_awareness_snapshots")

    # Restore original jarvis_messages CHECK constraint
    op.drop_constraint("ck_jarvis_message_type", "jarvis_messages", type_="check")
    op.create_check_constraint(
        "ck_jarvis_message_type",
        "jarvis_messages",
        sa.column("message_type").in_(
            [
                "text", "bill_summary", "payment_card", "otp_card",
                "handoff_card", "demo_call_card", "action_ticket",
                "call_summary", "recharge_cta",
                "limit_reached", "pack_expired", "error",
            ]
        ),
    )
