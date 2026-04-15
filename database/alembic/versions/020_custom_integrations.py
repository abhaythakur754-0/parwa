"""020_custom_integrations: custom_integrations + webhook_delivery_logs

F-031: Custom Integration Builder
Revises: 019_ooo_bounce_tables
"""

from alembic import op
import sqlalchemy as sa

revision = "020_custom_integrations"
down_revision = "019_ooo_bounce_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("integration_type", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft", index=True),
        sa.Column("config_encrypted", sa.Text, nullable=False, server_default="{}"),
        sa.Column("settings", sa.Text, nullable=False, server_default="{}"),
        sa.Column("webhook_id", sa.String(36), unique=True, index=True),
        sa.Column("webhook_secret", sa.String(255)),
        sa.Column("consecutive_error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.Text),
        sa.Column("last_tested_at", sa.DateTime),
        sa.Column("last_test_result", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_custom_integrations_type", "custom_integrations", ["integration_type"])
    op.create_index("ix_custom_integrations_status", "custom_integrations", ["status"])

    op.create_table(
        "webhook_delivery_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "custom_integration_id", sa.String(36),
            sa.ForeignKey("custom_integrations.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("trigger_event_id", sa.String(36)),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("response_status_code", sa.Integer),
        sa.Column("response_body", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("payload_snapshot", sa.Text),
        sa.Column("scheduled_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("webhook_delivery_logs")
    op.drop_table("custom_integrations")
