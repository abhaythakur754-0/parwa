"""Audit Trail view and IP/User-Agent tracking

Revision ID: 003
Revises: 002
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add missing ip_address column to audit_logs
    op.add_column(
        'audit_logs',
        sa.Column('ip_address', sa.VARCHAR(length=45), nullable=True)
    )
    
    # 2. Add user_agent column
    op.add_column(
        'audit_logs',
        sa.Column('user_agent', sa.Text(), nullable=True)
    )
    
    # 3. Create human-readable view for admin dashboards
    op.execute("""
        CREATE OR REPLACE VIEW v_audit_trail_readable AS
        SELECT 
            al.id,
            t.name as tenant_name,
            al.actor_type,
            COALESCE(u.email, 'System/AI') as actor_identifier,
            al.action,
            al.resource_type,
            al.resource_id,
            al.ip_address,
            al.user_agent,
            al.created_at,
            al.payload::text as payload_text,
            al.sha256_hash
        FROM audit_logs al
        LEFT JOIN tenants t ON al.tenant_id = t.id
        LEFT JOIN users u ON al.actor_id = u.id;
    """)


def downgrade() -> None:
    # 1. Drop the view
    op.execute("DROP VIEW IF EXISTS v_audit_trail_readable")
    
    # 2. Drop the columns
    op.drop_column('audit_logs', 'user_agent')
    op.drop_column('audit_logs', 'ip_address')
