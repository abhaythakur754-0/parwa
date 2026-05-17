"""Shadow Mode tables for Phase 4 Feature Completion.

Creates:
  - shadow_mode_configs: Per-company shadow mode settings
  - shadow_mode_results: Comparison results between live and shadow variants

Revision ID: 024_shadow_mode_tables
Revises: 023_paddle_reconciliation
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "024_shadow_mode_tables"
down_revision = "023_paddle_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── shadow_mode_configs ──
    op.create_table(
        "shadow_mode_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("live_variant", sa.String(50), nullable=False),
        sa.Column("shadow_variant", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="shadow"),
        sa.Column("live_instance_id", sa.String(36), nullable=True),
        sa.Column("shadow_instance_id", sa.String(36), nullable=True),
        sa.Column("sample_rate", sa.Numeric(5, 4), server_default="1.0000"),
        sa.Column(
            "auto_graduation_threshold",
            sa.Numeric(5, 4),
            server_default="0.9500",
        ),
        sa.Column("auto_graduation_window", sa.Integer(), server_default="100"),
        sa.Column(
            "supervised_timeout_seconds",
            sa.Integer(),
            server_default="300",
        ),
        sa.Column(
            "auto_promote_to_supervised",
            sa.Boolean(),
            server_default="true",
        ),
        sa.Column(
            "auto_promote_to_graduated",
            sa.Boolean(),
            server_default="false",
        ),
        sa.Column("current_quality_streak", sa.Integer(), server_default="0"),
        sa.Column("total_comparisons", sa.Integer(), server_default="0"),
        sa.Column("shadow_wins", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enabled_by_user_id", sa.String(36), nullable=True),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.Column("supervised_at", sa.DateTime(), nullable=True),
        sa.Column("graduated_at", sa.DateTime(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('shadow', 'supervised', 'graduated', 'disabled')",
            name="ck_shadow_config_valid_status",
        ),
        sa.CheckConstraint(
            "sample_rate >= 0 AND sample_rate <= 1",
            name="ck_shadow_config_sample_rate_range",
        ),
        sa.CheckConstraint(
            "auto_graduation_threshold >= 0 AND auto_graduation_threshold <= 1",
            name="ck_shadow_config_grad_threshold_range",
        ),
    )

    op.create_index(
        "ix_shadow_config_comp_active",
        "shadow_mode_configs",
        ["company_id", "is_active"],
    )
    op.create_index(
        "ix_shadow_config_comp_status",
        "shadow_mode_configs",
        ["company_id", "status"],
    )

    # ── shadow_mode_results ──
    op.create_table(
        "shadow_mode_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "config_id",
            sa.String(36),
            sa.ForeignKey("shadow_mode_configs.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("ticket_id", sa.String(36), nullable=True, index=True),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("message_hash", sa.String(64), nullable=True),
        sa.Column("live_variant", sa.String(50), nullable=False),
        sa.Column("live_response", sa.Text(), nullable=True),
        sa.Column("live_quality_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("live_latency_ms", sa.Integer(), nullable=True),
        sa.Column("live_tokens_used", sa.Integer(), nullable=True),
        sa.Column("shadow_variant", sa.String(50), nullable=False),
        sa.Column("shadow_response", sa.Text(), nullable=True),
        sa.Column("shadow_quality_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("shadow_latency_ms", sa.Integer(), nullable=True),
        sa.Column("shadow_tokens_used", sa.Integer(), nullable=True),
        sa.Column("quality_delta", sa.Numeric(7, 4), nullable=True),
        sa.Column("latency_delta_ms", sa.Integer(), nullable=True),
        sa.Column("token_delta", sa.Integer(), nullable=True),
        sa.Column("shadow_winner", sa.Boolean(), nullable=True),
        sa.Column("human_reviewed", sa.Boolean(), server_default="false"),
        sa.Column("human_verdict", sa.String(20), nullable=True),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "mode_at_comparison",
            sa.String(20),
            nullable=False,
            server_default="shadow",
        ),
        sa.Column("auto_fallback_used", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "mode_at_comparison IN ('shadow', 'supervised')",
            name="ck_shadow_result_valid_mode",
        ),
        sa.CheckConstraint(
            "human_verdict IN ('shadow_better', 'live_better', 'equal', 'skip') "
            "OR human_verdict IS NULL",
            name="ck_shadow_result_valid_verdict",
        ),
    )

    op.create_index(
        "ix_shadow_result_comp_config",
        "shadow_mode_results",
        ["company_id", "config_id", "created_at"],
    )
    op.create_index(
        "ix_shadow_result_comp_winner",
        "shadow_mode_results",
        ["company_id", "shadow_winner"],
    )
    op.create_index(
        "ix_shadow_result_comp_review",
        "shadow_mode_results",
        ["company_id", "human_reviewed"],
    )


def downgrade() -> None:
    op.drop_table("shadow_mode_results")
    op.drop_table("shadow_mode_configs")
