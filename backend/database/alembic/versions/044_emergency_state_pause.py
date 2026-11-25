"""Create the persisted company-wide AI emergency pause table.

Revision ID: 044_emergency_state_pause
Revises: 043_razorpay_ledger_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = "044_emergency_state_pause"
down_revision = "043_razorpay_ledger_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emergency_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paused_channels", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "paused_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("paused_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_emergency_states_company_id",
        "emergency_states",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_emergency_states_company_id", table_name="emergency_states")
    op.drop_table("emergency_states")
