"""Compliance data partitions and constraints

Revision ID: 004
Revises: 003
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Apply compliance constraints and privacy partitions."""
    
    # GDPR Right to Erasure / PII Data Partitioning
    # Adding a specific compliance_status and retention_expires_at to track data lifecycle
    
    op.add_column(
        'customers',
        sa.Column('compliance_status', sa.Text(), server_default='active', nullable=False)
    )
    
    op.add_column(
        'customers',
        sa.Column('retention_expires_at', sa.TIMESTAMP(timezone=True), nullable=True)
    )
    
    # Add constraint to ensure compliance status is valid
    op.create_check_constraint(
        'ck_customers_compliance_status',
        'customers',
        "compliance_status IN ('active', 'erasure_requested', 'erased', 'frozen')"
    )

    # Add an index to rapidly find data that needs to be purged based on retention policy
    op.create_index(
        'ix_customers_retention_expires_at',
        'customers',
        ['retention_expires_at']
    )

    # Portability Requests tracking table
    op.create_table(
        'compliance_data_requests',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_type', sa.Text(), nullable=False), # 'access', 'erasure', 'portability'
        sa.Column('status', sa.Text(), server_default='pending', nullable=False), # 'pending', 'processing', 'completed', 'failed'
        sa.Column('details', JSONB(), server_default="{}", nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.CheckConstraint("request_type IN ('access', 'erasure', 'portability')", name='ck_compliance_req_type'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name='ck_compliance_req_status')
    )
    
    op.create_index('ix_compliance_req_tenant_status', 'compliance_data_requests', ['tenant_id', 'status'])


def downgrade() -> None:
    """Remove compliance constraints and partitions."""
    
    # Drop Portability Tracking Table
    op.drop_table('compliance_data_requests')
    
    # Remove indexes and check constraints from Customers
    op.drop_index('ix_customers_retention_expires_at', table_name='customers')
    op.drop_constraint('ck_customers_compliance_status', 'customers', type_='check')
    
    # Drop Columns
    op.drop_column('customers', 'retention_expires_at')
    op.drop_column('customers', 'compliance_status')
