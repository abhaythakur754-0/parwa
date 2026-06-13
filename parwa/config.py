"""Variant configurations for Mini PARWA, PARWA, and PARWA High.

Per PARWA Product Documentation v6.0:

VARIANT HIERARCHY:
    Mini PARWA ("The 24/7 Trainee")  — Collects info, verifies eligibility,
        NEVER executes financial actions. Uses Light Tier (Gemma-4B).
        $1,000/month, 200 tickets/day, Email+Chat, 3 concurrent.

    PARWA ("The Junior Agent") — Makes intelligent RECOMMENDATIONS with
        reasoning, but doesn't execute financial actions. Uses Light+Medium
        (Gemma-4B + Gemini-Flash). $2,500/month, 300 tickets/day,
        Email+Chat, 4 concurrent.

    PARWA High ("The Senior Agent") — Strategic recommendations with
        risk-benefit analysis. CAN execute financial actions after approval.
        Uses Light+Medium+Heavy (Gemma-4B + Gemini-Flash + DeepSeek-R1).
        $4,000/month, 500+ tickets/day, Email+Chat+Voice, 6 concurrent.

CORE APPROVAL RULES (Apply to ALL Variants):
    ALL variants ALWAYS require approval for:
    - Refunds (Any Type, Any Amount)
    - Returns (Any item, any value)
    - Account changes (Billing, security, email, password)
    - Policy exceptions (Anything outside normal rules)
    - New decision types (Situations AI hasn't seen before)
    - VIP customer actions (High-value customer requests)
    - Financial transactions (Credits, adjustments, discounts >$10)

WHAT VARIES BY VARIANT:
    - How the variant handles the action (collect vs recommend vs strategic)
    - Depth of analysis (basic vs detailed vs strategic)
    - Model tier used (Light vs Medium vs Heavy)
    - Whether it can EXECUTE financial actions or only RECOMMEND
    - Speed, concurrent capacity, channel support

SMART ROUTER (Per Docs v6.0):
    Light Tier:  google/gemma-3-4b-it:free   (FAQs, Greetings, Order Status)
    Medium Tier: google/gemini-2.0-flash-exp:free (Drafting, Summarizing, Recommendations)
    Heavy Tier:  deepseek/deepseek-r1-0528:free (Refunds, Fraud, Complex Logic)
    Routing: complexity 0-4 → Light, 5-9 → Medium, 10+ → Heavy
    Failover: If primary model hits rate limit → auto-failover to next in tier
"""

from __future__ import annotations

from parwa.state import ActionType, ExecutionMode, TicketChannel


# ─── Variant Definitions ────────────────────────────────────────────────────────

MINI_PARWA = "mini"
PARWA = "parwa"
PARWA_HIGH = "high"

VARIANT_NAMES = {MINI_PARWA, PARWA_HIGH, PARWA}


# ─── Model Tier Definitions (Google AI Primary + OpenRouter Fallback) ──────────
# Smart Router routes to Light/Medium/Heavy based on task complexity.
# Primary: Google Gemini models (direct API — generous free tier, no rate limit issues)
# Fallback: OpenRouter free tier models (needs OPENROUTER_KEY env var)
# Failover: if primary model hits 429, auto-try next in tier.

MODEL_TIERS = {
    "light": [
        "gemini/gemini-2.0-flash-lite",                  # Primary: Fast, cheap, handles FAQs/status (Google AI direct)
        "openrouter/google/gemma-3-4b-it:free",          # Fallback 1 (needs OpenRouter key)
        "openrouter/meta-llama/llama-3.1-8b-instruct:free",  # Fallback 2
    ],
    "medium": [
        "gemini/gemini-2.0-flash",                       # Primary: Balanced, drafting, recommendations (Google AI direct)
        "openrouter/google/gemini-2.0-flash-exp:free",   # Fallback 1 (needs OpenRouter key)
        "openrouter/google/gemma-3-4b-it:free",          # Fallback 2 (downgrade to light)
    ],
    "heavy": [
        "gemini/gemini-2.0-flash",                       # Primary: Complex reasoning, fraud, refunds (Google AI direct)
        "openrouter/deepseek/deepseek-r1-0528:free",     # Fallback 1 (needs OpenRouter key)
        "openrouter/meta-llama/llama-4-maverick:free",   # Fallback 2
    ],
    "guardrail": [
        "gemini/gemini-2.0-flash-lite",                  # Primary: Safety checks (Google AI direct)
        "openrouter/meta-llama/llama-guard-4-12b:free",  # Fallback (needs OpenRouter key)
    ],
}

# Which tiers each variant can access (per docs)
VARIANT_MODEL_TIERS: dict[str, list[str]] = {
    MINI_PARWA: ["light", "guardrail"],
    PARWA: ["light", "medium", "guardrail"],
    PARWA_HIGH: ["light", "medium", "heavy", "guardrail"],
}

# Node → tier mapping (which tier to use for each node)
NODE_TIER_MAP: dict[str, str] = {
    # Router Agent (simple classification — LIGHT)
    "INGEST": "light",
    "INTENT_CLASSIFIER": "light",
    "SENTIMENT_ANALYZER": "light",
    "ESCALATION_DECISION": "light",
    # Knowledge Agent (medium — needs semantic understanding)
    "FAQ_MATCHER": "light",
    "KB_RETRIEVER": "medium",
    "CONTEXT_MANAGER": "light",
    "INTEGRATION_LOOKUP": "light",
    # Reasoning Agent (medium/heavy — core thinking)
    "REASONING_ENGINE": "medium",
    "REVERSE_THINKER": "medium",
    "TREE_OF_THOUGHTS": "medium",
    "STRATEGY_PLANNER": "heavy",
    # Action Agent (medium — structured work with decisions)
    "ACTION_PLANNER": "medium",
    "ACTION_EXECUTOR": "light",
    "ACTION_VERIFIER": "light",
    # Proactive Agent (light/medium)
    "PROACTIVE_CHECKER": "light",
    "PREDICTION_ENGINE": "medium",
    "FEEDBACK_LOOP": "light",
    # Compliance Agent (light/medium)
    "PII_COMPLIANCE_GUARD": "light",
    "AUDIT_LOGGER": "light",
    "QUALITY_SCORER": "medium",
    "RESPONSE_FORMATTER": "medium",
    # FrameworkBrain technique nodes
    "FRAMEWORKBRAIN_COT": "medium",
    "FRAMEWORKBRAIN_REACT": "medium",
    "FRAMEWORKBRAIN_CLARA": "medium",
    "FRAMEWORKBRAIN_HYDE": "medium",
    "FRAMEWORKBRAIN_MULTI_QUERY": "medium",
    "FRAMEWORKBRAIN_STEP_BACK": "medium",
    "FRAMEWORKBRAIN_REFLEXION": "medium",
    "FRAMEWORKBRAIN_SC": "medium",
    "FRAMEWORKBRAIN_CRP": "medium",
    "FRAMEWORKBRAIN_LTM": "medium",
    # Guardrail tier for safety
    "GUARDRAIL_CHECK": "guardrail",
}


# ─── Variant Pricing & Capacity (Per Docs v6.0) ─────────────────────────────────

VARIANT_CONFIG: dict[str, dict] = {
    MINI_PARWA: {
        "role": "The 24/7 Trainee",
        "price_monthly": 1000,
        "tickets_per_day": 200,
        "tickets_per_month": 6000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT],
        "concurrent_tickets": 3,
        "ai_resolution_rate": 0.60,
        "voice_addon_price": 75,  # $75 per additional call slot
        "can_execute_financial": False,  # Mini NEVER executes financial actions
        "action_style": "collect",  # Collects info, verifies basic eligibility, sends to manager
    },
    PARWA: {
        "role": "The Junior Agent",
        "price_monthly": 2500,
        "tickets_per_day": 300,
        "tickets_per_month": 9000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT],
        "concurrent_tickets": 4,
        "ai_resolution_rate": 0.75,
        "voice_addon_price": 75,
        "can_execute_financial": False,  # PARWA recommends but doesn't execute financial actions
        "action_style": "recommend",  # Makes intelligent recommendations with reasoning
    },
    PARWA_HIGH: {
        "role": "The Senior Agent",
        "price_monthly": 4000,
        "tickets_per_day": 500,
        "tickets_per_month": 15000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT, TicketChannel.VOICE],
        "concurrent_tickets": 6,
        "ai_resolution_rate": 0.85,
        "voice_addon_price": 0,  # included
        "can_execute_financial": True,  # High CAN execute financial actions after approval
        "action_style": "strategic",  # Strategic recommendations with risk-benefit analysis
    },
}


# ─── Action Permission Matrix (Per Docs v6.0) ───────────────────────────────────
#
# KEY INSIGHT from the docs:
#   Mini PARWA: Collects info, verifies basic eligibility, NEVER executes refunds.
#              Only prepares the request for manager review.
#   PARWA: Makes intelligent recommendations with confidence scores and reasoning,
#          but doesn't execute financial actions. Manager clicks Approve/Deny.
#   PARWA High: Strategic recommendations with risk-benefit analysis.
#              CAN execute financial actions after approval gate.
#
# ExecutionMode meanings:
#   EXECUTE   → Action runs immediately (lookups, FAQs, status checks)
#   RECOMMEND → Variant RECOMMENDS the action with reasoning but CANNOT execute it.
#               Manager must approve first. The action is PREPARED, not run.
#               This is the CORE differentiator between variants.
#   DENY      → Feature removed from the product entirely (social media)
#
# ALL variants still THINK identically (same 22 nodes, same tools, same brain).
# The difference is in the ACT phase — what they're allowed to DO with the results.

ACTION_PERMISSIONS: dict[str, dict[ActionType, ExecutionMode]] = {
    MINI_PARWA: {
        # ─── Autonomous actions (Mini CAN execute these) ──────────────
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,       # Can reply with collected info
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,        # Can share FAQ answers
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,     # Can share policy text
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,      # Can add notes to tickets
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE, # Can escalate
        ActionType.SEND_SMS: ExecutionMode.EXECUTE,         # Can send SMS (status updates)
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,      # Can trigger webhooks for data

        # ─── Recommendation-only actions (Mini COLLECTS but CANNOT execute) ──
        ActionType.PROCESS_REFUND: ExecutionMode.RECOMMEND,  # Collects eligibility, NEVER executes
        ActionType.CANCEL_ORDER: ExecutionMode.RECOMMEND,    # Collects info, prepares request
        ActionType.MODIFY_ACCOUNT: ExecutionMode.RECOMMEND,  # Collects new info, flags for review

        # ─── Premium/Addon features ───────────────────────────────────
        ActionType.VOICE_CALL: ExecutionMode.DENY,          # Addon only ($75/call slot)
        ActionType.ACCESS_ANALYTICS: ExecutionMode.DENY,    # Not available on Mini
        ActionType.BULK_OPERATION: ExecutionMode.DENY,      # Not available on Mini

        # ─── Product-removed features ─────────────────────────────────
        ActionType.POST_SOCIAL: ExecutionMode.DENY,         # Social media removed from product
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.DENY,  # Not available on Mini
    },
    PARWA: {
        # ─── Autonomous actions (PARWA CAN execute these) ─────────────
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,        # Can draft and send replies
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,         # Can share FAQ answers
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,      # Can share policy text
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,       # Can add notes to tickets
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE, # Can escalate with summaries
        ActionType.SEND_SMS: ExecutionMode.EXECUTE,          # Can send SMS
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,       # Can trigger webhooks
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.EXECUTE, # Can use custom integrations

        # ─── Recommendation-only actions (PARWA RECOMMENDS, doesn't execute) ──
        ActionType.PROCESS_REFUND: ExecutionMode.RECOMMEND,  # Recommends with confidence + reasoning
        ActionType.CANCEL_ORDER: ExecutionMode.RECOMMEND,    # Recommends with analysis
        ActionType.MODIFY_ACCOUNT: ExecutionMode.RECOMMEND,  # Prepares change, flags for review

        # ─── Premium/Addon features ───────────────────────────────────
        ActionType.VOICE_CALL: ExecutionMode.DENY,          # Addon only ($75/call slot)
        ActionType.ACCESS_ANALYTICS: ExecutionMode.RECOMMEND, # Can view basic analytics
        ActionType.BULK_OPERATION: ExecutionMode.RECOMMEND,  # Can recommend bulk actions

        # ─── Product-removed features ─────────────────────────────────
        ActionType.POST_SOCIAL: ExecutionMode.DENY,         # Social media removed from product
    },
    PARWA_HIGH: {
        # ─── Autonomous actions (High CAN execute ALL of these) ───────
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.SEND_SMS: ExecutionMode.EXECUTE,
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.EXECUTE,

        # ─── Financial actions (High CAN execute after approval gate) ──
        # Per docs: High makes strategic recommendations with risk-benefit
        # analysis. CAN execute financial actions after approval.
        ActionType.PROCESS_REFUND: ExecutionMode.EXECUTE,    # Strategic recommendation + execution
        ActionType.CANCEL_ORDER: ExecutionMode.EXECUTE,      # Strategic analysis + execution
        ActionType.MODIFY_ACCOUNT: ExecutionMode.EXECUTE,    # Can execute account changes

        # ─── Included premium features ────────────────────────────────
        ActionType.VOICE_CALL: ExecutionMode.EXECUTE,        # Included in High
        ActionType.ACCESS_ANALYTICS: ExecutionMode.EXECUTE,  # Included in High
        ActionType.BULK_OPERATION: ExecutionMode.EXECUTE,    # Included in High

        # ─── Product-removed features ─────────────────────────────────
        ActionType.POST_SOCIAL: ExecutionMode.DENY,         # Social media removed from product
    },
}


# ─── Approval-Required Actions (Core Approval Rules from Docs) ──────────────────
# Per docs: ALL variants ALWAYS require approval for these actions.
# This is the CONTROL SYSTEM (software layer) that enforces safety.
# Even PARWA High needs approval — the difference is High CAN execute
# after approval, while Mini/PARWA only PREPARE the request.

APPROVAL_REQUIRED_ACTIONS: frozenset[ActionType] = frozenset({
    ActionType.PROCESS_REFUND,      # Refunds — Any type, any amount
    ActionType.CANCEL_ORDER,        # Returns — Any item, any value
    ActionType.MODIFY_ACCOUNT,      # Account changes — billing, security, email
    ActionType.BULK_OPERATION,      # Bulk operations — multiple affected records
})


# ─── Complexity Score Routing (Per Docs v6.0 Smart Router) ─────────────────────

def calculate_complexity_score(ticket: dict) -> int:
    """Calculate complexity score for Smart Router routing.

    Per docs:
        score 0-4  → Light Tier (Gemma-4B)
        score 5-9  → Medium Tier (Gemini-Flash)
        score 10+  → Heavy Tier (DeepSeek-R1)

    Factors:
        +3 for refund/return/chargeback
        +2 for VIP customer
        +2 for amount > $100
        +2 for angry sentiment
        +4 for legal involvement
        +1 for long message (>100 words)
    """
    score = 0
    ticket_type = ticket.get("type", ticket.get("intent", "")).lower()
    customer_tier = ticket.get("customer_tier", "standard").lower()
    amount = ticket.get("amount", 0)
    sentiment = ticket.get("sentiment", "neutral").lower()
    involves_legal = ticket.get("involves_legal", False)
    message = ticket.get("message", ticket.get("raw_message", ""))

    if any(t in ticket_type for t in ["refund", "return", "chargeback"]):
        score += 3
    if customer_tier in ("vip", "premium", "enterprise"):
        score += 2
    if isinstance(amount, (int, float)) and amount > 100:
        score += 2
    if sentiment in ("angry", "furious"):
        score += 2
    if involves_legal:
        score += 4
    if isinstance(message, str) and len(message.split()) > 100:
        score += 1

    return score


def route_to_tier(score: int) -> str:
    """Route a complexity score to the appropriate model tier.

    Per docs v6.0:
        0-4  → Light  (google/gemma-3-4b-it:free)
        5-9  → Medium (google/gemini-2.0-flash-exp:free)
        10+  → Heavy  (deepseek/deepseek-r1-0528:free)
    """
    if score <= 4:
        return "light"
    elif score <= 9:
        return "medium"
    else:
        return "heavy"


# ─── Helper Functions ────────────────────────────────────────────────────────────

def get_permission(variant: str, action_type: ActionType) -> ExecutionMode:
    """Get the execution mode for an action type on a specific variant.

    EXECUTE   → Action runs immediately
    RECOMMEND → Variant collects info and recommends, but CANNOT execute.
                The request is prepared for manager review.
    DENY      → Feature not available on this variant or removed from product
    """
    if variant not in ACTION_PERMISSIONS:
        raise ValueError(f"Unknown variant: {variant}. Must be one of {VARIANT_NAMES}")
    return ACTION_PERMISSIONS[variant].get(action_type, ExecutionMode.EXECUTE)


def can_execute(variant: str, action_type: ActionType) -> bool:
    """Check if a variant can directly execute an action.

    Returns True only for EXECUTE mode.
    RECOMMEND means the variant PREPARES but CANNOT execute — needs approval.
    DENY means the feature is not available.
    """
    return get_permission(variant, action_type) == ExecutionMode.EXECUTE


def can_recommend(variant: str, action_type: ActionType) -> bool:
    """Check if a variant can at least recommend an action.

    Returns True for both EXECUTE and RECOMMEND modes.
    Only DENY returns False.
    """
    mode = get_permission(variant, action_type)
    return mode in (ExecutionMode.EXECUTE, ExecutionMode.RECOMMEND)


def requires_approval(action_type: ActionType) -> bool:
    """Check if an action requires approval before execution.

    Per docs: ALL variants ALWAYS require approval for:
    - Refunds, Returns, Account changes, Policy exceptions,
      VIP actions, Financial transactions

    The CONTROL SYSTEM (software layer) enforces these safety rules
    across ALL variants regardless of tier.
    """
    return action_type in APPROVAL_REQUIRED_ACTIONS


def get_variant_channels(variant: str) -> list[TicketChannel]:
    """Get the channels available for a variant."""
    if variant not in VARIANT_CONFIG:
        raise ValueError(f"Unknown variant: {variant}")
    return VARIANT_CONFIG[variant]["channels"]


def get_variant_config(variant: str) -> dict:
    """Get the full configuration for a variant."""
    if variant not in VARIANT_CONFIG:
        raise ValueError(f"Unknown variant: {variant}")
    return VARIANT_CONFIG[variant]


def get_variant_tiers(variant: str) -> list[str]:
    """Get the model tiers available for a variant.

    Mini -> light + guardrail only
    PARWA -> light + medium + guardrail
    High -> light + medium + heavy + guardrail
    """
    if variant not in VARIANT_MODEL_TIERS:
        raise ValueError(f"Unknown variant: {variant}")
    return VARIANT_MODEL_TIERS[variant]


def get_node_tier(node_name: str) -> str:
    """Get the model tier for a node.

    Returns 'light' as default if node not found.
    """
    return NODE_TIER_MAP.get(node_name, "light")


def get_model_for_node(node_name: str, variant: str = "parwa") -> str:
    """Get the best available model for a node given a variant.

    1. Determine which tier the node needs
    2. Check if variant has access to that tier
    3. If not, downgrade to highest available tier
    4. Return the primary model from the selected tier

    This is the core of the variant-aware Smart Router.
    """
    required_tier = get_node_tier(node_name)
    available_tiers = get_variant_tiers(variant)

    if required_tier in available_tiers:
        selected_tier = required_tier
    else:
        # Downgrade: pick the best tier that variant has access to
        tier_priority = ["heavy", "medium", "light"]
        selected_tier = "light"
        for tier in tier_priority:
            if tier in available_tiers:
                selected_tier = tier
                break

    models = MODEL_TIERS.get(selected_tier, MODEL_TIERS["light"])
    return models[0]


def get_all_models_for_node(node_name: str, variant: str = "parwa") -> list[str]:
    """Get all fallback models for a node given a variant.

    Returns the full fallback chain for the selected tier.
    """
    required_tier = get_node_tier(node_name)
    available_tiers = get_variant_tiers(variant)

    tier_priority = ["heavy", "medium", "light"]

    if required_tier in available_tiers:
        selected_tier = required_tier
    else:
        selected_tier = "light"
        for tier in tier_priority:
            if tier in available_tiers:
                selected_tier = tier
                break

    return MODEL_TIERS.get(selected_tier, MODEL_TIERS["light"])
