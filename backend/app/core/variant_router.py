"""
Code-Orchestrated Router: Python conditional edges for LangGraph.

This is the routing brain of the Variant Engine. It decides which node
runs next based on the current state — using PYTHON CODE, not LLM calls.

Why code routing (FREE):
  - Routing is deterministic: variant_tier + industry + state → next node
  - No LLM needed for "if variant is mini, go to generate"
  - Saves ~$0.001 per query on routing (that's 33% of Mini's cost budget)
  - Faster: Python if/else takes microseconds vs LLM call takes seconds
  - Predictable: same input always gives same route

When LLM IS used (inside nodes, not for routing):
  - Classification: understanding what the customer wants
  - Generation: writing the actual response
  - Quality Gate: evaluating response quality
  - Technique Execution: reasoning through complex problems

Architecture:
  The router is a collection of pure functions that take ParwaGraphState
  and return the name of the next node. LangGraph's `add_conditional_edges`
  wires these functions as decision points in the graph.

  Each function is a "routing decision" that happens AFTER a specific node.
  For example, `route_after_classify` decides what comes after classify.

BC-001: company_id first parameter on public methods.
BC-008: Every function has a safe default — never crashes.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

from typing import List

from app.logger import get_logger

logger = get_logger("variant_router")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Valid node names in the pipeline
NODE_PII = "pii_check"
NODE_EMPATHY = "empathy_check"
NODE_EMERGENCY = "emergency_check"
NODE_CLASSIFY = "classify"
NODE_EXTRACT_SIGNALS = "extract_signals"
NODE_TECHNIQUE_SELECT = "technique_select"
NODE_CONTEXT_COMPRESS = "context_compress"
NODE_GENERATE = "generate"
NODE_QUALITY_GATE = "quality_gate"
NODE_CONTEXT_HEALTH = "context_health"
NODE_DEDUP = "dedup"
NODE_FORMAT = "format"
NODE_END = "__end__"

# All valid node names (for validation)
ALL_NODES = [
    NODE_PII,
    NODE_EMPATHY,
    NODE_EMERGENCY,
    NODE_CLASSIFY,
    NODE_EXTRACT_SIGNALS,
    NODE_TECHNIQUE_SELECT,
    NODE_CONTEXT_COMPRESS,
    NODE_GENERATE,
    NODE_QUALITY_GATE,
    NODE_CONTEXT_HEALTH,
    NODE_DEDUP,
    NODE_FORMAT,
]


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def route_after_pii(state: dict) -> str:
    """Decide what comes after PII check.

    Always goes to empathy check. PII is a safety gate that runs
    first regardless of variant tier or industry.

    Returns:
        Next node name.
    """
    try:
        return NODE_EMPATHY
    except Exception:
        return NODE_EMPATHY


def route_after_empathy(state: dict) -> str:
    """Decide what comes after empathy check.

    Goes to emergency check. Empathy flags inform emergency detection.

    Returns:
        Next node name.
    """
    try:
        return NODE_EMERGENCY
    except Exception:
        return NODE_EMERGENCY


def route_after_emergency(state: dict) -> str:
    """Decide what comes after emergency check.

    If emergency detected → skip pipeline, go straight to format
    with an escalation message. Otherwise → proceed to classify.

    This is a CRITICAL safety gate. If a customer threatens legal
    action, mentions safety concerns, or shows signs of crisis,
    we bypass the AI pipeline and route to human escalation.

    Returns:
        Next node name.
    """
    try:
        if state.get("emergency_flag", False):
            # Emergency: skip AI pipeline, format will create
            # a human escalation message
            logger.warning(
                "Emergency detected — bypassing AI pipeline. "
                "emergency_type=%s, company_id=%s",
                state.get("emergency_type", "unknown"),
                state.get("company_id", ""),
            )
            return NODE_FORMAT

        return NODE_CLASSIFY
    except Exception:
        # On error, go to classify (safe default — pipeline continues)
        return NODE_CLASSIFY


def route_after_classify(state: dict) -> str:
    """Decide what comes after classify.

    THE KEY ROUTING DECISION in the Variant Engine.

    Mini:  classify → generate (skip signal extraction and techniques)
    Pro:   classify → extract_signals (go deeper)
    High:  classify → extract_signals (go deepest)

    This is where variant_tier drives pipeline depth. Mini saves
    cost by skipping signal extraction and technique selection —
    it goes straight to generation with just the classification.

    Returns:
        Next node name.
    """
    try:
        variant_tier = state.get("variant_tier", "parwa")

        if variant_tier == "mini_parwa":
            return NODE_GENERATE
        else:
            # Both Pro and High go through signal extraction
            return NODE_EXTRACT_SIGNALS
    except Exception:
        # Safe default: go to generate (simplest path)
        return NODE_GENERATE


def route_after_extract_signals(state: dict) -> str:
    """Decide what comes after extract signals.

    Always goes to technique select. Signals inform technique choice.

    Returns:
        Next node name.
    """
    try:
        return NODE_TECHNIQUE_SELECT
    except Exception:
        return NODE_TECHNIQUE_SELECT


def route_after_technique_select(state: dict) -> str:
    """Decide what comes after technique select.

    Pro:  technique_select → generate (no compression)
    High: technique_select → context_compress (compress before generate)

    Returns:
        Next node name.
    """
    try:
        variant_tier = state.get("variant_tier", "parwa")

        if variant_tier == "parwa_high":
            return NODE_CONTEXT_COMPRESS
        else:
            return NODE_GENERATE
    except Exception:
        return NODE_GENERATE


def route_after_context_compress(state: dict) -> str:
    """Decide what comes after context compression.

    Always goes to generate. Compression optimizes context before
    the generation step.

    Returns:
        Next node name.
    """
    try:
        return NODE_GENERATE
    except Exception:
        return NODE_GENERATE


def route_after_generate(state: dict) -> str:
    """Decide what comes after response generation.

    Mini:  generate → format (skip quality gate)
    Pro:   generate → quality_gate (check quality)
    High:  generate → quality_gate (check quality)

    Mini skips quality gate to save cost and latency. Pro and High
    verify response quality before delivering to customer.

    Returns:
        Next node name.
    """
    try:
        variant_tier = state.get("variant_tier", "parwa")

        if variant_tier == "mini_parwa":
            return NODE_FORMAT
        else:
            return NODE_QUALITY_GATE
    except Exception:
        return NODE_FORMAT


def route_after_quality_gate(state: dict) -> str:
    """Decide what comes after quality gate.

    If quality failed and retry budget remains → regenerate
    If quality passed or retries exhausted → proceed

    Pro:   quality_gate → format
    High:  quality_gate → context_health

    Returns:
        Next node name.
    """
    try:
        variant_tier = state.get("variant_tier", "parwa")

        # Check if quality gate failed and we should retry
        quality_passed = state.get("quality_passed", True)
        retry_count = state.get("quality_retry_count", 0)
        max_retries = 1  # Only retry once to control cost

        if not quality_passed and retry_count < max_retries:
            logger.info(
                "Quality gate failed (retry %d/%d) — regenerating. "
                "company_id=%s, variant=%s",
                retry_count, max_retries,
                state.get("company_id", ""),
                variant_tier,
            )
            return NODE_GENERATE

        # Quality passed or retries exhausted
        if variant_tier == "parwa_high":
            return NODE_CONTEXT_HEALTH
        else:
            return NODE_FORMAT
    except Exception:
        return NODE_FORMAT


def route_after_context_health(state: dict) -> str:
    """Decide what comes after context health check.

    Always goes to dedup. Context health is informational —
    it logs health state but doesn't change the pipeline flow.

    Returns:
        Next node name.
    """
    try:
        return NODE_DEDUP
    except Exception:
        return NODE_DEDUP


def route_after_dedup(state: dict) -> str:
    """Decide what comes after dedup check.

    Always goes to format. Dedup flags duplicates but the format
    node handles what to do with that information.

    Returns:
        Next node name.
    """
    try:
        return NODE_FORMAT
    except Exception:
        return NODE_FORMAT


# ══════════════════════════════════════════════════════════════════
# PIPELINE DEFINITIONS
# ══════════════════════════════════════════════════════════════════


def get_mini_pipeline_steps() -> List[str]:
    """Get the ordered steps for Mini Parwa pipeline.

    Mini = 5 steps (3 core + 2 safety):
      pii → empathy → emergency → classify → generate → format

    Cost target: ~$0.003/query
    Latency target: <3s
    """
    return [
        NODE_PII,
        NODE_EMPATHY,
        NODE_EMERGENCY,
        NODE_CLASSIFY,
        NODE_GENERATE,
        NODE_FORMAT,
    ]


def get_pro_pipeline_steps() -> List[str]:
    """Get the ordered steps for Pro Parwa pipeline.

    Pro = 8 steps (Mini's 5 + 3 deeper):
      pii → empathy → emergency → classify → extract_signals →
      technique_select → generate → quality_gate → format

    Cost target: ~$0.008/query
    Latency target: <8s
    """
    return [
        NODE_PII,
        NODE_EMPATHY,
        NODE_EMERGENCY,
        NODE_CLASSIFY,
        NODE_EXTRACT_SIGNALS,
        NODE_TECHNIQUE_SELECT,
        NODE_GENERATE,
        NODE_QUALITY_GATE,
        NODE_FORMAT,
    ]


def get_high_pipeline_steps() -> List[str]:
    """Get the ordered steps for High Parwa pipeline.

    High = 11 steps (Pro's 8 + 3 deepest):
      pii → empathy → emergency → classify → extract_signals →
      technique_select → context_compress → generate → quality_gate →
      context_health → dedup → format

    Cost target: ~$0.015/query
    Latency target: <15s
    """
    return [
        NODE_PII,
        NODE_EMPATHY,
        NODE_EMERGENCY,
        NODE_CLASSIFY,
        NODE_EXTRACT_SIGNALS,
        NODE_TECHNIQUE_SELECT,
        NODE_CONTEXT_COMPRESS,
        NODE_GENERATE,
        NODE_QUALITY_GATE,
        NODE_CONTEXT_HEALTH,
        NODE_DEDUP,
        NODE_FORMAT,
    ]


# ══════════════════════════════════════════════════════════════════
# ROUTER CLASS
# ══════════════════════════════════════════════════════════════════


class VariantRouter:
    """Code-orchestrated router for the Variant Engine.

    Provides the routing functions and pipeline definitions that
    LangGraph uses to build conditional edges in the StateGraph.

    Usage:
        router = VariantRouter()

        # Add conditional edges to LangGraph builder
        builder.add_conditional_edges("pii_check", router.route_after_pii)
        builder.add_conditional_edges("classify", router.route_after_classify)
        builder.add_conditional_edges("generate", router.route_after_generate)
        # ... etc

    All routing is FREE — pure Python code, no LLM calls.
    """

    def __init__(self) -> None:
        """Initialize the router."""
        logger.info("VariantRouter initialized — code-orchestrated routing (FREE)")

    # Expose routing functions as instance methods for convenience
    # (can also be used as standalone functions)

    def route_after_pii(self, state: dict) -> str:
        return route_after_pii(state)

    def route_after_empathy(self, state: dict) -> str:
        return route_after_empathy(state)

    def route_after_emergency(self, state: dict) -> str:
        return route_after_emergency(state)

    def route_after_classify(self, state: dict) -> str:
        return route_after_classify(state)

    def route_after_extract_signals(self, state: dict) -> str:
        return route_after_extract_signals(state)

    def route_after_technique_select(self, state: dict) -> str:
        return route_after_technique_select(state)

    def route_after_context_compress(self, state: dict) -> str:
        return route_after_context_compress(state)

    def route_after_generate(self, state: dict) -> str:
        return route_after_generate(state)

    def route_after_quality_gate(self, state: dict) -> str:
        return route_after_quality_gate(state)

    def route_after_context_health(self, state: dict) -> str:
        return route_after_context_health(state)

    def route_after_dedup(self, state: dict) -> str:
        return route_after_dedup(state)

    def get_pipeline_steps(self, variant_tier: str) -> List[str]:
        """Get the pipeline step list for a variant tier.

        Args:
            variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

        Returns:
            Ordered list of node names for the pipeline.
        """
        pipelines = {
            "mini_parwa": get_mini_pipeline_steps,
            "parwa": get_pro_pipeline_steps,
            "parwa_high": get_high_pipeline_steps,
        }
        builder = pipelines.get(variant_tier, get_pro_pipeline_steps)
        return builder()

    def get_all_conditional_edges(self) -> dict:
        """Get all conditional edge mappings for building the LangGraph.

        Returns:
            Dict mapping source node → routing function.
            Pass each entry to builder.add_conditional_edges().
        """
        return {
            NODE_PII: route_after_pii,
            NODE_EMPATHY: route_after_empathy,
            NODE_EMERGENCY: route_after_emergency,
            NODE_CLASSIFY: route_after_classify,
            NODE_EXTRACT_SIGNALS: route_after_extract_signals,
            NODE_TECHNIQUE_SELECT: route_after_technique_select,
            NODE_CONTEXT_COMPRESS: route_after_context_compress,
            NODE_GENERATE: route_after_generate,
            NODE_QUALITY_GATE: route_after_quality_gate,
            NODE_CONTEXT_HEALTH: route_after_context_health,
            NODE_DEDUP: route_after_dedup,
            # FORMAT always goes to END — no conditional edge needed
        }
