"""012_jarvis_system: Jarvis onboarding chat system

Revision ID: 012
Revises: 011
Create Date: 2026-04-11

Jarvis onboarding chat — sessions, messages, knowledge tracking,
and action tickets. One page, one Jarvis, everything happens in chat.

Tables:
- jarvis_sessions: Per-user chat sessions with context_json memory
- jarvis_messages: All chat messages (user, jarvis, system) with rich types
- jarvis_knowledge_used: Tracks which KB files were used per response
- jarvis_action_tickets: Every user action as a visible ticket with result
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── jarvis_sessions (root table — FK target for all others) ──

    op.create_table(
        "jarvis_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        # 'onboarding' before purchase, 'customer_care' after handoff
        sa.Column("type", sa.String(20), nullable=False, server_default="onboarding"),
        # Full journey memory: pages visited, variants, ROI, concerns, etc.
        sa.Column("context_json", sa.Text, server_default="{}"),
        # Message limits
        sa.Column(
            "message_count_today", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("last_message_date", sa.Date, nullable=True),
        sa.Column(
            "total_message_count", sa.Integer, nullable=False, server_default="0"
        ),
        # Monetization: 'free' (20/day) or 'demo' (500 + 3-min call, 24h)
        sa.Column("pack_type", sa.String(10), nullable=False, server_default="free"),
        sa.Column("pack_expiry", sa.DateTime, nullable=True),
        sa.Column("demo_call_used", sa.Boolean, nullable=False, server_default="0"),
        # Session state
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        # Payment: none → pending → completed / failed
        sa.Column(
            "payment_status", sa.String(15), nullable=False, server_default="none"
        ),
        sa.Column("handoff_completed", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        # CHECK constraints
        sa.CheckConstraint(
            "type IN ('onboarding','customer_care')",
            name="ck_jarvis_session_type",
        ),
        sa.CheckConstraint(
            "pack_type IN ('free','demo')",
            name="ck_jarvis_session_pack_type",
        ),
        sa.CheckConstraint(
            "payment_status IN ('none','pending','completed','failed')",
            name="ck_jarvis_session_payment_status",
        ),
        sa.CheckConstraint(
            "message_count_today >= 0",
            name="ck_jarvis_session_msg_count_nonneg",
        ),
        sa.CheckConstraint(
            "total_message_count >= 0",
            name="ck_jarvis_session_total_msg_nonneg",
        ),
    )
    # Named indexes
    op.create_index(
        "ix_jarvis_sess_user_active",
        "jarvis_sessions",
        ["user_id", "is_active"],
    )
    op.create_index(
        "ix_jarvis_sess_company",
        "jarvis_sessions",
        ["company_id"],
    )

    # ── jarvis_messages ──

    op.create_table(
        "jarvis_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # 'user', 'jarvis', 'system'
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        # Rich message types: text, bill_summary, payment_card, otp_card,
        # handoff_card, demo_call_card, action_ticket, call_summary,
        # recharge_cta, limit_reached, pack_expired, error
        sa.Column("message_type", sa.String(25), nullable=False, server_default="text"),
        sa.Column("metadata_json", sa.Text, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        # CHECK constraints
        sa.CheckConstraint(
            "role IN ('user','jarvis','system')",
            name="ck_jarvis_message_role",
        ),
        sa.CheckConstraint(
            "message_type IN ("
            "'text','bill_summary','payment_card','otp_card',"
            "'handoff_card','demo_call_card','action_ticket',"
            "'call_summary','recharge_cta',"
            "'limit_reached','pack_expired','error'"
            ")",
            name="ck_jarvis_message_type",
        ),
    )
    # Named indexes
    op.create_index(
        "ix_jarvis_msg_session_ts",
        "jarvis_messages",
        ["session_id", "created_at"],
    )

    # ── jarvis_knowledge_used (analytics — which KB was used per msg) ──

    op.create_table(
        "jarvis_knowledge_used",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("jarvis_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # e.g. '01_pricing_tiers.json', '07_objection_handling.json'
        sa.Column("knowledge_file", sa.String(100), nullable=False),
        sa.Column("relevance_score", sa.Numeric(5, 2), server_default="1.0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        # CHECK constraint
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_jarvis_ku_relevance_range",
        ),
    )
    op.create_index(
        "ix_jarvis_ku_message",
        "jarvis_knowledge_used",
        ["message_id"],
    )

    # ── jarvis_action_tickets (every action = visible ticket in chat) ──

    op.create_table(
        "jarvis_action_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Links to the in-chat message that rendered this ticket
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("jarvis_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Ticket types: otp_verification, otp_verified, payment_demo_pack,
        # payment_variant, payment_variant_completed, demo_call,
        # demo_call_completed, roi_import, handoff
        sa.Column("ticket_type", sa.String(30), nullable=False),
        # pending → in_progress → completed / failed
        sa.Column("status", sa.String(15), nullable=False, server_default="pending"),
        # Outcome data: call duration, summary, payment ID, etc.
        sa.Column("result_json", sa.Text, server_default="{}"),
        sa.Column("metadata_json", sa.Text, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        # CHECK constraints
        sa.CheckConstraint(
            "ticket_type IN ("
            "'otp_verification','otp_verified',"
            "'payment_demo_pack','payment_variant','payment_variant_completed',"
            "'demo_call','demo_call_completed',"
            "'roi_import','handoff'"
            ")",
            name="ck_jarvis_ticket_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','failed')",
            name="ck_jarvis_ticket_status",
        ),
    )
    # Named indexes
    op.create_index(
        "ix_jarvis_ticket_session",
        "jarvis_action_tickets",
        ["session_id"],
    )
    op.create_index(
        "ix_jarvis_ticket_sess_status",
        "jarvis_action_tickets",
        ["session_id", "status"],
    )


def downgrade() -> None:
    # Drop in reverse FK-dependency order
    op.drop_table("jarvis_action_tickets")
    op.drop_table("jarvis_knowledge_used")
    op.drop_table("jarvis_messages")
    op.drop_table("jarvis_sessions")
