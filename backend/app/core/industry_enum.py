"""
Industry Enum: Defines the industries the Variant Engine supports.

Each industry affects:
  - System prompts (tone, terminology, domain knowledge)
  - Available tools (Order Tracker for E-commerce, Shipment Tracker for Logistics)
  - Response formatting (technical for SaaS, warm for E-commerce)
  - Default routing behavior (which variant tier suits which queries)
  - Technique selection (different reasoning for different domains)

The 4 industries:
  ECOMMERCE  — Online retail, marketplaces, D2C brands
  LOGISTICS  — Shipping, warehousing, supply chain, freight
  SAAS       — Software companies, subscription services, tech platforms
  GENERAL    — Catch-all for industries not yet specialized

Why an enum instead of strings:
  - Type safety: IDEs catch typos at development time
  - Single source of truth: all code references this enum
  - Easy to extend: add a new industry in one place
  - Validation: reject unknown industries before they reach the pipeline
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Any


# ══════════════════════════════════════════════════════════════════
# INDUSTRY ENUM
# ══════════════════════════════════════════════════════════════════


class Industry(str, Enum):
    """Supported industries for the Variant Engine.

    Inherits from str + Enum so it's JSON-serializable and can be
    compared directly with string values: Industry.ECOMMERCE == "ecommerce"
    """

    ECOMMERCE = "ecommerce"
    LOGISTICS = "logistics"
    SAAS = "saas"
    GENERAL = "general"


# ══════════════════════════════════════════════════════════════════
# INDUSTRY METADATA
# ══════════════════════════════════════════════════════════════════

INDUSTRY_METADATA: Dict[str, Dict[str, Any]] = {
    Industry.ECOMMERCE.value: {
        "display_name": "E-Commerce",
        "description": "Online retail, marketplaces, D2C brands",
        "tone": "warm_friendly",
        "system_prompt_prefix": (
            "You are a customer service agent for an e-commerce business. "
            "You help customers with orders, returns, refunds, product inquiries, "
            "and shipping questions. Be warm, helpful, and solution-oriented."
        ),
        "available_tools": [
            "order_tracker",
            "shipment_tracker",
            "return_processor",
            "refund_calculator",
            "inventory_checker",
            "coupon_applier",
        ],
        "common_intents": [
            "order_status",
            "return_request",
            "refund_inquiry",
            "product_question",
            "shipping_delay",
            "payment_issue",
            "cancel_order",
            "track_shipment",
        ],
        "escalation_triggers": [
            "chargeback_threat",
            "legal_action",
            "repeated_complaint",
            "vip_customer",
        ],
        "default_variant_tier": "parwa",
        # E-commerce customers often need Pro-level context
    },
    Industry.LOGISTICS.value: {
        "display_name": "Logistics",
        "description": "Shipping, warehousing, supply chain, freight",
        "tone": "professional_precise",
        "system_prompt_prefix": (
            "You are a customer service agent for a logistics company. "
            "You help with shipment tracking, delivery scheduling, freight "
            "inquiries, warehouse issues, and supply chain questions. "
            "Be precise, factual, and time-sensitive."
        ),
        "available_tools": [
            "shipment_tracker",
            "delivery_scheduler",
            "freight_calculator",
            "warehouse_checker",
            "route_optimizer",
            "customs_checker",
        ],
        "common_intents": [
            "shipment_status",
            "delivery_schedule",
            "freight_quote",
            "customs_inquiry",
            "warehouse_issue",
            "route_change",
            "delay_notification",
            "proof_of_delivery",
        ],
        "escalation_triggers": [
            "perishable_goods_risk",
            "high_value_shipment",
            "regulatory_compliance",
            "safety_incident",
        ],
        "default_variant_tier": "parwa",
    },
    Industry.SAAS.value: {
        "display_name": "SaaS",
        "description": "Software companies, subscription services, tech platforms",
        "tone": "technical_helpful",
        "system_prompt_prefix": (
            "You are a customer service agent for a SaaS company. "
            "You help with account issues, billing questions, feature requests, "
            "bug reports, integration help, and subscription management. "
            "Be technical but accessible, and always offer next steps."
        ),
        "available_tools": [
            "account_manager",
            "subscription_manager",
            "feature_checker",
            "bug_tracker",
            "integration_helper",
            "usage_analyzer",
        ],
        "common_intents": [
            "billing_inquiry",
            "account_issue",
            "feature_request",
            "bug_report",
            "integration_help",
            "subscription_change",
            "api_question",
            "data_export",
        ],
        "escalation_triggers": [
            "data_loss_risk",
            "security_incident",
            "enterprise_customer",
            "churn_risk",
        ],
        "default_variant_tier": "parwa",
    },
    Industry.GENERAL.value: {
        "display_name": "General",
        "description": "Catch-all for industries not yet specialized",
        "tone": "professional_adaptable",
        "system_prompt_prefix": (
            "You are a helpful customer service agent. "
            "Assist the customer with their inquiry professionally and clearly. "
            "If the question falls outside your scope, escalate to a human."
        ),
        "available_tools": [
            "knowledge_search",
            "ticket_creator",
            "escalation_handler",
        ],
        "common_intents": [
            "general_inquiry",
            "complaint",
            "feedback",
            "information_request",
            "contact_request",
        ],
        "escalation_triggers": [
            "legal_threat",
            "safety_concern",
            "repeated_escalation",
        ],
        "default_variant_tier": "mini_parwa",
        # General defaults to Mini since no specialized tools needed
    },
}


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def validate_industry(industry: str) -> Industry:
    """Validate and convert a string to an Industry enum.

    Args:
        industry: String industry value to validate.

    Returns:
        Industry enum member.

    Raises:
        ValueError: If the industry string is not recognized.
    """
    try:
        return Industry(industry.lower().strip())
    except ValueError:
        valid = [i.value for i in Industry]
        raise ValueError(
            f"Unknown industry '{industry}'. Valid industries: {valid}"
        )


def get_industry_prompt(industry: str) -> str:
    """Get the system prompt prefix for an industry.

    Falls back to GENERAL if the industry is unknown.

    Args:
        industry: Industry string value.

    Returns:
        System prompt prefix string.
    """
    meta = INDUSTRY_METADATA.get(industry, INDUSTRY_METADATA[Industry.GENERAL.value])
    return meta.get("system_prompt_prefix", "")


def get_industry_tools(industry: str) -> List[str]:
    """Get the available tools for an industry.

    Falls back to GENERAL tools if the industry is unknown.

    Args:
        industry: Industry string value.

    Returns:
        List of tool identifier strings.
    """
    meta = INDUSTRY_METADATA.get(industry, INDUSTRY_METADATA[Industry.GENERAL.value])
    return meta.get("available_tools", [])


def get_industry_tone(industry: str) -> str:
    """Get the response tone for an industry.

    Falls back to GENERAL tone if the industry is unknown.

    Args:
        industry: Industry string value.

    Returns:
        Tone identifier string.
    """
    meta = INDUSTRY_METADATA.get(industry, INDUSTRY_METADATA[Industry.GENERAL.value])
    return meta.get("tone", "professional_adaptable")


def map_onboarding_industry_to_enum(onboarding_industry: str) -> Industry:
    """Map the 14 onboarding industries to the 4 Variant Engine industries.

    The onboarding flow has 14 options. The Variant Engine groups them
    into 4 specialized categories. This mapping bridges the two.

    Args:
        onboarding_industry: Industry string from onboarding.

    Returns:
        Industry enum member for the Variant Engine.
    """
    mapping = {
        # E-commerce group
        "ecommerce": Industry.ECOMMERCE,
        "retail": Industry.ECOMMERCE,
        "hospitality": Industry.ECOMMERCE,

        # Logistics group
        "logistics": Industry.LOGISTICS,

        # SaaS group
        "saas": Industry.SAAS,
        "technology": Industry.SAAS,
        "finance": Industry.SAAS,
        "healthcare": Industry.SAAS,
        "education": Industry.SAAS,

        # General group
        "real_estate": Industry.GENERAL,
        "manufacturing": Industry.GENERAL,
        "consulting": Industry.GENERAL,
        "agency": Industry.GENERAL,
        "nonprofit": Industry.GENERAL,
        "other": Industry.GENERAL,
    }

    return mapping.get(
        onboarding_industry.lower().strip(),
        Industry.GENERAL,
    )
