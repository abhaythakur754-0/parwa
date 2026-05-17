"""013_some_migration: Stub migration bridging 012 to 014

Revision ID: 013_some_migration
Revises: 012
Create Date: 2026-04-12

No-op migration to fill the gap in the version chain between
012_jarvis_system and 014_email_verification.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013_some_migration'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op migration."""
    pass


def downgrade() -> None:
    """No-op migration."""
    pass
