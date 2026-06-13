"""PARWA LangGraph pipeline — The main StateGraph definition.

This is the SKELETON of the entire PARWA system. LangGraph is the traffic cop
that routes tickets between 30 nodes, 6 agents, and handles conditional branching
and quality loop-backs. LangGraph ROUTES — it does NOT think.

P1 ADDITIONS:
- RED_TEAM node: Adversarial validation after reverse thinker
- AGENT_DEBATE node: Advocate vs Skeptic debate after tree of thoughts
- Both only activate for complex/critical tickets

P2 ADDITIONS:
- SITUATION_MODEL node: Builds holistic context model after knowledge pipeline
- POLICY_GUARD node: Enforces policy constraints on reasoning and actions
- Confidence-gated escalation: Enhanced escalation with confidence signals

P3 ADDITIONS:
- META_REASONER node: Reasons about the pipeline's own reasoning quality
- CONVERSATIONAL_REPAIR node: Detects and fixes broken responses
- Feed-forward signals: Upstream nodes predict downstream needs
- Closed feedback loop: Feedback adjusts behavior within the same ticket

Pipeline flow:
  INGEST → INTENT_CLASSIFIER → SENTIMENT_ANALYZER
      → (branch) ESCALATION_DECISION / FAQ_MATCHER
      → KB_RETRIEVER → CONTEXT_MANAGER → INTEGRATION_LOOKUP
      → SITUATION_MODEL → POLICY_GUARD  [P2: context synthesis + policy constraints]
      → REASONING_ENGINE
      → (simple) ACTION_PLANNER
      → (complex) REVERSE_THINKER → RED_TEAM → TREE_OF_THOUGHTS → AGENT_DEBATE
                   → STRATEGY_PLANNER → ACTION_PLANNER
      → ACTION_EXECUTOR → ACTION_VERIFIER
      → (parallel) PROACTIVE_CHECKER / PREDICTION_ENGINE / FEEDBACK_LOOP
      → PII_COMPLIANCE_GUARD → AUDIT_LOGGER → QUALITY_SCORER
      → META_REASONER  [P3: evaluates reasoning structure]
      → (if score >= 80) RESPONSE_FORMATTER → CONVERSATIONAL_REPAIR → END  [P3: last defense]
      → (if score < 80) loop back to REASONING_ENGINE
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Annotated, AsyncGenerator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from parwa.state import validate_state
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.graph")


# Keys that should be APPENDED (concatenated) across nodes
# All other list keys use REPLACE semantics (node returns the full list)
_APPEND_KEYS = frozenset({
    "pipeline_errors",     # errors accumulate across nodes
    "active_frameworks",   # frameworks activated accumulate (nodes return ONLY new items)
    "evidence_chain",      # P0: evidence entries accumulate across nodes (APPEND semantics)
    "feed_forward_signals", # P3: feed-forward signals accumulate across nodes
})
# NOTE: reasoning_chain uses REPLACE semantics — each reasoning engine run
# produces a complete chain that replaces the previous one. This avoids
# duplication on loop-back and keeps the chain meaningful.


def _merge_dicts(left: dict, right: dict) -> dict:
    """Reducer function that merges right dict into left dict.

    For keys in _APPEND_KEYS, lists are concatenated instead of replaced.
    All other keys use standard replacement semantics.
    This ensures pipeline_errors accumulate without duplication,
    while nodes that manage their own lists (context_history, audit_log)
    can return the complete list without double-counting.
    """
    merged = dict(left)
    for k, v in right.items():
        if k in _APPEND_KEYS and isinstance(v, list) and isinstance(merged.get(k), list):
            merged[k] = merged[k] + v
        else:
            merged[k] = v
    return merged


# State type with merge reducer — each node returns a partial dict,
# and LangGraph merges it into the accumulated state
GraphState = Annotated[dict, _merge_dicts]

from parwa.nodes.ingest import ingest
from parwa.nodes.intent_classifier import intent_classifier
from parwa.nodes.sentiment_analyzer import sentiment_analyzer
from parwa.nodes.escalation_decision import escalation_decision
from parwa.nodes.faq_matcher import faq_matcher
from parwa.nodes.kb_retriever import kb_retriever
from parwa.nodes.context_manager import context_manager
from parwa.nodes.integration_lookup import integration_lookup
from parwa.nodes.situation_model import situation_model
from parwa.nodes.policy_guard import policy_guard
from parwa.nodes.reasoning_engine import reasoning_engine
from parwa.nodes.reverse_thinker import reverse_thinker
from parwa.nodes.red_team import red_team
from parwa.nodes.tree_of_thoughts import tree_of_thoughts
from parwa.nodes.agent_debate import agent_debate
from parwa.nodes.strategy_planner import strategy_planner
from parwa.nodes.action_planner import action_planner
from parwa.nodes.action_executor import action_executor
from parwa.nodes.action_verifier import action_verifier
from parwa.nodes.proactive_checker import proactive_checker
from parwa.nodes.prediction_engine import prediction_engine
from parwa.nodes.feedback_loop import feedback_loop
from parwa.nodes.pii_compliance_guard import pii_compliance_guard
from parwa.nodes.audit_logger import audit_logger
from parwa.nodes.quality_scorer import quality_scorer
from parwa.nodes.meta_reasoner import meta_reasoner
from parwa.nodes.response_formatter import response_formatter
from parwa.nodes.conversational_repair import conversational_repair


# ─── Conditional Edge Functions ──────────────────────────────────────────────────

def _after_sentiment(state: dict[str, Any]) -> str:
    """Route after sentiment analysis.

    Check escalation for:
    - Angry + complex/critical
    - Angry + high urgency
    - Messages with legal/escalation keywords
    Otherwise → FAQ matcher
    """
    sentiment = state.get("sentiment", "neutral")
    complexity = state.get("complexity", "simple")
    urgency = state.get("sentiment_urgency", 0.0)

    # Check message content for escalation triggers
    raw_message = (state.get("raw_message", "") or "").lower()
    escalation_keywords = ["attorney", "lawyer", "lawsuit", "legal action", "court",
                          "fraud", "speak to manager", "supervisor", "human agent",
                          "third email", "nobody has responded", "still not resolved"]
    # Note: "sue" checked separately with word boundary to avoid matching "issue"
    import re
    has_escalation_keyword = (
        any(kw in raw_message for kw in escalation_keywords)
        or bool(re.search(r'\bsue\b', raw_message))
    )

    if has_escalation_keyword:
        logger.info("route: sentiment→escalation (escalation keyword detected)")
        return "escalation_decision"

    # Angry + complex/critical → always escalate
    if sentiment in ("angry", "frustrated") and complexity in ("complex", "critical"):
        logger.info("route: sentiment→escalation (sentiment=%s, complexity=%s)", sentiment, complexity)
        return "escalation_decision"

    # Angry + high urgency → escalate even without critical complexity
    if sentiment == "angry" and isinstance(urgency, (int, float)) and urgency >= 0.8:
        logger.info("route: sentiment→escalation (angry, urgency=%.2f)", urgency)
        return "escalation_decision"

    logger.debug("route: sentiment→faq_matcher (sentiment=%s)", sentiment)
    return "faq_matcher"


def _after_escalation(state: dict[str, Any]) -> str:
    """Route after escalation decision.

    Should escalate → go through situation_model + policy_guard first,
    then to compliance (quick exit for human-handled tickets).
    P2 FIX: Even escalated tickets benefit from situation modeling and
    policy-aware reasoning before being handed to humans.
    Should not escalate → continue to FAQ matcher
    """
    if state.get("should_escalate", False):
        logger.info("route: escalation→situation_model (escalated, but still needs P2 context)")
        return "situation_model"
    logger.debug("route: escalation→faq_matcher (not escalated)")
    return "faq_matcher"


def _after_faq_matcher(state: dict[str, Any]) -> str:
    """Route after FAQ matching.

    High confidence FAQ match → skip to reasoning (FAQ has the context)
    No match → search KB

    P2: Both paths now go through situation_model before reasoning.
    """
    faq_match = state.get("faq_match")
    if faq_match and faq_match.get("relevance_score", 0) > 0.8:
        logger.info("route: faq→reasoning (high relevance=%.2f)", faq_match.get("relevance_score", 0))
        return "reasoning_engine"
    logger.debug("route: faq→kb_retriever (no high match)")
    return "kb_retriever"


def _after_policy_guard(state: dict[str, Any]) -> str:
    """Route after policy guard.

    P2: If the ticket is escalated, skip reasoning and go straight to
    compliance (the human agent gets the situation model + policy context
    in the response). Non-escalated tickets continue to reasoning.
    """
    if state.get("should_escalate", False):
        logger.info("route: policy_guard→pii_compliance_guard (escalated, P2 context enriched)")
        return "pii_compliance_guard"
    logger.debug("route: policy_guard→reasoning_engine")
    return "reasoning_engine"


def _after_reasoning(state: dict[str, Any]) -> str:
    """Route after reasoning engine.

    Simple problem → skip advanced reasoning, go to action planner
    Complex problem → explore multiple paths (ToT, Reverse, Strategy)
    After a loop-back → always go to action_planner (already reasoned once)
    """
    loop_count = state.get("loop_count", 0)
    if loop_count > 0:
        logger.info("route: reasoning→action_planner (loop_back, count=%d)", loop_count)
        return "action_planner"

    complexity = state.get("complexity", "simple")
    if complexity in ("simple",):
        logger.debug("route: reasoning→action_planner (simple)")
        return "action_planner"
    logger.debug("route: reasoning→reverse_thinker (complex)")
    return "reverse_thinker"


def _after_reverse_thinker(state: dict[str, Any]) -> str:
    """After reverse thinking, go to RED_TEAM for adversarial validation.

    P1: Red Team attacks the reasoning to find flaws that self-validation missed.
    This catches issues like hallucinated claims, logical fallacies, and
    confirmation bias that reverse_thinker (which validates forward) doesn't catch.
    """
    return "red_team"


def _after_tree_of_thoughts(state: dict[str, Any]) -> str:
    """After tree of thoughts, go to AGENT_DEBATE for advocate vs skeptic.

    P1: Agent Debate creates a structured argument between advocate and skeptic
    before deciding on strategy. This surfaces evidence that single-path
    analysis misses and catches overconfident conclusions.
    """
    return "agent_debate"


def _after_strategy_planner(state: dict[str, Any]) -> str:
    """After strategy planner, go to action planner."""
    return "action_planner"


def _after_action_verifier(state: dict[str, Any]) -> str:
    """Route after action verification.

    Failed + can loop → back to reasoning engine
    Passed → proactive checker
    """
    if state.get("should_loop_back", False):
        logger.info("route: verifier→reasoning (loop_back)")
        return "reasoning_engine"
    return "proactive_checker"


def _after_quality_scorer(state: dict[str, Any]) -> str:
    """Route after quality scoring.

    P3: Now routes to meta_reasoner instead of directly to response formatter.
    This function is kept for backwards compatibility but is no longer used
    as a conditional edge (quality_scorer now always goes to meta_reasoner).
    """
    quality_score = state.get("quality_score", 0.0)
    should_loop = state.get("should_loop_back", False)

    if quality_score >= 80:
        logger.info("route: quality→response_formatter (score=%.1f)", quality_score)
        return "response_formatter"
    if should_loop:
        logger.info("route: quality→reasoning (score=%.1f, loop_back)", quality_score)
        return "reasoning_engine"
    logger.warning("route: quality→response_formatter (score=%.1f, max_loops reached)", quality_score)
    return "response_formatter"


def _after_meta_reasoner(state: dict[str, Any]) -> str:
    """Route after meta-reasoning.

    P3: Meta-reasoner evaluates the pipeline structure and may adjust
    the quality score. It then decides whether to proceed to response
    formatting or loop back for re-reasoning.

    The meta-reasoner can:
    - Adjust quality score based on structural issues
    - Force a loop-back if it finds serious problems
    - Override quality score if it finds the score is miscalibrated
    """
    meta = state.get("meta_reasoning", {})
    if not isinstance(meta, dict):
        meta = {}

    quality_score = state.get("quality_score", 0.0)
    should_loop = state.get("should_loop_back", False)
    verdict = meta.get("verdict", "acceptable")
    adjustment = meta.get("quality_adjustment", 0)

    # Apply meta-reasoning adjustment to effective score
    effective_score = max(0.0, quality_score + adjustment)

    # If meta-reasoner verdict is "poor", always loop back (if loops remain)
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)

    if verdict == "poor" and loop_count < max_loops:
        logger.info(
            "route: meta→reasoning (verdict=%s, adjustment=%+.0f, score=%.1f→%.1f)",
            verdict, adjustment, quality_score, effective_score,
        )
        return "reasoning_engine"

    if effective_score >= 80:
        logger.info(
            "route: meta→response_formatter (score=%.1f→%.1f, verdict=%s)",
            quality_score, effective_score, verdict,
        )
        return "response_formatter"

    if should_loop and loop_count < max_loops:
        logger.info(
            "route: meta→reasoning (score=%.1f→%.1f, loop_back, verdict=%s)",
            quality_score, effective_score, verdict,
        )
        return "reasoning_engine"

    # Max loops reached or score is borderline — proceed with best effort
    logger.warning(
        "route: meta→response_formatter (score=%.1f→%.1f, verdict=%s, best effort)",
        quality_score, effective_score, verdict,
    )
    return "response_formatter"


# ─── Loop-back handler ────────────────────────────────────────────────────────────

@safe_node("LOOP_BACK_HANDLER", fallback={"loop_count": 1, "should_loop_back": False})
async def _handle_loop_back(state: dict[str, Any]) -> dict[str, Any]:
    """Increment loop counter when looping back to reasoning (async)."""
    loop_count = state.get("loop_count", 0)
    # Guard: ensure loop_count is numeric
    if not isinstance(loop_count, (int, float)):
        loop_count = 0
    loop_count = int(loop_count)
    logger.info("loop_back_handler: incrementing loop_count %d→%d", loop_count, loop_count + 1)
    return {"loop_count": loop_count + 1, "should_loop_back": False}


# ─── Build the Graph ──────────────────────────────────────────────────────────────

def build_parwa_graph(
    *,
    use_checkpointer: bool = True,
    interrupt_before_action: bool = False,
) -> StateGraph:
    """Build the complete PARWA LangGraph with all 22 nodes and conditional edges.

    Args:
        use_checkpointer: Enable MemorySaver for crash recovery (default True).
        interrupt_before_action: Pause before action_executor for human approval
            (useful for Mini PARWA recommendations in production).

    Returns:
        A compiled StateGraph ready for execution.
    """
    graph = StateGraph(GraphState)

    # ─── Add all 25 nodes (22 original + 3 P1 additions) ───────────────
    # Router Agent nodes
    graph.add_node("ingest", ingest)
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("sentiment_analyzer", sentiment_analyzer)
    graph.add_node("escalation_decision", escalation_decision)

    # Knowledge Agent nodes
    graph.add_node("faq_matcher", faq_matcher)
    graph.add_node("kb_retriever", kb_retriever)
    graph.add_node("context_manager", context_manager)
    graph.add_node("integration_lookup", integration_lookup)

    # P2: Context synthesis + policy enforcement
    graph.add_node("situation_model", situation_model)  # P2: Holistic context synthesis
    graph.add_node("policy_guard", policy_guard)  # P2: Policy constraint enforcement

    # Reasoning Agent nodes
    graph.add_node("reasoning_engine", reasoning_engine)
    graph.add_node("reverse_thinker", reverse_thinker)
    graph.add_node("red_team", red_team)  # P1: Adversarial validation
    graph.add_node("tree_of_thoughts", tree_of_thoughts)
    graph.add_node("agent_debate", agent_debate)  # P1: Advocate vs Skeptic debate
    graph.add_node("strategy_planner", strategy_planner)

    # Action Agent nodes
    graph.add_node("action_planner", action_planner)
    graph.add_node("action_executor", action_executor)
    graph.add_node("action_verifier", action_verifier)

    # Proactive Agent nodes
    graph.add_node("proactive_checker", proactive_checker)
    graph.add_node("prediction_engine", prediction_engine)
    graph.add_node("feedback_loop", feedback_loop)

    # Compliance Agent nodes
    graph.add_node("pii_compliance_guard", pii_compliance_guard)
    graph.add_node("audit_logger", audit_logger)
    graph.add_node("quality_scorer", quality_scorer)
    graph.add_node("meta_reasoner", meta_reasoner)  # P3: Meta-reasoning about pipeline quality
    graph.add_node("response_formatter", response_formatter)
    graph.add_node("conversational_repair", conversational_repair)  # P3: Last line of defense

    # Loop-back handler node
    graph.add_node("loop_back_handler", _handle_loop_back)

    # ─── Set entry point ─────────────────────────────────────────────────────
    graph.set_entry_point("ingest")

    # ─── Add edges (linear + conditional) ────────────────────────────────────

    # Linear pipeline: INGEST → INTENT_CLASSIFIER → SENTIMENT_ANALYZER
    graph.add_edge("ingest", "intent_classifier")
    graph.add_edge("intent_classifier", "sentiment_analyzer")

    # Conditional: After SENTIMENT → escalation or FAQ
    graph.add_conditional_edges(
        "sentiment_analyzer",
        _after_sentiment,
        {
            "escalation_decision": "escalation_decision",
            "faq_matcher": "faq_matcher",
        },
    )

    # Conditional: After ESCALATION → P2 context (situation_model) or continue
    # P2 FIX: Escalated tickets now go through situation_model + policy_guard
    # before compliance, so the human agent gets a full situation brief
    graph.add_conditional_edges(
        "escalation_decision",
        _after_escalation,
        {
            "situation_model": "situation_model",
            "faq_matcher": "faq_matcher",
        },
    )

    # Conditional: After FAQ → reasoning or KB
    # P2: High-relevance FAQ match goes through situation_model before reasoning
    # (situation_model needs to run regardless of FAQ match quality)
    graph.add_conditional_edges(
        "faq_matcher",
        _after_faq_matcher,
        {
            "reasoning_engine": "situation_model",  # P2: route through situation model
            "kb_retriever": "kb_retriever",
        },
    )

    # Knowledge pipeline: KB → CONTEXT → INTEGRATION → SITUATION_MODEL → POLICY_GUARD → REASONING
    # P2: Situation Model and Policy Guard sit between knowledge and reasoning
    graph.add_edge("kb_retriever", "context_manager")
    graph.add_edge("context_manager", "integration_lookup")
    graph.add_edge("integration_lookup", "situation_model")  # P2: synthesize context first
    graph.add_edge("situation_model", "policy_guard")  # P2: then check policies
    # Conditional: After POLICY_GUARD → reasoning or compliance (escalated)
    # P2: Escalated tickets skip reasoning but still get situation+policy context
    graph.add_conditional_edges(
        "policy_guard",
        _after_policy_guard,
        {
            "reasoning_engine": "reasoning_engine",
            "pii_compliance_guard": "pii_compliance_guard",
        },
    )

    # Conditional: After REASONING → simple (action) or complex (advanced reasoning)
    graph.add_conditional_edges(
        "reasoning_engine",
        _after_reasoning,
        {
            "action_planner": "action_planner",
            "reverse_thinker": "reverse_thinker",
        },
    )

    # Advanced reasoning chain (P1: with RED_TEAM and AGENT_DEBATE):
    # REVERSE_THINKER → RED_TEAM → TREE_OF_THOUGHTS → AGENT_DEBATE → STRATEGY → ACTION_PLANNER
    #
    # P1 changes:
    # - RED_TEAM goes after REVERSE_THINKER to attack the validated reasoning
    # - AGENT_DEBATE goes after TREE_OF_THOUGHTS to debate before strategizing
    # - If RED_TEAM finds critical flaws, it sets should_loop_back=True
    # - If AGENT_DEBATE skeptic wins, it sets should_loop_back=True
    graph.add_edge("reverse_thinker", "red_team")
    graph.add_edge("red_team", "tree_of_thoughts")
    graph.add_edge("tree_of_thoughts", "agent_debate")
    graph.add_edge("agent_debate", "strategy_planner")
    graph.add_edge("strategy_planner", "action_planner")

    # Action pipeline: PLANNER → EXECUTOR → VERIFIER
    graph.add_edge("action_planner", "action_executor")
    graph.add_edge("action_executor", "action_verifier")

    # Conditional: After VERIFIER → loop back or proactive
    graph.add_conditional_edges(
        "action_verifier",
        _after_action_verifier,
        {
            "reasoning_engine": "loop_back_handler",
            "proactive_checker": "proactive_checker",
        },
    )

    # Loop-back handler → reasoning engine
    graph.add_edge("loop_back_handler", "reasoning_engine")

    # Proactive pipeline: CHECKER → PREDICTION → FEEDBACK (sequential)
    graph.add_edge("proactive_checker", "prediction_engine")
    graph.add_edge("prediction_engine", "feedback_loop")
    graph.add_edge("feedback_loop", "pii_compliance_guard")

    # Compliance pipeline: PII → AUDIT → QUALITY → META_REASONER
    graph.add_edge("pii_compliance_guard", "audit_logger")
    graph.add_edge("audit_logger", "quality_scorer")
    graph.add_edge("quality_scorer", "meta_reasoner")  # P3: meta-reason after quality scoring

    # Conditional: After META_REASONER → format or loop back
    # P3: Meta-reasoner may adjust quality score before routing
    graph.add_conditional_edges(
        "meta_reasoner",
        _after_meta_reasoner,
        {
            "response_formatter": "response_formatter",
            "reasoning_engine": "loop_back_handler",
        },
    )

    # Response pipeline: FORMATTER → CONVERSATIONAL_REPAIR → END
    # P3: Last line of defense catches broken responses
    graph.add_edge("response_formatter", "conversational_repair")
    graph.add_edge("conversational_repair", END)

    # ─── Compile with optional features ──────────────────────────────────────
    checkpointer = MemorySaver() if use_checkpointer else None

    # Human-in-the-loop: interrupt before action_executor for Mini variant
    interrupt_nodes = []
    if interrupt_before_action:
        interrupt_nodes = ["action_executor"]

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes if interrupt_nodes else None,
    )

    logger.info(
        "build_parwa_graph: compiled graph with 30 nodes (22 original + 3 P1: red_team, agent_debate, loop_back_handler + 2 P2: situation_model, policy_guard + 3 P3: meta_reasoner, conversational_repair, feed_forward), checkpointer=%s, interrupt=%s",
        use_checkpointer, interrupt_before_action,
    )

    return compiled


# ─── Convenience functions ─────────────────────────────────────────────────────────

# Compiled graph singleton (thread-safe)
_compiled_graph = None
_graph_lock = threading.Lock()


def get_parwa_graph(
    *,
    use_checkpointer: bool = True,
    interrupt_before_action: bool = False,
):
    """Get or create the compiled PARWA graph singleton (thread-safe).

    Uses a lock to prevent race conditions when multiple threads
    try to create the graph simultaneously.

    Args:
        use_checkpointer: Enable MemorySaver for crash recovery.
        interrupt_before_action: Pause before action for human approval.

    Returns:
        A compiled StateGraph.
    """
    global _compiled_graph
    if _compiled_graph is None:
        with _graph_lock:
            # Double-check after acquiring lock
            if _compiled_graph is None:
                _compiled_graph = build_parwa_graph(
                    use_checkpointer=use_checkpointer,
                    interrupt_before_action=interrupt_before_action,
                )
    return _compiled_graph


def reset_parwa_graph() -> None:
    """Reset the compiled graph singleton (useful for testing with different configs)."""
    global _compiled_graph
    _compiled_graph = None


def _make_thread_config(thread_id: str | None = None) -> dict:
    """Create a LangGraph config dict with thread_id for checkpointing.

    Args:
        thread_id: Optional thread ID (auto-generated if None).

    Returns:
        Config dict with configurable.thread_id set.
    """
    if thread_id:
        return {"configurable": {"thread_id": thread_id}}
    return {"configurable": {"thread_id": f"ticket-{uuid.uuid4().hex[:8]}"}}


def process_ticket(
    raw_message: str,
    customer_id: str = "",
    channel: str = "email",
    variant: str = "parwa",
    *,
    thread_id: str | None = None,
    interrupt_before_action: bool = False,
) -> dict[str, Any]:
    """Process a single ticket through the full PARWA pipeline (sync wrapper).

    Since all PARWA nodes are async, this runs aprocess_ticket in an event loop.
    For production async code, prefer using aprocess_ticket directly.

    Args:
        raw_message: The customer's message
        customer_id: Customer identifier
        channel: Communication channel (email, chat, social, voice)
        variant: PARWA variant (mini, parwa, high)
        thread_id: Optional thread ID for checkpointing (auto-generated if None)
        interrupt_before_action: Pause before action for human approval

    Returns:
        The final ticket state after processing through all 22 nodes
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    coro = aprocess_ticket(
        raw_message, customer_id, channel, variant,
        thread_id=thread_id,
        interrupt_before_action=interrupt_before_action,
    )

    if loop and loop.is_running():
        # We're inside an existing event loop — create a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        # No event loop running — safe to use asyncio.run
        return asyncio.run(coro)


async def aprocess_ticket(
    raw_message: str,
    customer_id: str = "",
    channel: str = "email",
    variant: str = "parwa",
    *,
    thread_id: str | None = None,
    interrupt_before_action: bool = False,
) -> dict[str, Any]:
    """Process a single ticket through the full PARWA pipeline (async).

    Non-blocking version of process_ticket. Uses LangGraph's ainvoke()
    to run all 22 async nodes without blocking the event loop.
    This is the recommended way to process tickets in production.

    Args:
        raw_message: The customer's message
        customer_id: Customer identifier
        channel: Communication channel (email, chat, social, voice)
        variant: PARWA variant (mini, parwa, high)
        thread_id: Optional thread ID for checkpointing (auto-generated if None)
        interrupt_before_action: Pause before action for human approval

    Returns:
        The final ticket state after processing through all 22 nodes
    """
    graph = get_parwa_graph(interrupt_before_action=interrupt_before_action)

    # Validate input
    if not raw_message or not isinstance(raw_message, str):
        return {
            "error": "raw_message is required and must be a string",
            "final_response": "Error: No message provided.",
        }

    if variant not in ("mini", "parwa", "high"):
        logger.warning("aprocess_ticket: invalid variant '%s', defaulting to 'parwa'", variant)
        variant = "parwa"

    initial_state = {
        "raw_message": raw_message,
        "customer_id": customer_id,
        "channel": channel,
        "variant": variant,
        "max_loops": 0,  # Disable quality loop-back for faster execution
    }

    # Validate initial state
    is_valid, issues = validate_state(initial_state)
    if not is_valid:
        logger.warning("aprocess_ticket: input validation issues: %s", issues)

    config = _make_thread_config(thread_id)

    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error("aprocess_ticket: graph.ainvoke failed: %s", exc, exc_info=True)
        return {
            "error": f"Pipeline execution failed: {exc}",
            "final_response": "We apologize, but an internal error occurred while processing your request. A human agent will follow up shortly.",
            "pipeline_errors": [{"node": "graph_engine", "error": str(exc), "error_type": type(exc).__name__}],
        }

    # Validate output
    is_valid, issues = validate_state(result)
    if not is_valid:
        logger.warning("aprocess_ticket: output validation issues: %s", issues)

    # Check for pipeline errors
    errors = result.get("pipeline_errors", [])
    if errors:
        logger.warning(
            "aprocess_ticket: %d node errors encountered: %s",
            len(errors), [e.get("node", "?") for e in errors],
        )

    return result


async def astream_ticket(
    raw_message: str,
    customer_id: str = "",
    channel: str = "email",
    variant: str = "parwa",
    *,
    thread_id: str | None = None,
    interrupt_before_action: bool = False,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream ticket processing through the full PARWA pipeline (async).

    Yields state updates as each node completes, enabling real-time
    progress tracking and partial result display. Uses LangGraph's
    astream_events() for granular event streaming.

    This is ideal for:
    - Real-time UI updates (showing which node is processing)
    - Progress tracking (e.g., "Classifying intent... 3/22 nodes done")
    - Early termination if intermediate results are unacceptable

    Args:
        raw_message: The customer's message
        customer_id: Customer identifier
        channel: Communication channel (email, chat, social, voice)
        variant: PARWA variant (mini, parwa, high)
        thread_id: Optional thread ID for checkpointing
        interrupt_before_action: Pause before action for human approval

    Yields:
        State dict after each node completes.
    """
    graph = get_parwa_graph(interrupt_before_action=interrupt_before_action)

    # Validate input
    if not raw_message or not isinstance(raw_message, str):
        yield {
            "error": "raw_message is required and must be a string",
            "final_response": "Error: No message provided.",
        }
        return

    if variant not in ("mini", "parwa", "high"):
        logger.warning("astream_ticket: invalid variant '%s', defaulting to 'parwa'", variant)
        variant = "parwa"

    initial_state = {
        "raw_message": raw_message,
        "customer_id": customer_id,
        "channel": channel,
        "variant": variant,
        "max_loops": 0,  # Disable quality loop-back for faster execution
    }

    config = _make_thread_config(thread_id)

    try:
        async for event in graph.astream(initial_state, config=config):
            yield event
    except Exception as exc:
        logger.error("astream_ticket: graph.astream failed: %s", exc, exc_info=True)
        yield {
            "error": f"Pipeline streaming failed: {exc}",
            "pipeline_errors": [{"node": "graph_engine", "error": str(exc), "error_type": type(exc).__name__}],
        }
