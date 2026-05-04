"""
ParwaGraphState — Shared State for the Multi-Agent LangGraph System

This TypedDict defines the single shared state object that flows through
ALL 18+ agent nodes in the PARWA LangGraph graph. Every node reads from
and writes to this state.

Design Principles:
  1. Every field is Optional — nodes only read what they need, write what they produce
  2. Annotated[list, operator.add] for append-only lists (errors, audit trail)
  3. Annotated[dict, operator.or_] for merge-accumulated dicts (node_outputs)
  4. variant_tier is the KING field — it drives agent availability, MAKER mode,
     technique access, channel availability, and approval requirements
  5. Groups are logical, not enforced by Python — they help developers understand
     which fields belong together

Groups (18):
  1. INPUT              — Raw query + metadata
  2. PII_REDACTION      — PII-scrubbed message + detected entities
  3. EMPATHY_ENGINE     — Sentiment, urgency, threat detection
  4. ROUTER_AGENT       — Intent, complexity, target agent selection
  5. DOMAIN_AGENT       — Agent response, confidence, proposed action
  6. MAKER_VALIDATOR    — K-solution generation, selection, red flags
  7. CONTROL_SYSTEM     — Approval decisions, confidence breakdowns
  8. DSPY_OPTIMIZER     — Prompt optimization metadata
  9. GUARDRAILS         — Safety checks, flags, blocks
  10. CHANNEL_DELIVERY   — Delivery status, confirmations
  11. STATE_UPDATE       — Persistence, audit, metrics
  12. GSD_STATE          — Guided Support Dialogue state machine
  13. METADATA           — Processing timing, token usage, execution log
  14. JARVIS_AWARENESS   — System-wide awareness for Jarvis Command Center
  15. EMERGENCY_CONTROLS — AI pause, circuit breakers, emergency state
  16. ANTI_ARBITRAGE     — Gaming detection, risk scoring
  17. BRAND_VOICE_RAG    — Brand voice application, RAG retrieval
  18. COLLECTIVE_INTEL   — Collective intelligence, reward signals

BC-001: company_id (tenant_id) is always present for multi-tenant isolation.
BC-008: Never crash — all nodes wrap in try/except, write errors to state.errors.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from typing import TypedDict


# ══════════════════════════════════════════════════════════════════
# Append-only list reducer: new items are appended, never replaced
# ══════════════════════════════════════════════════════════════════

def _merge_lists(existing: List[Any], new: List[Any]) -> List[Any]:
    """Reducer: append new items to existing list."""
    return existing + new


def _merge_dicts(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer: merge new dict into existing dict (new keys override)."""
    merged = {**existing, **new}
    return merged


def _max_float(existing: float, new: float) -> float:
    """Reducer: keep the maximum value (for scores)."""
    return max(existing, new)


def _replace(existing: Any, new: Any) -> Any:
    """Reducer: last write wins (default behavior)."""
    return new


# ══════════════════════════════════════════════════════════════════
# PARWA GRAPH STATE — 18 Groups, ~117 Fields
# ══════════════════════════════════════════════════════════════════


class ParwaGraphState(TypedDict, total=False):
    """
    Shared state flowing through all LangGraph agent nodes.

    Every field is optional (total=False) because:
      - Nodes only write the fields they produce
      - The graph starts with minimal INPUT fields
      - Fields accumulate as the graph executes

    variant_tier is the KING field — it determines:
      - Which agents are available (mini=3, pro=6, high=all)
      - MAKER mode (efficiency/balanced/conservative)
      - Technique access (T1 / T1+T2 / T1+T2+T3)
      - Channel availability (voice=pro+high, video=high)
      - Approval requirements (none / money+vip / all risky)
    """

    # ──────────────────────────────────────────────────────────────
    # GROUP 1: INPUT (11 fields)
    # Raw query + metadata that starts the graph
    # ──────────────────────────────────────────────────────────────

    message: str
    """Raw incoming message from customer (before PII redaction)."""

    channel: str
    """Origin channel: email, sms, voice, chat, api."""

    customer_id: str
    """Unique customer identifier (BC-001 tenant-scoped)."""

    tenant_id: str
    """Company/tenant identifier — KING field for multi-tenant isolation (BC-001)."""

    variant_tier: str
    """Variant tier: mini, pro, high — DRIVES EVERYTHING."""

    customer_tier: str
    """Customer segment: free, pro, enterprise, vip."""

    industry: str
    """Industry vertical for domain-specific handling."""

    language: str
    """Detected/requested language code (e.g., en, hi, es)."""

    conversation_id: str
    """Ongoing conversation identifier for continuity."""

    ticket_id: str
    """Associated ticket identifier (created or existing)."""

    session_id: str
    """Session identifier for state persistence."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 2: PII REDACTION (2 fields)
    # PII-scrubbed message + detected entities
    # ──────────────────────────────────────────────────────────────

    pii_redacted_message: str
    """Message after PII entities have been redacted/masked."""

    pii_entities_found: Annotated[List[Dict[str, Any]], _merge_lists]
    """List of PII entities detected: [{type, value, position, replacement}]."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 3: EMPATHY ENGINE (5 fields)
    # Sentiment, urgency, threat detection
    # ──────────────────────────────────────────────────────────────

    sentiment_score: float
    """Sentiment score 0.0-1.0 (0=very negative, 1=very positive)."""

    sentiment_intensity: str
    """Intensity level: low, medium, high, extreme."""

    legal_threat_detected: bool
    """Whether legal threats were detected in the message."""

    urgency: str
    """Urgency classification: low, medium, high, critical."""

    sentiment_trend: str
    """Sentiment trend across conversation: improving, stable, declining, spiraling."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 4: ROUTER AGENT (6 fields)
    # Intent, complexity, target agent selection
    # ──────────────────────────────────────────────────────────────

    intent: str
    """Classified intent: faq, refund, technical, billing, complaint, escalation, general."""

    complexity_score: float
    """Query complexity 0.0-1.0."""

    target_agent: str
    """Selected domain agent: faq, refund, technical, billing, complaint, escalation."""

    model_tier: str
    """Selected model tier: light, medium, heavy."""

    technique_stack: Annotated[List[str], _merge_lists]
    """Ordered list of technique IDs to apply (driven by variant_tier + signals)."""

    signals_extracted: Dict[str, Any]
    """Extracted query signals for technique routing (QuerySignals as dict)."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 5: DOMAIN AGENT (6 fields)
    # Agent response, confidence, proposed action
    # ──────────────────────────────────────────────────────────────

    agent_response: str
    """The domain agent's generated response text."""

    agent_confidence: float
    """Agent's confidence in its response 0.0-1.0."""

    proposed_action: str
    """Proposed action: respond, refund, escalate, create_ticket, etc."""

    action_type: str
    """Action classification: informational, monetary, destructive, escalation."""

    agent_reasoning: str
    """Agent's chain-of-thought reasoning for audit/debugging."""

    agent_type: str
    """Which domain agent produced this: faq, refund, technical, billing, complaint, escalation."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 6: MAKER VALIDATOR (8 fields)
    # K-solution generation, selection, red flags
    # Applied to ALL tiers (mini=K3, pro=K3-5, high=K5-7)
    # ──────────────────────────────────────────────────────────────

    k_solutions: Annotated[List[Dict[str, Any]], _merge_lists]
    """Generated K candidate solutions: [{solution, confidence, reasoning}]."""

    selected_solution: str
    """The best solution selected by MAKER from K candidates."""

    red_flag: bool
    """Whether MAKER detected a red flag (confidence below threshold)."""

    maker_mode: str
    """Current MAKER mode: efficiency (mini), balanced (pro), conservative (high)."""

    k_value_used: int
    """K value used for this execution (3/3-5/5-7 based on tier)."""

    fake_threshold: float
    """Confidence threshold applied: 0.50 (mini), 0.60 (pro), 0.75 (high)."""

    maker_decomposition: Dict[str, Any]
    """MAKER's problem decomposition for audit trail."""

    maker_audit_trail: Annotated[List[Dict[str, Any]], _merge_lists]
    """Step-by-step audit of MAKER evaluation process."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 7: CONTROL SYSTEM (7 fields)
    # Approval decisions, confidence breakdowns, interrupt logic
    # ──────────────────────────────────────────────────────────────

    approval_decision: str
    """Control decision: approved, rejected, needs_human_approval, auto_approved."""

    confidence_breakdown: Dict[str, float]
    """Confidence breakdown: {agent_confidence, maker_confidence, guardrails_score, overall}."""

    system_mode: str
    """System mode: auto, supervised, shadow, paused."""

    dnd_applies: bool
    """Whether Do Not Disturb rules apply for this customer."""

    money_rule_triggered: bool
    """Whether a monetary action rule was triggered (refund, discount, etc.)."""

    vip_rule_triggered: bool
    """Whether a VIP customer rule was triggered."""

    approval_timeout_seconds: int
    """Timeout for human approval before auto-escalation."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 8: DSPY OPTIMIZER (2 fields)
    # Prompt optimization metadata
    # ──────────────────────────────────────────────────────────────

    prompt_optimized: bool
    """Whether DSPy prompt optimization was applied."""

    optimized_prompt_version: str
    """Version identifier of the optimized prompt used."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 9: GUARDRAILS (3 fields)
    # Safety checks, flags, blocks
    # ──────────────────────────────────────────────────────────────

    guardrails_passed: bool
    """Whether all guardrail checks passed."""

    guardrails_flags: Annotated[List[Dict[str, Any]], _merge_lists]
    """List of guardrail flags: [{rule_id, severity, message}]."""

    guardrails_blocked_reason: str
    """If blocked, the reason; empty string if not blocked."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 10: CHANNEL DELIVERY (6 fields)
    # Delivery status, confirmations, fallbacks
    # ──────────────────────────────────────────────────────────────

    delivery_status: str
    """Delivery status: pending, sent, delivered, failed, bounced."""

    delivery_channel: str
    """Actual delivery channel used (may differ from input channel after fallback)."""

    delivery_timestamp: str
    """UTC ISO timestamp of delivery attempt."""

    delivery_confirmation_id: str
    """Delivery confirmation/receipt identifier."""

    delivery_failure_reason: str
    """Reason for delivery failure, if any."""

    fallback_attempted: bool
    """Whether a fallback channel was attempted after primary failure."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 11: STATE UPDATE (8 fields)
    # Persistence, audit, metrics updates
    # ──────────────────────────────────────────────────────────────

    ticket_created: bool
    """Whether a new ticket was created during this flow."""

    ticket_updated: bool
    """Whether an existing ticket was updated."""

    ticket_status: str
    """Current ticket status: open, in_progress, resolved, closed, escalated."""

    gsd_state_persisted: bool
    """Whether GSD state was persisted to database."""

    audit_log_written: bool
    """Whether an audit log entry was written."""

    metrics_updated: bool
    """Whether metrics counters were incremented."""

    jarvis_feed_pushed: bool
    """Whether state was pushed to Jarvis awareness feed."""

    fifty_mistake_check: Dict[str, Any]
    """Agent Lightning 50-mistake rule check result: {agent_id, mistake_count, training_needed}."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 12: GSD STATE (4 fields)
    # Guided Support Dialogue state machine
    # ──────────────────────────────────────────────────────────────

    gsd_state: str
    """Current GSD state: new, greeting, diagnosis, resolution, follow_up, escalate, human_handoff, closed."""

    gsd_step: str
    """Current step within the GSD state."""

    context_health: float
    """Context health score 0.0-1.0 (1.0 = perfectly healthy)."""

    context_compressed: bool
    """Whether context compression was applied to manage token budget."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 13: METADATA (9 fields)
    # Processing timing, token usage, execution log
    # ──────────────────────────────────────────────────────────────

    processing_start_time: str
    """UTC ISO timestamp when processing started."""

    model_used: str
    """LLM model identifier used for primary generation."""

    tokens_consumed: int
    """Total tokens consumed across all LLM calls."""

    total_llm_calls: int
    """Total number of LLM API calls made."""

    node_execution_log: Annotated[List[Dict[str, Any]], _merge_lists]
    """Per-node execution log: [{node_name, duration_ms, tokens, status, timestamp}]."""

    error: str
    """Last error message, if any (non-fatal)."""

    reward_signal: float
    """Reward signal for Collective Intelligence feedback (0.0-1.0)."""

    shadow_mode_intercepted: bool
    """Whether this flow was intercepted in Shadow Mode (SHADOW→SUPERVISED→GRADUATED)."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 14: JARVIS AWARENESS (21 fields)
    # System-wide awareness for Jarvis Command Center
    # Jarvis needs to know EVERYTHING happening in the system
    # ──────────────────────────────────────────────────────────────

    current_plan: str
    """Current subscription plan: mini, pro, high."""

    plan_usage_today: float
    """Plan usage percentage today (0.0-100.0)."""

    subscription_status: str
    """Subscription status: active, past_due, cancelled, trial."""

    days_until_renewal: int
    """Days until subscription renewal date."""

    system_health: str
    """Overall system health: healthy, degraded, critical, down."""

    channel_health: Dict[str, str]
    """Per-channel health status: {email: healthy, sms: degraded, voice: healthy}."""

    active_alerts: Annotated[List[Dict[str, Any]], _merge_lists]
    """Active system alerts: [{alert_id, severity, message, channel}]."""

    ticket_volume_today: int
    """Total tickets processed today for this tenant."""

    ticket_volume_avg: float
    """Average daily ticket volume (7-day rolling)."""

    ticket_volume_spike: bool
    """Whether today's volume exceeds 2x average."""

    active_agents: int
    """Number of currently active AI agents for this tenant."""

    agent_pool_capacity: int
    """Maximum concurrent agents allowed for this tier."""

    agent_pool_utilization: float
    """Agent pool utilization percentage (0.0-100.0)."""

    training_running: bool
    """Whether Agent Lightning training is currently running."""

    training_mistake_count: int
    """Current mistake count for Agent Lightning (out of 50)."""

    training_model_version: str
    """Current model version being trained by Agent Lightning."""

    drift_status: str
    """Model drift status: none, slight, moderate, severe."""

    drift_score: float
    """Drift detection score (0.0-1.0, higher = more drift)."""

    quality_score: float
    """Overall quality score across recent responses (0.0-1.0)."""

    quality_alerts: Annotated[List[Dict[str, Any]], _merge_lists]
    """Quality-related alerts: [{metric, threshold, actual, severity}]."""

    last_5_errors: Annotated[List[Dict[str, Any]], _merge_lists]
    """Last 5 error records: [{error, node, timestamp, tenant_id}]."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 15: EMERGENCY CONTROLS (6 fields)
    # AI pause, circuit breakers, emergency state
    # ──────────────────────────────────────────────────────────────

    ai_paused: bool
    """Whether AI processing is globally paused for this tenant."""

    paused_channels: Annotated[List[str], _merge_lists]
    """Channels where AI is currently paused: [email, sms, voice]."""

    paused_actions: Annotated[List[str], _merge_lists]
    """Action types currently paused: [refund, escalation, etc.]."""

    emergency_state: str
    """Emergency state: normal, yellow_alert, red_alert, full_stop."""

    circuit_breaker_trips: int
    """Number of circuit breaker trips in the last hour."""

    global_pause_reason: str
    """Reason for global AI pause, if any."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 16: ANTI-ARBITRAGE (4 fields)
    # Gaming detection, risk scoring
    # ──────────────────────────────────────────────────────────────

    arbitrage_risk_score: float
    """Arbitrage risk score 0.0-1.0 (7 signal types aggregated)."""

    arbitrage_signals: Annotated[List[Dict[str, Any]], _merge_lists]
    """Detected arbitrage signals: [{signal_type, value, threshold, triggered}]."""

    active_sessions: int
    """Number of active sessions for this customer (gaming indicator)."""

    plan_cycling_detected: bool
    """Whether plan cycling (subscribe/cancel/re-subscribe) was detected."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 17: BRAND VOICE & RAG (5 fields)
    # Brand voice application, RAG retrieval
    # ──────────────────────────────────────────────────────────────

    brand_voice_applied: bool
    """Whether brand voice profile was applied to the response."""

    brand_voice_profile: Dict[str, Any]
    """Applied brand voice settings: {tone, formality, greeting, closing, prohibited_terms}."""

    rag_documents_retrieved: Annotated[List[Dict[str, Any]], _merge_lists]
    """RAG retrieved documents: [{doc_id, content, score, source}]."""

    rag_reranked: bool
    """Whether RAG results were reranked for relevance."""

    kb_documents_used: Annotated[List[str], _merge_lists]
    """Knowledge base document IDs used in response generation."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 18: COLLECTIVE INTELLIGENCE & REWARD (5 fields)
    # Shared learning, reward signals, manager corrections
    # ──────────────────────────────────────────────────────────────

    collective_patterns_used: Annotated[List[Dict[str, Any]], _merge_lists]
    """Collective intelligence patterns applied: [{pattern_id, source, confidence}]."""

    manager_correction: bool
    """Whether a human manager corrected this response."""

    auto_approved_rule_created: bool
    """Whether an auto-approval rule was created from this interaction."""

    batch_cluster_id: str
    """Batch processing cluster identifier for analytics."""

    node_outputs: Annotated[Dict[str, Any], _merge_dicts]
    """Accumulated outputs from each node: {node_name: output_dict}.
    This is the primary way nodes share data with downstream nodes."""

    errors: Annotated[List[str], _merge_lists]
    """Accumulated error messages across all nodes (BC-008 graceful degradation)."""


# ══════════════════════════════════════════════════════════════════
# HELPER: Create default state for graph invocation
# ══════════════════════════════════════════════════════════════════


def create_initial_state(
    message: str,
    channel: str,
    customer_id: str,
    tenant_id: str,
    variant_tier: str,
    customer_tier: str = "free",
    industry: str = "general",
    language: str = "en",
    conversation_id: str = "",
    ticket_id: str = "",
    session_id: str = "",
) -> Dict[str, Any]:
    """
    Create the initial state dict for LangGraph graph invocation.

    Only INPUT group fields are populated; all other groups start
    with empty/default values. Nodes will populate their fields
    as the graph executes.

    Args:
        message: Raw incoming message from customer
        channel: Origin channel (email, sms, voice, chat, api)
        customer_id: Customer identifier
        tenant_id: Company/tenant identifier (BC-001)
        variant_tier: Variant tier (mini, pro, high)
        customer_tier: Customer segment (free, pro, enterprise, vip)
        industry: Industry vertical
        language: Language code
        conversation_id: Conversation ID (empty = new conversation)
        ticket_id: Ticket ID (empty = new ticket)
        session_id: Session ID (empty = new session)

    Returns:
        Dict with all ParwaGraphState fields initialized to defaults.
    """
    from datetime import datetime, timezone

    return {
        # GROUP 1: INPUT
        "message": message,
        "channel": channel,
        "customer_id": customer_id,
        "tenant_id": tenant_id,
        "variant_tier": variant_tier,
        "customer_tier": customer_tier,
        "industry": industry,
        "language": language,
        "conversation_id": conversation_id,
        "ticket_id": ticket_id,
        "session_id": session_id,

        # GROUP 2: PII REDACTION
        "pii_redacted_message": "",
        "pii_entities_found": [],

        # GROUP 3: EMPATHY ENGINE
        "sentiment_score": 0.5,
        "sentiment_intensity": "low",
        "legal_threat_detected": False,
        "urgency": "low",
        "sentiment_trend": "stable",

        # GROUP 4: ROUTER AGENT
        "intent": "general",
        "complexity_score": 0.0,
        "target_agent": "faq",
        "model_tier": "medium",
        "technique_stack": [],
        "signals_extracted": {},

        # GROUP 5: DOMAIN AGENT
        "agent_response": "",
        "agent_confidence": 0.0,
        "proposed_action": "respond",
        "action_type": "informational",
        "agent_reasoning": "",
        "agent_type": "",

        # GROUP 6: MAKER VALIDATOR
        "k_solutions": [],
        "selected_solution": "",
        "red_flag": False,
        "maker_mode": "",
        "k_value_used": 0,
        "fake_threshold": 0.0,
        "maker_decomposition": {},
        "maker_audit_trail": [],

        # GROUP 7: CONTROL SYSTEM
        "approval_decision": "",
        "confidence_breakdown": {},
        "system_mode": "auto",
        "dnd_applies": False,
        "money_rule_triggered": False,
        "vip_rule_triggered": False,
        "approval_timeout_seconds": 300,

        # GROUP 8: DSPY OPTIMIZER
        "prompt_optimized": False,
        "optimized_prompt_version": "",

        # GROUP 9: GUARDRAILS
        "guardrails_passed": False,
        "guardrails_flags": [],
        "guardrails_blocked_reason": "",

        # GROUP 10: CHANNEL DELIVERY
        "delivery_status": "pending",
        "delivery_channel": "",
        "delivery_timestamp": "",
        "delivery_confirmation_id": "",
        "delivery_failure_reason": "",
        "fallback_attempted": False,

        # GROUP 11: STATE UPDATE
        "ticket_created": False,
        "ticket_updated": False,
        "ticket_status": "open",
        "gsd_state_persisted": False,
        "audit_log_written": False,
        "metrics_updated": False,
        "jarvis_feed_pushed": False,
        "fifty_mistake_check": {},

        # GROUP 12: GSD STATE
        "gsd_state": "new",
        "gsd_step": "",
        "context_health": 1.0,
        "context_compressed": False,

        # GROUP 13: METADATA
        "processing_start_time": datetime.now(timezone.utc).isoformat(),
        "model_used": "",
        "tokens_consumed": 0,
        "total_llm_calls": 0,
        "node_execution_log": [],
        "error": "",
        "reward_signal": 0.0,
        "shadow_mode_intercepted": False,

        # GROUP 14: JARVIS AWARENESS
        "current_plan": variant_tier,
        "plan_usage_today": 0.0,
        "subscription_status": "active",
        "days_until_renewal": 30,
        "system_health": "healthy",
        "channel_health": {},
        "active_alerts": [],
        "ticket_volume_today": 0,
        "ticket_volume_avg": 0.0,
        "ticket_volume_spike": False,
        "active_agents": 0,
        "agent_pool_capacity": 5,
        "agent_pool_utilization": 0.0,
        "training_running": False,
        "training_mistake_count": 0,
        "training_model_version": "",
        "drift_status": "none",
        "drift_score": 0.0,
        "quality_score": 0.0,
        "quality_alerts": [],
        "last_5_errors": [],

        # GROUP 15: EMERGENCY CONTROLS
        "ai_paused": False,
        "paused_channels": [],
        "paused_actions": [],
        "emergency_state": "normal",
        "circuit_breaker_trips": 0,
        "global_pause_reason": "",

        # GROUP 16: ANTI-ARBITRAGE
        "arbitrage_risk_score": 0.0,
        "arbitrage_signals": [],
        "active_sessions": 1,
        "plan_cycling_detected": False,

        # GROUP 17: BRAND VOICE & RAG
        "brand_voice_applied": False,
        "brand_voice_profile": {},
        "rag_documents_retrieved": [],
        "rag_reranked": False,
        "kb_documents_used": [],

        # GROUP 18: COLLECTIVE INTELLIGENCE & REWARD
        "collective_patterns_used": [],
        "manager_correction": False,
        "auto_approved_rule_created": False,
        "batch_cluster_id": "",
        "node_outputs": {},
        "errors": [],
    }


# ══════════════════════════════════════════════════════════════════
# FIELD COUNT VALIDATION
# ══════════════════════════════════════════════════════════════════

def _count_fields() -> Dict[str, int]:
    """Count fields per group for documentation/validation."""
    group_counts = {
        "1_INPUT": 11,
        "2_PII_REDACTION": 2,
        "3_EMPATHY_ENGINE": 5,
        "4_ROUTER_AGENT": 6,
        "5_DOMAIN_AGENT": 6,
        "6_MAKER_VALIDATOR": 8,
        "7_CONTROL_SYSTEM": 7,
        "8_DSPY_OPTIMIZER": 2,
        "9_GUARDRAILS": 3,
        "10_CHANNEL_DELIVERY": 6,
        "11_STATE_UPDATE": 8,
        "12_GSD_STATE": 4,
        "13_METADATA": 9,
        "14_JARVIS_AWARENESS": 21,
        "15_EMERGENCY_CONTROLS": 6,
        "16_ANTI_ARBITRAGE": 4,
        "17_BRAND_VOICE_RAG": 5,
        "18_COLLECTIVE_INTEL": 5,  # + node_outputs + errors (shared accumulators)
    }
    return group_counts


def get_total_field_count() -> int:
    """Get total field count across all groups."""
    counts = _count_fields()
    # +2 for node_outputs and errors which are shared accumulators
    return sum(counts.values()) + 2
