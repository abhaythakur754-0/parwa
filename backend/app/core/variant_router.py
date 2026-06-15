"""
Code-Orchestrated Router: Python conditional edges for LangGraph.

UNIFIED ROUTING ARCHITECTURE:
  ALL 3 variants (Mini, Pro, High) now go through the SAME pipeline.
  The difference between variants is ONLY in task permissions — not
  in pipeline depth, intelligence, or technique availability.

  OLD (broken):
    Mini:  classify → generate → format  (skipped 17 nodes!)
    Pro:   classify → extract_signals → technique_select → generate → quality → format
    High:  All 27 nodes

  NEW (unified):
    ALL variants: classify → smart_enrichment → deep_enrichment → extract_signals
                  → technique_select → reasoning_chain → context_enrich
                  → context_compress → generate → crp_compress → clara_quality_gate
                  → quality_retry → confidence_assess → context_health → dedup
                  → strategic_decision → peer_review → auto_action → format

  Inside each node, the variant checks its TASK PERMISSIONS to decide
  what ACTIONS it can take (refund, cancel, etc.), NOT whether to skip
  the node entirely.

Why code routing (FREE):
  - Routing is deterministic: variant_tier + industry + state → next node
  - No LLM needed for "if variant is mini, go to generate"
  - Saves ~$0.001 per query on routing
  - Faster: Python if/else takes microseconds vs LLM call takes seconds
  - Predictable: same input always gives same route

BC-001: company_id first parameter on public methods.
BC-008: Every function has a safe default — never crashes.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.logger import get_logger

logger = get_logger("variant_router")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Valid node names in the pipeline
NODE_PII = "pii_check"
NODE_EMPATHY = "empathy_check"
NODE_EMERGENCY = "emergency_check"
NODE_GSD = "gsd_state"
NODE_CLASSIFY = "classify"
NODE_SMART_ENRICHMENT = "smart_enrichment"
NODE_EXTRACT_SIGNALS = "extract_signals"
NODE_TECHNIQUE_SELECT = "technique_select"
NODE_REASONING_CHAIN = "reasoning_chain"
NODE_CONTEXT_ENRICH = "context_enrich"
NODE_CONTEXT_COMPRESS = "context_compress"
NODE_GENERATE = "generate"
NODE_CRP_COMPRESS = "crp_compress"
NODE_QUALITY_GATE = "clara_quality_gate"
NODE_QUALITY_RETRY = "quality_retry"
NODE_CONFIDENCE_ASSESS = "confidence_assess"
NODE_CONTEXT_HEALTH = "context_health"
NODE_DEDUP = "dedup"
NODE_STRATEGIC_DECISION = "strategic_decision"
NODE_PEER_REVIEW = "peer_review"
NODE_AUTO_ACTION = "auto_action"
NODE_FORMAT = "format"
NODE_END = "__end__"

# Deep enrichment nodes
NODE_COMPLAINT_HANDLER = "complaint_handler"
NODE_RETENTION_NEGOTIATOR = "retention_negotiator"
NODE_BILLING_RESOLVER = "billing_resolver"
NODE_TECH_DIAGNOSTIC = "tech_diagnostic"
NODE_SHIPPING_TRACKER = "shipping_tracker"

# All valid node names
ALL_NODES = [
    NODE_PII, NODE_EMPATHY, NODE_EMERGENCY, NODE_GSD,
    NODE_CLASSIFY, NODE_SMART_ENRICHMENT,
    NODE_COMPLAINT_HANDLER, NODE_RETENTION_NEGOTIATOR,
    NODE_BILLING_RESOLVER, NODE_TECH_DIAGNOSTIC, NODE_SHIPPING_TRACKER,
    NODE_EXTRACT_SIGNALS, NODE_TECHNIQUE_SELECT, NODE_REASONING_CHAIN,
    NODE_CONTEXT_ENRICH, NODE_CONTEXT_COMPRESS,
    NODE_GENERATE, NODE_CRP_COMPRESS, NODE_QUALITY_GATE,
    NODE_QUALITY_RETRY, NODE_CONFIDENCE_ASSESS,
    NODE_CONTEXT_HEALTH, NODE_DEDUP, NODE_STRATEGIC_DECISION,
    NODE_PEER_REVIEW, NODE_AUTO_ACTION, NODE_FORMAT,
]


# ══════════════════════════════════════════════════════════════════
# INTENT → DEEP ENRICHMENT MAPPING
# ══════════════════════════════════════════════════════════════════

# Maps classified intents to deep enrichment nodes
INTENT_DEEP_ENRICHMENT_MAP: Dict[str, str] = {
    # Complaint / Feedback
    "complaint": NODE_COMPLAINT_HANDLER,
    "feedback": NODE_COMPLAINT_HANDLER,
    "review": NODE_COMPLAINT_HANDLER,
    "dissatisfied": NODE_COMPLAINT_HANDLER,
    "unhappy": NODE_COMPLAINT_HANDLER,
    "bad_experience": NODE_COMPLAINT_HANDLER,
    # Cancellation / Retention
    "cancellation": NODE_RETENTION_NEGOTIATOR,
    "cancel": NODE_RETENTION_NEGOTIATOR,
    "unsubscribe": NODE_RETENTION_NEGOTIATOR,
    "leave": NODE_RETENTION_NEGOTIATOR,
    "switch": NODE_RETENTION_NEGOTIATOR,
    # Billing / Payment
    "billing": NODE_BILLING_RESOLVER,
    "payment": NODE_BILLING_RESOLVER,
    "refund": NODE_BILLING_RESOLVER,
    "charge": NODE_BILLING_RESOLVER,
    "invoice": NODE_BILLING_RESOLVER,
    "overcharge": NODE_BILLING_RESOLVER,
    "subscription": NODE_BILLING_RESOLVER,
    # Technical
    "technical": NODE_TECH_DIAGNOSTIC,
    "bug": NODE_TECH_DIAGNOSTIC,
    "error": NODE_TECH_DIAGNOSTIC,
    "not_working": NODE_TECH_DIAGNOSTIC,
    "broken": NODE_TECH_DIAGNOSTIC,
    "crash": NODE_TECH_DIAGNOSTIC,
    "technical_support": NODE_TECH_DIAGNOSTIC,
    "password_reset": NODE_TECH_DIAGNOSTIC,
    "login_issue": NODE_TECH_DIAGNOSTIC,
    "account_access": NODE_TECH_DIAGNOSTIC,
    # Shipping / Order
    "shipping": NODE_SHIPPING_TRACKER,
    "delivery": NODE_SHIPPING_TRACKER,
    "tracking": NODE_SHIPPING_TRACKER,
    "order": NODE_SHIPPING_TRACKER,
    "package": NODE_SHIPPING_TRACKER,
    "late_delivery": NODE_SHIPPING_TRACKER,
    "missing_order": NODE_SHIPPING_TRACKER,
}


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS — UNIFIED (ALL variants same path)
# ══════════════════════════════════════════════════════════════════


def route_after_pii(state: dict) -> str:
    """After PII check → always empathy_check."""
    try:
        return NODE_EMPATHY
    except Exception:
        return NODE_EMPATHY


def route_after_empathy(state: dict) -> str:
    """After empathy check → always emergency_check."""
    try:
        return NODE_EMERGENCY
    except Exception:
        return NODE_EMERGENCY


def route_after_emergency(state: dict) -> str:
    """After emergency check → gsd_state (for all variants now).

    Emergency detection happens in gsd_state routing.
    ALL variants go through gsd_state — this is the conversation
    state machine that tracks the interaction.
    """
    try:
        if state.get("emergency_flag", False):
            return NODE_FORMAT
        return NODE_GSD
    except Exception:
        return NODE_GSD


def route_after_gsd(state: dict) -> str:
    """After GSD state → classify for ALL variants.

    If emergency + escalate → skip to format.
    Otherwise → classify (ALL variants, including Mini).
    """
    try:
        emergency_flag = state.get("emergency_flag", False)
        step_outputs = state.get("step_outputs", {})
        gsd_output = step_outputs.get("gsd_state", {})

        if emergency_flag:
            return NODE_FORMAT

        if isinstance(gsd_output, dict) and gsd_output.get("to_state") == "escalate":
            return NODE_FORMAT

        # ALL variants go to classify now
        return NODE_CLASSIFY
    except Exception:
        return NODE_CLASSIFY


def route_after_classify(state: dict) -> str:
    """After classify → smart_enrichment for ALL variants.

    UNIFIED: ALL variants (Mini, Pro, High) now go through smart_enrichment.
    The enrichment node checks variant_tier to adjust behavior but does
    NOT skip the node. Same intelligence, same pipeline.
    """
    try:
        return NODE_SMART_ENRICHMENT
    except Exception:
        return NODE_SMART_ENRICHMENT


def route_after_smart_enrichment(state: dict) -> str:
    """After smart_enrichment → deep enrichment (intent-specific) OR extract_signals.

    ALL variants go through this routing. The deep enrichment nodes
    check task permissions to decide what actions to take.
    """
    try:
        classification = state.get("classification", {})
        intent = classification.get("intent", "").lower()

        # Check if intent maps to a deep enrichment node
        deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(intent)
        if deep_node:
            return deep_node

        # Also check secondary intents
        secondary_intents = classification.get("secondary_intents", [])
        for sec_intent in secondary_intents:
            deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(sec_intent.lower())
            if deep_node:
                return deep_node

        # No deep enrichment needed → extract signals
        return NODE_EXTRACT_SIGNALS
    except Exception:
        return NODE_EXTRACT_SIGNALS


def route_after_deep_enrichment(state: dict) -> str:
    """After deep enrichment → always extract_signals."""
    try:
        return NODE_EXTRACT_SIGNALS
    except Exception:
        return NODE_EXTRACT_SIGNALS


def route_after_extract_signals(state: dict) -> str:
    """After extract_signals → technique_select for ALL variants.

    UNIFIED: ALL variants now use technique selection and reasoning.
    Same techniques, same intelligence.
    """
    try:
        return NODE_TECHNIQUE_SELECT
    except Exception:
        return NODE_TECHNIQUE_SELECT


def route_after_technique_select(state: dict) -> str:
    """After technique_select → reasoning_chain for ALL variants.

    UNIFIED: ALL variants now execute reasoning techniques.
    """
    try:
        return NODE_REASONING_CHAIN
    except Exception:
        return NODE_REASONING_CHAIN


def route_after_reasoning(state: dict) -> str:
    """After reasoning_chain → context_enrich for ALL variants."""
    try:
        return NODE_CONTEXT_ENRICH
    except Exception:
        return NODE_CONTEXT_ENRICH


def route_after_context_enrich(state: dict) -> str:
    """After context_enrich → context_compress for ALL variants.

    UNIFIED: ALL variants compress context now.
    """
    try:
        return NODE_CONTEXT_COMPRESS
    except Exception:
        return NODE_CONTEXT_COMPRESS


def route_after_context_compress(state: dict) -> str:
    """After context_compress → generate for ALL variants."""
    try:
        return NODE_GENERATE
    except Exception:
        return NODE_GENERATE


def route_after_generate(state: dict) -> str:
    """After generate → crp_compress for ALL variants.

    UNIFIED: ALL variants now go through quality checks.
    """
    try:
        return NODE_CRP_COMPRESS
    except Exception:
        return NODE_CRP_COMPRESS


def route_after_crp(state: dict) -> str:
    """After CRP compress → CLARA quality gate for ALL variants."""
    try:
        return NODE_QUALITY_GATE
    except Exception:
        return NODE_QUALITY_GATE


def route_after_quality_gate(state: dict) -> str:
    """After CLARA quality gate.

    UNIFIED: ALL variants go through quality retry loop now.
    The retry count and threshold are set per-variant in permissions.

    If quality failed and retries remain → quality_retry
    If quality passed or retries exhausted → confidence_assess
    """
    try:
        from app.core.variant_permissions import get_permissions

        variant_tier = state.get("variant_tier", "parwa")
        perms = get_permissions(variant_tier)

        quality_passed = state.get("quality_passed", True)
        retry_count = state.get("quality_retry_count", 0)
        max_retries = perms.max_quality_retries

        if not quality_passed and retry_count < max_retries:
            logger.info(
                "Quality gate failed (retry %d/%d) — regenerating. "
                "variant=%s, company_id=%s",
                retry_count, max_retries,
                variant_tier,
                state.get("company_id", ""),
            )
            return NODE_QUALITY_RETRY

        # Quality passed or retries exhausted
        return NODE_CONFIDENCE_ASSESS
    except Exception:
        return NODE_CONFIDENCE_ASSESS


def route_after_quality_retry(state: dict) -> str:
    """After quality_retry → back to generate for retry."""
    try:
        return NODE_GENERATE
    except Exception:
        return NODE_GENERATE


def route_after_confidence(state: dict) -> str:
    """After confidence_assess → context_health for ALL variants.

    UNIFIED: ALL variants now go through context health checks.
    """
    try:
        return NODE_CONTEXT_HEALTH
    except Exception:
        return NODE_CONTEXT_HEALTH


def route_after_context_health(state: dict) -> str:
    """After context_health → dedup for ALL variants."""
    try:
        return NODE_DEDUP
    except Exception:
        return NODE_DEDUP


def route_after_dedup(state: dict) -> str:
    """After dedup → strategic_decision for ALL variants.

    UNIFIED: ALL variants now go through strategic decision + peer review.
    The nodes adjust behavior per-variant but don't skip.
    """
    try:
        return NODE_STRATEGIC_DECISION
    except Exception:
        return NODE_STRATEGIC_DECISION


def route_after_strategic_decision(state: dict) -> str:
    """After strategic_decision → peer_review for ALL variants."""
    try:
        return NODE_PEER_REVIEW
    except Exception:
        return NODE_PEER_REVIEW


def route_after_peer_review(state: dict) -> str:
    """After peer_review → auto_action for ALL variants."""
    try:
        return NODE_AUTO_ACTION
    except Exception:
        return NODE_AUTO_ACTION


def route_after_auto_action(state: dict) -> str:
    """After auto_action → always format."""
    try:
        return NODE_FORMAT
    except Exception:
        return NODE_FORMAT


# ══════════════════════════════════════════════════════════════════
# UNIFIED PIPELINE STEPS
# ══════════════════════════════════════════════════════════════════


def get_unified_pipeline_steps() -> List[str]:
    """Get the ordered steps for the UNIFIED pipeline.

    ALL variants now use the SAME pipeline:
      pii_check → empathy_check → emergency_check → gsd_state
      → classify → smart_enrichment → [deep_enrichment]
      → extract_signals → technique_select → reasoning_chain
      → context_enrich → context_compress → generate
      → crp_compress → clara_quality_gate → quality_retry
      → confidence_assess → context_health → dedup
      → strategic_decision → peer_review → auto_action → format

    The only difference is the PERMISSIONS inside each node.
    """
    return [
        NODE_PII,
        NODE_EMPATHY,
        NODE_EMERGENCY,
        NODE_GSD,
        NODE_CLASSIFY,
        NODE_SMART_ENRICHMENT,
        # Deep enrichment is conditional based on intent
        NODE_EXTRACT_SIGNALS,
        NODE_TECHNIQUE_SELECT,
        NODE_REASONING_CHAIN,
        NODE_CONTEXT_ENRICH,
        NODE_CONTEXT_COMPRESS,
        NODE_GENERATE,
        NODE_CRP_COMPRESS,
        NODE_QUALITY_GATE,
        NODE_QUALITY_RETRY,
        NODE_CONFIDENCE_ASSESS,
        NODE_CONTEXT_HEALTH,
        NODE_DEDUP,
        NODE_STRATEGIC_DECISION,
        NODE_PEER_REVIEW,
        NODE_AUTO_ACTION,
        NODE_FORMAT,
    ]


# Legacy aliases (backwards compatibility)
get_mini_pipeline_steps = get_unified_pipeline_steps
get_pro_pipeline_steps = get_unified_pipeline_steps
get_high_pipeline_steps = get_unified_pipeline_steps


# ══════════════════════════════════════════════════════════════════
# ROUTER CLASS
# ══════════════════════════════════════════════════════════════════


class VariantRouter:
    """Code-orchestrated router for the UNIFIED Variant Engine.

    ALL variants now follow the SAME pipeline path. The only
    difference is in task permissions inside each node.

    Usage:
        router = VariantRouter()
        builder.add_conditional_edges("pii_check", router.route_after_pii)
        builder.add_conditional_edges("classify", router.route_after_classify)
        # ... etc
    """

    def __init__(self) -> None:
        """Initialize the router."""
        logger.info("VariantRouter initialized — UNIFIED routing for ALL variants (FREE)")

    # Expose routing functions as instance methods
    def route_after_pii(self, state: dict) -> str:
        return route_after_pii(state)

    def route_after_empathy(self, state: dict) -> str:
        return route_after_empathy(state)

    def route_after_emergency(self, state: dict) -> str:
        return route_after_emergency(state)

    def route_after_gsd(self, state: dict) -> str:
        return route_after_gsd(state)

    def route_after_classify(self, state: dict) -> str:
        return route_after_classify(state)

    def route_after_smart_enrichment(self, state: dict) -> str:
        return route_after_smart_enrichment(state)

    def route_after_deep_enrichment(self, state: dict) -> str:
        return route_after_deep_enrichment(state)

    def route_after_extract_signals(self, state: dict) -> str:
        return route_after_extract_signals(state)

    def route_after_technique_select(self, state: dict) -> str:
        return route_after_technique_select(state)

    def route_after_reasoning(self, state: dict) -> str:
        return route_after_reasoning(state)

    def route_after_context_enrich(self, state: dict) -> str:
        return route_after_context_enrich(state)

    def route_after_context_compress(self, state: dict) -> str:
        return route_after_context_compress(state)

    def route_after_generate(self, state: dict) -> str:
        return route_after_generate(state)

    def route_after_crp(self, state: dict) -> str:
        return route_after_crp(state)

    def route_after_quality_gate(self, state: dict) -> str:
        return route_after_quality_gate(state)

    def route_after_quality_retry(self, state: dict) -> str:
        return route_after_quality_retry(state)

    def route_after_confidence(self, state: dict) -> str:
        return route_after_confidence(state)

    def route_after_context_health(self, state: dict) -> str:
        return route_after_context_health(state)

    def route_after_dedup(self, state: dict) -> str:
        return route_after_dedup(state)

    def route_after_strategic_decision(self, state: dict) -> str:
        return route_after_strategic_decision(state)

    def route_after_peer_review(self, state: dict) -> str:
        return route_after_peer_review(state)

    def route_after_auto_action(self, state: dict) -> str:
        return route_after_auto_action(state)

    def get_pipeline_steps(self, variant_tier: str) -> List[str]:
        """Get the pipeline step list — SAME for all variants now."""
        return get_unified_pipeline_steps()

    def get_all_conditional_edges(self) -> dict:
        """Get all conditional edge mappings for building the LangGraph."""
        return {
            NODE_PII: route_after_pii,
            NODE_EMPATHY: route_after_empathy,
            NODE_EMERGENCY: route_after_emergency,
            NODE_GSD: route_after_gsd,
            NODE_CLASSIFY: route_after_classify,
            NODE_SMART_ENRICHMENT: route_after_smart_enrichment,
            NODE_EXTRACT_SIGNALS: route_after_extract_signals,
            NODE_TECHNIQUE_SELECT: route_after_technique_select,
            NODE_REASONING_CHAIN: route_after_reasoning,
            NODE_CONTEXT_ENRICH: route_after_context_enrich,
            NODE_CONTEXT_COMPRESS: route_after_context_compress,
            NODE_GENERATE: route_after_generate,
            NODE_CRP_COMPRESS: route_after_crp,
            NODE_QUALITY_GATE: route_after_quality_gate,
            NODE_QUALITY_RETRY: route_after_quality_retry,
            NODE_CONFIDENCE_ASSESS: route_after_confidence,
            NODE_CONTEXT_HEALTH: route_after_context_health,
            NODE_DEDUP: route_after_dedup,
            NODE_STRATEGIC_DECISION: route_after_strategic_decision,
            NODE_PEER_REVIEW: route_after_peer_review,
            NODE_AUTO_ACTION: route_after_auto_action,
        }
