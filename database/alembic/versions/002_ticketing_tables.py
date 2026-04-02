"""002_ticketing_tables: Sessions, Interactions, Customers, Channels, Attachments, Notes

Revision ID: 002
Revises: 001
Create Date: 2026-04-02

"""

from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'customers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('external_id', sa.String(255)),
        sa.Column('email', sa.String(255)),
        sa.Column('phone', sa.String(50)),
        sa.Column('name', sa.String(255)),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'channels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('channel_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='SET NULL')),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), server_default='open'),
        sa.Column('subject', sa.String(255)),
        sa.Column('priority', sa.String(20), server_default='normal'),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('assigned_to', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('classification_intent', sa.String(100)),
        sa.Column('classification_type', sa.String(50)),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime),
    )

    op.create_index('ix_sessions_customer_id', 'sessions', ['customer_id'])
    op.create_index('ix_sessions_status', 'sessions', ['status'])

    op.create_table(
        'interactions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'ticket_attachments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_url', sa.Text, nullable=False),
        sa.Column('file_size', sa.Integer),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('uploaded_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'ticket_internal_notes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_pinned', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('ticket_internal_notes')
    op.drop_table('ticket_attachments')
    op.drop_table('interactions')
    op.drop_table('sessions')
    op.drop_table('channels')
    op.drop_table('customers')
