"""Shadow Mode: dual-control system tables — shadow_log, shadow_preferences, system_mode on companies

Revision ID: 026_shadow_mode
Revises: 025_day6_missing_features
Create Date: 2026-04-17

Adds:
- shadow_log table (audit trail for shadow mode actions)
- shadow_preferences table (per-company per-category mode preferences)
- system_mode column on companies (shadow/supervised/graduated)
- Composite indexes for efficient querying
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "026_shadow_mode"
down_revision = "025_day6_missing_features"
branch_labels = None
depends_on = None


def upgrade():
    # ── shadow_log ──────────────────────────────────────────────
    op.create_table(
        "shadow_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column(
            "action_payload", postgresql.JSONB,
            nullable=False, server_default="{}",
        ),
        sa.Column("jarvis_risk_score", sa.Float(), nullable=True),
        sa.Column(
            "mode", sa.String(15), nullable=False,
            server_default="supervised",
        ),
        sa.Column("manager_decision", sa.String(15), nullable=True),
        sa.Column("manager_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "idx_shadow_log_company",
        "shadow_log",
        ["company_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_shadow_log_mode",
        "shadow_log",
        ["mode", "manager_decision"],
    )

    # ── shadow_preferences ──────────────────────────────────────
    op.create_table(
        "shadow_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_category", sa.String(50), nullable=False),
        sa.Column(
            "preferred_mode", sa.String(15), nullable=False,
            server_default="shadow",
        ),
        sa.Column(
            "set_via", sa.String(10), nullable=False,
            server_default="ui",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "company_id", "action_category",
            name="uq_shadow_prefs_company_category",
        ),
    )

    op.create_index(
        "idx_shadow_prefs_company",
        "shadow_preferences",
        ["company_id"],
    )

    # ── system_mode on companies ────────────────────────────────
    op.add_column(
        "companies",
        sa.Column(
            "system_mode", sa.String(15), nullable=False,
            server_default="supervised",
        ),
    )


def downgrade():
    op.drop_column("companies", "system_mode")
    op.drop_index("idx_shadow_prefs_company", table_name="shadow_preferences")
    op.drop_index("idx_shadow_log_mode", table_name="shadow_log")
    op.drop_index("idx_shadow_log_company", table_name="shadow_log")
    op.drop_table("shadow_preferences")
    op.drop_table("shadow_log")
