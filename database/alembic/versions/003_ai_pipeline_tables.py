"""003_ai_pipeline_tables: api_providers, service_configs, gsd_sessions,
confidence_scores, guardrail_blocks, guardrail_rules, prompt_templates,
model_usage_logs.

Revision ID: 003
Revises: 002
Create Date: 2026-04-02

"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_providers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("required_fields", sa.Text, server_default="[]"),
        sa.Column("optional_fields", sa.Text, server_default="[]"),
        sa.Column("default_endpoint", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "service_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("api_providers.id")),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("display_name", sa.String(255)),
        sa.Column("api_key_encrypted", sa.Text),
        sa.Column("api_secret_encrypted", sa.Text),
        sa.Column("endpoint", sa.String(255)),
        sa.Column("settings", sa.Text, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "gsd_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("current_step", sa.String(100), nullable=False),
        sa.Column("state_data", sa.Text, server_default="{}"),
        sa.Column("status", sa.String(50), server_default="in_progress"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "confidence_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("retrieval_score", sa.Numeric(5, 2)),
        sa.Column("intent_score", sa.Numeric(5, 2)),
        sa.Column("sentiment_score", sa.Numeric(5, 2)),
        sa.Column("context_score", sa.Numeric(5, 2)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "guardrail_blocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("block_type", sa.String(50), nullable=False),
        sa.Column("original_response", sa.Text),
        sa.Column("block_reason", sa.Text),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("status", sa.String(50), server_default="pending_review"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "guardrail_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("action", sa.String(50), nullable=False, server_default="block"),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("intent_type", sa.String(100)),
        sa.Column("template_text", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "model_usage_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id")),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer, server_default="0"),
        sa.Column("output_tokens", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("model_usage_logs")
    op.drop_table("prompt_templates")
    op.drop_table("guardrail_rules")
    op.drop_table("guardrail_blocks")
    op.drop_table("confidence_scores")
    op.drop_table("gsd_sessions")
    op.drop_table("service_configs")
    op.drop_table("api_providers")
