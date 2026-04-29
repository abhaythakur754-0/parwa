"""
Technique Models: technique_configurations, technique_executions, technique_versions.

AI Technique Framework (TRIVYA v1.0) — BC-013, F-140 to F-148.

BC-001: Every table has company_id.
BC-002: Money fields use DECIMAL(10,2).

Tables:
  - technique_configurations: Per-tenant technique enable/disable settings.
  - technique_executions: Technique activation logs, token usage, latency, fallback.
  - technique_versions: Versioned technique implementations with A/B test metadata.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Technique Configurations (per-tenant settings) ──────────────────


class TechniqueConfiguration(Base):
    """
    Per-tenant technique enable/disable settings.
    Tier 1 techniques (CLARA, CRP, GSD) are always active and
    cannot be disabled — this table controls Tier 2 and Tier 3.

    Plan defaults:
      Free      = Tier 1 only
      Pro       = Tier 1 + Tier 2
      Enterprise = Tier 1 + Tier 2 + Tier 3 (full)
    """

    __tablename__ = "technique_configurations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    technique_id = Column(String(50), nullable=False)
    # e.g. "reverse_thinking", "step_back", "cot", "react", "thot",
    #       "gst", "uot", "tot", "self_consistency", "reflexion",
    #       "least_to_most"

    tier = Column(String(10), nullable=False)
    # "tier_2" or "tier_3"

    is_enabled = Column(Boolean, default=True, nullable=False)

    # Per-tenant overrides
    custom_token_budget = Column(Integer, nullable=True)
    # NULL = use system default; non-null = override per technique

    custom_trigger_threshold = Column(Float, nullable=True)
    # NULL = use system default; e.g. complexity > 0.4 → can override to 0.3

    custom_timeout_ms = Column(Integer, nullable=True)
    # Max execution time in ms; NULL = use system default

    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "technique_id",
            name="uq_technique_config_company",
        ),
        Index(
            "ix_tech_config_company_tier",
            "company_id",
            "tier",
        ),
    )


# ── Technique Executions (activation logs) ──────────────────────────


class TechniqueExecution(Base):
    """
    Logs every technique activation with token usage, latency,
    and fallback tracking. Feeds into Agent Performance Analytics (F-098).
    """

    __tablename__ = "technique_executions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ticket_id = Column(String(36), nullable=True, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)

    technique_id = Column(String(50), nullable=False, index=True)
    tier = Column(String(10), nullable=False)

    # Input signals at time of activation
    query_complexity = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    customer_tier = Column(String(20), nullable=True)
    monetary_value = Column(Numeric(10, 2), nullable=True)
    turn_count = Column(Integer, nullable=True)
    intent_type = Column(String(50), nullable=True)

    # Trigger rule(s) that activated this technique
    trigger_rules = Column(Text, default="[]")
    # JSON list of rule numbers, e.g. ["2", "4"]

    # Execution metrics
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    tokens_overhead = Column(Integer, default=0)
    # Overhead = extra tokens consumed by the technique itself

    latency_ms = Column(Integer, default=0)
    # Total execution time in milliseconds

    # Result
    result_status = Column(String(20), nullable=False, default="success")
    # "success", "fallback", "timeout", "error", "skipped_budget"

    fallback_technique = Column(String(50), nullable=True)
    # If result_status = "fallback", which T2 technique was used instead

    fallback_reason = Column(String(255), nullable=True)
    # Human-readable reason, e.g. "token budget exceeded"

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.utcnow(), index=True)

    __table_args__ = (
        Index(
            "ix_tech_exec_company_date",
            "company_id",
            "created_at",
        ),
        Index(
            "ix_tech_exec_technique_date",
            "technique_id",
            "created_at",
        ),
    )


# ── Technique Versions (A/B testing) ────────────────────────────────


class TechniqueVersion(Base):
    """
    Versioned technique implementations with A/B test metadata.
    Managed via DSPy (F-061) optimization framework.

    Versioning pattern: {technique_id}-v{N}, e.g. "cot-v1", "cot-v2"
    """

    __tablename__ = "technique_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    technique_id = Column(String(50), nullable=False)
    version = Column(String(10), nullable=False)
    # e.g. "v1", "v2"

    label = Column(String(100), nullable=False)
    # Human-readable label, e.g. "Chain of Thought v2 (compressed prompts)"

    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    # Only one version per (company_id, technique_id) can be is_default=True

    # A/B testing metadata
    ab_test_enabled = Column(Boolean, default=False)
    ab_test_traffic_pct = Column(Integer, default=50)
    # Percentage of traffic routed to this version during A/B test

    # Performance metrics (updated periodically)
    total_activations = Column(Integer, default=0)
    avg_accuracy_lift = Column(Float, nullable=True)
    # Accuracy improvement when this version is active vs inactive
    avg_tokens_consumed = Column(Float, nullable=True)
    avg_latency_ms = Column(Integer, nullable=True)
    csat_delta = Column(Float, nullable=True)
    # Customer satisfaction delta for this version

    # Prompt/template content
    prompt_template = Column(Text, nullable=True)
    # The actual prompt template or configuration for this version

    configuration = Column(Text, default="{}")
    # JSON blob with technique-specific parameters

    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "technique_id",
            "version",
            name="uq_technique_version",
        ),
        Index(
            "ix_tech_ver_company_tech",
            "company_id",
            "technique_id",
        ),
    )
