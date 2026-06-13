"""Shared state schema for all 22 nodes in the PARWA LangGraph pipeline.

This is the central state object that flows through every node.
Each node reads from and writes to this state.

Phase 4: GSD (Global State Decompression) is woven into state management.
GSD compresses state between nodes (12,000→180 tokens) for efficient
passing. Nodes always see FULL state — compression only affects
serialization between nodes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class TicketChannel(str, Enum):
    """Supported communication channels."""
    EMAIL = "email"
    CHAT = "chat"
    SOCIAL = "social"
    VOICE = "voice"


class TicketComplexity(str, Enum):
    """Ticket complexity levels that determine framework activation."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"


class SentimentType(str, Enum):
    """Customer sentiment categories."""
    HAPPY = "happy"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"


class IntentType(str, Enum):
    """Primary intent categories for customer tickets."""
    ORDER_STATUS = "order_status"
    REFUND_REQUEST = "refund_request"
    CANCELLATION = "cancellation"
    BILLING_ISSUE = "billing_issue"
    TECHNICAL_SUPPORT = "technical_support"
    FAQ_QUESTION = "faq_question"
    COMPLAINT = "complaint"
    ACCOUNT_MODIFICATION = "account_modification"
    ESCALATION = "escalation"
    GENERAL_INQUIRY = "general_inquiry"


class ActionType(str, Enum):
    """Actions the system can take."""
    SEND_REPLY = "send_reply"
    PROCESS_REFUND = "process_refund"
    CANCEL_ORDER = "cancel_order"
    MODIFY_ACCOUNT = "modify_account"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    SHARE_FAQ = "share_faq"
    SHARE_POLICY = "share_policy"
    CREATE_NOTE = "create_note"
    POST_SOCIAL = "post_social"
    VOICE_CALL = "voice_call"
    SEND_SMS = "send_sms"
    BULK_OPERATION = "bulk_operation"
    API_WEBHOOK = "api_webhook"
    CUSTOM_INTEGRATION = "custom_integration"
    ACCESS_ANALYTICS = "access_analytics"


class ExecutionMode(str, Enum):
    """How an action is handled based on variant permissions."""
    EXECUTE = "execute"
    RECOMMEND = "recommend"
    DENY = "deny"


class ActionPlan(BaseModel):
    """A planned action with all necessary details."""
    action_type: ActionType
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    mode: ExecutionMode = ExecutionMode.EXECUTE
    evidence: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class KnowledgeResult(BaseModel):
    """Result from knowledge retrieval (FAQ/KB/Integration)."""
    source: str = ""
    content: str = ""
    relevance_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningPath(BaseModel):
    """A single reasoning path explored by Tree of Thoughts or Strategy Planner."""
    path_id: str = ""
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    selected: bool = False


class EvidenceEntry(BaseModel):
    """A single piece of structured evidence from a technique or node.

    P0 EVIDENCE CHAIN: Instead of passing just conclusion strings between
    nodes, we pass structured (claim, source, confidence, technique) entries.
    This lets downstream nodes verify, cross-reference, and build upon
    the reasoning of upstream nodes instead of trusting bare strings.
    """
    claim: str = ""  # What this evidence claims (the conclusion)
    sources: list[str] = Field(default_factory=list)  # What supports the claim
    confidence: float = 0.0  # How confident (0.0-1.0)
    technique: str = ""  # Which technique produced this
    category: str = ""  # Technique category (reasoning, rag, quality, etc.)
    node: str = ""  # Which node produced this (filled by the node)


class ProactiveInsight(BaseModel):
    """A proactive prediction or follow-up insight."""
    type: str = "follow_up"  # follow_up, prediction, cross_sell
    description: str = ""
    confidence: float = 0.0
    suggested_action: str = ""


class TicketState(BaseModel):
    """Central state object that flows through all 22 nodes.

    This is the single source of truth for a ticket as it moves
    through the PARWA pipeline. Every node reads from and writes to
    this state.
    """

    # ─── Input (set at INGEST) ────────────────────────────
    ticket_id: str = ""
    raw_message: str = ""
    customer_id: str = ""
    channel: TicketChannel = TicketChannel.EMAIL
    variant: str = "parwa"  # "mini", "parwa", "high"

    # ─── Router Agent outputs (Nodes 1, 2, 18, 20) ────────
    intent: IntentType = IntentType.GENERAL_INQUIRY
    intent_confidence: float = 0.0
    sentiment: SentimentType = SentimentType.NEUTRAL
    sentiment_urgency: float = 0.0
    should_escalate: bool = False
    escalation_reason: str = ""
    complexity: TicketComplexity = TicketComplexity.SIMPLE

    # ─── Knowledge Agent outputs (Nodes 3, 4, 19, 5) ──────
    faq_match: KnowledgeResult | None = None
    kb_results: list[KnowledgeResult] = Field(default_factory=list)
    context_history: list[dict[str, Any]] = Field(default_factory=list)
    integration_data: dict[str, Any] = Field(default_factory=dict)

    # ─── Reasoning Agent outputs (Nodes 6, 10, 12, 11) ────
    reasoning_chain: list[str] = Field(default_factory=list)
    reasoning_conclusion: str = ""
    reasoning_paths: list[ReasoningPath] = Field(default_factory=list)
    reverse_validation: dict[str, Any] = Field(default_factory=dict)
    strategy_plan: list[str] = Field(default_factory=list)
    selected_path: ReasoningPath | None = None

    # ─── P1: Red Team and Agent Debate outputs ───────────────────────────
    # Red Team: Adversarial validation that actively tries to break reasoning
    red_team_report: dict[str, Any] = Field(default_factory=dict)
    # Agent Debate: Advocate vs Skeptic debate results
    debate_result: dict[str, Any] = Field(default_factory=dict)

    # ─── P0: Cross-node Evidence Chain ───────────────────────────
    # Structured evidence that flows between ALL nodes. Each node reads
    # from this chain to understand what upstream nodes concluded and WHY.
    # Each node also ADDS its own evidence entries.
    # This replaces the old pattern of passing bare conclusion strings.
    evidence_chain: list[dict[str, Any]] = Field(default_factory=list)

    # ─── Action Agent outputs (Nodes 7, 8, 9) ─────────────
    action_plans: list[ActionPlan] = Field(default_factory=list)
    execution_results: list[dict[str, Any]] = Field(default_factory=list)
    verification_passed: bool = False
    recommendation: dict[str, Any] | None = None

    # ─── Proactive Agent outputs (Nodes 13, 14, 22) ───────
    proactive_insights: list[ProactiveInsight] = Field(default_factory=list)
    predictions: list[ProactiveInsight] = Field(default_factory=list)
    feedback_signal: dict[str, Any] = Field(default_factory=dict)

    # ─── Compliance Agent outputs (Nodes 15, 16, 21, 17) ──
    pii_detected: bool = False
    pii_redacted_message: str = ""
    audit_log: list[dict[str, Any]] = Field(default_factory=list)
    quality_score: float = 0.0
    quality_issues: list[str] = Field(default_factory=list)
    final_response: str = ""

    # ─── Framework activation tracking ─────────────────────
    active_frameworks: list[str] = Field(default_factory=list)

    # ─── Internal routing flags ────────────────────────────
    should_loop_back: bool = False
    loop_count: int = 0
    max_loops: int = 2

    # ─── Production metadata (error tracking) ────────────────
    pipeline_errors: list[dict[str, Any]] = Field(default_factory=list)
    node_error: dict[str, Any] | None = None

    # ─── TurboQuant token tracking ─────────────────────────
    token_budget_total: int = 0
    token_budget_used: int = 0
    token_budget_remaining: int = 0
    token_usage_by_node: dict[str, dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True, extra="allow")


def validate_state(state: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a state dict against the TicketState schema.

    Performs both Pydantic schema validation AND business rule validation
    (valid variant, valid channel, required fields for pipeline entry).

    Returns:
        Tuple of (is_valid, list_of_issues).
    """
    issues: list[str] = []

    # Pydantic schema validation
    try:
        TicketState(**state)
    except Exception as exc:
        issues.append(f"State validation error: {exc}")

    # Business rule validation
    variant = state.get("variant", "parwa")
    if variant not in ("mini", "parwa", "high"):
        issues.append(f"variant must be mini/parwa/high, got '{variant}'")

    channel = state.get("channel", "email")
    if channel not in ("email", "chat", "social", "voice"):
        issues.append(f"channel must be email/chat/social/voice, got '{channel}'")

    raw_message = state.get("raw_message", "")
    if raw_message and not isinstance(raw_message, str):
        issues.append(f"raw_message must be str, got {type(raw_message).__name__}")

    return len(issues) == 0, issues


def state_to_dict(state: TicketState) -> dict[str, Any]:
    """Convert a TicketState Pydantic model to a plain dict for LangGraph.

    Args:
        state: The TicketState instance.

    Returns:
        A plain dict with all state fields.
    """
    return state.model_dump()


def dict_to_state(data: dict[str, Any]) -> TicketState:
    """Convert a plain dict to a TicketState Pydantic model.

    Args:
        data: The state dict.

    Returns:
        A validated TicketState instance.

    Raises:
        ValidationError: If the dict doesn't match the schema.
    """
    return TicketState(**data)
