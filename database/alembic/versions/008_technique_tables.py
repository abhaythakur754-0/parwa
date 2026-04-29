"""008_technique_tables: technique_configurations, technique_executions,
technique_versions.

AI Technique Framework (TRIVYA v1.0) — BC-013, F-140 to F-148.

Revision ID: 008
Revises: 007
Create Date: 2026-04-02

BC-001: Every tenant table has company_id.
BC-002: Money fields DECIMAL(10,2).
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── technique_configurations ──────────────────────────────────
    op.create_table(
        "technique_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("technique_id", sa.String(50), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("custom_token_budget", sa.Integer, nullable=True),
        sa.Column("custom_trigger_threshold", sa.Float, nullable=True),
        sa.Column("custom_timeout_ms", sa.Integer, nullable=True),
        sa.Column(
            "updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "uq_technique_config_company",
        "technique_configurations",
        ["company_id", "technique_id"],
    )

    op.create_index(
        "ix_tech_config_company_tier",
        "technique_configurations",
        ["company_id", "tier"],
    )

    # ── technique_executions ──────────────────────────────────────
    op.create_table(
        "technique_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ticket_id", sa.String(36), nullable=True, index=True),
        sa.Column("conversation_id", sa.String(36), nullable=True, index=True),
        sa.Column("technique_id", sa.String(50), nullable=False, index=True),
        sa.Column("tier", sa.String(10), nullable=False),
        # Input signals
        sa.Column("query_complexity", sa.Float, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("sentiment_score", sa.Float, nullable=True),
        sa.Column("customer_tier", sa.String(20), nullable=True),
        sa.Column("monetary_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("turn_count", sa.Integer, nullable=True),
        sa.Column("intent_type", sa.String(50), nullable=True),
        # Trigger rules
        sa.Column("trigger_rules", sa.Text, server_default="[]"),
        # Execution metrics
        sa.Column("tokens_input", sa.Integer, server_default="0"),
        sa.Column("tokens_output", sa.Integer, server_default="0"),
        sa.Column("tokens_overhead", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Integer, server_default="0"),
        # Result
        sa.Column(
            "result_status", sa.String(20), nullable=False, server_default="success"
        ),
        sa.Column("fallback_technique", sa.String(50), nullable=True),
        sa.Column("fallback_reason", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
    )

    op.create_index(
        "ix_tech_exec_company_date",
        "technique_executions",
        ["company_id", "created_at"],
    )

    op.create_index(
        "ix_tech_exec_technique_date",
        "technique_executions",
        ["technique_id", "created_at"],
    )

    # ── technique_versions ────────────────────────────────────────
    op.create_table(
        "technique_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("technique_id", sa.String(50), nullable=False),
        sa.Column("version", sa.String(10), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("is_default", sa.Boolean, server_default="0"),
        # A/B testing
        sa.Column("ab_test_enabled", sa.Boolean, server_default="0"),
        sa.Column("ab_test_traffic_pct", sa.Integer, server_default="50"),
        # Performance metrics
        sa.Column("total_activations", sa.Integer, server_default="0"),
        sa.Column("avg_accuracy_lift", sa.Float, nullable=True),
        sa.Column("avg_tokens_consumed", sa.Float, nullable=True),
        sa.Column("avg_latency_ms", sa.Integer, nullable=True),
        sa.Column("csat_delta", sa.Float, nullable=True),
        # Content
        sa.Column("prompt_template", sa.Text, nullable=True),
        sa.Column("configuration", sa.Text, server_default="{}"),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "uq_technique_version",
        "technique_versions",
        ["company_id", "technique_id", "version"],
    )

    op.create_index(
        "ix_tech_ver_company_tech",
        "technique_versions",
        ["company_id", "technique_id"],
    )


def downgrade() -> None:
    op.drop_table("technique_versions")
    op.drop_table("technique_executions")
    op.drop_table("technique_configurations")
