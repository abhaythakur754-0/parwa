"""
Shadow Mode Models: Tables for the SHADOW→SUPERVISED→GRADUATED pipeline.

Tables:
  - shadow_mode_configs: Per-company shadow mode settings
  - shadow_mode_results: Comparison results between shadow and live responses

Shadow Mode is a safe deployment strategy:
  1. SHADOW: Both live and new variant process messages. Only live response
     is delivered to customer. Shadow response is logged for comparison.
  2. SUPERVISED: Shadow variant handles messages, but human reviews before
     delivery. If reviewer is slow, live variant auto-responds.
  3. GRADUATED: Shadow variant is now the live variant. Transition complete.

BC-001: Every tenant-scoped table has company_id with index.
BC-002: Money fields use Numeric(10,4). No Float for money.
BC-012: created_at/updated_at on all tables.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric,
    String, Text, ForeignKey, Index,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Shadow Mode Config ──────────────────────────────────────────────

class ShadowModeConfig(Base):
    """
    Per-company shadow mode configuration.

    Controls which variant is being "shadow tested" against
    the current live variant. The progression is:
      SHADOW → SUPERVISED → GRADUATED

    When status is 'shadow':
      - Incoming messages are processed by BOTH live and shadow variants
      - Only live variant response is sent to customer
      - Shadow variant response is logged for offline comparison

    When status is 'supervised':
      - Shadow variant generates the response
      - Human reviewer must approve before delivery
      - Auto-fallback to live variant if review times out

    When status is 'graduated':
      - Shadow variant IS the new live variant
      - No more comparison logging needed
      - Config can be archived
    """

    __tablename__ = "shadow_mode_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # The variant currently handling live traffic
    live_variant = Column(String(50), nullable=False)
    # e.g., "mini_parwa" or "parwa"

    # The variant being tested in shadow
    shadow_variant = Column(String(50), nullable=False)
    # e.g., "parwa" or "parwa_high"

    # Current shadow mode status
    status = Column(String(20), nullable=False, default="shadow")
    # shadow, supervised, graduated, disabled

    # Instance IDs for fine-grained routing
    live_instance_id = Column(String(36), nullable=True)
    shadow_instance_id = Column(String(36), nullable=True)

    # Sampling configuration
    sample_rate = Column(Numeric(5, 4), default=1.0)
    # 1.0 = 100% of messages go through shadow, 0.1 = 10% sample

    # Quality threshold for auto-graduation
    auto_graduation_threshold = Column(Numeric(5, 4), default=0.95)
    # If shadow quality >= threshold for N consecutive comparisons,
    # auto-graduate to next phase

    # Number of consecutive quality passes required for auto-graduation
    auto_graduation_window = Column(Integer, default=100)

    # Supervised mode timeout (seconds) before auto-fallback to live
    supervised_timeout_seconds = Column(Integer, default=300)

    # Whether to auto-graduate from shadow→supervised after threshold met
    auto_promote_to_supervised = Column(Boolean, default=True)

    # Whether to auto-graduate from supervised→graduated after threshold met
    auto_promote_to_graduated = Column(Boolean, default=False)

    # Current streak of quality passes (for auto-graduation)
    current_quality_streak = Column(Integer, default=0)

    # Total comparisons made
    total_comparisons = Column(Integer, default=0)

    # Comparisons where shadow matched or exceeded live quality
    shadow_wins = Column(Integer, default=0)

    # Whether this config is currently active
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    enabled_by_user_id = Column(String(36), nullable=True)
    enabled_at = Column(DateTime, nullable=True)
    supervised_at = Column(DateTime, nullable=True)
    graduated_at = Column(DateTime, nullable=True)
    disabled_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_shadow_config_comp_active",
            "company_id", "is_active",
        ),
        Index(
            "ix_shadow_config_comp_status",
            "company_id", "status",
        ),
        CheckConstraint(
            "status IN ('shadow', 'supervised', 'graduated', 'disabled')",
            name="ck_shadow_config_valid_status",
        ),
        CheckConstraint(
            "sample_rate >= 0 AND sample_rate <= 1",
            name="ck_shadow_config_sample_rate_range",
        ),
        CheckConstraint(
            "auto_graduation_threshold >= 0 AND auto_graduation_threshold <= 1",
            name="ck_shadow_config_grad_threshold_range",
        ),
    )


# ── Shadow Mode Result ──────────────────────────────────────────────

class ShadowModeResult(Base):
    """
    Comparison result between live and shadow variant responses.

    Each row represents one message that was processed by both
    the live and shadow variants during shadow mode testing.
    Contains quality scores, latency, and human review decisions.
    """

    __tablename__ = "shadow_mode_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    config_id = Column(
        String(36),
        ForeignKey("shadow_mode_configs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Ticket / conversation context
    ticket_id = Column(String(36), nullable=True, index=True)
    conversation_id = Column(String(36), nullable=True)
    message_hash = Column(String(64), nullable=True)
    # SHA-256 of the incoming message for dedup

    # Live variant results
    live_variant = Column(String(50), nullable=False)
    live_response = Column(Text, nullable=True)
    live_quality_score = Column(Numeric(5, 4), nullable=True)
    live_latency_ms = Column(Integer, nullable=True)
    live_tokens_used = Column(Integer, nullable=True)

    # Shadow variant results
    shadow_variant = Column(String(50), nullable=False)
    shadow_response = Column(Text, nullable=True)
    shadow_quality_score = Column(Numeric(5, 4), nullable=True)
    shadow_latency_ms = Column(Integer, nullable=True)
    shadow_tokens_used = Column(Integer, nullable=True)

    # Comparison metrics
    quality_delta = Column(Numeric(7, 4), nullable=True)
    # shadow_quality - live_quality (positive = shadow better)
    latency_delta_ms = Column(Integer, nullable=True)
    # shadow_latency - live_latency (negative = shadow faster)
    token_delta = Column(Integer, nullable=True)
    # shadow_tokens - live_tokens

    # Verdict
    shadow_winner = Column(Boolean, nullable=True)
    # True if shadow_quality >= live_quality

    # Human review (supervised mode)
    human_reviewed = Column(Boolean, default=False)
    human_verdict = Column(String(20), nullable=True)
    # "shadow_better", "live_better", "equal", "skip"
    reviewer_id = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Mode at time of comparison
    mode_at_comparison = Column(String(20), nullable=False, default="shadow")
    # shadow, supervised

    # Auto-fallback flag (supervised mode timed out)
    auto_fallback_used = Column(Boolean, default=False)

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_shadow_result_comp_config",
            "company_id", "config_id", "created_at",
        ),
        Index(
            "ix_shadow_result_comp_winner",
            "company_id", "shadow_winner",
        ),
        Index(
            "ix_shadow_result_comp_review",
            "company_id", "human_reviewed",
        ),
        CheckConstraint(
            "mode_at_comparison IN ('shadow', 'supervised')",
            name="ck_shadow_result_valid_mode",
        ),
        CheckConstraint(
            "human_verdict IN ('shadow_better', 'live_better', 'equal', 'skip') OR human_verdict IS NULL",
            name="ck_shadow_result_valid_verdict",
        ),
    )
