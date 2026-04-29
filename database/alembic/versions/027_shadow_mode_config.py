"""Shadow Mode Config + Ticket Shadow Fields

Revision ID: 027_shadow_mode_config
Revises: 026_shadow_mode
Create Date: 2026-04-17

Adds:
- undo_window_minutes column on companies (default: 30)
- risk_threshold_shadow column on companies (default: 0.7)
- risk_threshold_auto column on companies (default: 0.3)
- shadow_actions_remaining column on companies (Stage 0 counter)
- shadow_status column on tickets
- risk_score column on tickets
- approved_by column on tickets
- approved_at column on tickets
- shadow_log_id column on tickets
"""

from alembic import op
import sqlalchemy as sa

revision = "027_shadow_mode_config"
down_revision = "026_shadow_mode"
branch_labels = None
depends_on = None


def upgrade():
    # ── Shadow Mode Config on Companies ──────────────────────────
    op.add_column(
        "companies",
        sa.Column(
            "undo_window_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "risk_threshold_shadow",
            sa.Float(),
            nullable=False,
            server_default="0.7",
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "risk_threshold_auto",
            sa.Float(),
            nullable=False,
            server_default="0.3",
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "shadow_actions_remaining",
            sa.Integer(),
            nullable=True,
            server_default="10",
        ),
    )

    # ── Ticket Shadow Fields ─────────────────────────────────────
    op.add_column(
        "tickets",
        sa.Column(
            "shadow_status",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("risk_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("approved_by", sa.String(36), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "shadow_log_id",
            sa.String(36),
            sa.ForeignKey("shadow_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Indexes for efficient filtering
    op.create_index(
        "idx_tickets_shadow_status",
        "tickets",
        ["shadow_status"],
    )
    op.create_index(
        "idx_tickets_risk_score",
        "tickets",
        ["risk_score"],
    )


def downgrade():
    # Ticket shadow fields
    op.drop_index("idx_tickets_risk_score", table_name="tickets")
    op.drop_index("idx_tickets_shadow_status", table_name="tickets")
    op.drop_column("tickets", "shadow_log_id")
    op.drop_column("tickets", "approved_at")
    op.drop_column("tickets", "approved_by")
    op.drop_column("tickets", "risk_score")
    op.drop_column("tickets", "shadow_status")

    # Company shadow config
    op.drop_column("companies", "shadow_actions_remaining")
    op.drop_column("companies", "risk_threshold_auto")
    op.drop_column("companies", "risk_threshold_shadow")
    op.drop_column("companies", "undo_window_minutes")
