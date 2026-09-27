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

    # ── LANE ROUTING (Commit 2: 3-lane system) ─────────────────────
    # Set by Node 1 after running all 16 non-LLM techniques. Controls
    # which nodes run AFTER Node 1:
    #   FULL    → Node 2 → 3 → 3.5 → 4 → 4.5 → 5 → 6 → END (new complex tickets)
    #   QUICK   → Node 7 (Simple Resolver) → END (follow-ups, 0-3 LLM calls)
    #   INSTANT → finalize_simple (canned response) → END (gratitude, 0 LLM)
    message_type: str                    # NEW_ISSUE, FOLLOW_UP, CLARIFICATION, GRATITUDE, SIMPLE_QUESTION
    lane: str                             # FULL, QUICK, INSTANT

    # ── NODE 1: INGEST + CLASSIFY ──────────────────────────────────
    ticket_type: str                     # refund_request, billing, technical, faq, complaint, etc.
    complexity: str                      # simple, medium, complex, hard
    required_action: str                 # execute_refund, provide_info, escalate, etc.
    action_details: Dict[str, Any]       # amount, currency, etc.
    classification_confidence: float     # 0.0-1.0
    routing_suggestion: str              # simple_medium_path, complex_path
    node_1_token_usage: int
    system_flags: Dict[str, Any]         # Jarvis/system flags loaded at ingest
    enhancement_data: Dict[str, Any]     # customer_context enrichment result
    conversation_summary: Optional[str]  # F-160 rolling conversation summary
    escalation_record: Optional[Any]     # EscalationRecord (graceful_escalation) or None

    # ── NODE 2: SMART ROUTE ────────────────────────────────────────
    variant_tier: str                    # mini_parwa, parwa, parwa_high (DB name)
    variant_tier_short: str              # mini, parwa, high (short key for downstream)
    quota_remaining: Dict[str, int]      # {"mini": 347, "parwa": 0, "high": 1856}
    route_decision: str                  # simple_path, complex_path
    variant_capabilities: List[str]      # what this tier CAN do
    verified_agent_id: Optional[str]     # Builder/Superglue agent verified by Node 2
    verified_tool_id: Optional[str]      # linked Superglue tool id
    agent_verification_status: str       # exists | created | failed | error
    tool_verification_status: str        # exists | created | failed | not_needed | error

    # ── BUILDER AGENT (Node 1 → Builder) ───────────────────────────
    builder_agent_id: Optional[str]      # agent_id if Builder created an agent
    builder_used: bool                   # True if Builder pipeline was invoked
    builder_quality_score: float         # 0.0-1.0 from Builder VERIFY/REFINE

    # ── NODE 3: KNOWLEDGE FETCH ────────────────────────────────────
    connected_databases: List[Dict[str, Any]]  # tenant's connected databases from DBConnection table
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
    jarvis_guidance: str                       # Phase 11: Jarvis guidance for this ticket
    intent_signals: Dict[str, Any]             # boosted intent signals
    query_decomposition: Dict[str, Any]        # GSD decomposition of the query
    completeness_tracker: Dict[str, Any]       # KB completeness tracking
    context_signals: Dict[str, Any]            # UCB context signals
    context_scores: Dict[str, Any]             # UCB context scores
    wiki_diversity: Dict[str, Any]             # wiki pattern diversity metrics
    wiki_conflict_resolution: Dict[str, Any]   # conflicting wiki pattern check
    temporal_check: Dict[str, Any]             # temporal relevance of KB docs
    version_tracker: Dict[str, Any]            # KB doc version tracking
    partial_data: Dict[str, Any]               # partial CRM data handling result

    # ── NODE 3.5: FEW-SHOT INJECTION (Phase 8) ─────────────────────
    # 0 LLM calls. Pulls 2-3 past resolved tickets in the same category
    # for in-context learning. Critical for weak LLMs (Llama 3.1 8B).
    few_shot_examples: List[Dict[str, Any]]   # [{customer_message, ai_response, score}]

    # ── NODE 4: REASONING ENGINE ───────────────────────────────────
    sub_problems: List[str]              # decomposed sub-problems
    sub_solutions: List[Dict[str, Any]]  # each sub-problem's solution
    combined_answer: str                 # final combined reasoning
    reasoning_confidence: float          # 0.0-1.0
    techniques_used: List[str]           # Phase 6: techniques used (for wiki write-back)
    node_4_token_usage: int

    # ── NODE 4 PHASE 9: SELF-CONSISTENCY VOTING ───────────────────
    # Generate 3 candidates, score each against KB, pick the best.
    # Averages out Llama 3.1 8B's high variance (Wang et al. 2022).
    # 3x LLM calls instead of 1 (still 3x cheaper than 1 GLM call).
    self_consistency_candidates: List[Dict[str, Any]]  # [{index, response, score, verified_claims, total_claims}]
    maker_bridges: List[Dict[str, Any]]  # MAKER bridges (sub-problem ↔ KB)
    maker_confidences: List[Any]         # confidence per MAKER bridge
    maker_flagged: bool                  # MAKER flagged ungrounded content
    maker_zsv_removed: int               # bridges removed by the ZSV gate
    maker_bridge_safe: bool              # final MAKER bridge safety check
    query_decompose_hash: str            # idempotency hash of the decomposition
    llm_technique_results: List[Dict[str, Any]]  # BC-013 TechniqueExecutor results
    llm_technique_hints: List[Dict[str, Any]]    # hints extracted from LLM techniques

    # ── NODE 4.5: CHAIN-OF-VERIFICATION (Phase 8) ──────────────────
    # Verifies every claim in combined_answer against KB chunks.
    # Regenerates response if verification_score < 0.50.
    # 0 LLM calls in happy path; 1 only when regeneration needed.
    verified_response: str               # final response after CoVe (may overwrite combined_answer)
    verification_score: float            # 0.0-1.0 (fraction of claims supported by KB)
    verification_claims: List[Dict[str, Any]]  # [{claim, verified, reason}]
    cove_regenerated: bool               # True if regeneration was triggered
    cove_blocked: bool                   # Phase 10: True if score < 0.5 even after regen → safe fallback + escalate
    node_4_5_token_usage: int

    # ── NODE 4/5: HUMAN ESCALATION SIGNAL ──────────────────────────
    # Set by Node 4 (hallucination strict-mode) or Node 5 (legal/sensitive
    # short-circuit) to force the dispatcher to mark the ticket as
    # awaiting_human instead of resolved. Without this field declared in
    # state, LangGraph drops it from the return dict.
    force_human_handoff: bool

    # ── NODE 5: ACT + VERIFY ───────────────────────────────────────
    actions_taken: List[Dict[str, Any]]  # [{action, status, result}]
    actions_verified: bool
    verification_result: str
    node_5_token_usage: int
    # Approval queue (BC-009) — set via state mutation inside _react_execute;
    # declared here so LangGraph keeps the fields instead of dropping them.
    pending_approval: bool               # action queued for human approval
    pending_approval_reason: str         # why approval is required
    pending_approval_tool_input: str     # serialized tool input for the approval queue
    pending_approval_agent_id: Optional[str]  # Builder agent awaiting approval
    pending_approval_tool_id: Optional[str]   # Superglue tool awaiting approval
    action_audit: Dict[str, Any]         # audit trail of executed actions
    push_to_crm: bool                    # Jarvis guidance: push result to CRM
    crm_reason: str                      # why the CRM push was requested
    escalation_required: bool            # escalation decision (nodes 5/6)
    escalation_reasons: List[str]        # why escalation was triggered
    sufficiency: bool                    # knowledge sufficiency verdict
    meta_confidence_adjustment: float    # MetaLearner confidence adjustment (node 5)
    maker_final_block: bool              # final MAKER check blocked the answer (node 5)
    policy_cited: bool                   # PolicyCitationChecker result (node 5)

    # ── NODE 6: QUALITY + FORMAT ───────────────────────────────────
    quality_score: float                 # 0.0-1.0
    quality_details: Dict[str, float]    # per-technique scores
    formatted_response: str              # final customer-facing response
    quality_passed: bool                 # True if score > threshold
    node_6_token_usage: int
    cove_verified: bool                  # CoVe verification passed (checked again in node 6)
    contradiction_detected: bool         # contradiction check result
    maker_gaps: List[Dict[str, Any]]     # MAKER gap report
    rule_violations: List[Dict[str, Any]]  # rule-based check violations
    meta_adjustment: float               # MetaLearner score adjustment (node 6)
    guardrail_safe: bool                 # guardrail check passed
    reverse_thinking_risks: int          # reverse-thinking risk count
    step_back_passes: bool               # step-back abstraction check
    least_to_most_score: float           # least-to-most decomposition score
    theory_of_mind_addressed: bool       # theory-of-mind intent coverage
    fake_voting_consensus: float         # fake voting consensus score

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

    # ── NODE 6.5: DELIVER (BC-015) ─────────────────────────────────
    delivery_status: str                 # dispatched, sent, stored, stub, error, skipped_empty_response
    delivery_channel: Optional[str]      # email, sms, chat, voice, internal (None if skipped/failed)
    delivery_fallback_reason: Optional[str]  # None, sms_length_exceeded, provider_failure:<channel>, missing_channel_default, unknown_channel_default
    delivery_result: Dict[str, Any]      # raw return from ChannelDispatcher.dispatch
    delivery_attempts: int               # number of channels tried (1 = primary only, 2+ = fallbacks used)
    node_6_5_token_usage: int
    # NEW — production hardening (BC-015 v2):
    delivery_message_id: Optional[str]   # provider-returned message ID (for traceability)
    delivery_audit_id: Optional[str]     # audit_log.id (for compliance lookup)
    delivery_retry_count: int            # times retried within a channel before fallback (0 = first attempt)
    delivery_circuit_open: bool          # was a circuit breaker tripped on any channel?
    delivery_dlq_entry_id: Optional[str] # FK to GraphExecutionDLQ.id if persisted on all-fail

    # ── NODE 6.5 PHASE 2: CRM PUSH-BACK (BC-016) ──────────────────
    # After customer dispatch succeeds, push "resolved" to the originating
    # CRM. Best-effort — failures go to DLQ with error_type=crm_push_failed.
    crm_push_status: str                 # success, skipped_no_crm, skipped_disabled, error, dlq_persisted
    crm_push_provider: Optional[str]     # zendesk, hubspot, generic (None if no CRM ticket)
    crm_push_attempts: int               # number of retries attempted (0 = first-attempt success)
    crm_push_result: Dict[str, Any]      # raw return from CRMBridge.push_response
    crm_push_dlq_entry_id: Optional[str] # FK to GraphExecutionDLQ.id if persisted on all-fail
    crm_push_error: Optional[str]        # short error message if status=error/dlq_persisted

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