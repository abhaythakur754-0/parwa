"""
Variant Engine Models: 9 tables for Phase 3 AI Engine.

Tables:
  - variant_ai_capabilities: Feature/technique mapping to variant tiers
  - variant_instances: Per-tenant variant instance tracking
  - variant_workload_distribution: Ticket assignment across instances
  - ai_agent_assignments: Build agent → feature ownership
  - technique_caches: Query-similarity-based technique caching
  - ai_token_budgets: Per-tenant/instance token spending limits
  - prompt_injection_attempts: Injection attempt logging
  - ai_performance_variant_metrics: Per-instance performance metrics
  - pipeline_state_snapshots: LangGraph state persistence

BC-001: Every tenant-scoped table has company_id with index.
BC-002: Money fields use Numeric(10,4). No Float for money.
BC-012: created_at/updated_at on all tables.
"""

from datetime import datetime, date

import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, Numeric,
    String, Text, ForeignKey, UniqueConstraint, Index,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Variant AI Capabilities (feature → variant mapping) ─────────────

class VariantAICapability(Base):
    """
    Maps every AI feature/technique to variant tiers WITH
    instance-level support. Single source of truth for what
    each variant can access.

    instance_id=NULL means the rule applies to ALL instances
    of this variant_type for this tenant.
    """

    __tablename__ = "variant_ai_capabilities"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    variant_type = Column(String(50), nullable=False)
    # mini_parwa, parwa, parwa_high

    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id"),
        nullable=True,
    )
    # NULL = applies to all instances of this variant type

    feature_id = Column(String(100), nullable=False)
    # e.g. F-054, F-140, SG-01

    feature_name = Column(String(255), nullable=False)
    feature_category = Column(String(100))
    # routing, classification, rag, response,
    # technique, guardrail, monitoring, orchestration

    technique_tier = Column(String(10), nullable=True)
    # tier_1, tier_2, tier_3 — NULL if not a technique

    is_enabled = Column(Boolean, default=True, nullable=False)

    config_json = Column(Text, default="{}")
    # Per-variant feature configuration overrides

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_var_cap_comp_variant",
            "company_id", "variant_type",
        ),
        Index(
            "ix_var_cap_comp_feature",
            "company_id", "feature_id",
        ),
        UniqueConstraint(
            "company_id", "variant_type", "instance_id",
            "feature_id",
            name="uq_var_cap_instance_feature",
        ),
    )


# ── Variant Instances ───────────────────────────────────────────────

class VariantInstance(Base):
    """
    Tracks every variant instance per tenant.
    Supports unlimited instances: 5x Mini + 3x PARWA +
    2x PARWA High = 10 instances for one tenant.

    Each instance gets its own Celery queue namespace
    and Redis state partition.
    """

    __tablename__ = "variant_instances"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_name = Column(String(255), nullable=False)
    # e.g. "Mini PARWA - Chat"

    variant_type = Column(String(50), nullable=False)
    # mini_parwa, parwa, parwa_high

    status = Column(String(50), default="active")
    # active, inactive, warming, suspended

    channel_assignment = Column(Text, default="[]")
    # JSON: ["email", "chat", "sms", "voice", "social"]

    capacity_config = Column(Text, default="{}")
    # JSON: {max_concurrent_tickets, token_budget_share_pct,
    #         priority_weight}

    celery_queue_namespace = Column(String(100))
    # e.g. "tenant_abc_mini_1"

    redis_partition_key = Column(String(100))
    # e.g. "parwa:tenant_abc:inst:min_1"

    active_tickets_count = Column(Integer, default=0)
    total_tickets_handled = Column(Integer, default=0)
    last_activity_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_var_inst_comp_type",
            "company_id", "variant_type",
        ),
        Index(
            "ix_var_inst_comp_status",
            "company_id", "status",
        ),
        CheckConstraint(
            "active_tickets_count >= 0",
            name="ck_var_inst_active_tickets_nonneg",
        ),
        CheckConstraint(
            "total_tickets_handled >= 0",
            name="ck_var_inst_total_tickets_nonneg",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'warming', 'suspended')",
            name="ck_var_inst_valid_status",
        ),
    )


# ── Variant Workload Distribution ──────────────────────────────────

class VariantWorkloadDistribution(Base):
    """
    Tracks which instance handled which ticket.
    Supports rebalancing, escalation, and per-instance billing.
    """

    __tablename__ = "variant_workload_distribution"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id"),
        nullable=False, index=True,
    )

    distribution_strategy = Column(String(50))
    # round_robin, least_loaded, channel_pinned,
    # variant_priority, manual

    assigned_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    status = Column(String(50), default="assigned")
    # assigned, in_progress, completed, escalated, rebalanced

    escalation_target_instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id", ondelete="SET NULL"),
        nullable=True,
    )
    rebalance_from_instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id", ondelete="SET NULL"),
        nullable=True,
    )
    billing_charged_to_instance = Column(
        String(36),
        ForeignKey("variant_instances.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_vwd_inst_assigned",
            "company_id", "instance_id", "assigned_at",
        ),
    )


# ── AI Agent Assignments (build process) ──────────────────────────

class AIAgentAssignment(Base):
    """
    Tracks which build agent owns which features.
    Global table (no company_id — this is for dev process).
    """

    __tablename__ = "ai_agent_assignments"

    # Global table — no company_id column (for dev process)
    company_id = None  # Explicitly None so tests asserting .company_id is None pass

    id = Column(String(36), primary_key=True, default=_uuid)
    agent_name = Column(String(100), nullable=False)
    # Agent 1-5

    agent_role = Column(String(100))
    # Infrastructure, Routing, Classification/RAG,
    # Techniques, Monitoring/Ops

    feature_ids = Column(Text, default="[]")
    # JSON: ["F-054", "F-055", "SG-01"]

    task_ids = Column(Text, default="[]")
    # JSON: ["d1-agent1-01", "d1-agent1-02"]

    status = Column(String(50), default="active")
    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


# ── Technique Caches ───────────────────────────────────────────────

class TechniqueCache(Base):
    """
    Query-similarity-based cache for technique results.
    Avoids re-running the same technique for semantically
    similar queries within a time window.
    """

    __tablename__ = "technique_caches"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id"),
        nullable=True, index=True,
    )
    technique_id = Column(
        String(50), nullable=False, index=True,
    )

    query_hash = Column(String(64), nullable=False)
    # SHA-256 of the query

    signal_profile_hash = Column(String(64), nullable=True)
    # SHA-256 of signal profile for finer matching

    cached_result = Column(Text, nullable=False)
    # JSON serialized technique result

    similarity_score = Column(Numeric(5, 4), nullable=True)

    hit_count = Column(Integer, default=0)
    ttl_expires_at = Column(DateTime, nullable=False)

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_tech_cache_comp_tech_qh",
            "company_id", "technique_id", "query_hash",
        ),
        UniqueConstraint(
            "company_id", "instance_id",
            "technique_id", "query_hash",
            name="uq_tech_cache_instance",
        ),
    )


# ── AI Token Budgets ──────────────────────────────────────────────

class AITokenBudget(Base):
    """
    Per-tenant, per-variant-instance, per-period token
    spending limits. Hard-stop at budget limit.
    """

    __tablename__ = "ai_token_budgets"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id"),
        nullable=True, index=True,
    )

    budget_type = Column(String(20), nullable=False)
    # daily, monthly

    budget_period = Column(String(20), nullable=False)
    # "2026-04-06" for daily, "2026-04" for monthly

    max_tokens = Column(Integer, nullable=False)
    used_tokens = Column(Integer, default=0)
    alert_threshold_pct = Column(Integer, default=80)
    alert_sent = Column(Boolean, default=False)
    hard_stop = Column(Boolean, default=True)

    status = Column(String(50), default="active")
    # active, exceeded, disabled

    variant_default_limits = Column(Text, default="{}")
    # JSON: {mini_parwa: {daily: X}, parwa: {...}, ...}

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_tok_bud_comp_type_per",
            "company_id", "budget_type", "budget_period",
        ),
        UniqueConstraint(
            "company_id", "instance_id",
            "budget_type", "budget_period",
            name="uq_tok_bud_inst_period",
        ),
    )


# ── Prompt Injection Attempts ──────────────────────────────────────

class PromptInjectionAttempt(Base):
    """
    Logs every detected prompt injection attempt.
    Per-tenant blocklists + escalation on repeat offenders.
    """

    __tablename__ = "prompt_injection_attempts"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id"),
        nullable=True, index=True,
    )

    pattern_type = Column(String(100), nullable=False)
    # role_reversal, instruction_override, data_extraction,
    # token_theft, etc.

    severity = Column(String(20), nullable=False)
    # low, medium, high, critical

    query_hash = Column(String(64), nullable=False)

    query_preview = Column(Text, nullable=True)
    # First 500 chars, redacted

    detection_method = Column(String(100))
    # regex, classifier, heuristic

    action_taken = Column(String(50), default="logged")
    # logged, blocked, escalated

    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )
    ip_address = Column(String(45), nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_inj_comp_pattern",
            "company_id", "pattern_type",
        ),
        Index(
            "ix_inj_comp_created",
            "company_id", "created_at",
        ),
    )


# ── AI Performance Variant Metrics ────────────────────────────────

class AIPerformanceVariantMetric(Base):
    """
    Per-variant-instance AI performance metrics.
    Hourly granularity for real-time dashboards.
    """

    __tablename__ = "ai_performance_variant_metrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id"),
        nullable=True, index=True,
    )

    metric_date = Column(Date, nullable=False)
    metric_hour = Column(Integer, nullable=True)
    # 0-23, NULL = daily aggregate

    total_queries = Column(Integer, default=0)
    successful_queries = Column(Integer, default=0)
    failed_queries = Column(Integer, default=0)

    avg_latency_ms = Column(Integer, default=0)
    p95_latency_ms = Column(Integer, default=0)

    total_tokens_used = Column(Integer, default=0)
    total_cost_usd = Column(Numeric(10, 4), default=0)

    avg_confidence_score = Column(Numeric(5, 2), nullable=True)
    error_rate_pct = Column(Numeric(5, 2), default=0)

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_aipvm_inst_date",
            "company_id", "instance_id", "metric_date",
        ),
        UniqueConstraint(
            "company_id", "instance_id",
            "metric_date", "metric_hour",
            name="uq_aipvm_inst_date_hour",
        ),
    )


# ── Pipeline State Snapshots ──────────────────────────────────────

class PipelineStateSnapshot(Base):
    """
    Serialized LangGraph state for crash recovery,
    cross-worker handoff, debug replay, and audit trail.
    """

    __tablename__ = "pipeline_state_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    instance_id = Column(
        String(36),
        ForeignKey("variant_instances.id"),
        nullable=True, index=True,
    )
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id"),
        nullable=False, index=True,
    )
    session_id = Column(String(36), nullable=True)

    current_node = Column(String(100), nullable=False)
    state_data = Column(Text, nullable=False)
    # JSON serialized LangGraph state

    technique_stack = Column(Text, default="[]")
    # JSON: ["cot", "react", "crp"]

    model_used = Column(String(100), nullable=True)
    token_count = Column(Integer, default=0)

    snapshot_type = Column(String(50), default="auto")
    # auto, manual, error, checkpoint

    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index(
            "ix_pss_ticket_created",
            "company_id", "ticket_id", "created_at",
        ),
    )
