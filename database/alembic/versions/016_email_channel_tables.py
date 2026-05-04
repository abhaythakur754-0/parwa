"""Alembic migration 016: Email channel tables.

Week 13 Day 1 (F-121: Email Inbound).

Creates:
- inbound_emails: Raw email storage for audit trail
- email_threads: Maps email threads to tickets

BC-001: Every table has company_id.
BC-003: Idempotent webhook processing via unique message_id.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "016_email_channel_tables"
down_revision = "015_business_email_otp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── inbound_emails ───────────────────────────────────────────
    op.create_table(
        "inbound_emails",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # RFC 2822 headers
        sa.Column("message_id", sa.String(255), unique=True, index=True),
        sa.Column("in_reply_to", sa.String(255), nullable=True),
        sa.Column("references", sa.Text(), nullable=True),
        # Email metadata
        sa.Column("sender_email", sa.String(254), nullable=False, index=True),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("headers_json", sa.Text(), server_default="{}"),
        # Processing state
        sa.Column("is_auto_reply", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_loop", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey("tickets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("raw_size_bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
        ),
    )

    # ── email_threads ───────────────────────────────────────────
    op.create_table(
        "email_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Thread tracking
        sa.Column("thread_message_id", sa.String(255), nullable=False, index=True),
        sa.Column("latest_message_id", sa.String(255), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("participants_json", sa.Text(), server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("email_threads")
    op.drop_table("inbound_emails")
