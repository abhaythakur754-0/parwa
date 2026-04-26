"""Jarvis Production System Tables

Revision ID: jarvis_production
Revises: jarvis_system
Create Date: 2025-04-26

Creates tables for Production Jarvis:
- jarvis_production_sessions
- jarvis_activity_events
- jarvis_memories
- jarvis_drafts
- jarvis_alerts
- jarvis_action_logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = 'jarvis_production'
down_revision = 'jarvis_system'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create jarvis_production_sessions table
    op.create_table(
        'jarvis_production_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('context_json', sa.Text(), default='{}'),
        sa.Column('today_tasks_json', sa.Text(), default='[]'),
        sa.Column('last_interaction_at', sa.DateTime(), nullable=True),
        sa.Column('variant_tier', sa.String(20), nullable=False, default='starter'),
        sa.Column('features_enabled_json', sa.Text(), default='{}'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.CheckConstraint("variant_tier IN ('starter', 'growth', 'high')", name='ck_jarvis_prod_tier'),
    )
    op.create_index('ix_jarvis_prod_session_user_company', 'jarvis_production_sessions', ['user_id', 'company_id'])
    
    # Create jarvis_activity_events table
    op.create_table(
        'jarvis_activity_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('jarvis_production_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_category', sa.String(30), nullable=False),
        sa.Column('event_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), default='{}'),
        sa.Column('page_url', sa.String(500), nullable=True),
        sa.Column('page_name', sa.String(100), nullable=True),
        sa.Column('related_ticket_id', sa.String(36), nullable=True),
        sa.Column('related_user_id', sa.String(36), nullable=True),
        sa.Column('related_integration', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now(), index=True),
    )
    op.create_index('ix_jarvis_activity_company_time', 'jarvis_activity_events', ['company_id', 'created_at'])
    op.create_index('ix_jarvis_activity_user_time', 'jarvis_activity_events', ['user_id', 'created_at'])
    op.create_index('ix_jarvis_activity_type_time', 'jarvis_activity_events', ['event_type', 'created_at'])
    
    # Create jarvis_memories table
    op.create_table(
        'jarvis_memories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('jarvis_production_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('memory_key', sa.String(100), nullable=False),
        sa.Column('memory_value', sa.Text(), nullable=False),
        sa.Column('importance', sa.Integer(), default=5),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.CheckConstraint('importance >= 1 AND importance <= 10', name='ck_jarvis_memory_importance'),
    )
    op.create_index('ix_jarvis_memory_lookup', 'jarvis_memories', ['company_id', 'user_id', 'category', 'memory_key'])
    
    # Create jarvis_drafts table
    op.create_table(
        'jarvis_drafts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('jarvis_production_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('draft_type', sa.String(50), nullable=False),
        sa.Column('subject', sa.String(255), nullable=True),
        sa.Column('content_json', sa.Text(), nullable=False),
        sa.Column('recipient_count', sa.Integer(), default=0),
        sa.Column('recipients_json', sa.Text(), default='[]'),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('approved_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_result_json', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'cancelled', 'expired', 'executing', 'completed', 'failed')",
            name='ck_jarvis_draft_status'
        ),
    )
    op.create_index('ix_jarvis_draft_pending', 'jarvis_drafts', ['company_id', 'status'])
    
    # Create jarvis_alerts table
    op.create_table(
        'jarvis_alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('jarvis_production_sessions.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('suggested_action_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('delivered_via', sa.String(50), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name='ck_jarvis_alert_severity'),
        sa.CheckConstraint("status IN ('active', 'acknowledged', 'dismissed', 'resolved')", name='ck_jarvis_alert_status'),
    )
    op.create_index('ix_jarvis_alert_active', 'jarvis_alerts', ['company_id', 'status', 'severity'])
    
    # Create jarvis_action_logs table
    op.create_table(
        'jarvis_action_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('jarvis_production_sessions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=False, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('action_category', sa.String(30), nullable=False),
        sa.Column('execution_mode', sa.String(20), nullable=False),
        sa.Column('input_json', sa.Text(), nullable=True),
        sa.Column('output_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('can_undo', sa.Boolean(), default=False),
        sa.Column('undone_at', sa.DateTime(), nullable=True),
        sa.Column('undone_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('draft_id', sa.String(36), sa.ForeignKey('jarvis_drafts.id'), nullable=True),
        sa.Column('related_ticket_id', sa.String(36), nullable=True),
        sa.Column('related_integration', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now(), index=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'success', 'failed', 'undone')", name='ck_jarvis_action_status'),
        sa.CheckConstraint("execution_mode IN ('direct', 'draft_approved', 'auto')", name='ck_jarvis_action_mode'),
    )
    op.create_index('ix_jarvis_action_company_time', 'jarvis_action_logs', ['company_id', 'created_at'])
    op.create_index('ix_jarvis_action_user_time', 'jarvis_action_logs', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('jarvis_action_logs')
    op.drop_table('jarvis_alerts')
    op.drop_table('jarvis_drafts')
    op.drop_table('jarvis_memories')
    op.drop_table('jarvis_activity_events')
    op.drop_table('jarvis_production_sessions')
