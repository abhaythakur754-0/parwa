"""
Voice Channel Models — Voice Call API

Tables:
- VoiceCall: Tracks every voice call with Twilio CallSid,
  delivery status, recording, transcript, and ticket association.
- VoiceConversation: Maps phone number pairs to conversations for
  threading (same participants = same conversation).
- VoiceChannelConfig: Per-company Twilio voice credentials and
  voice settings (recording, TTS, business hours, rate limits).

Building Codes:
- BC-001: Every table has company_id
- BC-003: Idempotent webhook processing (Twilio CallSid)
- BC-006: Rate limiting (calls/number/hour outbound)
- BC-010: TCPA compliance (opt-out for voice calls)
- BC-011: Twilio credentials encrypted at rest
- BC-012: Structured error responses
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (CHECK constraints) ────────────────

_VOICE_DIRECTIONS = "'inbound','outbound'"
_VOICE_STATUSES = (
    "'queued','ringing','in-progress','completed',"
    "'failed','busy','no-answer','canceled'"
)
_VOICE_ROLES = "'agent','bot','system','visitor'"
_VOICE_VARIANT_TIERS = "'mini_parwa','parwa','parwa_high'"


class VoiceCall(Base):
    """Voice call tracking record.

    One row per voice call (inbound or outbound) with Twilio
    CallSid correlation for status tracking and audit trail.

    BC-001: Scoped to company_id.
    BC-003: Twilio CallSid used for idempotency.
    BC-010: TCPA opt-out tracking.
    """

    __tablename__ = "voice_calls"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Conversation threading
    conversation_id = Column(
        String(36),
        ForeignKey("voice_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Ticket association
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Call identification
    twilio_call_sid = Column(
        String(64), nullable=True, unique=True, index=True,
    )
    twilio_account_sid = Column(String(64), nullable=True)

    # Call details
    direction = Column(String(10), nullable=False)
    from_number = Column(String(30), nullable=False, index=True)
    to_number = Column(String(30), nullable=False)
    status = Column(
        String(20), nullable=False, default="queued",
    )

    # Variant & AI
    variant_tier = Column(
        String(20), nullable=False, default="parwa",
    )
    intent_detected = Column(String(100), nullable=True)
    resolution = Column(String(50), nullable=True)

    # Timing
    duration_seconds = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    # Recording
    recording_url = Column(String(500), nullable=True)
    recording_sid = Column(String(64), nullable=True)
    recording_enabled = Column(Boolean, nullable=False, default=False)

    # Transcript
    transcript_json = Column(Text, nullable=True)
    transcript_summary = Column(Text, nullable=True)

    # Post-call analytics
    topics_discussed = Column(Text, nullable=True)  # JSON array
    key_moments_json = Column(Text, nullable=True)  # JSON array
    satisfaction_score = Column(Float, nullable=True)

    # Sender info
    sender_id = Column(String(36), nullable=True)
    sender_role = Column(String(10), nullable=False, default="agent")

    # Metadata
    metadata_json = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    conversation = relationship(
        "VoiceConversation", back_populates="calls",
    )
    ticket = relationship("Ticket", foreign_keys=[ticket_id])

    __table_args__ = (
        CheckConstraint(
            f"direction IN ({_VOICE_DIRECTIONS})",
            name="ck_voice_call_direction",
        ),
        CheckConstraint(
            f"status IN ({_VOICE_STATUSES})",
            name="ck_voice_call_status",
        ),
        CheckConstraint(
            f"sender_role IN ({_VOICE_ROLES})",
            name="ck_voice_call_role",
        ),
        CheckConstraint(
            f"variant_tier IN ({_VOICE_VARIANT_TIERS})",
            name="ck_voice_call_variant_tier",
        ),
        CheckConstraint(
            "duration_seconds >= 0",
            name="ck_voice_call_duration",
        ),
        CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 0 AND satisfaction_score <= 10)",
            name="ck_voice_call_satisfaction_range",
        ),
        Index(
            "ix_voice_company_from_to",
            "company_id", "from_number", "to_number",
        ),
        Index(
            "ix_voice_company_status",
            "company_id", "status",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize voice call for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "conversation_id": self.conversation_id,
            "ticket_id": self.ticket_id,
            "twilio_call_sid": self.twilio_call_sid,
            "twilio_account_sid": self.twilio_account_sid,
            "direction": self.direction,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "status": self.status,
            "variant_tier": self.variant_tier,
            "intent_detected": self.intent_detected,
            "resolution": self.resolution,
            "duration_seconds": self.duration_seconds,
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "ended_at": (
                self.ended_at.isoformat() if self.ended_at else None
            ),
            "recording_url": self.recording_url,
            "recording_sid": self.recording_sid,
            "recording_enabled": self.recording_enabled,
            "transcript_json": self.transcript_json,
            "transcript_summary": self.transcript_summary,
            "topics_discussed": self.topics_discussed,
            "key_moments_json": self.key_moments_json,
            "satisfaction_score": self.satisfaction_score,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


class VoiceConversation(Base):
    """Voice conversation thread mapping.

    Maps a unique phone number pair (customer <-> Twilio number)
    to a conversation for threading. Multiple voice calls between
    the same numbers are grouped into one conversation.

    BC-001: Scoped to company_id.
    BC-010: TCPA opt-out tracking for voice.
    """

    __tablename__ = "voice_conversations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Phone number pair (normalized E.164)
    customer_number = Column(String(30), nullable=False, index=True)
    twilio_number = Column(String(30), nullable=False)

    # Conversation metrics
    call_count = Column(Integer, nullable=False, default=0)
    total_duration_seconds = Column(Integer, nullable=False, default=0)
    last_call_at = Column(DateTime, nullable=True)

    # TCPA opt-out tracking for voice (BC-010)
    is_opted_out = Column(Boolean, nullable=False, default=False)
    opt_out_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    calls = relationship(
        "VoiceCall", back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="VoiceCall.created_at",
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "customer_number", "twilio_number",
            name="uq_voice_conversation_numbers",
        ),
        CheckConstraint("call_count >= 0", name="ck_voice_conv_call_count"),
        CheckConstraint(
            "total_duration_seconds >= 0",
            name="ck_voice_conv_total_duration",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize voice conversation for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "customer_number": self.customer_number,
            "twilio_number": self.twilio_number,
            "call_count": self.call_count,
            "total_duration_seconds": self.total_duration_seconds,
            "last_call_at": (
                self.last_call_at.isoformat()
                if self.last_call_at else None
            ),
            "is_opted_out": self.is_opted_out,
            "opt_out_at": (
                self.opt_out_at.isoformat() if self.opt_out_at else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


class VoiceChannelConfig(Base):
    """Per-company Twilio voice configuration.

    Stores encrypted Twilio credentials and voice channel settings
    including recording, TTS, rate limits, and business hours.

    BC-001: One config per company.
    BC-011: Credentials encrypted at rest.
    """

    __tablename__ = "voice_channel_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Twilio credentials (encrypted in production via BC-011)
    twilio_account_sid = Column(String(64), nullable=False)
    twilio_auth_token_encrypted = Column(Text, nullable=False)
    twilio_phone_number = Column(String(30), nullable=False)

    # Channel settings
    is_enabled = Column(Boolean, nullable=False, default=True)
    default_variant = Column(
        String(20), nullable=False, default="parwa",
    )
    max_call_duration_minutes = Column(
        Integer, nullable=False, default=30,
    )
    enable_recording = Column(Boolean, nullable=False, default=False)

    # Speech settings
    speech_language = Column(String(10), nullable=False, default="en-IN")
    tts_voice = Column(String(50), nullable=False, default="Polly.Aditi")

    # Transfer
    transfer_number = Column(String(30), nullable=True)

    # Rate limiting (BC-006)
    max_calls_per_hour = Column(Integer, nullable=False, default=10)
    max_calls_per_day = Column(Integer, nullable=False, default=100)

    # Greeting & messages
    greeting_message = Column(Text, nullable=True)
    after_hours_message = Column(Text, nullable=True)
    business_hours_json = Column(Text, default="{}")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            f"default_variant IN ({_VOICE_VARIANT_TIERS})",
            name="ck_voice_cfg_variant",
        ),
        CheckConstraint(
            "max_call_duration_minutes > 0",
            name="ck_voice_cfg_max_duration",
        ),
        CheckConstraint(
            "max_calls_per_hour > 0",
            name="ck_voice_cfg_hourly_limit",
        ),
        CheckConstraint(
            "max_calls_per_day > 0",
            name="ck_voice_cfg_daily_limit",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize voice config for API responses (no secrets).

        H-17 FIX: twilio_account_sid is masked to prevent credential leakage.
        """
        def _mask_sid(sid: str) -> str:
            """Mask a Twilio SID, showing only last 4 chars."""
            if not sid or len(sid) < 8:
                return "********"
            return f"****{sid[-4:]}"

        return {
            "id": self.id,
            "company_id": self.company_id,
            "twilio_account_sid": _mask_sid(self.twilio_account_sid),
            "twilio_phone_number": self.twilio_phone_number,
            "is_enabled": self.is_enabled,
            "default_variant": self.default_variant,
            "max_call_duration_minutes": self.max_call_duration_minutes,
            "enable_recording": self.enable_recording,
            "speech_language": self.speech_language,
            "tts_voice": self.tts_voice,
            "transfer_number": self.transfer_number,
            "max_calls_per_hour": self.max_calls_per_hour,
            "max_calls_per_day": self.max_calls_per_day,
            "greeting_message": self.greeting_message,
            "after_hours_message": self.after_hours_message,
            "business_hours": self.business_hours_json,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }
