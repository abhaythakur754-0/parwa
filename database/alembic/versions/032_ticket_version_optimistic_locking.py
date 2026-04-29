"""add_ticket_version_for_optimistic_locking

Revision ID: 032_ticket_version_optimistic_locking
Revises: 031_payment_failure_grace_period
Create Date: 2026-04-28

"""

from alembic import op
import sqlalchemy as sa

revision = "032_ticket_version_optimistic_locking"
down_revision = "031_payment_failure_grace_period"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_tickets_version", "tickets", ["version"])


def downgrade() -> None:
    op.drop_index("ix_tickets_version", table_name="tickets")
    op.drop_column("tickets", "version")
