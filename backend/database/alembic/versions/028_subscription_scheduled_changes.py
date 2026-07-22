"""Add scheduled_change_type, scheduled_change_variant, metadata_json to subscriptions; make user_id nullable in cancellation_requests.

Revision ID: 028_subscription_scheduled_changes
Revises: 027

Renumbered from 024 to 028 to resolve Alembic branch conflict
(original 024 conflicted with 024_shadow_mode_tables).
"""
from alembic import op
import sqlalchemy as sa

revision = "028_subscription_scheduled_changes"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to subscriptions table
    op.add_column(
        "subscriptions",
        sa.Column("scheduled_change_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("scheduled_change_variant", sa.String(50), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("metadata_json", sa.Text, nullable=True),
    )

    # Make user_id nullable in cancellation_requests (Bug 7 fix)
    op.alter_column(
        "cancellation_requests",
        "user_id",
        existing_type=sa.String(36),
        nullable=True,
    )


def downgrade() -> None:
    # Revert user_id to NOT NULL
    op.alter_column(
        "cancellation_requests",
        "user_id",
        existing_type=sa.String(36),
        nullable=False,
    )

    # Remove new columns from subscriptions
    op.drop_column("subscriptions", "metadata_json")
    op.drop_column("subscriptions", "scheduled_change_variant")
    op.drop_column("subscriptions", "scheduled_change_type")