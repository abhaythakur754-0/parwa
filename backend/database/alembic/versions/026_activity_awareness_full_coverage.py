"""Activity Store full awareness coverage

Add new event categories for shadow_mode, dashboard, variant_ops,
knowledge_ops, onboarding, notification, approval_flow.
Add shadow_mode and dashboard columns to awareness snapshots.

Revision ID: 026
Revises: 025
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ensure the activity-event table exists on fresh installations.
    # The ORM model predates this migration, but older migration chains never
    # created its table. Build it here so a clean database can reach head.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("jarvis_activity_events"):
        op.create_table(
            "jarvis_activity_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "company_id", sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("variant_scope", sa.String(50), nullable=True),
            sa.Column("instance_id", sa.String(36), nullable=True),
            sa.Column("event_source", sa.String(30), nullable=False, server_default="system"),
            sa.Column("event_category", sa.String(30), nullable=False, server_default="config"),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("severity", sa.String(15), nullable=False, server_default="info"),
            sa.Column("actor_id", sa.String(36), nullable=True),
            sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("context_json", sa.Text, server_default="{}"),
            sa.Column("old_value", sa.Text, nullable=True),
            sa.Column("new_value", sa.Text, nullable=True),
            sa.Column("resource_type", sa.String(50), nullable=True),
            sa.Column("resource_id", sa.String(36), nullable=True),
            sa.Column("jarvis_relevant", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("jarvis_control_boundary", sa.String(30), nullable=True, server_default="notify_only"),
            sa.Column("session_id", sa.String(36), nullable=True),
            sa.Column("occurred_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.CheckConstraint(
                "event_source IN ('user_action','billing','channel','admin','system','integration','agent_action','unknown')",
                name="ck_jarvis_act_event_source",
            ),
            sa.CheckConstraint(
                "severity IN ('info','warning','critical','emergency')",
                name="ck_jarvis_act_severity",
            ),
            sa.CheckConstraint(
                "event_category IN ('ui','subscription','payment','refund','channel_email','channel_sms','channel_voice','channel_chat','channel_webhook','config','security','integration','cron','agent','sla','escalation','quality','training','shadow_mode','dashboard','variant_ops','knowledge_ops','onboarding','notification','approval_flow')",
                name="ck_jarvis_act_category",
            ),
            sa.CheckConstraint(
                "jarvis_control_boundary IN ('notify_only','agent_controlled','jarvis_can_act','human_required')",
                name="ck_jarvis_act_control_boundary",
            ),
            sa.CheckConstraint(
                "actor_type IN ('user','admin','system','agent','api_key','cron')",
                name="ck_jarvis_act_actor_type",
            ),
        )
        op.create_index("ix_jarvis_act_comp_created", "jarvis_activity_events", ["company_id", "created_at"])
        op.create_index("ix_jarvis_act_comp_source", "jarvis_activity_events", ["company_id", "event_source"])
        op.create_index("ix_jarvis_act_comp_category", "jarvis_activity_events", ["company_id", "event_category"])
        op.create_index("ix_jarvis_act_comp_relevant", "jarvis_activity_events", ["company_id", "jarvis_relevant", "created_at"])
        op.create_index("ix_jarvis_act_comp_variant", "jarvis_activity_events", ["company_id", "variant_scope", "created_at"])
        op.create_index("ix_jarvis_act_comp_severity", "jarvis_activity_events", ["company_id", "severity", "created_at"])
        op.create_index("ix_jarvis_act_comp_resource", "jarvis_activity_events", ["company_id", "resource_type", "resource_id"])
        op.create_index("ix_jarvis_act_comp_control", "jarvis_activity_events", ["company_id", "jarvis_control_boundary", "created_at"])
    else:
        # Existing installs may have the older, narrower category CHECK.
        with op.batch_alter_table("jarvis_activity_events") as batch_op:
            batch_op.drop_constraint("ck_jarvis_act_category", type_="check")
            batch_op.create_check_constraint(
                "ck_jarvis_act_category",
                sa.column("event_category").in_(
                    [
                        "ui", "subscription", "payment", "refund", "channel_email",
                        "channel_sms", "channel_voice", "channel_chat", "channel_webhook",
                        "config", "security", "integration", "cron", "agent",
                        "sla", "escalation", "quality", "training",
                        "shadow_mode", "dashboard", "variant_ops", "knowledge_ops",
                        "onboarding", "notification", "approval_flow",
                    ]
                ),
            )

    # 2. Add shadow_mode columns to awareness snapshots
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_active", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_phase", sa.String(20), nullable=True),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_live_variant", sa.String(50), nullable=True),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_shadow_variant", sa.String(50), nullable=True),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_win_rate", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_total_comparisons", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_quality_streak", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("shadow_mode_recent_events_json", sa.Text(), server_default="[]", nullable=False),
    )

    # 3. Add dashboard columns to awareness snapshots
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("user_current_page", sa.String(255), nullable=True),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("recent_dashboard_action_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("recent_ticket_action_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("recent_dashboard_events_json", sa.Text(), server_default="[]", nullable=False),
    )
    op.add_column(
        "jarvis_awareness_snapshots",
        sa.Column("recent_ticket_actions_json", sa.Text(), server_default="[]", nullable=False),
    )

    # 4. Add indexes for new event categories
    op.create_index(
        "ix_jarvis_act_comp_shadow_mode",
        "jarvis_activity_events",
        ["company_id", "event_category", "created_at"],
        postgresql_where=sa.text("event_category = 'shadow_mode'"),
    )
    op.create_index(
        "ix_jarvis_act_comp_dashboard",
        "jarvis_activity_events",
        ["company_id", "event_category", "created_at"],
        postgresql_where=sa.text("event_category = 'dashboard'"),
    )


def downgrade() -> None:
    # Drop new indexes
    op.drop_index("ix_jarvis_act_comp_dashboard", table_name="jarvis_activity_events")
    op.drop_index("ix_jarvis_act_comp_shadow_mode", table_name="jarvis_activity_events")

    # Drop dashboard columns
    op.drop_column("jarvis_awareness_snapshots", "recent_ticket_actions_json")
    op.drop_column("jarvis_awareness_snapshots", "recent_dashboard_events_json")
    op.drop_column("jarvis_awareness_snapshots", "recent_ticket_action_count")
    op.drop_column("jarvis_awareness_snapshots", "recent_dashboard_action_count")
    op.drop_column("jarvis_awareness_snapshots", "user_current_page")

    # Drop shadow mode columns
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_recent_events_json")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_quality_streak")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_total_comparisons")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_win_rate")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_shadow_variant")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_live_variant")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_phase")
    op.drop_column("jarvis_awareness_snapshots", "shadow_mode_active")

    # Revert CHECK constraint
    with op.batch_alter_table("jarvis_activity_events") as batch_op:
        batch_op.drop_constraint("ck_jarvis_act_category", type_="check")
        batch_op.create_check_constraint(
            "ck_jarvis_act_category",
            sa.column("event_category").in_(
                [
                    "ui", "subscription", "payment", "refund", "channel_email",
                    "channel_sms", "channel_voice", "channel_chat", "channel_webhook",
                    "config", "security", "integration", "cron", "agent",
                    "sla", "escalation", "quality", "training",
                ]
            ),
        )
