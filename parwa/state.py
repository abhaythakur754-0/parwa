"""Shared state schema for all 22 nodes in the PARWA LangGraph pipeline.

This is the central state object that flows through every node.
Each node reads from and writes to this state.
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

    model_config = ConfigDict(use_enum_values=True)
