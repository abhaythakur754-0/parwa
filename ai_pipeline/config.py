"""Variant configurations for Mini PARWA, PARWA, and PARWA High.

Same Brain, Different Capacity.
All variants share identical AI (22 nodes, 6 agents, 7 frameworks).
The difference is Volume x Channels x Concurrency x Action Permissions.

Phase 7: Now includes real LiteLLM model tier definitions with
variant-aware model routing. Mini → Light tier, PARWA → Light+Medium,
High → Light+Medium+Heavy.
"""

from __future__ import annotations

from parwa.state import ActionType, ExecutionMode, TicketChannel


# ─── Variant Definitions ────────────────────────────────────────────────────────

MINI_PARWA = "mini"
PARWA = "parwa"
PARWA_HIGH = "high"

VARIANT_NAMES = {MINI_PARWA, PARWA, PARWA_HIGH}


# ─── Model Tier Definitions (Real LiteLLM Models) ────────────────────────────────
# These map to the actual LLM providers: Google AI, Groq, Cerebras
# LiteLLM auto-routes prefixes (gemini/, groq/, cerebras/) to the correct API key.

MODEL_TIERS = {
    "light": [
        "cerebras/llama-3.1-8b",          # Primary: fastest, cheapest
        "groq/llama-3.1-8b-instant",      # Fallback 1
        "gemini/gemma-3-27b-it",          # Fallback 2
    ],
    "medium": [
        "gemini/gemini-2.0-flash-lite",    # Primary: balanced speed/quality
        "gemini/gemini-2.0-flash",         # Fallback 1
        "groq/llama-3.3-70b-versatile",    # Fallback 2
        "groq/qwen3-32b",                  # Fallback 3
    ],
    "heavy": [
        "groq/llama-3.3-70b-versatile",    # Primary: most capable available
        "cerebras/llama-4-scout-17b-16e-instruct",  # Fallback 1
        "groq/llama-3.1-8b-instant",       # Fallback 2 (last resort)
    ],
    "guardrail": [
        "groq/llama-guard-4-12b",          # Safety checks on all responses
    ],
}

# Which tiers each variant can access
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
    "STRATEGY_PLANNER": "medium",
    # Action Agent (light/medium — structured work)
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


# ─── Variant Pricing & Capacity ─────────────────────────────────────────────────

VARIANT_CONFIG: dict[str, dict] = {
    MINI_PARWA: {
        "price_monthly": 999,
        "tickets_per_month": 500,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT],
        "concurrent_tickets": 3,
        "ai_resolution_rate": 0.60,
        "voice_addon_price": 199,
    },
    PARWA: {
        "price_monthly": 2499,
        "tickets_per_month": 2000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT],
        "concurrent_tickets": 4,
        "ai_resolution_rate": 0.75,
        "voice_addon_price": 199,
    },
    PARWA_HIGH: {
        "price_monthly": 4999,
        "tickets_per_month": 5000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT, TicketChannel.VOICE],
        "concurrent_tickets": 6,
        "ai_resolution_rate": 0.85,
        "voice_addon_price": 0,  # included
    },
}


# ─── Action Permission Matrix ───────────────────────────────────────────────────
# Mini PARWA: Execute basics + Recommend restricted
# PARWA: Execute all
# PARWA High: Execute all + analytics + bulk + custom

ACTION_PERMISSIONS: dict[str, dict[ActionType, ExecutionMode]] = {
    MINI_PARWA: {
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.PROCESS_REFUND: ExecutionMode.RECOMMEND,
        ActionType.CANCEL_ORDER: ExecutionMode.RECOMMEND,
        ActionType.MODIFY_ACCOUNT: ExecutionMode.RECOMMEND,
        ActionType.VOICE_CALL: ExecutionMode.DENY,       # add-on only
        ActionType.SEND_SMS: ExecutionMode.EXECUTE,      # SMS available on all
        ActionType.POST_SOCIAL: ExecutionMode.DENY,       # social media removed
        ActionType.BULK_OPERATION: ExecutionMode.DENY,
        ActionType.API_WEBHOOK: ExecutionMode.DENY,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.DENY,
        ActionType.ACCESS_ANALYTICS: ExecutionMode.DENY,
    },
    PARWA: {
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.PROCESS_REFUND: ExecutionMode.EXECUTE,
        ActionType.CANCEL_ORDER: ExecutionMode.EXECUTE,
        ActionType.MODIFY_ACCOUNT: ExecutionMode.EXECUTE,
        ActionType.VOICE_CALL: ExecutionMode.DENY,       # add-on only
        ActionType.SEND_SMS: ExecutionMode.EXECUTE,      # SMS available on all
        ActionType.POST_SOCIAL: ExecutionMode.DENY,      # social media removed
        ActionType.BULK_OPERATION: ExecutionMode.DENY,
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.EXECUTE,
        ActionType.ACCESS_ANALYTICS: ExecutionMode.DENY,
    },
    PARWA_HIGH: {
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.PROCESS_REFUND: ExecutionMode.EXECUTE,
        ActionType.CANCEL_ORDER: ExecutionMode.EXECUTE,
        ActionType.MODIFY_ACCOUNT: ExecutionMode.EXECUTE,
        ActionType.VOICE_CALL: ExecutionMode.EXECUTE,    # included
        ActionType.SEND_SMS: ExecutionMode.EXECUTE,      # SMS available on all
        ActionType.POST_SOCIAL: ExecutionMode.DENY,      # social media removed
        ActionType.BULK_OPERATION: ExecutionMode.EXECUTE,
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.EXECUTE,
        ActionType.ACCESS_ANALYTICS: ExecutionMode.EXECUTE,
    },
}


# ─── Helper Functions ────────────────────────────────────────────────────────────

def get_permission(variant: str, action_type: ActionType) -> ExecutionMode:
    """Get the execution mode for an action type on a specific variant.

    Args:
        variant: One of "mini", "parwa", "high"
        action_type: The action to check permissions for

    Returns:
        ExecutionMode: EXECUTE, RECOMMEND, or DENY
    """
    if variant not in ACTION_PERMISSIONS:
        raise ValueError(f"Unknown variant: {variant}. Must be one of {VARIANT_NAMES}")
    return ACTION_PERMISSIONS[variant].get(action_type, ExecutionMode.DENY)


def can_execute(variant: str, action_type: ActionType) -> bool:
    """Check if a variant can directly execute an action (vs recommend or deny)."""
    return get_permission(variant, action_type) == ExecutionMode.EXECUTE


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

    # Tier priority: heavy > medium > light
    tier_priority = ["heavy", "medium", "light"]

    if required_tier in available_tiers:
        selected_tier = required_tier
    else:
        # Downgrade: pick the best tier that variant has access to
        # that is still adequate for the task
        selected_tier = "light"  # default fallback
        for tier in tier_priority:
            if tier in available_tiers:
                selected_tier = tier
                break

    # Return primary model from selected tier
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
