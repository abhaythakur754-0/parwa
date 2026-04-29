"""Week 13 Day 3: OOO detection tables and email bounces tables

Revision ID: 019_ooo_bounce_tables
Revises: 018_email_delivery_events
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019_ooo_bounce_tables"
down_revision = "018_email_delivery_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── OOO Detection Rules ───────────────────────────────────────
    op.create_table(
        "ooo_detection_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=True, index=True),
        sa.Column("rule_type", sa.String(50), nullable=False, server_default="body"),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column(
            "pattern_type", sa.String(50), nullable=False, server_default="regex"
        ),
        sa.Column(
            "classification", sa.String(50), nullable=False, server_default="ooo"
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_matched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_ooo_rules_company_id", "ooo_detection_rules", ["company_id"])

    # ── OOO Detection Log ─────────────────────────────────────────
    op.create_table(
        "ooo_detection_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("sender_email", sa.String(254), nullable=False, index=True),
        sa.Column("thread_id", sa.String(36), nullable=True),
        sa.Column("related_ticket_id", sa.String(36), nullable=True),
        sa.Column("message_id", sa.String(255), nullable=True),
        sa.Column(
            "classification", sa.String(50), nullable=False, server_default="ooo"
        ),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("detected_signals", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("rule_ids_matched", sa.Text(), nullable=True, server_default="[]"),
        sa.Column(
            "action_taken", sa.String(50), nullable=False, server_default="tagged"
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_ooo_log_company_id", "ooo_detection_log", ["company_id"])
    op.create_index("ix_ooo_log_sender", "ooo_detection_log", ["sender_email"])

    # ── OOO Sender Profiles ───────────────────────────────────────
    op.create_table(
        "ooo_sender_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("sender_email", sa.String(254), nullable=False, index=True),
        sa.Column(
            "ooo_detected_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_ooo_at", sa.DateTime(), nullable=True),
        sa.Column("ooo_until", sa.DateTime(), nullable=True),
        sa.Column("active_ooo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_ooo_profiles_company_email",
        "ooo_sender_profiles",
        ["company_id", "sender_email"],
        unique=True,
    )

    # ── Email Bounces ─────────────────────────────────────────────
    op.create_table(
        "email_bounces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("customer_email", sa.String(254), nullable=False, index=True),
        sa.Column("bounce_type", sa.String(50), nullable=False, index=True),
        sa.Column("bounce_reason", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="other"),
        sa.Column("provider_code", sa.String(50), nullable=True),
        sa.Column("event_id", sa.String(255), nullable=True, unique=True),
        sa.Column("related_ticket_id", sa.String(36), nullable=True),
        sa.Column(
            "email_status_before",
            sa.String(50),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "email_status_after", sa.String(50), nullable=False, server_default="active"
        ),
        sa.Column("whitelisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("whitelist_justification", sa.Text(), nullable=True),
        sa.Column("whitelisted_by", sa.String(36), nullable=True),
        sa.Column("whitelisted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_bounces_company_email", "email_bounces", ["company_id", "customer_email"]
    )
    op.create_index("ix_bounces_type", "email_bounces", ["bounce_type"])

    # ── Customer Email Status ───────────────────────────────────────
    op.create_table(
        "customer_email_status",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("customer_email", sa.String(254), nullable=False, index=True),
        sa.Column(
            "email_status",
            sa.String(50),
            nullable=False,
            server_default="active",
            index=True,
        ),
        sa.Column("bounce_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("complaint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_bounce_at", sa.DateTime(), nullable=True),
        sa.Column("last_complaint_at", sa.DateTime(), nullable=True),
        sa.Column("suppressed_at", sa.DateTime(), nullable=True),
        sa.Column("whitelisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_email_status_company_email",
        "customer_email_status",
        ["company_id", "customer_email"],
        unique=True,
    )

    # ── Email Deliverability Alerts ────────────────────────────────
    op.create_table(
        "email_deliverability_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.String(255), nullable=True),
        sa.Column("threshold", sa.String(255), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledged_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_company", "email_deliverability_alerts", ["company_id"])
    op.create_index("ix_alerts_severity", "email_deliverability_alerts", ["severity"])


def downgrade() -> None:
    op.drop_table("email_deliverability_alerts")
    op.drop_table("customer_email_status")
    op.drop_table("email_bounces")
    op.drop_table("ooo_sender_profiles")
    op.drop_table("ooo_detection_log")
    op.drop_table("ooo_detection_rules")
