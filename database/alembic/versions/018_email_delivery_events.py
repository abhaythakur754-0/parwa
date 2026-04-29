"""Week 13 Day 3: Email delivery events table

Revision ID: 018_email_delivery_events
Revises: 017_outbound_email
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018_email_delivery_events"
down_revision = "017_outbound_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_delivery_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=True),
        sa.Column("brevo_message_id", sa.String(255), nullable=True),
        sa.Column("brevo_event_id", sa.String(255), nullable=True, unique=True),
        sa.Column("outbound_email_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("bounce_type", sa.String(50), nullable=True),
        sa.Column("ooo_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="brevo"),
        sa.Column("provider_data", postgresql.JSONB(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "event_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
    op.create_index(
        "ix_email_delivery_events_company_id", "email_delivery_events", ["company_id"]
    )
    op.create_index(
        "ix_email_delivery_events_event_type", "email_delivery_events", ["event_type"]
    )
    op.create_index(
        "ix_delivery_company_event",
        "email_delivery_events",
        ["company_id", "event_type"],
    )
    op.create_index(
        "ix_delivery_recipient", "email_delivery_events", ["recipient_email"]
    )
    op.create_index(
        "ix_delivery_brevo_event",
        "email_delivery_events",
        ["brevo_event_id"],
        unique=True,
    )
    op.create_index(
        "ix_delivery_outbound", "email_delivery_events", ["outbound_email_id"]
    )
    op.create_index("ix_delivery_processed", "email_delivery_events", ["is_processed"])
    op.create_index(
        "ix_delivery_next_retry", "email_delivery_events", ["next_retry_at"]
    )


def downgrade() -> None:
    op.drop_table("email_delivery_events")
