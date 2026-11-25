"""Ensure persisted company-wide AI pause storage exists.

Revision ID: 044_emergency_state_pause
Revises: 043_razorpay_ledger_idempotency

The original emergency_states table is already created by migration 001.
This guarded migration keeps older/partial installations compatible without
attempting to create the table twice on databases that ran the full chain.
"""
from alembic import op
import sqlalchemy as sa

revision = "044_emergency_state_pause"
down_revision = "043_razorpay_ledger_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("emergency_states"):
        return

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
        sa.Column("paused_channels", sa.Text(), nullable=False, server_default=sa.text("''")),
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
    # The table predates this guarded migration (revision 001) on normal
    # installations. Never drop pre-existing tenant emergency state here.
    pass
