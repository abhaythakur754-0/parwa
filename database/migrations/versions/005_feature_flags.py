"""Feature Flags schema

Revision ID: 005
Revises: 004
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Feature flags allow DB-based overrides (e.g. per-tenant routing)
    op.create_table(
        'feature_flags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('flag_key', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default="false", nullable=False),
        sa.Column('conditions', JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    # Index on tenant_id + flag_key for fast lookups
    op.create_index('ix_feature_flags_tenant_key', 'feature_flags', ['tenant_id', 'flag_key'], unique=True)
    op.create_index('ix_feature_flags_flag_key', 'feature_flags', ['flag_key'])


def downgrade() -> None:
    op.drop_index('ix_feature_flags_flag_key', table_name='feature_flags')
    op.drop_index('ix_feature_flags_tenant_key', table_name='feature_flags')
    op.drop_table('feature_flags')
