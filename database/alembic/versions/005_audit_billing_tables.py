"""005_audit_billing_tables: audit_trail, webhook_events,
rate_limit_events, api_key_audit_log, subscriptions, invoices,
overage_charges, transactions, cancellation_requests.

Revision ID: 005
Revises: 004
Create Date: 2026-04-02

BC-001: Every table has company_id.
BC-002: All money fields DECIMAL(10,2).
"""

from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_trail',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('actor_id', sa.String(36)),
        sa.Column('actor_type', sa.String(50), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100)),
        sa.Column('resource_id', sa.String(36)),
        sa.Column('old_value', sa.Text),
        sa.Column('new_value', sa.Text),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(100)),
        sa.Column('payload', sa.Text),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('processing_started_at', sa.DateTime),
        sa.Column('processing_completed_at', sa.DateTime),
        sa.Column('retry_count', sa.Integer, server_default='0'),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index('ix_webhook_events_provider_event_id', 'webhook_events', ['provider', 'event_id'], unique=True)
    op.create_index('ix_webhook_events_event_id', 'webhook_events', ['event_id'])

    op.create_table(
        'rate_limit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('key', sa.String(255), nullable=False, index=True),
        sa.Column('endpoint_category', sa.String(50), nullable=False, index=True),
        sa.Column('failure_count', sa.Integer, server_default='0'),
        sa.Column('lockout_until', sa.DateTime, nullable=True),
        sa.Column('last_attempt_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'api_key_audit_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('api_key_id', sa.String(36), sa.ForeignKey('api_keys.id', ondelete='SET NULL'), nullable=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('endpoint', sa.String(255)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Billing tables
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tier', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('current_period_start', sa.DateTime),
        sa.Column('current_period_end', sa.DateTime),
        sa.Column('cancel_at_period_end', sa.Boolean, server_default='0'),
        sa.Column('paddle_subscription_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'invoices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('paddle_invoice_id', sa.String(255)),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('invoice_date', sa.DateTime),
        sa.Column('due_date', sa.DateTime),
        sa.Column('paid_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'overage_charges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('tickets_over_limit', sa.Integer, nullable=False, server_default='0'),
        sa.Column('charge_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('paddle_charge_id', sa.String(255)),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'transactions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('paddle_transaction_id', sa.String(255)),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD'),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('transaction_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'cancellation_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.Text, nullable=False),
        sa.Column('feedback', sa.Text),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('contacted_at', sa.DateTime),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('cancellation_requests')
    op.drop_table('transactions')
    op.drop_table('overage_charges')
    op.drop_table('invoices')
    op.drop_table('subscriptions')
    op.drop_table('api_key_audit_log')
    op.drop_table('rate_limit_events')
    op.drop_table('webhook_events')
    op.drop_table('audit_trail')
