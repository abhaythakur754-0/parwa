"""Voice channel tables.

Creates:
  - voice_calls: Voice call tracking with Twilio CallSid
  - voice_conversations: Phone number pair threading
  - voice_channel_configs: Per-company Twilio voice config

BC-001: Every table has company_id.
BC-003: Idempotent webhook processing via unique twilio_call_sid.
BC-006: Rate limiting config (max_calls_per_hour/day).
BC-010: TCPA compliance (is_opted_out on conversations).
BC-011: Credentials encrypted at rest.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "026_voice_channel_tables"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── voice_conversations ────────────────────────────────────
    # Must be created first since voice_calls references it
    op.create_table(
        "voice_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("customer_number", sa.String(30), nullable=False, index=True),
        sa.Column("twilio_number", sa.String(30), nullable=False),
        sa.Column("call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_duration_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_call_at", sa.DateTime(), nullable=True),
        sa.Column("is_opted_out", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("opt_out_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "company_id", "customer_number", "twilio_number",
            name="uq_voice_conversation_numbers",
        ),
        sa.CheckConstraint("call_count >= 0", name="ck_voice_conv_call_count"),
        sa.CheckConstraint(
            "total_duration_seconds >= 0",
            name="ck_voice_conv_total_duration",
        ),
    )

    # ── voice_calls ───────────────────────────────────────────
    op.create_table(
        "voice_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("voice_conversations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey("tickets.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Call identification
        sa.Column("twilio_call_sid", sa.String(64), unique=True, index=True, nullable=True),
        sa.Column("twilio_account_sid", sa.String(64), nullable=True),
        # Call details
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("from_number", sa.String(30), nullable=False, index=True),
        sa.Column("to_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        # Variant & AI
        sa.Column("variant_tier", sa.String(20), server_default="parwa", nullable=False),
        sa.Column("intent_detected", sa.String(100), nullable=True),
        sa.Column("resolution", sa.String(50), nullable=True),
        # Timing
        sa.Column("duration_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        # Recording
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column("recording_sid", sa.String(64), nullable=True),
        sa.Column("recording_enabled", sa.Boolean(), server_default="false", nullable=False),
        # Transcript
        sa.Column("transcript_json", sa.Text(), nullable=True),
        sa.Column("transcript_summary", sa.Text(), nullable=True),
        # Post-call analytics
        sa.Column("topics_discussed", sa.Text(), nullable=True),
        sa.Column("key_moments_json", sa.Text(), nullable=True),
        sa.Column("satisfaction_score", sa.Float(), nullable=True),
        # Sender info
        sa.Column("sender_id", sa.String(36), nullable=True),
        sa.Column("sender_role", sa.String(10), server_default="agent", nullable=False),
        # Metadata
        sa.Column("metadata_json", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Check constraints
        sa.CheckConstraint(
            "direction IN ('inbound','outbound')",
            name="ck_voice_call_direction",
        ),
        sa.CheckConstraint(
            "status IN ('queued','ringing','in-progress','completed',"
            "'failed','busy','no-answer','canceled')",
            name="ck_voice_call_status",
        ),
        sa.CheckConstraint(
            "sender_role IN ('agent','bot','system','visitor')",
            name="ck_voice_call_role",
        ),
        sa.CheckConstraint(
            "variant_tier IN ('mini_parwa','parwa','parwa_high')",
            name="ck_voice_call_variant_tier",
        ),
        sa.CheckConstraint(
            "duration_seconds >= 0",
            name="ck_voice_call_duration",
        ),
        sa.CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 0 AND satisfaction_score <= 10)",
            name="ck_voice_call_satisfaction_range",
        ),
    )

    # Composite indexes
    op.create_index(
        "ix_voice_company_from_to",
        "voice_calls",
        ["company_id", "from_number", "to_number"],
    )
    op.create_index(
        "ix_voice_company_status",
        "voice_calls",
        ["company_id", "status"],
    )

    # ── voice_channel_configs ──────────────────────────────────
    op.create_table(
        "voice_channel_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        # Twilio credentials
        sa.Column("twilio_account_sid", sa.String(64), nullable=False),
        sa.Column("twilio_auth_token_encrypted", sa.Text(), nullable=False),
        sa.Column("twilio_phone_number", sa.String(30), nullable=False),
        # Channel settings
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("default_variant", sa.String(20), server_default="parwa", nullable=False),
        sa.Column("max_call_duration_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("enable_recording", sa.Boolean(), server_default="false", nullable=False),
        # Speech settings
        sa.Column("speech_language", sa.String(10), server_default="en-IN", nullable=False),
        sa.Column("tts_voice", sa.String(50), server_default="Polly.Aditi", nullable=False),
        # Transfer
        sa.Column("transfer_number", sa.String(30), nullable=True),
        # Rate limiting
        sa.Column("max_calls_per_hour", sa.Integer(), server_default="10", nullable=False),
        sa.Column("max_calls_per_day", sa.Integer(), server_default="100", nullable=False),
        # Greeting & messages
        sa.Column("greeting_message", sa.Text(), nullable=True),
        sa.Column("after_hours_message", sa.Text(), nullable=True),
        sa.Column("business_hours_json", sa.Text(), server_default="{}"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Check constraints
        sa.CheckConstraint(
            "default_variant IN ('mini_parwa','parwa','parwa_high')",
            name="ck_voice_cfg_variant",
        ),
        sa.CheckConstraint(
            "max_call_duration_minutes > 0",
            name="ck_voice_cfg_max_duration",
        ),
        sa.CheckConstraint(
            "max_calls_per_hour > 0",
            name="ck_voice_cfg_hourly_limit",
        ),
        sa.CheckConstraint(
            "max_calls_per_day > 0",
            name="ck_voice_cfg_daily_limit",
        ),
    )


def downgrade() -> None:
    op.drop_table("voice_channel_configs")
    op.drop_index("ix_voice_company_status", table_name="voice_calls")
    op.drop_index("ix_voice_company_from_to", table_name="voice_calls")
    op.drop_table("voice_calls")
    op.drop_table("voice_conversations")
