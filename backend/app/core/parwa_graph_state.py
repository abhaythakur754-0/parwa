"""
ParwaGraphState: Unified State Object for the Variant Engine.

A single TypedDict that travels through EVERY node in EVERY variant
pipeline. Every node reads from it and writes to it.

Design principles:
  - One state object for ALL variant tiers (Mini, Pro, High)
  - One state object for ALL industries (E-commerce, Logistics, SaaS, General)
  - Fields that don't apply to a tier simply remain default/None
  - Nodes write ONLY the fields they own; other fields pass through untouched

Architecture:
  INCOMING  — set before pipeline starts (by the router/caller)
  PIPELINE  — nodes read/write during execution
  OUTPUT    — pipeline fills these for the final response
  METADATA  — audit, billing, compliance

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional, TypedDict


# ══════════════════════════════════════════════════════════════════
# PARWA GRAPH STATE
# ══════════════════════════════════════════════════════════════════


class ParwaGraphState(TypedDict, total=False):
    """Unified state object that flows through every node in the LangGraph pipeline.

    This is the single source of truth for all pipeline data. Nodes READ
    from it and WRITE to it. The LangGraph reducer ``operator.or_`` merges
    dict updates, so nodes only need to return the fields they changed.

    Fields are grouped by purpose. Not all fields are used by every variant
    tier — Mini doesn't use `signals` or `technique`, but those fields
    exist harmlessly as None/empty for Mini and get populated for Pro/High.
    """

    # ── INCOMING: Set before pipeline starts ──────────────────────
    # These are provided by the router/caller when invoking the graph.

    query: str
    """The customer's raw input message."""

    company_id: str
    """Tenant identifier (BC-001)."""

    variant_tier: str
    """Which variant tier is running: 'mini_parwa' | 'parwa' | 'parwa_high'."""

    variant_instance_id: str
    """Which specific instance is handling this ticket.
    Same tier can have multiple instances (e.g., 2x Pro).
    Used for per-instance metrics, billing, capacity tracking."""

    industry: str
    """Industry context: 'ecommerce' | 'logistics' | 'saas' | 'general'.
    Affects system prompts, available tools, response tone."""

    channel: str
    """Inbound channel: 'chat' | 'email' | 'phone' | 'web_widget' | 'social'.
    Affects response formatting and default variant routing."""

    conversation_id: str
    """Ongoing conversation tracking for multi-turn context."""

    ticket_id: str
    """Ticket ID for audit trail and state persistence."""

    customer_id: str
    """Customer identifier for personalization and CRM lookups."""

    customer_tier: str
    """Customer subscription tier: 'free' | 'starter' | 'growth' | 'enterprise'.
    Affects tone, escalation priority, and technique selection."""

    # ── PIPELINE CONTROL: Nodes read/write during execution ───────

    current_step: str
    """Which node is currently executing. Updated by the router before each node."""

    # -- PII Detection node writes --
    pii_detected: bool
    """Whether PII was found in the query."""

    pii_redacted_query: str
    """Query with PII redacted. Nodes after PII should use this instead of `query`."""

    pii_entities: List[Dict[str, Any]]
    """List of detected PII entities: [{type, value, start, end}]."""

    # -- Empathy Check node writes --
    empathy_score: float
    """0.0-1.0 empathy assessment of the query's emotional state."""

    empathy_flags: List[str]
    """Flags like 'frustrated', 'urgent', 'grieving', 'angry'."""

    # -- Emergency Check node writes --
    emergency_flag: bool
    """True if the query requires immediate human escalation."""

    emergency_type: str
    """Type of emergency: 'legal_threat' | 'safety' | 'compliance' | 'media'."""

    # -- Classify node writes --
    classification: Dict[str, Any]
    """Intent classification result:
    {
        'intent': str,           # primary intent
        'confidence': float,     # 0.0-1.0
        'secondary_intents': [], # alternative intents
        'method': str,           # 'ai' | 'regex' | 'fallback'
    }"""

    # -- Extract Signals node writes (Pro+ only) --
    signals: Dict[str, Any]
    """Extracted signals from the query:
    {
        'complexity': float,         # 0.0-1.0
        'sentiment': float,          # 0.0-1.0
        'frustration_score': float,  # 0-100
        'monetary_value': float,     # detected monetary amount
        'customer_tier': str,        # derived customer tier
        'turn_count': int,           # conversation turn number
        'resolution_path_count': int,# number of possible solutions
        'reasoning_loop_detected': bool,
    }"""

    # -- Technique Select node writes (Pro+ only) --
    technique: Dict[str, Any]
    """Selected reasoning technique:
    {
        'technique': str,              # primary technique ID
        'activated_techniques': [],    # all activated techniques
        'model_tier': str,            # 'light' | 'medium' | 'heavy'
        'trigger_rules_matched': [],   # which rules triggered
        'method': str,                 # 'ai' | 'rule' | 'cache'
    }"""

    # -- Smart Enrichment node writes (Pro+ only) --
    emotion_profile: Dict[str, Any]
    """Emotional intelligence profile from EI engine:
    {
        'primary_emotion': str,
        'secondary_emotions': List[str],
        'intensity': float,
        'risk_level': str,
        'emotional_needs': List[str],
        'escalation_trajectory': str,
        'de_escalation_priority': float,
    }"""

    recovery_playbook: Dict[str, Any]
    """Service recovery playbook selection:
    {
        'strategy': str,
        'actions': List[str],
        'compensation': Optional[str],
        'escalation': bool,
        'playbook_name': str,
    }"""

    churn_risk: Dict[str, Any]
    """Churn risk scoring result:
    {
        'churn_probability': float,
        'risk_tier': str,
        'primary_reason': str,
        'retention_urgency': str,
    }"""

    retention_offers: Dict[str, Any]
    """Dynamic retention offer selection:
    {
        'recommended_offers': List[Dict],
        'primary_offer': Dict,
        'contingency_offers': List[Dict],
    }"""

    billing_dispute: Dict[str, Any]
    """Billing dispute classification:
    {
        'dispute_category': str,
        'auto_resolvable': bool,
        'resolution_type': str,
        'priority': str,
    }"""

    billing_anomaly: Dict[str, Any]
    """Billing anomaly detection:
    {
        'anomaly_detected': bool,
        'anomaly_types': List[str],
        'severity': str,
    }"""

    known_issue: Dict[str, Any]
    """Known issue detection:
    {
        'known_issue_detected': bool,
        'issue_id': str,
        'severity': str,
        'message': str,
        'eta_hours': int,
    }"""

    tech_diagnostics: Dict[str, Any]
    """Technical diagnostic steps:
    {
        'diagnostic_steps': List[Dict],
        'diagnostic_categories': List[str],
        'estimated_resolution_time': str,
    }"""

    severity_score: Dict[str, Any]
    """Escalation severity scoring:
    {
        'severity_score': float,
        'severity_level': str,
        'escalation_path': str,
        'recommended_actions': List[str],
    }"""

    shipping_issue: Dict[str, Any]
    """Shipping issue classification:
    {
        'issue_detected': bool,
        'issue_type': str,
        'severity': str,
        'resolution': str,
    }"""

    shipping_delay: Dict[str, Any]
    """Shipping delay assessment:
    {
        'delay_detected': bool,
        'delay_reason': str,
        'compensation_eligible': bool,
    }"""

    tracking_info: Dict[str, Any]
    """Tracking number detection:
    {
        'tracking_detected': bool,
        'tracking_numbers': List[Dict],
        'primary_carrier': str,
    }"""

    enrichment_context: str
    """Combined enrichment prompt addition for LLM generation."""

    # -- Deep Enrichment: Complaint Handling Enhancement --

    complaint_resolution: Dict[str, Any]
    """Deep complaint resolution result:
    {
        'resolution_strategy': str,
        'de_escalation_applied': bool,
        'compensation_type': str,
        'follow_up_scheduled': bool,
        'escalation_triggered': bool,
        'resolution_confidence': float,
    }"""

    sentiment_escalation: Dict[str, Any]
    """Sentiment-based escalation decision:
    {
        'escalation_needed': bool,
        'escalation_level': str,
        'trigger_reason': str,
        'priority_score': float,
    }"""

    # -- Deep Enrichment: Cancellation/Retention Enhancement --

    retention_negotiation: Dict[str, Any]
    """Retention negotiation result:
    {
        'negotiation_strategy': str,
        'offer_presented': str,
        'counter_offers': List[str],
        'acceptance_likelihood': float,
        'negotiation_stage': str,
    }"""

    winback_sequence: Dict[str, Any]
    """Win-back automation sequence:
    {
        'sequence_active': bool,
        'sequence_steps': List[Dict],
        'total_duration_days': int,
        'primary_offer': str,
    }"""

    # -- Deep Enrichment: Billing Enhancement --

    billing_self_service: Dict[str, Any]
    """Self-service billing portal context:
    {
        'portal_url': str,
        'available_actions': List[str],
        'dispute_status': str,
        'refund_eligible': bool,
    }"""

    paddle_dispute: Dict[str, Any]
    """Paddle dispute auto-resolution:
    {
        'dispute_id': str,
        'auto_resolved': bool,
        'resolution_action': str,
        'refund_amount': Optional[float],
        'processing_time_hours': int,
    }"""

    # -- Deep Enrichment: Technical Support Enhancement --

    diagnostic_result: Dict[str, Any]
    """Deep diagnostic result:
    {
        'steps_provided': int,
        'known_issue_match': bool,
        'severity_assessment': str,
        'auto_fix_available': bool,
        'resolution_path': str,
    }"""

    escalation_decision: Dict[str, Any]
    """Escalation severity decision:
    {
        'escalate': bool,
        'escalation_level': str,
        'severity_factors': Dict[str, float],
        'recommended_actions': List[str],
    }"""

    # -- Deep Enrichment: Shipping Enhancement --

    shipping_carrier_data: Dict[str, Any]
    """Multi-carrier API integration data:
    {
        'carrier': str,
        'tracking_status': str,
        'estimated_delivery': str,
        'carrier_api_called': bool,
        'last_update': str,
    }"""

    delay_notification: Dict[str, Any]
    """Proactive delay notification:
    {
        'notification_sent': bool,
        'notification_type': str,
        'delay_reason': str,
        'revised_eta': str,
        'compensation_offered': bool,
    }"""

    # -- Context Compress node writes (High only) --
    context_compressed: bool
    """Whether context compression was applied."""

    context_compression_ratio: float
    """Compression ratio achieved (0.0-1.0, lower = more compressed)."""

    compressed_context: str
    """The compressed context string (replaces raw context for Generate)."""

    # -- Generate node writes --
    generated_response: str
    """The raw AI-generated response (before quality check)."""

    generation_model: str
    """Which LLM model was used for generation."""

    generation_tokens: int
    """Tokens used for the generation step specifically."""

    # -- Quality Gate node writes (Pro+ only) --
    quality_score: float
    """0.0-1.0 quality assessment of the generated response."""

    quality_passed: bool
    """Whether the response passes quality threshold."""

    quality_issues: List[str]
    """List of quality issues found: ['hallucination', 'off_topic', etc.]."""

    quality_retry_count: int
    """Number of times generation was retried after quality gate failure."""

    # -- Context Health node writes (High only) --
    context_health: Dict[str, Any]
    """Context health assessment:
    {
        'health_score': float,       # 0.0-1.0
        'degradation_level': str,    # 'none' | 'mild' | 'moderate' | 'severe'
        'recommendation': str,       # 'continue' | 'compress' | 'reset'
        'drift_detected': bool,
    }"""

    # -- Dedup node writes (High only) --
    dedup_similarity_score: float
    """Similarity score to previous responses (0.0-1.0)."""

    dedup_is_duplicate: bool
    """Whether this response is too similar to a previous one."""

    # -- Format node writes --
    formatted_response: str
    """The final formatted response ready for the customer."""

    response_format: str
    """Format applied: 'chat' | 'email' | 'phone_transcript' | 'social'."""

    # ── OUTPUT: Pipeline fills these ──────────────────────────────

    final_response: str
    """What the customer sees — the last step writes this."""

    total_tokens: int
    """Cumulative token count across all steps (for cost tracking)."""

    total_latency_ms: float
    """Total pipeline execution time in milliseconds."""

    pipeline_status: str
    """Overall pipeline result: 'success' | 'partial' | 'failed' | 'timeout'."""

    steps_completed: List[str]
    """List of step IDs that completed successfully."""

    # ── METADATA: Audit, billing, compliance ──────────────────────

    audit_log: Annotated[List[Dict[str, Any]], operator.add]
    """Audit entries appended by each node:
    [{
        'step': str,
        'action': str,
        'timestamp': str,  # ISO-8601 UTC
        'duration_ms': float,
        'tokens_used': int,
        'details': dict,
    }]
    Uses operator.add reducer so nodes can append without overwriting."""

    billing_tier: str
    """Which billing rate to apply: matches variant_tier."""

    billing_tokens: int
    """Tokens counted for billing (may differ from total_tokens due to free steps)."""

    billing_cost_usd: float
    """Estimated cost in USD for this pipeline run."""

    errors: Annotated[List[str], operator.add]
    """Errors encountered during pipeline execution.
    Uses operator.add reducer so nodes can append without overwriting."""

    # ── STEP OUTPUTS: Per-step results for LangGraph state management ──

    step_outputs: Annotated[Dict[str, Any], operator.or_]
    """Per-step output keyed by step_id. LangGraph uses operator.or_
    to merge dict updates from each node."""


# ══════════════════════════════════════════════════════════════════
# HELPER: Create initial state
# ══════════════════════════════════════════════════════════════════


def create_initial_state(
    query: str,
    company_id: str,
    variant_tier: str,
    variant_instance_id: str = "",
    industry: str = "general",
    channel: str = "chat",
    conversation_id: str = "",
    ticket_id: str = "",
    customer_id: str = "",
    customer_tier: str = "free",
) -> ParwaGraphState:
    """Create a fresh ParwaGraphState with all fields initialized.

    This is the ONLY way to create initial state for the pipeline.
    Ensures all fields exist (even if default) so nodes never hit KeyError.

    Args:
        query: Customer's raw message.
        company_id: Tenant identifier (BC-001).
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'.
        variant_instance_id: Specific instance handling this ticket.
        industry: 'ecommerce' | 'logistics' | 'saas' | 'general'.
        channel: 'chat' | 'email' | 'phone' | 'web_widget' | 'social'.
        conversation_id: For multi-turn tracking.
        ticket_id: Ticket identifier.
        customer_id: Customer identifier.
        customer_tier: Customer subscription tier.

    Returns:
        Fully initialized ParwaGraphState ready for pipeline execution.
    """
    return ParwaGraphState(
        # INCOMING
        query=query,
        company_id=company_id,
        variant_tier=variant_tier,
        variant_instance_id=variant_instance_id,
        industry=industry,
        channel=channel,
        conversation_id=conversation_id,
        ticket_id=ticket_id,
        customer_id=customer_id,
        customer_tier=customer_tier,
        # PIPELINE CONTROL — defaults
        current_step="",
        pii_detected=False,
        pii_redacted_query=query,  # falls back to raw query if PII node doesn't run
        pii_entities=[],
        empathy_score=0.0,
        empathy_flags=[],
        emergency_flag=False,
        emergency_type="",
        classification={},
        signals={},
        technique={},
        context_compressed=False,
        context_compression_ratio=1.0,
        compressed_context="",
        generated_response="",
        generation_model="",
        generation_tokens=0,
        quality_score=0.0,
        quality_passed=True,  # default pass — Mini doesn't use quality gate
        quality_issues=[],
        quality_retry_count=0,
        # Enhancement fields — defaults
        emotion_profile={},
        recovery_playbook={},
        churn_risk={},
        retention_offers={},
        billing_dispute={},
        billing_anomaly={},
        known_issue={},
        tech_diagnostics={},
        severity_score={},
        shipping_issue={},
        shipping_delay={},
        tracking_info={},
        enrichment_context="",
        # Deep enrichment fields — defaults
        complaint_resolution={},
        sentiment_escalation={},
        retention_negotiation={},
        winback_sequence={},
        billing_self_service={},
        paddle_dispute={},
        diagnostic_result={},
        escalation_decision={},
        shipping_carrier_data={},
        delay_notification={},
        # High-specific fields
        context_health={},
        dedup_similarity_score=0.0,
        dedup_is_duplicate=False,
        formatted_response="",
        response_format=channel,
        # OUTPUT — defaults
        final_response="",
        total_tokens=0,
        total_latency_ms=0.0,
        pipeline_status="pending",
        steps_completed=[],
        # METADATA — defaults
        audit_log=[],
        billing_tier=variant_tier,
        billing_tokens=0,
        billing_cost_usd=0.0,
        errors=[],
        step_outputs={},
    )


# ══════════════════════════════════════════════════════════════════
# HELPER: Extract node output from state
# ══════════════════════════════════════════════════════════════════


def get_step_output(state: ParwaGraphState, step_id: str) -> Dict[str, Any]:
    """Safely get a previous step's output from state.

    Args:
        state: Current pipeline state.
        step_id: The step whose output to retrieve.

    Returns:
        The step's output dict, or empty dict if not found.
    """
    try:
        step_outputs = state.get("step_outputs", {})
        output = step_outputs.get(step_id, {})
        return output if isinstance(output, dict) else {}
    except Exception:
        return {}


def append_audit_entry(
    state: ParwaGraphState,
    step: str,
    action: str,
    duration_ms: float = 0.0,
    tokens_used: int = 0,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an audit log entry to return from a node.

    Since audit_log uses operator.add reducer, returning this entry
    will APPEND it to the existing list (not overwrite).

    Args:
        state: Current pipeline state (for context).
        step: Which node is logging.
        action: What action was performed.
        duration_ms: How long the action took.
        tokens_used: Tokens consumed by this action.
        details: Additional context.

    Returns:
        Dict with audit_log key containing the new entry.
    """
    entry = {
        "step": step,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(duration_ms, 2),
        "tokens_used": tokens_used,
        "company_id": state.get("company_id", ""),
        "variant_tier": state.get("variant_tier", ""),
        "industry": state.get("industry", ""),
        "details": details or {},
    }
    return {"audit_log": [entry]}
