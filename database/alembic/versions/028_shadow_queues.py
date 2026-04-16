"""Shadow Queue Tables for Channel Interceptors

Revision ID: 028_shadow_queues
Revises: 027_shadow_mode_config
Create Date: 2026-04-17

Adds:
- email_shadow_queue table
- sms_shadow_queue table  
- chat_shadow_queue table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "028_shadow_queues"
down_revision = "027_shadow_mode_config"
branch_labels = None
depends_on = None


def upgrade():
    # ── Email Shadow Queue ──────────────────────────────────────
    op.create_table(
        "email_shadow_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shadow_log_id", sa.String(36), sa.ForeignKey("shadow_log.id")),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("cc_addresses", sa.Text),
        sa.Column("bcc_addresses", sa.Text),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_text", sa.Text),
        sa.Column("body_html", sa.Text),
        sa.Column("from_address", sa.String(255)),
        sa.Column("reply_to", sa.String(255)),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id")),
        sa.Column("template_id", sa.String(36)),
        sa.Column("template_data", postgresql.JSONB, default={}),
        sa.Column("attachments", postgresql.JSONB, default=[]),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="pending",
        ),
        sa.Column("message_id", sa.String(255)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index("idx_email_shadow_queue_company", "email_shadow_queue", ["company_id"])
    op.create_index("idx_email_shadow_queue_status", "email_shadow_queue", ["status"])
    op.create_index("idx_email_shadow_queue_shadow_log", "email_shadow_queue", ["shadow_log_id"])

    # ── SMS Shadow Queue ───────────────────────────────────────
    op.create_table(
        "sms_shadow_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shadow_log_id", sa.String(36), sa.ForeignKey("shadow_log.id")),
        sa.Column("to_number", sa.String(20), nullable=False),
        sa.Column("from_number", sa.String(20)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id")),
        sa.Column("media_urls", postgresql.JSONB, default=[]),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="pending",
        ),
        sa.Column("message_sid", sa.String(100)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(20)),
        sa.Column("error_message", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index("idx_sms_shadow_queue_company", "sms_shadow_queue", ["company_id"])
    op.create_index("idx_sms_shadow_queue_status", "sms_shadow_queue", ["status"])
    op.create_index("idx_sms_shadow_queue_shadow_log", "sms_shadow_queue", ["shadow_log_id"])

    # ── Chat Shadow Queue ───────────────────────────────────────
    op.create_table(
        "chat_shadow_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shadow_log_id", sa.String(36), sa.ForeignKey("shadow_log.id")),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("message_type", sa.String(20), default="text"),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id")),
        sa.Column("metadata", postgresql.JSONB, default={}),
        sa.Column("original_message", sa.Text),
        sa.Column("edited_message", sa.Text),
        sa.Column("was_edited", sa.Boolean, default=False),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="pending",
        ),
        sa.Column("message_uuid", sa.String(100)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index("idx_chat_shadow_queue_company", "chat_shadow_queue", ["company_id"])
    op.create_index("idx_chat_shadow_queue_status", "chat_shadow_queue", ["status"])
    op.create_index("idx_chat_shadow_queue_session", "chat_shadow_queue", ["session_id"])
    op.create_index("idx_chat_shadow_queue_shadow_log", "chat_shadow_queue", ["shadow_log_id"])


def downgrade():
    # Chat shadow queue
    op.drop_index("idx_chat_shadow_queue_shadow_log", table_name="chat_shadow_queue")
    op.drop_index("idx_chat_shadow_queue_session", table_name="chat_shadow_queue")
    op.drop_index("idx_chat_shadow_queue_status", table_name="chat_shadow_queue")
    op.drop_index("idx_chat_shadow_queue_company", table_name="chat_shadow_queue")
    op.drop_table("chat_shadow_queue")
    
    # SMS shadow queue
    op.drop_index("idx_sms_shadow_queue_shadow_log", table_name="sms_shadow_queue")
    op.drop_index("idx_sms_shadow_queue_status", table_name="sms_shadow_queue")
    op.drop_index("idx_sms_shadow_queue_company", table_name="sms_shadow_queue")
    op.drop_table("sms_shadow_queue")
    
    # Email shadow queue
    op.drop_index("idx_email_shadow_queue_shadow_log", table_name="email_shadow_queue")
    op.drop_index("idx_email_shadow_queue_status", table_name="email_shadow_queue")
    op.drop_index("idx_email_shadow_queue_company", table_name="email_shadow_queue")
    op.drop_table("email_shadow_queue")
