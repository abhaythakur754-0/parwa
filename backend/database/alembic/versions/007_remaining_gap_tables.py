"""007_remaining_gap_tables: approval_queues, auto_approve_rules,
executed_actions, undo_log, phone_otps, response_templates, email_logs,
rate_limit_counters, feature_flags, classification_log,
guardrails_audit_log, guardrails_blocked_queue, ai_response_feedback,
confidence_thresholds, human_corrections, approval_batches,
notifications, first_victories.

Revision ID: 007
Revises: 006
Create Date: 2026-04-02

BC-001: Every tenant table has company_id.
BC-002: Money fields DECIMAL(10,2).
"""

from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Approval tables
    op.create_table(
        'approval_queues',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('confidence_score', sa.Numeric(5, 2)),
        sa.Column('risk_level', sa.String(50)),
        sa.Column('amount', sa.Numeric(10, 2)),
        sa.Column('reasoning', sa.Text),
        sa.Column('response_data', sa.Text),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('batch_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('resolved_by', sa.String(36), sa.ForeignKey('users.id')),
    )

    op.create_table(
        'auto_approve_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('min_confidence', sa.Numeric(5, 2), nullable=False),
        sa.Column('max_amount', sa.Numeric(10, 2)),
        sa.Column('risk_levels', sa.Text, server_default='low'),
        sa.Column('is_active', sa.Boolean, server_default='0'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'executed_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('approval_id', sa.String(36), sa.ForeignKey('approval_queues.id')),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('action_data', sa.Text),
        sa.Column('response_data', sa.Text),
        sa.Column('amount', sa.Numeric(10, 2)),
        sa.Column('executed_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'undo_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('executed_action_id', sa.String(36), sa.ForeignKey('executed_actions.id'), nullable=False),
        sa.Column('undo_type', sa.String(50), nullable=False),
        sa.Column('original_data', sa.Text),
        sa.Column('undo_data', sa.Text),
        sa.Column('undo_reason', sa.Text),
        sa.Column('undone_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Phone OTP
    op.create_table(
        'phone_otps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('verified', sa.Boolean, server_default='0'),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('attempts', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Remaining gap tables
    op.create_table(
        'response_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('intent_type', sa.String(100)),
        sa.Column('template_text', sa.Text, nullable=False),
        sa.Column('variables', sa.Text, server_default='[]'),
        sa.Column('language', sa.String(10), server_default='en'),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('version', sa.Integer, server_default='1'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'email_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('recipient', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500)),
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(50), server_default='brevo'),
        sa.Column('provider_message_id', sa.String(255)),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('error_message', sa.Text),
        sa.Column('retries', sa.Integer, server_default='0'),
        sa.Column('sent_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'rate_limit_counters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('identifier', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('count', sa.Integer, server_default='0'),
        sa.Column('window_start', sa.DateTime, nullable=False),
        sa.Column('window_end', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index(
        'ix_rlc_identifier_category_window',
        'rate_limit_counters',
        ['identifier', 'category', 'window_start'],
    )

    op.create_table(
        'feature_flags',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('flag_key', sa.String(100), nullable=False),
        sa.Column('flag_value', sa.Text, server_default='false'),
        sa.Column('description', sa.Text),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('enabled_for_tiers', sa.Text, server_default='[]'),
        sa.Column('enabled_for_roles', sa.Text, server_default='[]'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_unique_constraint('uq_feature_flags_company_key', 'feature_flags', ['company_id', 'flag_key'])

    op.create_table(
        'classification_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('interaction_id', sa.String(36)),
        sa.Column('input_text', sa.Text),
        sa.Column('classified_intent', sa.String(100)),
        sa.Column('classified_sentiment', sa.String(50)),
        sa.Column('confidence_score', sa.Numeric(5, 2)),
        sa.Column('model_name', sa.String(100)),
        sa.Column('latency_ms', sa.Integer),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'guardrails_audit_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('rule_id', sa.String(36)),
        sa.Column('rule_name', sa.String(255)),
        sa.Column('input_summary', sa.Text),
        sa.Column('output_summary', sa.Text),
        sa.Column('action_taken', sa.String(100)),
        sa.Column('severity', sa.String(20), server_default='info'),
        sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'guardrails_blocked_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('block_type', sa.String(50), nullable=False),
        sa.Column('original_response', sa.Text),
        sa.Column('block_reason', sa.Text),
        sa.Column('severity', sa.String(20), server_default='medium'),
        sa.Column('status', sa.String(50), server_default='pending_review'),
        sa.Column('auto_resolved', sa.Boolean, server_default='0'),
        sa.Column('resolved_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('resolution_notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'ai_response_feedback',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('interaction_id', sa.String(36)),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('feedback_text', sa.Text),
        sa.Column('ai_response_text', sa.Text),
        sa.Column('confidence_at_time', sa.Numeric(5, 2)),
        sa.Column('provided_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'confidence_thresholds',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('intent_type', sa.String(100), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('min_confidence', sa.Numeric(5, 2), nullable=False),
        sa.Column('max_confidence', sa.Numeric(5, 2)),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_unique_constraint('uq_conf_thresh_company_intent_action', 'confidence_thresholds', ['company_id', 'intent_type', 'action_type'])

    op.create_table(
        'human_corrections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('interaction_id', sa.String(36)),
        sa.Column('original_response', sa.Text),
        sa.Column('corrected_response', sa.Text, nullable=False),
        sa.Column('correction_reason', sa.String(255)),
        sa.Column('corrected_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('used_in_training', sa.Boolean, server_default='0'),
        sa.Column('training_run_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'approval_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('batch_status', sa.String(50), server_default='pending'),
        sa.Column('total_items', sa.Integer, server_default='0'),
        sa.Column('approved_items', sa.Integer, server_default='0'),
        sa.Column('rejected_items', sa.Integer, server_default='0'),
        sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text),
        sa.Column('status', sa.String(50), server_default='unread'),
        sa.Column('channel', sa.String(50), server_default='in_app'),
        sa.Column('action_url', sa.String(500)),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('read_at', sa.DateTime),
        sa.Column('dismissed_at', sa.DateTime),
        sa.Column('expires_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'first_victories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('milestone_type', sa.String(100), nullable=False),
        sa.Column('achieved_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('resource_id', sa.String(36)),
        sa.Column('resource_type', sa.String(50)),
        sa.Column('celebrated', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_unique_constraint('uq_first_victories_company_user_milestone', 'first_victories', ['company_id', 'user_id', 'milestone_type'])


def downgrade() -> None:
    op.drop_constraint('uq_first_victories_company_user_milestone', 'first_victories', type_='unique')
    op.drop_table('first_victories')
    op.drop_table('notifications')
    op.drop_table('approval_batches')
    op.drop_table('human_corrections')
    op.drop_constraint('uq_conf_thresh_company_intent_action', 'confidence_thresholds', type_='unique')
    op.drop_table('confidence_thresholds')
    op.drop_table('ai_response_feedback')
    op.drop_table('guardrails_blocked_queue')
    op.drop_table('guardrails_audit_log')
    op.drop_table('classification_log')
    op.drop_constraint('uq_feature_flags_company_key', 'feature_flags', type_='unique')
    op.drop_table('feature_flags')
    op.drop_table('rate_limit_counters')
    op.drop_table('email_logs')
    op.drop_table('response_templates')
    op.drop_table('phone_otps')
    op.drop_table('undo_log')
    op.drop_table('executed_actions')
    op.drop_table('auto_approve_rules')
    op.drop_table('approval_queues')
