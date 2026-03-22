"""Agent Lightning specific updates

Revision ID: 002
Revises: 001
Create Date: 2026-03-16

Updates the human_corrections table to support Agent Lightning's continuous training loops
by tracking which corrections have already been exported.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add a column to track if a correction has been exported for LoRA training
    op.add_column(
        'human_corrections',
        sa.Column('exported_for_training', sa.Boolean(), server_default='false', nullable=False)
    )

    # Create an index to quickly find un-exported, approved corrections for a tenant
    op.create_index(
        'ix_human_corrections_tenant_exported',
        'human_corrections',
        ['tenant_id', 'exported_for_training']
    )


def downgrade() -> None:
    # Drop the index
    op.drop_index('ix_human_corrections_tenant_exported', table_name='human_corrections')

    # Drop the column
    op.drop_column('human_corrections', 'exported_for_training')
