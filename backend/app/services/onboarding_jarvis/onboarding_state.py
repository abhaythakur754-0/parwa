"""
PARWA Onboarding Jarvis State — LangGraph State for the Onboarding Agent Graph

This defines the state that flows through the Onboarding Jarvis agent graph.
Mirrors the structure of JarvisCommandState but adapted for the pre-purchase
demo/onboarding experience.

The state carries:
  - The user's message and session context
  - The router's decision on which agent to invoke
  - The specialist agent's reasoning and action plan
  - The executor's result after taking action
  - Full awareness of the onboarding journey (variant, industry, entry source)

Flow:
  User Message → OnboardingRouter → [AgentSelector] → SpecialistAgent
      → OnboardingExecutor → Result
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from typing import TypedDict


def _merge_dicts(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer: merge new dict into existing (new keys override)."""
    return {**existing, **new}


def _merge_lists(existing: List[Any], new: List[Any]) -> List[Any]:
    """Reducer: append new items to existing list."""
    return existing + new


class OnboardingJarvisState(TypedDict, total=False):
    """State flowing through the Onboarding Jarvis Agent Graph.

    Unlike JarvisCommandState (which handles post-onboarding operations),
    this state handles the entire pre-purchase demo experience. When a
    potential client chats with Jarvis, this state tracks the full journey
    from first "hello" to payment and handoff.

    Groups:
      1. TRIGGER     — What initiated this turn (user message, call event)
      2. CONTEXT     — Onboarding awareness (variant, industry, demo state)
      3. ROUTER      — Router agent's decision on which agent to invoke
      4. AGENT       — The specialist agent's decision and reasoning
      5. EXECUTION   — What actually happened when the action was executed
      6. AWARENESS   — Onboarding-specific awareness data
      7. AUDIT       — Full audit trail for analytics
    """

    # ──────────────────────────────────────────────────────────────
    # GROUP 1: TRIGGER — What started this turn
    # ──────────────────────────────────────────────────────────────

    trigger_type: str
    """What triggered this turn: 'user_message' (chat), 'call_event' (voice),
    'system_event' (stage change), 'payment_event' (payment callback)."""

    user_message: str
    """The raw user message text."""

    session_id: str
    """The onboarding session ID."""

    company_id: str
    """BC-001: Company ID for tenant isolation (may be empty pre-payment)."""

    user_id: str
    """User ID for security scoping."""

    conversation_turn: int
    """Current turn number in the conversation."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 2: CONTEXT — Onboarding awareness (pre-purchase state)
    # ──────────────────────────────────────────────────────────────

    entry_source: str
    """Where the user came from: 'direct', 'pricing', 'variant_demo',
    'roi_calculator', 'landing_hero', 'floating_chat'."""

    entry_variant_id: str
    """If user came from a variant demo, which variant."""

    entry_variant_name: str
    """Human-readable variant name (e.g., 'Returns & Refunds')."""

    industry: str
    """Selected or detected industry: 'ecommerce', 'saas', 'logistics', 'others'."""

    detected_stage: str
    """Current onboarding stage: 'welcome', 'discovery', 'demo', 'pricing',
    'bill_review', 'verification', 'payment', 'handoff'."""

    message_count_today: int
    """How many messages sent today (for rate limiting)."""

    pack_type: str
    """Current pack: 'free' or 'demo'."""

    payment_status: str
    """Payment status: 'none', 'pending', 'completed', 'failed'."""

    demo_topics: List[str]
    """Topics discussed during demo (for awareness)."""

    concerns_raised: List[str]
    """Objections or concerns raised by the client."""

    selected_variants: List[Dict[str, Any]]
    """Variants the client has selected: [{id, name, qty, price}]."""

    business_email: str
    """Client's business email (if provided)."""

    email_verified: bool
    """Whether the business email has been verified via OTP."""

    pages_visited: List[str]
    """Pages the client has visited on the site."""

    roi_result: Optional[Dict[str, Any]]
    """ROI calculation result if client used the calculator."""

    uploaded_docs: List[Dict[str, Any]]
    """Documents uploaded during onboarding demo."""

    call_completed: bool
    """Whether the client has completed a demo call."""

    call_topics_discussed: List[str]
    """Topics covered during the demo call."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 3: ROUTER — Onboarding Router Agent's decision
    # ──────────────────────────────────────────────────────────────

    router_decision: str
    """Which agent the router selected: 'guide', 'salesman', 'demo',
    'call', 'awareness', 'no_action'."""

    router_reasoning: str
    """Why the router selected this agent."""

    router_confidence: float
    """Router's confidence in its decision (0.0-1.0)."""

    router_source: str
    """How the router decided: 'zai_llm' or 'rule_based_fallback'."""

    router_parameters: Dict[str, Any]
    """Router's suggested parameters for the agent."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 4: AGENT — Specialist agent's decision
    # ──────────────────────────────────────────────────────────────

    agent_type: str
    """Which agent was invoked (same as router_decision)."""

    agent_action: str
    """The action the agent decided to take."""

    agent_decision: Dict[str, Any]
    """Full structured decision from the agent."""

    agent_reasoning: str
    """Agent's reasoning for its decision."""

    agent_source: str
    """How the agent decided: 'zai_llm' or 'rule_based_fallback'."""

    response_text: str
    """The conversational response text to send back to the user."""

    response_card_type: str
    """If the response includes a rich card: 'bill_summary', 'payment_card',
    'otp_card', 'handoff_card', 'demo_call_card', 'none'."""

    response_card_data: Dict[str, Any]
    """Data for the rich card if response_card_type != 'none'."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 5: EXECUTION — What actually happened
    # ──────────────────────────────────────────────────────────────

    execution_status: str
    """Execution status: 'pending', 'completed', 'failed', 'skipped'."""

    execution_result: Dict[str, Any]
    """Structured result from executing the agent's decision."""

    execution_error: str
    """Error message if execution failed."""

    execution_time_ms: float
    """Total execution time in milliseconds."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 6: AWARENESS — Onboarding-specific awareness enrichment
    # ──────────────────────────────────────────────────────────────

    awareness_updated: bool
    """Whether the awareness agent updated the context."""

    awareness_changes: Dict[str, Any]
    """What the awareness agent detected/changed."""

    stage_transition: Optional[str]
    """If the stage changed, what it changed to."""

    new_concerns: List[str]
    """Newly detected concerns from this message."""

    new_topics: List[str]
    """Newly detected demo topics from this message."""

    intent_detected: str
    """Detected intent from user message: 'greeting', 'question', 'objection',
    'demo_request', 'pricing_inquiry', 'call_request', 'purchase_intent',
    'document_upload', 'chitchat', 'other'."""

    sentiment: str
    """Detected sentiment: 'positive', 'neutral', 'negative', 'excited',
    'frustrated', 'skeptical'."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 7: AUDIT — Full trail
    # ──────────────────────────────────────────────────────────────

    node_outputs: Annotated[Dict[str, Any], _merge_dicts]
    """Accumulated outputs from each node: {node_name: output_dict}."""

    audit_trail: Annotated[List[Dict[str, Any]], _merge_lists]
    """Step-by-step audit entries."""

    errors: Annotated[List[str], _merge_lists]
    """Accumulated error messages (BC-008 graceful degradation)."""


def create_onboarding_state(
    session_id: str,
    user_id: str,
    user_message: str,
    company_id: str = "",
    entry_source: str = "direct",
    entry_variant_id: str = "",
    entry_variant_name: str = "",
    industry: str = "",
    detected_stage: str = "welcome",
    message_count_today: int = 0,
    pack_type: str = "free",
    payment_status: str = "none",
    demo_topics: Optional[List[str]] = None,
    concerns_raised: Optional[List[str]] = None,
    selected_variants: Optional[List[Dict[str, Any]]] = None,
    business_email: str = "",
    email_verified: bool = False,
    pages_visited: Optional[List[str]] = None,
    roi_result: Optional[Dict[str, Any]] = None,
    uploaded_docs: Optional[List[Dict[str, Any]]] = None,
    call_completed: bool = False,
    call_topics_discussed: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create initial onboarding state from a user message.

    This is how every turn in the onboarding chat enters the agent graph.
    The state carries the full onboarding journey context so every agent
    knows exactly where the client is in their journey.
    """
    return {
        # TRIGGER
        "trigger_type": "user_message",
        "user_message": user_message,
        "session_id": session_id,
        "company_id": company_id,
        "user_id": user_id,
        "conversation_turn": 0,

        # CONTEXT
        "entry_source": entry_source,
        "entry_variant_id": entry_variant_id,
        "entry_variant_name": entry_variant_name,
        "industry": industry,
        "detected_stage": detected_stage,
        "message_count_today": message_count_today,
        "pack_type": pack_type,
        "payment_status": payment_status,
        "demo_topics": demo_topics or [],
        "concerns_raised": concerns_raised or [],
        "selected_variants": selected_variants or [],
        "business_email": business_email,
        "email_verified": email_verified,
        "pages_visited": pages_visited or [],
        "roi_result": roi_result,
        "uploaded_docs": uploaded_docs or [],
        "call_completed": call_completed,
        "call_topics_discussed": call_topics_discussed or [],

        # ROUTER
        "router_decision": "",
        "router_reasoning": "",
        "router_confidence": 0.0,
        "router_source": "",
        "router_parameters": {},

        # AGENT
        "agent_type": "",
        "agent_action": "",
        "agent_decision": {},
        "agent_reasoning": "",
        "agent_source": "",
        "response_text": "",
        "response_card_type": "none",
        "response_card_data": {},

        # EXECUTION
        "execution_status": "pending",
        "execution_result": {},
        "execution_error": "",
        "execution_time_ms": 0.0,

        # AWARENESS
        "awareness_updated": False,
        "awareness_changes": {},
        "stage_transition": None,
        "new_concerns": [],
        "new_topics": [],
        "intent_detected": "",
        "sentiment": "neutral",

        # AUDIT
        "node_outputs": {},
        "audit_trail": [{
            "step": "init",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": "user_message",
            "stage": detected_stage,
            "entry_source": entry_source,
        }],
        "errors": [],
    }
