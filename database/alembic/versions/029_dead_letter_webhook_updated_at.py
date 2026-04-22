"""029_dead_letter_webhook_updated_at: Add missing updated_at column to dead_letter_webhooks

The webhook_health_service writes to updated_at on every status transition
(retry, process, discard), but the original migration 024 and ORM model
omitted the column, which would cause runtime SQLAlchemy errors.

Revises: 028_shadow_queues
"""

from alembic import op
import sqlalchemy as sa

revision = "029_dead_letter_webhook_updated_at"
down_revision = "028_shadow_queues"


def upgrade() -> None:
    op.add_column(
        "dead_letter_webhooks",
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=True,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("dead_letter_webhooks", "updated_at")
