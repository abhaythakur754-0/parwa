"""004_integration_tables: integrations, connectors, MCP, DB connections, etc.

Revision ID: 004
Revises: 003
Create Date: 2026-04-02

"""

from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'integrations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('integration_type', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('status', sa.String(50), server_default='disconnected'),
        sa.Column('credentials_encrypted', sa.Text),
        sa.Column('settings', sa.Text, server_default='{}'),
        sa.Column('last_sync', sa.DateTime),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'rest_connectors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('integration_id', sa.String(36), sa.ForeignKey('integrations.id'), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('auth_type', sa.String(50), nullable=False),
        sa.Column('auth_config', sa.Text),
        sa.Column('headers', sa.Text, server_default='{}'),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'webhook_integrations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('integration_id', sa.String(36), sa.ForeignKey('integrations.id'), nullable=False),
        sa.Column('webhook_url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(255)),
        sa.Column('events', sa.Text, server_default='[]'),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'mcp_connections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('server_url', sa.String(500)),
        sa.Column('auth_token', sa.Text),
        sa.Column('status', sa.String(50), server_default='disconnected'),
        sa.Column('capabilities', sa.Text, server_default='[]'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'db_connections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('db_type', sa.String(50), nullable=False),
        sa.Column('connection_string', sa.Text),
        sa.Column('is_readonly', sa.Boolean, server_default='1'),
        sa.Column('status', sa.String(50), server_default='disconnected'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'event_buffer',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_data', sa.Text),
        sa.Column('ttl_seconds', sa.Integer, server_default='86400'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'error_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('error_type', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text, nullable=False),
        sa.Column('stack_trace', sa.Text),
        sa.Column('path', sa.String(500)),
        sa.Column('method', sa.String(10)),
        sa.Column('status_code', sa.Integer),
        sa.Column('correlation_id', sa.String(36)),
        sa.Column('resolved', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'outgoing_webhooks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(255)),
        sa.Column('events', sa.Text, server_default='[]'),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('last_delivery_at', sa.DateTime),
        sa.Column('last_status', sa.String(50)),
        sa.Column('failure_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('outgoing_webhooks')
    op.drop_table('error_log')
    op.drop_table('event_buffer')
    op.drop_table('db_connections')
    op.drop_table('mcp_connections')
    op.drop_table('webhook_integrations')
    op.drop_table('rest_connectors')
    op.drop_table('integrations')
