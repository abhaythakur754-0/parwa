"""
Jarvis Service — Shared imports, state, and lazy service loaders.

All jarvis submodules import from here to avoid duplication.
"""

import asyncio
import json
import logging
import secrets
import concurrent.futures
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    ValidationError,
    RateLimitError,
    InternalError,
)
from database.models.jarvis import (
    JarvisSession,
    JarvisMessage,
    JarvisKnowledgeUsed,
    JarvisActionTicket,
)
from app.services.email_service import send_email
from app.core.email_renderer import render_email_template

logger = logging.getLogger("parwa.jarvis")

# ── Constants ──────────────────────────────────────────────────────

FREE_DAILY_LIMIT = 20
DEMO_DAILY_LIMIT = 500
DEMO_PACK_HOURS = 24
DEMO_CALL_DURATION_SECONDS = 180  # 3 minutes
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 3
MAX_CONTEXT_HISTORY_MESSAGES = 20  # Last N messages for AI context

# ── Lazy Service Loading Infrastructure ────────────────────────────

_service_cache: Dict[str, Any] = {}


def _get_service(service_name: str) -> Any:
    """Lazily import and cache a service module by name."""
    if service_name in _service_cache:
        return _service_cache[service_name]

    module_map = {
        "ai_service": "app.services.ai_service",
        "pii_scan": "app.services.pii_scan_service",
        "brand_voice": "app.services.brand_voice_service",
        "response_template": "app.services.response_template_service",
        "sentiment_technique_mapper": "app.services.sentiment_technique_mapper",
        "conversation": "app.services.conversation_service",
        "token_budget": "app.services.token_budget_service",
        "embedding": "app.services.embedding_service",
        "analytics": "app.services.analytics_service",
        "lead": "app.services.lead_service",
        "ticket": "app.services.ticket_service",
        "ticket_lifecycle": "app.services.ticket_lifecycle_service",
        "ticket_state_machine": "app.services.ticket_state_machine",
        "ticket_analytics": "app.services.ticket_analytics_service",
        "ticket_search": "app.services.ticket_search_service",
        "ticket_merge": "app.services.ticket_merge_service",
        "stale_ticket": "app.services.stale_ticket_service",
        "classification": "app.services.classification_service",
        "spam_detection": "app.services.spam_detection_service",
        "usage_tracking": "app.services.usage_tracking_service",
        "usage_burst_protection": "app.services.usage_burst_protection",
        "cost_protection": "app.services.cost_protection_service",
        "overage": "app.services.overage_service",
        "invoice": "app.services.invoice_service",
        "rate_limit": "app.services.rate_limit_service",
        "audit": "app.services.audit_service",
        "audit_log": "app.services.audit_log_service",
        "onboarding": "app.services.onboarding_service",
        "pricing": "app.services.pricing_service",
        "notification": "app.services.notification_service",
        "email": "app.services.email_service",
        "webhook": "app.services.webhook_service",
        "tag": "app.services.tag_service",
        "category": "app.services.category_service",
        "priority": "app.services.priority_service",
        "assignment": "app.services.assignment_service",
        "sla": "app.services.sla_service",
        "trigger": "app.services.trigger_service",
        "internal_note": "app.services.internal_note_service",
        "message": "app.services.message_service",
        "attachment": "app.services.attachment_service",
        "company": "app.services.company_service",
        "customer": "app.services.customer_service",
        "channel": "app.services.channel_service",
        "bulk_action": "app.services.bulk_action_service",
        "demo_billing": "app.services.demo_billing_service",
        "demo_usage": "app.services.demo_usage_service",
        "demo_knowledge": "app.services.demo_knowledge_base_service",
        "demo_variant": "app.services.demo_variant_bridge",
        "variant_orchestration": "app.services.variant_orchestration_service",
        "variant_capability": "app.services.variant_capability_service",
        "variant_limit": "app.services.variant_limit_service",
        "variant_instance": "app.services.variant_instance_service",
        "subscription": "app.services.subscription_service",
        "custom_field": "app.services.custom_field_service",
        "collision": "app.services.collision_service",
        "intent_technique_mapper": "app.services.intent_technique_mapper",
        "intent_prompt_templates": "app.services.intent_prompt_templates",
        "phone_otp": "app.services.phone_otp_service",
        "business_email_otp": "app.services.business_email_otp_service",
        "self_healing": "app.services.self_healing_service",
        "client_refund": "app.services.client_refund_service",
        "cross_channel": "app.services.cross_channel_service",
        "data_freshness": "app.services.data_freshness_service",
        "ooo_detection": "app.services.ooo_detection_service",
        "bounce_complaint": "app.services.bounce_complaint_service",
        "sms_channel": "app.services.sms_channel_service",
        "voice_channel": "app.services.voice_channel_service",
        "email_channel": "app.services.email_channel_service",
        "chat_widget": "app.services.chat_widget_service",
        "prompt_template": "app.services.prompt_template_service",
        "activity_log": "app.services.activity_log_service",
        "file_storage": "app.services.file_storage_service",
        "identity_resolution": "app.services.identity_resolution_service",
        "onboarding_jarvis": "app.services.onboarding_jarvis_service",
        "onboarding_jarvis_awareness": "app.services.onboarding_jarvis_awareness",
        "onboarding_jarvis_orchestrator": "app.services.onboarding_jarvis_orchestrator",
        "onboarding_jarvis_function_registry": "app.services.onboarding_jarvis_function_registry",
        "jarvis_proactive_injector": "app.services.jarvis_proactive_injector",
        "jarvis_safety_gate": "app.services.jarvis_safety_gate",
        "jarvis_cc": "app.services.jarvis_cc_service",
        "jarvis_knowledge": "app.services.jarvis_knowledge_service",
        "jarvis_function_registry": "app.services.jarvis_function_registry",
        "jarvis_event_dispatcher": "app.services.jarvis_event_dispatcher",
        "jarvis_product_commands": "app.services.jarvis_product_commands",
        "jarvis_pipeline_feedback": "app.services.jarvis_agents.pipeline_feedback",
        "provider_management": "app.services.provider_management_service",
        "entitlement": "app.services.entitlement_middleware",
        "spam_detection_service": "app.services.spam_detection_service",
        "verification": "app.services.verification_service",
        "password_reset": "app.services.password_reset_service",
        "mfa": "app.services.mfa_service",
        "session": "app.services.session_service",
        "api_key": "app.services.api_key_service",
        "proration": "app.services.proration_service",
        "anti_arbitrage": "app.services.anti_arbitrage_service",
        "client_factory": "app.services.client_factory",
        "webhook_ordering": "app.services.webhook_ordering_service",
        "webhook_processor": "app.services.webhook_processor",
        "webhook_action_processor": "app.services.webhook_action_processor",
        "incident": "app.services.incident_service",
        "template": "app.services.template_service",
        "custom_connector": "app.services.custom_connector_service",
        "rule_migration": "app.services.rule_migration_service",
        "shadow_mode": "app.services.shadow_mode_service",
        "openapi_importer": "app.services.openapi_importer_service",
        "approval": "app.services.approval_service",
        "training_data_isolation": "app.services.training_data_isolation",
        "brand_voice_service": "app.services.brand_voice_service",
        "response_template_service": "app.services.response_template_service",
        "token_budget_service": "app.services.token_budget_service",
        "embedding_service": "app.services.embedding_service",
        "usage_tracking_service": "app.services.usage_tracking_service",
        "audit_service": "app.services.audit_service",
        "audit_log_service": "app.services.audit_log_service",
        "lead_service": "app.services.lead_service",
        "ticket_service": "app.services.ticket_service",
        "ticket_lifecycle_service": "app.services.ticket_lifecycle_service",
        "ticket_state_machine": "app.services.ticket_state_machine",
        "ticket_analytics_service": "app.services.ticket_analytics_service",
        "ticket_search_service": "app.services.ticket_search_service",
        "ticket_merge_service": "app.services.ticket_merge_service",
        "stale_ticket_service": "app.services.stale_ticket_service",
        "classification_service": "app.services.classification_service",
        "spam_detection_service": "app.services.spam_detection_service",
        "usage_burst_protection": "app.services.usage_burst_protection",
        "cost_protection_service": "app.services.cost_protection_service",
        "overage_service": "app.services.overage_service",
        "invoice_service": "app.services.invoice_service",
        "rate_limit_service": "app.services.rate_limit_service",
        "onboarding_service": "app.services.onboarding_service",
        "pricing_service": "app.services.pricing_service",
        "notification_service": "app.services.notification_service",
        "email_service": "app.services.email_service",
        "webhook_service": "app.services.webhook_service",
        "tag_service": "app.services.tag_service",
        "category_service": "app.services.category_service",
        "priority_service": "app.services.priority_service",
        "assignment_service": "app.services.assignment_service",
        "sla_service": "app.services.sla_service",
        "trigger_service": "app.services.trigger_service",
        "internal_note_service": "app.services.internal_note_service",
        "message_service": "app.services.message_service",
        "attachment_service": "app.services.attachment_service",
        "company_service": "app.services.company_service",
        "customer_service": "app.services.customer_service",
        "channel_service": "app.services.channel_service",
        "bulk_action_service": "app.services.bulk_action_service",
    }

    module_path = module_map.get(service_name)
    if module_path is None:
        raise ValueError(f"Unknown service: {service_name}")

    import importlib
    module = importlib.import_module(module_path)
    _service_cache[service_name] = module
    return module


def _get_service_module(service_name: str) -> Any:
    """Alias for _get_service."""
    return _get_service(service_name)


def _clear_service_cache() -> None:
    """Clear the service cache (for testing)."""
    _service_cache.clear()
