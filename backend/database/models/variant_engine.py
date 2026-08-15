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

from datetime import datetime, timezone, date

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
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
        ForeignKey("tickets.id", ondelete="CASCADE"),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
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
    Per-company agent assignments (BC-001).
    """

    __tablename__ = "ai_agent_assignments"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

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

    # Capability-aware routing (Phase: capability-aware Node 1)
    # domain: free-form label shown in UI (e.g. "Refunds", "Legal Review")
    # capabilities: JSON array of capability keys from the fixed vocabulary
    #   refund_processing, billing_inquiry, technical_support, faq_general,
    #   complaint_handling, account_management, fraud_security,
    #   shipping_delivery, product_information, legal_review,
    #   vip_enterprise, other
    # Node 1 reads these to route tickets to the right agent; if no agent
    # claims the matched capability, the ticket auto-escalates to human.
    domain = Column(String(100), nullable=True, index=True)
    capabilities = Column(Text, default="[]")
    instructions = Column(Text, nullable=True)
    restrictions = Column(Text, nullable=True)

    # ── Superglue tool linkage ───────────────────────────────────────
    # When the Builder Agent creates an AI agent, it ALSO requests Superglue
    # to generate a multi-step tool for it (via Superglue's own Agent API).
    # The returned tool_id is stored here. When a ticket routes to this agent,
    # Node 5 calls execute_tool(superglue_tool_id, inputs) to run the chain.
    #
    # Status flow:
    #   none      → no tool linked yet (agent can still respond via KB)
    #   pending   → Superglue Agent is generating the tool (async)
    #   active    → tool exists on Superglue, ready to execute
    #   failed    → Superglue Agent couldn't generate a tool (admin can retry)
    #   disabled  → admin paused the tool (still linked but not executed)
    superglue_tool_id = Column(String(100), nullable=True, index=True)
    superglue_tool_status = Column(String(20), default="none")  # none|pending|active|failed|disabled
    superglue_tool_definition = Column(Text, nullable=True)  # cached JSON for audit
    superglue_tool_created_at = Column(DateTime, nullable=True)

    # ── Approval gates (eliminate the risky part of tool execution) ──
    # When a customer requests a risky action (refund > $1000, cancel sub,
    # delete account), the tool execution is PAUSED and the ticket moves to
    # the "Pending Approval" queue. Admin reviews + clicks Approve/Reject.
    #
    # approval_required: TRUE if this agent's tool does dangerous actions
    # approval_threshold: numeric limit above which approval is required
    #   (e.g. 1000 = $10.00 in cents = $10 — adjust per capability)
    #
    # Default thresholds by capability (set by Builder Agent):
    #   refund_processing → approval_required=True, threshold=100000 ($1000)
    #   subscription_management → approval_required=True, threshold=0 (always)
    #   account_management → approval_required=True, threshold=0 (always)
    #   customer_lookup → approval_required=False (read-only)
    #   faq_general → approval_required=False (no tool)
    approval_required = Column(Boolean, default=False)
    approval_threshold_cents = Column(Integer, default=0)  # in cents, 0 = always require approval if required

    status = Column(String(50), default="active")
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ── Custom Categories (Builder Agent) ──────────────────────────────

class CustomCategory(Base):
    """
    Custom categories created by the Builder Agent.

    When the Builder creates an agent that doesn't map to any built-in
    ticket category (TICKET_PATTERNS), it creates a custom category
    with trigger keywords. Node 1 checks these during classification
    so tickets route to the right custom agent.

    ROADMAP Phase 5: "Custom categories + keywords created by Builder
    appear in Node 1 classification."
    """

    __tablename__ = "custom_categories"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    # e.g. "freight_tracking", "insurance_claim", or user-defined

    keywords = Column(Text, default="[]")
    # JSON array of trigger keywords: ["freight", "cargo", "shipment"]

    agent_id = Column(
        String(36),
        ForeignKey("ai_agent_assignments.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Which agent handles this custom category

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "name",
            name="uq_custom_category_company_name",
        ),
        Index(
            "ix_custom_cat_company_active",
            "company_id", "is_active",
        ),
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
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
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
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
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
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address = Column(String(45), nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
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
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
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
        ForeignKey("variant_instances.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="CASCADE"),
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
        DateTime, default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_pss_ticket_created",
            "company_id", "ticket_id", "created_at",
        ),
    )


# ── Agent Templates (shared across tenants — saves LLM cost) ──────
# Built ONCE per capability, reused by ALL tenants.
# Saves 99% of LLM calls (was 12 calls × N tenants = 12N, now 12 calls total).
#
# User vision (2026-08-12): "verify if it's in database, if yes don't
# make it again, if not present then make it"
#
# What's shared (template):
#   - base_instructions: "Handle refunds professionally..."
#   - base_restrictions: "Never refund > $1000..."
#   - capabilities: ["refund_processing", "billing_inquiry"]
#   - default_approval_threshold: 100000 ($1000)
#
# What's per-tenant (instance in AIAgentAssignment):
#   - company_id (tenant scoping — security)
#   - superglue_tool_id (tenant's OWN Stripe/Shopify API)
#   - kb_context (tenant's OWN refund policy docs)
#   - approval_threshold_cents (tenant's custom limit)

class AgentTemplate(Base):
    """Shared agent template — built once, cloned per tenant.

    When CRM analysis recommends "refund_processing":
      1. Check: does template exist? → YES → clone to AIAgentAssignment (0.1s)
      2. Check: does template exist? → NO → build via external Builder (12 LLM calls)
         → save as template → clone to AIAgentAssignment

    This saves 99% of LLM calls when multiple tenants need the same capability.
    """
    __tablename__ = "agent_templates"

    id = Column(String(36), primary_key=True, default=_uuid)

    # The capability this template handles (unique — one template per capability)
    capability = Column(String(100), nullable=False, unique=True, index=True)

    # Template content (shared across all tenants)
    agent_name = Column(String(100), nullable=False)
    agent_role = Column(String(100), default="template")
    domain = Column(String(100), nullable=True)
    capabilities = Column(Text, default="[]")  # JSON array
    instructions = Column(Text, nullable=True)  # base instructions
    restrictions = Column(Text, nullable=True)  # base restrictions

    # Default approval settings (tenants can override in their instance)
    default_approval_required = Column(Boolean, default=False)
    default_approval_threshold_cents = Column(Integer, default=0)

    # Metadata about the template creation
    quality_score = Column(Float, default=0.85)
    stage_iterations = Column(Text, nullable=True)  # JSON: {"explore":3,"design":4,"verify":5}
    created_by_build = Column(String(100), nullable=True)  # "external_builder" or "local"

    # Cache info
    times_used = Column(Integer, default=0)  # how many tenants cloned this
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<AgentTemplate capability={self.capability} used={self.times_used}>"

    def to_dict(self):
        """Serialize for API response."""
        import json as _json
        return {
            "id": self.id,
            "capability": self.capability,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "domain": self.domain,
            "capabilities": _json.loads(self.capabilities) if self.capabilities else [],
            "instructions": self.instructions,
            "restrictions": self.restrictions,
            "default_approval_required": self.default_approval_required,
            "default_approval_threshold_cents": self.default_approval_threshold_cents,
            "quality_score": self.quality_score,
            "times_used": self.times_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
