"""006_analytics_onboarding_tables: metric_aggregates, roi_snapshots,
drift_reports, qa_scores, training_runs, onboarding_sessions,
consent_records, knowledge_documents, document_chunks, demo_sessions,
newsletter_subscribers, training_datasets, training_checkpoints,
agent_mistakes, agent_performance.

Revision ID: 006
Revises: 005
Create Date: 2026-04-02

BC-001: Every tenant table has company_id.
BC-002: Financial metrics use DECIMAL(10,2).
"""

from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Analytics tables
    op.create_table(
        'metric_aggregates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('metric_type', sa.String(100), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('value', sa.Numeric(10, 2), nullable=False),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'roi_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('tickets_ai_resolved', sa.Integer, server_default='0'),
        sa.Column('tickets_human_resolved', sa.Integer, server_default='0'),
        sa.Column('avg_ai_cost', sa.Numeric(10, 2)),
        sa.Column('avg_human_cost', sa.Numeric(10, 2)),
        sa.Column('total_savings', sa.Numeric(10, 2), server_default='0'),
        sa.Column('ai_accuracy_pct', sa.Numeric(5, 2)),
        sa.Column('snapshot_date', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'drift_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('metric_type', sa.String(100), nullable=False),
        sa.Column('baseline_value', sa.Numeric(10, 2)),
        sa.Column('current_value', sa.Numeric(10, 2)),
        sa.Column('drift_pct', sa.Numeric(5, 2)),
        sa.Column('severity', sa.String(20), server_default='low'),
        sa.Column('report_date', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'qa_scores',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('accuracy', sa.Numeric(5, 2)),
        sa.Column('tone', sa.Numeric(5, 2)),
        sa.Column('completeness', sa.Numeric(5, 2)),
        sa.Column('overall', sa.Numeric(5, 2)),
        sa.Column('scored_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'training_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('trigger', sa.String(50), nullable=False),
        sa.Column('mistake_count_at_trigger', sa.Integer, server_default='0'),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('dataset_size', sa.Integer, server_default='0'),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('metrics', sa.Text),
        sa.Column('previous_model_id', sa.String(255)),
        sa.Column('new_model_id', sa.String(255)),
        sa.Column('rolled_back', sa.Boolean, server_default='0'),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Onboarding tables
    op.create_table(
        'onboarding_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('current_step', sa.Integer, server_default='1'),
        sa.Column('completed_steps', sa.Text, server_default='[]'),
        sa.Column('status', sa.String(50), server_default='in_progress'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime),
    )

    op.create_table(
        'consent_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('consent_type', sa.String(50), nullable=False),
        sa.Column('consent_version', sa.String(20), nullable=False),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('granted', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(50)),
        sa.Column('file_size', sa.Integer),
        sa.Column('category', sa.String(100)),
        sa.Column('status', sa.String(50), server_default='processing'),
        sa.Column('chunk_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'document_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', sa.Text, nullable=True),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'demo_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('guest_email', sa.String(255)),
        sa.Column('guest_name', sa.String(255)),
        sa.Column('guest_phone', sa.String(50)),
        sa.Column('session_token', sa.String(255), nullable=False, unique=True),
        sa.Column('messages_count', sa.Integer, server_default='0'),
        sa.Column('max_messages', sa.Integer, server_default='10'),
        sa.Column('is_voice', sa.Boolean, server_default='0'),
        sa.Column('voice_payment_id', sa.String(255)),
        sa.Column('voice_call_sid', sa.String(255)),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('expires_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'newsletter_subscribers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(255)),
        sa.Column('source', sa.String(100)),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('subscribed_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('unsubscribed_at', sa.DateTime),
    )

    # Training tables
    op.create_table(
        'training_datasets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('record_count', sa.Integer, server_default='0'),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('file_path', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'training_checkpoints',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('training_run_id', sa.String(36), sa.ForeignKey('training_runs.id'), nullable=False, index=True),
        sa.Column('checkpoint_name', sa.String(255), nullable=False),
        sa.Column('model_path', sa.Text),
        sa.Column('metrics', sa.Text),
        sa.Column('epoch', sa.Integer),
        sa.Column('is_best', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'agent_mistakes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id')),
        sa.Column('mistake_type', sa.String(100), nullable=False),
        sa.Column('original_response', sa.Text),
        sa.Column('expected_response', sa.Text),
        sa.Column('correction', sa.Text),
        sa.Column('severity', sa.String(20), server_default='medium'),
        sa.Column('used_in_training', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'agent_performance',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False, index=True),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('tickets_resolved', sa.Integer, server_default='0'),
        sa.Column('avg_confidence', sa.Numeric(5, 2)),
        sa.Column('avg_resolution_time_min', sa.Numeric(10, 2)),
        sa.Column('escalation_rate', sa.Numeric(5, 2)),
        sa.Column('csat_score', sa.Numeric(5, 2)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('agent_performance')
    op.drop_table('agent_mistakes')
    op.drop_table('training_checkpoints')
    op.drop_table('training_datasets')
    op.drop_table('newsletter_subscribers')
    op.drop_table('demo_sessions')
    op.drop_table('document_chunks')
    op.drop_table('knowledge_documents')
    op.drop_table('consent_records')
    op.drop_table('onboarding_sessions')
    op.drop_table('training_runs')
    op.drop_table('qa_scores')
    op.drop_table('drift_reports')
    op.drop_table('roi_snapshots')
    op.drop_table('metric_aggregates')
