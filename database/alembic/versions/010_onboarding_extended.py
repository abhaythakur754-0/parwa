"""010_onboarding_extended: user_details table + extend onboarding_sessions

Revision ID: 010
Revises: 009
Create Date: 2026-04-04

Week 6 Day 1: Post-Payment Details + Onboarding State

BC-001: Every tenant table has company_id.
"""

from alembic import op
import sqlalchemy as sa

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_details table for post-payment details collection
    op.create_table(
        'user_details',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('full_name', sa.String(100), nullable=False),
        sa.Column('company_name', sa.String(100), nullable=False),
        sa.Column('work_email', sa.String(255)),
        sa.Column('work_email_verified', sa.Boolean, server_default='0'),
        sa.Column('work_email_verification_token', sa.String(64)),
        sa.Column('work_email_verification_sent_at', sa.DateTime),
        sa.Column('industry', sa.String(50), nullable=False),
        sa.Column('company_size', sa.String(20)),
        sa.Column('website', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Extend onboarding_sessions with additional columns for wizard state
    op.add_column('onboarding_sessions', sa.Column('legal_accepted', sa.Boolean, server_default='0'))
    op.add_column('onboarding_sessions', sa.Column('terms_accepted_at', sa.DateTime))
    op.add_column('onboarding_sessions', sa.Column('privacy_accepted_at', sa.DateTime))
    op.add_column('onboarding_sessions', sa.Column('ai_data_accepted_at', sa.DateTime))
    op.add_column('onboarding_sessions', sa.Column('integrations', sa.Text, server_default='{}'))
    op.add_column('onboarding_sessions', sa.Column('knowledge_base_files', sa.Text, server_default='[]'))
    op.add_column('onboarding_sessions', sa.Column('ai_name', sa.String(50), server_default='Jarvis'))
    op.add_column('onboarding_sessions', sa.Column('ai_tone', sa.String(20), server_default='professional'))
    op.add_column('onboarding_sessions', sa.Column('ai_response_style', sa.String(20), server_default='concise'))
    op.add_column('onboarding_sessions', sa.Column('ai_greeting', sa.Text))
    op.add_column('onboarding_sessions', sa.Column('first_victory_completed', sa.Boolean, server_default='0'))
    op.add_column('onboarding_sessions', sa.Column('details_completed', sa.Boolean, server_default='0'))
    op.add_column('onboarding_sessions', sa.Column('wizard_started', sa.Boolean, server_default='0'))


def downgrade() -> None:
    # Remove added columns from onboarding_sessions
    op.drop_column('onboarding_sessions', 'wizard_started')
    op.drop_column('onboarding_sessions', 'details_completed')
    op.drop_column('onboarding_sessions', 'first_victory_completed')
    op.drop_column('onboarding_sessions', 'ai_greeting')
    op.drop_column('onboarding_sessions', 'ai_response_style')
    op.drop_column('onboarding_sessions', 'ai_tone')
    op.drop_column('onboarding_sessions', 'ai_name')
    op.drop_column('onboarding_sessions', 'knowledge_base_files')
    op.drop_column('onboarding_sessions', 'integrations')
    op.drop_column('onboarding_sessions', 'ai_data_accepted_at')
    op.drop_column('onboarding_sessions', 'privacy_accepted_at')
    op.drop_column('onboarding_sessions', 'terms_accepted_at')
    op.drop_column('onboarding_sessions', 'legal_accepted')

    # Drop user_details table
    op.drop_table('user_details')
