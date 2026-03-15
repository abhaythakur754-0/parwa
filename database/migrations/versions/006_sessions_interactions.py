"""Empty migration after consolidation

Revision ID: 006
Revises: 005
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
