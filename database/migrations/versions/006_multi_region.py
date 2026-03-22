"""
Multi-Region Database Migration.

Alembic migration for multi-region support.
Adds region column to companies table and region-specific compliance settings.

Revision ID: 006
Revises: 005
Create Date: 2026-03-22

Changes:
- Add region column to companies table
- Add region-specific compliance settings
- Create indexes for region-based queries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration for multi-region support."""
    # Add region column to companies table
    op.add_column(
        'companies',
        sa.Column(
            'region',
            sa.String(50),
            nullable=True,
            server_default='us-east-1',
            comment='Region identifier for data residency'
        )
    )

    # Add region-specific compliance settings column
    op.add_column(
        'companies',
        sa.Column(
            'region_compliance_settings',
            postgresql.JSONB,
            nullable=True,
            server_default='{}',
            comment='Region-specific compliance configuration'
        )
    )

    # Add data residency level column
    op.add_column(
        'companies',
        sa.Column(
            'data_residency_level',
            sa.String(20),
            nullable=True,
            server_default='standard',
            comment='Data residency level: standard, strict, maximum'
        )
    )

    # Create index on region for efficient queries
    op.create_index(
        'ix_companies_region',
        'companies',
        ['region'],
        unique=False
    )

    # Create index on data_residency_level
    op.create_index(
        'ix_companies_data_residency_level',
        'companies',
        ['data_residency_level'],
        unique=False
    )

    # Add region column to users table
    op.add_column(
        'users',
        sa.Column(
            'preferred_region',
            sa.String(50),
            nullable=True,
            server_default='us-east-1',
            comment='Preferred region for user operations'
        )
    )

    # Add region column to tickets table
    op.add_column(
        'tickets',
        sa.Column(
            'region',
            sa.String(50),
            nullable=True,
            comment='Region where ticket was created'
        )
    )

    # Create index on tickets region
    op.create_index(
        'ix_tickets_region',
        'tickets',
        ['region'],
        unique=False
    )

    # Add region column to audit_logs table
    op.add_column(
        'audit_logs',
        sa.Column(
            'region',
            sa.String(50),
            nullable=True,
            comment='Region where audit event occurred'
        )
    )

    # Create index on audit_logs region
    op.create_index(
        'ix_audit_logs_region',
        'audit_logs',
        ['region'],
        unique=False
    )

    # Create region_settings table for storing region-specific configurations
    op.create_table(
        'region_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('region_code', sa.String(50), nullable=False, unique=True),
        sa.Column('region_name', sa.String(100), nullable=False),
        sa.Column('compliance_requirements', postgresql.JSONB, nullable=True),
        sa.Column('data_residency_rules', postgresql.JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on region_settings region_code
    op.create_index(
        'ix_region_settings_region_code',
        'region_settings',
        ['region_code'],
        unique=True
    )

    # Insert default region settings
    op.execute("""
        INSERT INTO region_settings (region_code, region_name, compliance_requirements, data_residency_rules, is_active)
        VALUES
            ('us-east-1', 'US East (N. Virginia)', '{"gdpr": false, "hipaa": true}', '{"storage": "us", "backup": "us"}', true),
            ('us-west-2', 'US West (Oregon)', '{"gdpr": false, "hipaa": true}', '{"storage": "us", "backup": "us"}', true),
            ('eu-west-1', 'EU (Ireland)', '{"gdpr": true, "hipaa": false}', '{"storage": "eu", "backup": "eu"}', true),
            ('eu-central-1', 'EU (Frankfurt)', '{"gdpr": true, "hipaa": false}', '{"storage": "eu", "backup": "eu"}', true),
            ('ap-southeast-1', 'Asia Pacific (Singapore)', '{"gdpr": false, "hipaa": false}', '{"storage": "ap", "backup": "ap"}', true),
            ('ap-northeast-1', 'Asia Pacific (Tokyo)', '{"gdpr": false, "hipaa": false}', '{"storage": "ap", "backup": "ap"}', true)
    """)


def downgrade() -> None:
    """Revert migration for multi-region support."""
    # Drop region_settings table
    op.drop_index('ix_region_settings_region_code', 'region_settings')
    op.drop_table('region_settings')

    # Drop audit_logs region columns
    op.drop_index('ix_audit_logs_region', 'audit_logs')
    op.drop_column('audit_logs', 'region')

    # Drop tickets region columns
    op.drop_index('ix_tickets_region', 'tickets')
    op.drop_column('tickets', 'region')

    # Drop users region column
    op.drop_column('users', 'preferred_region')

    # Drop companies indexes
    op.drop_index('ix_companies_data_residency_level', 'companies')
    op.drop_index('ix_companies_region', 'companies')

    # Drop companies columns
    op.drop_column('companies', 'data_residency_level')
    op.drop_column('companies', 'region_compliance_settings')
    op.drop_column('companies', 'region')
