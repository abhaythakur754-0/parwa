"""002_ticketing_tables: Tickets, TicketMessages, Customers, Channels + Week 4 tables

REWRITTEN for Day 25:
- Renamed sessions → tickets
- Renamed interactions → ticket_messages
- Added all Day 24 columns
- Created all Week 4 support tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-02
Updated: 2026-04-03 (Day 25)

"""

from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════
    # CUSTOMERS
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    # CHANNELS (global lookup - no company_id)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'channels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('channel_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('is_active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKETS (renamed from sessions)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'tickets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='SET NULL')),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), server_default='open', nullable=False),
        sa.Column('subject', sa.String(255)),
        # MF01: Priority system
        sa.Column('priority', sa.String(20), server_default='medium', nullable=False),
        # MF02: Category
        sa.Column('category', sa.String(50), nullable=True),
        # MF03: Tags
        sa.Column('tags', sa.Text, server_default='[]'),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id')),
        sa.Column('assigned_to', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('classification_intent', sa.String(100)),
        sa.Column('classification_type', sa.String(50)),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        # PS04: reopen tracking
        sa.Column('reopen_count', sa.Integer, server_default='0', nullable=False),
        # PS07: frozen when account suspended
        sa.Column('frozen', sa.Boolean, server_default='0', nullable=False),
        # PS19: cross-variant parent tickets
        sa.Column('parent_ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='SET NULL'), nullable=True),
        # PS05: duplicate linking
        sa.Column('duplicate_of_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='SET NULL'), nullable=True),
        # MF21: spam flag
        sa.Column('is_spam', sa.Boolean, server_default='0', nullable=False),
        # PS02: AI can't solve
        sa.Column('awaiting_human', sa.Boolean, server_default='0', nullable=False),
        # PS08: awaiting client action
        sa.Column('awaiting_client', sa.Boolean, server_default='0', nullable=False),
        # PS27: escalation level
        sa.Column('escalation_level', sa.Integer, server_default='1', nullable=False),
        # PS11: SLA breach tracking
        sa.Column('sla_breached', sa.Boolean, server_default='0', nullable=False),
        # PS14: plan snapshot for grandfathering
        sa.Column('plan_snapshot', sa.Text, server_default='{}'),
        # PS25: variant version
        sa.Column('variant_version', sa.String(100)),
        # PS17: SLA first response tracking
        sa.Column('first_response_at', sa.DateTime),
        # SLA resolution target
        sa.Column('resolution_target_at', sa.DateTime),
        # PS23: client timezone
        sa.Column('client_timezone', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime),
    )

    op.create_index('ix_tickets_customer_id', 'tickets', ['customer_id'])
    op.create_index('ix_tickets_status', 'tickets', ['status'])
    op.create_index('ix_tickets_priority', 'tickets', ['priority'])
    op.create_index('ix_tickets_category', 'tickets', ['category'])
    op.create_index('ix_tickets_assigned_to', 'tickets', ['assigned_to'])

    # ═══════════════════════════════════════════════════════════════
    # TICKET_MESSAGES (renamed from interactions)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        # Internal notes distinction
        sa.Column('is_internal', sa.Boolean, server_default='0', nullable=False),
        # BL07/PS29: PII redacted
        sa.Column('is_redacted', sa.Boolean, server_default='0', nullable=False),
        # F-049: AI confidence
        sa.Column('ai_confidence', sa.Numeric(5, 2), nullable=True),
        # PS25: variant version
        sa.Column('variant_version', sa.String(100)),
        # F-049: classification
        sa.Column('classification', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_ATTACHMENTS
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_attachments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_url', sa.Text, nullable=False),
        sa.Column('file_size', sa.Integer),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('uploaded_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_INTERNAL_NOTES
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_internal_notes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_pinned', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_STATUS_CHANGES (MF04: Activity log)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_status_changes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('from_status', sa.String(50)),
        sa.Column('to_status', sa.String(50), nullable=False),
        sa.Column('changed_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # SLA_POLICIES (MF06)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'sla_policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('plan_tier', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(20), nullable=False),
        sa.Column('first_response_minutes', sa.Integer, nullable=False),
        sa.Column('resolution_minutes', sa.Integer, nullable=False),
        sa.Column('update_frequency_minutes', sa.Integer, nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # SLA_TIMERS
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'sla_timers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('policy_id', sa.String(36), sa.ForeignKey('sla_policies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('first_response_at', sa.DateTime),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('breached_at', sa.DateTime),
        sa.Column('is_breached', sa.Boolean, server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_ASSIGNMENTS (F-050)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('assignee_type', sa.String(50), nullable=False),
        sa.Column('assignee_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('score', sa.Numeric(5, 2), nullable=True),
        sa.Column('reason', sa.Text),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # ASSIGNMENT_RULES (F-050)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'assignment_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('conditions', sa.Text, server_default='{}', nullable=False),
        sa.Column('action', sa.Text, server_default='{}', nullable=False),
        sa.Column('priority_order', sa.Integer, server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # BULK_ACTION_LOGS (F-051)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'bulk_action_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('ticket_ids', sa.Text, nullable=False),
        sa.Column('performed_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('result_summary', sa.Text),
        sa.Column('undo_token', sa.String(255), unique=True, nullable=True),
        sa.Column('undone', sa.Boolean, server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # BULK_ACTION_FAILURES (F-051)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'bulk_action_failures',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('bulk_action_id', sa.String(36), sa.ForeignKey('bulk_action_logs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ticket_id', sa.String(36), nullable=False),
        sa.Column('error_message', sa.Text, nullable=False),
        sa.Column('failure_reason', sa.String(100)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_MERGES (F-051)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_merges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('primary_ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('merged_ticket_ids', sa.Text, nullable=False),
        sa.Column('merged_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('reason', sa.Text),
        sa.Column('undo_token', sa.String(255), unique=True, nullable=True),
        sa.Column('undone', sa.Boolean, server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # NOTIFICATION_TEMPLATES (MF05)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'notification_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('subject_template', sa.Text),
        sa.Column('body_template', sa.Text, nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_FEEDBACKS (MF13: CSAT)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_feedbacks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('rating', sa.Integer, nullable=False),
        sa.Column('comment', sa.Text),
        sa.Column('feedback_source', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # CUSTOMER_CHANNELS (F-052, F-070)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'customer_channels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('channel_type', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(255)),
        sa.Column('is_verified', sa.Boolean, server_default='0', nullable=False),
        sa.Column('metadata_json', sa.Text, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # IDENTITY_MATCH_LOGS (F-070)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'identity_match_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('input_email', sa.String(255)),
        sa.Column('input_phone', sa.String(50)),
        sa.Column('matched_customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('match_method', sa.String(50)),
        sa.Column('confidence_score', sa.Numeric(5, 2)),
        sa.Column('action_taken', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # TICKET_INTENTS (F-049)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'ticket_intents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('intent', sa.String(50), nullable=False),
        sa.Column('urgency', sa.String(50)),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=False),
        sa.Column('variant_version', sa.String(100)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # CLASSIFICATION_CORRECTIONS (F-049 feedback loop)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'classification_corrections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('original_intent', sa.String(50), nullable=False),
        sa.Column('corrected_intent', sa.String(50), nullable=False),
        sa.Column('original_urgency', sa.String(50)),
        sa.Column('corrected_urgency', sa.String(50)),
        sa.Column('corrected_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # CHANNEL_CONFIGS (F-052)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'channel_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('channel_type', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean, server_default='1', nullable=False),
        sa.Column('config_json', sa.Text, server_default='{}'),
        sa.Column('auto_create_ticket', sa.Boolean, server_default='1', nullable=False),
        sa.Column('char_limit', sa.Integer, nullable=True),
        sa.Column('allowed_file_types', sa.Text, server_default='[]'),
        sa.Column('max_file_size', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════
    # CUSTOMER_MERGE_AUDITS (F-070)
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'customer_merge_audits',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('primary_customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('merged_customer_ids', sa.Text, nullable=False),
        sa.Column('merged_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('reason', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('customer_merge_audits')
    op.drop_table('channel_configs')
    op.drop_table('classification_corrections')
    op.drop_table('ticket_intents')
    op.drop_table('identity_match_logs')
    op.drop_table('customer_channels')
    op.drop_table('ticket_feedbacks')
    op.drop_table('notification_templates')
    op.drop_table('ticket_merges')
    op.drop_table('bulk_action_failures')
    op.drop_table('bulk_action_logs')
    op.drop_table('assignment_rules')
    op.drop_table('ticket_assignments')
    op.drop_table('sla_timers')
    op.drop_table('sla_policies')
    op.drop_table('ticket_status_changes')
    op.drop_table('ticket_internal_notes')
    op.drop_table('ticket_attachments')
    op.drop_table('ticket_messages')
    op.drop_table('tickets')
    op.drop_table('channels')
    op.drop_table('customers')
