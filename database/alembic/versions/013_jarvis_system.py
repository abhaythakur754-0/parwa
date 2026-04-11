"""
Alembic Migration: Jarvis Chat Tables (013_jarvis_system)

Week 6 Day 8-9: Creates jarvis_sessions, jarvis_messages,
jarvis_knowledge_used, and jarvis_action_tickets tables.

BC-001: All tables have company_id for tenant isolation.
Indexes on user_id and session_id for fast lookups.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "013_jarvis_system"
down_revision = "012_pricing_variants" if False else "011_phase3_variant_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── jarvis_sessions table ──────────────────────────────────────
    op.create_table(
        "jarvis_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False, index=True,
        ),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("current_step", sa.String(100), server_default="greeting"),
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("selected_plan", sa.String(50), nullable=True),
        sa.Column("selected_industry", sa.String(50), nullable=True),
        sa.Column("pricing_selection", sa.Text(), nullable=True),
        sa.Column("payment_status", sa.String(50), nullable=True),
        sa.Column("paddle_session_id", sa.String(255), nullable=True),
        sa.Column("payment_amount", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # ── jarvis_messages table ──────────────────────────────────────
    op.create_table(
        "jarvis_messages",
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
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(50), server_default="text"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("step", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Index for message ordering within sessions
    op.create_index(
        "ix_jarvis_messages_session_created",
        "jarvis_messages",
        ["session_id", "created_at"],
    )

    # ── jarvis_knowledge_used table ──────────────────────────────
    op.create_table(
        "jarvis_knowledge_used",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "session_id", sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "message_id", sa.String(36),
            sa.ForeignKey("jarvis_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id", sa.String(36),
            sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("relevance_score", sa.Integer(), server_default="0"),
        sa.Column("chunk_content_preview", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── jarvis_action_tickets table ──────────────────────────────
    op.create_table(
        "jarvis_action_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "session_id", sa.String(36),
            sa.ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "message_id", sa.String(36),
            sa.ForeignKey("jarvis_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("jarvis_action_tickets")
    op.drop_table("jarvis_knowledge_used")
    op.drop_index("ix_jarvis_messages_session_created")
    op.drop_table("jarvis_messages")
    op.drop_table("jarvis_sessions")
