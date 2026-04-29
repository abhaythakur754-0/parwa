"""
Variant Feature Configuration (Mini Parwa Production)

Defines which features are available per variant tier.
Used by the variant gating middleware and UI components.

Mini Parwa Features (Tier 1):
- Basic AI Pipeline (Light model only)
- Ticket Management
- Knowledge Base (100 docs)
- Email Channel
- Live Chat Widget
- Shadow Mode
- Basic Analytics
- API Read-only

Excluded from Mini Parwa:
- Voice AI (Parwa+)
- SMS Channel (Parwa+)
- Custom System Prompts (Parwa+)
- Brand Voice (Parwa+)
- Quality Coach (High Parwa only)
- Outgoing Webhooks (High Parwa only)
"""

from enum import Enum
from typing import Dict, List, Set


class FeatureTier(str, Enum):
    """Feature availability tiers."""

    MINI_PARWA = "mini_parwa"
    PARWA = "parwa"
    HIGH_PARWA = "high_parwa"


# ── Feature Definitions ──────────────────────────────────────────────────────

# Features available at each tier (inheritance: higher tiers include lower)
VARIANT_FEATURES: Dict[str, Set[str]] = {
    "mini_parwa": {
        # Core Features
        "ticket_management",
        "ticket_create",
        "ticket_update",
        "ticket_close",
        "ticket_assign",
        "ticket_merge",
        "ticket_bulk_actions",
        # Channels
        "email_channel",
        "chat_widget",
        # AI Pipeline (Light model only)
        "ai_resolution",
        "ai_classification",
        "ai_sentiment",
        "ai_intent_detection",
        "ai_suggested_responses",
        "ai_kb_search",
        # AI Techniques (Tier 1 only)
        "technique_chain_of_thought",
        "technique_basic_react",
        # Knowledge Base
        "kb_upload",
        "kb_search",
        "kb_categories",
        # Authentication & Security
        "email_password_auth",
        "email_verification",
        "password_reset",
        "mfa_totp",
        "api_keys_readonly",
        "audit_logs",
        "rate_limiting",
        # Shadow Mode
        "shadow_mode",
        "shadow_preview",
        "shadow_approve_reject",
        "shadow_auto_execute",
        "shadow_log",
        # Billing
        "billing_monthly",
        "billing_yearly",
        "billing_upgrade",
        "billing_downgrade",
        "billing_cancel",
        "billing_invoices",
        # Analytics (Basic)
        "analytics_dashboard",
        "analytics_ticket_volume",
        "analytics_response_time",
        "analytics_agent_performance",
        # Settings
        "settings_company",
        "settings_user_management",
        "settings_notifications",
        "settings_branding_basic",
        # Industry Add-ons (optional)
        "industry_addons",
        "industry_ecommerce",
        "industry_saas",
        "industry_logistics",
        "industry_others",
    },
    "parwa": {
        # Inherits all Mini Parwa features PLUS:
        # Additional Channels
        "sms_channel",
        # AI Pipeline (Light + Medium models)
        "ai_model_medium",
        # AI Techniques (Tier 1 + 2)
        "technique_tree_of_thoughts",
        "technique_least_to_most",
        "technique_step_back",
        # RAG Advanced
        "rag_reranking",
        "rag_deep_search",
        # Custom Prompts
        "custom_system_prompts",
        "brand_voice",
        # API
        "api_readwrite",
        # Analytics (Advanced)
        "analytics_export",
        "analytics_reports",
        # Training
        "agent_training",
        "lightning_training",
        # Integrations
        "custom_integrations",
        "incoming_webhooks",
    },
    "high_parwa": {
        # Inherits all Parwa features PLUS:
        # Additional Channels
        "voice_ai_channel",
        # AI Pipeline (Light + Medium + Heavy models)
        "ai_model_heavy",
        # AI Techniques (All tiers)
        "technique_self_consistency",
        "technique_reflexion",
        "technique_universe_of_thoughts",
        "technique_crp",
        # Quality
        "quality_coach",
        "custom_guardrails",
        "ai_guardrails",
        # API
        "api_full",
        "outgoing_webhooks",
        # Analytics (Enterprise)
        "analytics_custom",
        "analytics_realtime",
        # Support
        "dedicated_csm",
        "premium_sla",
        "priority_routing",
    },
}


# ── Feature Restrictions (per variant) ───────────────────────────────────────

# Features explicitly BLOCKED for each tier
BLOCKED_FEATURES: Dict[str, Set[str]] = {
    "mini_parwa": {
        "voice_ai_channel",
        "sms_channel",
        "ai_model_medium",
        "ai_model_heavy",
        "technique_tree_of_thoughts",
        "technique_least_to_most",
        "technique_self_consistency",
        "technique_reflexion",
        "rag_reranking",
        "custom_system_prompts",
        "brand_voice",
        "api_readwrite",
        "api_full",
        "outgoing_webhooks",
        "custom_integrations",
        "quality_coach",
        "custom_guardrails",
        "analytics_export",
        "analytics_custom",
        "agent_training",
        "dedicated_csm",
    },
    "parwa": {
        "voice_ai_channel",
        "ai_model_heavy",
        "technique_self_consistency",
        "technique_reflexion",
        "quality_coach",
        "custom_guardrails",
        "api_full",
        "outgoing_webhooks",
        "dedicated_csm",
    },
    "high_parwa": set(),  # No restrictions
}


# ── Helper Functions ─────────────────────────────────────────────────────────


def get_variant_features(variant_type: str) -> Set[str]:
    """Get all features available for a variant (including inherited)."""
    return VARIANT_FEATURES.get(variant_type, VARIANT_FEATURES["mini_parwa"])


def is_feature_available(variant_type: str, feature: str) -> bool:
    """Check if a specific feature is available for a variant."""
    features = get_variant_features(variant_type)
    return feature in features


def is_feature_blocked(variant_type: str, feature: str) -> bool:
    """Check if a feature is explicitly blocked for a variant."""
    blocked = BLOCKED_FEATURES.get(variant_type, set())
    return feature in blocked


def get_blocked_features(variant_type: str) -> Set[str]:
    """Get all features blocked for a variant."""
    return BLOCKED_FEATURES.get(variant_type, set())


def get_upgrade_required_for_feature(variant_type: str, feature: str) -> List[str]:
    """Get list of variants that have access to a blocked feature."""
    if not is_feature_blocked(variant_type, feature):
        return []

    upgrade_options = []
    tier_order = ["mini_parwa", "parwa", "high_parwa"]
    current_idx = tier_order.index(variant_type)

    for tier in tier_order[current_idx + 1 :]:
        if is_feature_available(tier, feature):
            upgrade_options.append(tier)

    return upgrade_options


# ── Variant Limits (resource constraints) ────────────────────────────────────

VARIANT_LIMITS = {
    "mini_parwa": {
        "monthly_tickets": 2000,
        "ai_agents": 1,
        "team_members": 3,
        "voice_slots": 0,
        "kb_docs": 100,
        "model_tiers": ["light"],
        "technique_tiers": [1],
        "rag_top_k": 3,
        "api_access": "readonly",
    },
    "parwa": {
        "monthly_tickets": 5000,
        "ai_agents": 3,
        "team_members": 10,
        "voice_slots": 2,
        "kb_docs": 500,
        "model_tiers": ["light", "medium"],
        "technique_tiers": [1, 2],
        "rag_top_k": 5,
        "api_access": "readwrite",
    },
    "high_parwa": {
        "monthly_tickets": 15000,
        "ai_agents": 5,
        "team_members": 25,
        "voice_slots": 5,
        "kb_docs": 2000,
        "model_tiers": ["light", "medium", "heavy"],
        "technique_tiers": [1, 2, 3],
        "rag_top_k": 10,
        "api_access": "full",
    },
}


def get_variant_limit(variant_type: str, limit_name: str) -> int:
    """Get a specific limit value for a variant."""
    limits = VARIANT_LIMITS.get(variant_type, VARIANT_LIMITS["mini_parwa"])
    return limits.get(limit_name, 0)


def check_resource_limit(variant_type: str, resource: str, current_usage: int) -> dict:
    """Check if current usage is within limits for a resource."""
    limit = get_variant_limit(variant_type, resource)
    if limit == 0:
        return {
            "allowed": False,
            "reason": f"Resource '{resource}' not available for {variant_type}",
            "limit": 0,
            "current_usage": current_usage,
        }

    return {
        "allowed": current_usage < limit,
        "limit": limit,
        "current_usage": current_usage,
        "remaining": max(0, limit - current_usage),
        "utilization_pct": round((current_usage / limit) * 100, 2) if limit > 0 else 0,
    }
