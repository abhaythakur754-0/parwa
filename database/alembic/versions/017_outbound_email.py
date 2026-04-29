"""Week 13 Day 2: Outbound email tracking table

Revision ID: 017_outbound_email
Revises: 016_email_channel_tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "017_outbound_email"
down_revision = "016_email_channel_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbound_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("reply_to_message_id", sa.String(255), nullable=True),
        sa.Column("references", sa.Text(), nullable=True),
        sa.Column("brevo_message_id", sa.String(255), nullable=True, unique=True),
        sa.Column(
            "delivery_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="ai"),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("content_length", sa.Integer(), nullable=True),
        sa.Column("template_used", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_outbound_emails_company_id", "outbound_emails", ["company_id"])
    op.create_index("ix_outbound_emails_ticket_id", "outbound_emails", ["ticket_id"])
    op.create_index(
        "ix_outbound_company_ticket",
        "outbound_emails",
        ["company_id", "ticket_id"],
    )
    op.create_index(
        "ix_outbound_brevo_id",
        "outbound_emails",
        ["brevo_message_id"],
        unique=True,
    )
    op.create_index(
        "ix_outbound_delivery_status",
        "outbound_emails",
        ["delivery_status"],
    )


def downgrade() -> None:
    op.drop_table("outbound_emails")
