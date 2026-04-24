"""001_initial_schema: Core tables (companies, users, api_keys, sessions, etc.)

Revision ID: 001
Revises: None
Create Date: 2026-04-02

"""

from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'companies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('industry', sa.String(255)),
        sa.Column('subscription_tier', sa.String(50), nullable=False, server_default='mini_parwa'),
        sa.Column('subscription_status', sa.String(50), nullable=False, server_default='trialing'),
        sa.Column('mode', sa.String(50), nullable=False, server_default='shadow'),
        sa.Column('paddle_customer_id', sa.String(255)),
        sa.Column('paddle_subscription_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index('ix_companies_subscription_tier', 'companies', ['subscription_tier'])

    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('phone', sa.String(50)),
        sa.Column('avatar_url', sa.String(500)),
        sa.Column('role', sa.String(50), nullable=False, server_default='owner'),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('is_verified', sa.Boolean, server_default='0'),
        sa.Column('mfa_enabled', sa.Boolean, server_default='0'),
        sa.Column('mfa_secret', sa.String(255)),
        sa.Column('failed_login_count', sa.Integer, server_default='0'),
        sa.Column('locked_until', sa.DateTime),
        sa.Column('last_failed_login_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index('ix_users_company_id', 'users', ['company_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('device_info', sa.String(500)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('expires_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('scope', sa.String(50), server_default='read'),
        sa.Column('scopes', sa.Text, server_default='[]'),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('revoked', sa.Boolean, server_default='0'),
        sa.Column('revoked_at', sa.DateTime),
        sa.Column('rotated_from_id', sa.String(36)),
        sa.Column('grace_ends_at', sa.DateTime),
        sa.Column('created_by', sa.String(36)),
        sa.Column('last_used_at', sa.DateTime),
        sa.Column('expires_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index('ix_api_keys_company_id', 'api_keys', ['company_id'])
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'])

    op.create_table(
        'company_settings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('ooo_status', sa.String(50)),
        sa.Column('ooo_message', sa.Text),
        sa.Column('ooo_until', sa.DateTime),
        sa.Column('brand_voice', sa.Text),
        sa.Column('tone_guidelines', sa.Text),
        sa.Column('prohibited_phrases', sa.Text),
        sa.Column('pii_patterns', sa.Text),
        sa.Column('top_k', sa.Integer, server_default='5'),
        sa.Column('similarity_threshold', sa.Numeric(5, 2), server_default='0.70'),
        sa.Column('rerank_model', sa.String(255)),
        sa.Column('classification_config', sa.Text, server_default='{}'),
        sa.Column('assignment_rules', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'agents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('variant', sa.String(50), server_default='general'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('capacity_used', sa.Integer, server_default='0'),
        sa.Column('capacity_max', sa.Integer, server_default='0'),
        sa.Column('accuracy_rate', sa.Numeric(5, 2), server_default='0.00'),
        sa.Column('tickets_resolved', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'emergency_states',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('is_paused', sa.Boolean, server_default='0'),
        sa.Column('paused_channels', sa.Text, server_default='[]'),
        sa.Column('paused_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('paused_at', sa.DateTime),
        sa.Column('reason', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'user_notification_preferences',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean, server_default='1'),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'mfa_secrets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('secret_key', sa.String(255), nullable=False),
        sa.Column('is_verified', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'backup_codes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('is_used', sa.Boolean, server_default='0'),
        sa.Column('used_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'verification_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False, index=True),
        sa.Column('purpose', sa.String(50), server_default='email_verification'),
        sa.Column('is_used', sa.Boolean, server_default='0'),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('is_used', sa.Boolean, server_default='0'),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('provider_account_id', sa.String(255)),
        sa.Column('email', sa.String(255)),
        sa.Column('access_token', sa.Text),
        sa.Column('refresh_token', sa.Text),
        sa.Column('token_expires_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('oauth_accounts')
    op.drop_table('password_reset_tokens')
    op.drop_table('verification_tokens')
    op.drop_table('backup_codes')
    op.drop_table('mfa_secrets')
    op.drop_table('user_notification_preferences')
    op.drop_table('emergency_states')
    op.drop_table('agents')
    op.drop_table('company_settings')
    op.drop_table('api_keys')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    op.drop_table('companies')
