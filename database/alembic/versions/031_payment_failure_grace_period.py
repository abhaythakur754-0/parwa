"""Add grace_period_ends_at to payment_failures table

Revision ID: 031_payment_failure_grace_period
Revises: 030_jarvis_production
Create Date: 2025-01-01

Adds a 7-day grace period tracking column to the payment_failures table.
When a payment fails, the subscription enters 'past_due' status and
grace_period_ends_at is set to now + 7 days. After expiration, a cron
job escalates to full 'payment_failed' suspension.
"""

from alembic import op
import sqlalchemy as sa

revision = "031_payment_failure_grace_period"
down_revision = "030_jarvis_production"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_failures",
        sa.Column(
            "grace_period_ends_at",
            sa.DateTime(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("payment_failures", "grace_period_ends_at")
