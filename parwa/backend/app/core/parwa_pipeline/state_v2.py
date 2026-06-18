"""
PARWA Pipeline V2 — State Definition

Single state object that flows through all 8 nodes.
Every node reads from this state and writes its outputs back.
No per-node sub-states — one state, one source of truth.

Annotated with operator.add for LangGraph reducer behavior on list fields.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


def _merge(left: list, right: list) -> list:
    """Reducer: append right into left (for technique_log, actions, errors)."""
    if left is None:
        return right or []
    return left + (right or [])


class PipelineV2State(TypedDict, total=False):
    """State that flows through the entire 8-node PARWA pipeline.

    Every field is optional (total=False) so nodes can be built incrementally.
    Graph entry point must populate the required input fields.
    """

    # ── INPUT (populated before graph starts) ──────────────────────
    ticket_id: str
    tenant_id: str
    query: str
    channel_type: str                    # email, sms, chat, call
    customer_context: Dict[str, Any]     # from UCB normalization
    metadata: Dict[str, Any]             # sender, timestamp, etc.

    # ── NODE 1: INGEST + CLASSIFY ──────────────────────────────────
    ticket_type: str                     # refund_request, billing, technical, faq, complaint, etc.
    complexity: str                      # simple, medium, complex, hard
    required_action: str                 # execute_refund, provide_info, escalate, etc.
    action_details: Dict[str, Any]       # amount, currency, etc.
    classification_confidence: float     # 0.0-1.0
    routing_suggestion: str              # simple_medium_path, complex_path
    node_1_token_usage: int

    # ── NODE 2: SMART ROUTE ────────────────────────────────────────
    variant_tier: str                    # mini, parwa, high
    quota_remaining: Dict[str, int]      # {"mini": 347, "parwa": 0, "high": 1856}
    route_decision: str                  # simple_path, complex_path
    variant_capabilities: List[str]      # what this tier CAN do

    # ── NODE 3: KNOWLEDGE FETCH ────────────────────────────────────
    knowledge_context: List[Dict[str, Any]]   # retrieved documents
    wiki_section_a: List[Dict[str, Any]]      # ticket patterns
    wiki_section_b: List[Dict[str, Any]]      # admin behavior
    wiki_section_c: List[Dict[str, Any]]      # company knowledge + policies
    wiki_patterns: List[Dict[str, Any]]       # Phase 6: similar patterns from Wiki Section A
    crm_data: Dict[str, Any]                  # customer data from CRM via UCB
    policy_version: str                        # current policy version for Section C
    policy_sync_status: Dict[str, Any]        # Phase 6: policy version sync check result
    knowledge_sufficient: bool                 # CLARA gate: do we have enough?
    knowledge_contradictory: bool              # CLARA gate: contradictions found?
    node_3_token_usage: int

    # ── NODE 4: REASONING ENGINE ───────────────────────────────────
    sub_problems: List[str]              # decomposed sub-problems
    sub_solutions: List[Dict[str, Any]]  # each sub-problem's solution
    combined_answer: str                 # final combined reasoning
    reasoning_confidence: float          # 0.0-1.0
    techniques_used: List[str]           # Phase 6: techniques used (for wiki write-back)
    node_4_token_usage: int

    # ── NODE 5: ACT + VERIFY ───────────────────────────────────────
    actions_taken: List[Dict[str, Any]]  # [{action, status, result}]
    actions_verified: bool
    verification_result: str
    node_5_token_usage: int

    # ── NODE 6: QUALITY + FORMAT ───────────────────────────────────
    quality_score: float                 # 0.0-1.0
    quality_details: Dict[str, float]    # per-technique scores
    formatted_response: str              # final customer-facing response
    quality_passed: bool                 # True if score > threshold
    node_6_token_usage: int

    # ── NODE 7: SIMPLE/MEDIUM RESOLVER ─────────────────────────────
    simple_answer: str                   # non-LLM generated answer
    simple_confidence: float             # 0.0-1.0
    simple_actions_taken: List[Dict[str, Any]]
    auto_upgraded: bool                  # True if safety net triggered

    # ── NODE 8: SUPER NODE ─────────────────────────────────────────
    super_node_answer: str
    super_node_quality: float
    super_node_analysis: str             # why previous attempts failed
    node_8_token_usage: int

    # ── PIPELINE CONTROL ───────────────────────────────────────────
    loop_count: int                      # quality loop counter (max 2)
    current_path: str                    # "simple" or "complex"
    final_response: str                  # the answer sent to customer
    status: str                          # resolved, escalated, stuck
    escalation_context: Dict[str, Any]   # if escalated: original + all attempts + analysis

    # ── OBSERVABILITY ──────────────────────────────────────────────
    technique_log: Annotated[List[Dict[str, Any]], _merge]  # [{node, technique, duration_ms, result_summary}]
    total_token_usage: int
    errors: Annotated[List[Dict[str, Any]], _merge]         # [{node, error, details}]