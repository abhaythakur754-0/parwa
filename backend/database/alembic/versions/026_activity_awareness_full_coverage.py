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
    # 1. Update the CHECK constraint for event_category to include new categories
    op.drop_constraint("ck_jarvis_act_category", "jarvis_activity_events", type_="check")
    op.create_check_constraint(
        "ck_jarvis_act_category",
        "jarvis_activity_events",
        sa.column("event_category").in_(
            [
                "ui", "subscription", "payment", "refund", "channel_email",
                "channel_sms", "channel_voice", "channel_chat", "channel_webhook",
                "config", "security", "integration", "cron", "agent",
                "sla", "escalation", "quality", "training",
                # New categories
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
    op.drop_constraint("ck_jarvis_act_category", "jarvis_activity_events", type_="check")
    op.create_check_constraint(
        "ck_jarvis_act_category",
        "jarvis_activity_events",
        sa.column("event_category").in_(
            [
                "ui", "subscription", "payment", "refund", "channel_email",
                "channel_sms", "channel_voice", "channel_chat", "channel_webhook",
                "config", "security", "integration", "cron", "agent",
                "sla", "escalation", "quality", "training",
            ]
        ),
    )
