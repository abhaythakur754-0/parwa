"""
Per-Intent Prompt Templates (Core Module)

Lightweight prompt template system for intent-specific response generation.
Each of the 12 supported intents has a dedicated prompt template with
Jinja2-style ``{{variable}}`` rendering and version tracking.

This is the core module used by the classification and signal pipelines.
For the full-featured template service (CRUD, A/B testing, variant
overrides), see ``backend.app.services.prompt_template_service``.

Supported intents:
  refund, technical, billing, complaint, feature_request, general,
  cancellation, shipping, inquiry, escalation, account, feedback

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.logger import get_logger

logger = get_logger("prompt_templates")

# Regex for Jinja2-style ``{{variable}}`` and ``{{ variable }}`` placeholders
_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# ── All 12 supported intent types ───────────────────────────────────

ALL_INTENTS = [
    "refund",
    "technical",
    "billing",
    "complaint",
    "feature_request",
    "general",
    "cancellation",
    "shipping",
    "inquiry",
    "escalation",
    "account",
    "feedback",
]

# ── Data Class ──────────────────────────────────────────────────────


@dataclass
class PromptTemplate:
    """A single prompt template for an intent.

    Attributes:
        template_id: Unique identifier (e.g. ``refund_v1``).
        intent: The intent this template serves.
        template_text: The prompt body with ``{{variable}}`` markers.
        version: Semantic version for tracking changes.
        variables: List of ``{{var}}`` names found in template_text.
    """

    template_id: str
    intent: str
    template_text: str
    version: int = 1
    variables: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Auto-extract variable names from template_text."""
        if not self.variables and self.template_text:
            self.variables = _extract_variables(self.template_text)


# ── Built-in Templates for All 12 Intents ───────────────────────────

_BUILTIN_TEMPLATES: Dict[str, str] = {
    "refund": (
        "You are handling a refund request for {{company_name}}. "
        "The customer {{customer_name}} is requesting a refund for "
        "order {{order_id}} with an amount of {{amount}}. "
        "Verify the refund eligibility based on the refund policy. "
        "If approved, confirm the refund amount of {{amount}} and "
        "provide the estimated processing time of {{processing_time}}. "
        "If the refund cannot be processed, explain the reason and "
        "offer alternative solutions. Maintain an empathetic tone "
        "throughout the interaction."
    ),
    "technical": (
        "You are providing technical support for {{company_name}}. "
        "The customer {{customer_name}} is reporting: {{issue_description}}. "
        "The affected system/component is {{component}}. "
        "Error details: {{error_details}}. "
        "Provide step-by-step troubleshooting instructions. "
        "If the issue requires escalation, include relevant diagnostic "
        "information: {{diagnostic_info}}. "
        "Set expectations about resolution time: {{estimated_resolution}}. "
        "Use clear, non-technical language where possible."
    ),
    "billing": (
        "You are addressing a billing inquiry for {{company_name}}. "
        "The customer {{customer_name}} has a question about their "
        "{{billing_item}} on {{billing_date}}. "
        "Account: {{account_id}}, Plan: {{plan_name}}. "
        "Explain the charge clearly with a breakdown: {{charge_breakdown}}. "
        "If there is a billing error, confirm the correction amount "
        "of {{correction_amount}} and when it will be reflected. "
        "Provide next steps for any payment adjustments needed."
    ),
    "complaint": (
        "You are responding to a customer complaint at {{company_name}}. "
        "The customer {{customer_name}} has expressed dissatisfaction "
        "about: {{complaint_topic}}. "
        "Details of the complaint: {{complaint_details}}. "
        "This is the {{contact_count}} time the customer has "
        "contacted us about this issue. "
        "Acknowledge the frustration sincerely. Explain what "
        "corrective actions are being taken: {{corrective_actions}}. "
        "Offer a resolution: {{resolution_offer}}. "
        "Ensure the customer feels heard and valued throughout."
    ),
    "feature_request": (
        "You are handling a feature request for {{company_name}}. "
        "The customer {{customer_name}} has suggested: {{feature_description}}. "
        "The requested feature would help with: {{use_case}}. "
        "Acknowledge the suggestion positively. "
        "Check if this feature exists: {{feature_status}}. "
        "If available, explain how to use it. "
        "If planned, share timeline: {{planned_timeline}}. "
        "If not available, suggest alternatives: {{alternatives}}. "
        "Thank the customer for their input and offer to "
        "notify them of updates."
    ),
    "general": (
        "You are assisting a customer at {{company_name}}. "
        "The customer {{customer_name}} has a general inquiry: "
        "{{inquiry_text}}. "
        "Provide a clear, helpful response. If the inquiry "
        "requires detailed information, include: {{relevant_info}}. "
        "If further assistance is needed, suggest: {{next_steps}}. "
        "Maintain a professional yet warm tone. "
        "Keep the response concise and actionable."
    ),
    "cancellation": (
        "You are handling a cancellation request for {{company_name}}. "
        "The customer {{customer_name}} wants to cancel their "
        "{{subscription_type}} subscription ({{account_id}}). "
        "Reason for cancellation: {{cancellation_reason}}. "
        "Explain the cancellation process clearly. "
        "Detail what happens to: data ({{data_retention}}), "
        "remaining billing ({{remaining_billing}}), and access "
        "({{access_end_date}}). "
        "Offer retention options if applicable: {{retention_offers}}. "
        "Process the cancellation professionally without pressure."
    ),
    "shipping": (
        "You are addressing a shipping inquiry for {{company_name}}. "
        "The customer {{customer_name}} is inquiring about order "
        "{{order_id}}. "
        "Shipping method: {{shipping_method}}, "
        "Tracking number: {{tracking_number}}. "
        "Current status: {{shipment_status}}. "
        "Estimated delivery: {{estimated_delivery}}. "
        "If there is a shipping issue, explain: {{issue_details}} "
        "and provide resolution: {{shipping_resolution}}. "
        "Set clear expectations about next steps."
    ),
    "inquiry": (
        "You are answering a customer inquiry at {{company_name}}. "
        "The customer {{customer_name}} asks: {{question}}. "
        "Provide a thorough, organized response. "
        "Include relevant details: {{answer_details}}. "
        "If the inquiry references specific products or features, "
        "include: {{product_info}}. "
        "Anticipate follow-up questions and address them: "
        "{{anticipated_followups}}. "
        "Ensure the response is complete and actionable."
    ),
    "escalation": (
        "You are handling an escalated case at {{company_name}}. "
        "The customer {{customer_name}} ({{customer_tier}} tier) "
        "has requested escalation due to: {{escalation_reason}}. "
        "Previous attempts to resolve: {{previous_attempts}}. "
        "The issue has been open for: {{time_open}}. "
        "Acknowledge the customer's frustration and the wait time. "
        "Take personal ownership of the resolution. "
        "Provide a clear resolution plan: {{resolution_plan}}. "
        "Offer compensation if appropriate: {{compensation_offer}}. "
        "Ensure the customer feels their concern is prioritized."
    ),
    "account": (
        "You are helping with an account issue at {{company_name}}. "
        "The customer {{customer_name}} ({{account_id}}) "
        "needs help with: {{account_issue}}. "
        "Verify the customer's identity before making changes. "
        "If it is a password reset, provide secure steps: "
        "{{reset_instructions}}. "
        "If it is an access issue, check: {{access_details}}. "
        "If profile changes are needed, guide through: "
        "{{profile_update_steps}}. "
        "Ensure account security is maintained throughout."
    ),
    "feedback": (
        "You are receiving customer feedback at {{company_name}}. "
        "The customer {{customer_name}} ({{customer_tier}} tier) "
        "has shared: {{feedback_text}}. "
        "Feedback type: {{feedback_type}} (positive/negative/mixed). "
        "Thank the customer sincerely for their feedback. "
        "If positive, reinforce the positive experience. "
        "If negative, acknowledge and explain improvements: "
        "{{improvement_actions}}. "
        "If there are specific suggestions, address them: "
        "{{suggestion_response}}. "
        "Document the feedback for internal review."
    ),
}

# Default template for unknown/unrecognized intents
_DEFAULT_TEMPLATE = (
    "You are a helpful customer support agent at {{company_name}}. "
    "The customer {{customer_name}} has sent: {{message}}. "
    "Provide a clear, professional response addressing their concern. "
    "If you cannot fully resolve the issue, explain the next steps "
    "and offer to escalate to a specialist if needed."
)


# ── Utility ──────────────────────────────────────────────────────────


def _extract_variables(template_text: str) -> List[str]:
    """Extract all ``{{variable}}`` names from template text.

    Args:
        template_text: Template string with ``{{...}}`` markers.

    Returns:
        Sorted list of unique variable names found.
    """
    if not template_text:
        return []
    return sorted(set(_VARIABLE_PATTERN.findall(template_text)))


def _render_variables(
    template_text: str,
    variables: Dict[str, str],
) -> str:
    """Replace ``{{var}}`` placeholders with values.

    Missing variables are left as-is (BC-008: never crash).

    Args:
        template_text: Template string with ``{{...}}`` markers.
        variables: Mapping of variable name to replacement value.

    Returns:
        Rendered string with variables substituted.
    """
    if not template_text:
        return template_text

    missing: List[str] = []

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return str(variables[var_name])
        missing.append(var_name)
        return match.group(0)  # Leave as-is

    result = _VARIABLE_PATTERN.sub(_replacer, template_text)

    if missing:
        logger.warning(
            "prompt_template_missing_variables",
            missing_variables=missing,
            provided_variables=list(variables.keys()),
        )

    return result


# ── PromptTemplateManager ───────────────────────────────────────────


class PromptTemplateManager:
    """Manages per-intent prompt templates with version tracking.

    Features:
        - Templates for all 12 supported intents
        - Jinja2-style ``{{variable}}`` rendering
        - Default template for unknown intents
        - Version tracking per intent
        - Add custom templates at runtime

    BC-008: All public methods return safe defaults on error.
    """

    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}
        self._versions: Dict[str, int] = {}
        self._load_builtin_templates()

    def _load_builtin_templates(self) -> None:
        """Load all 12 built-in intent templates."""
        for intent, template_text in _BUILTIN_TEMPLATES.items():
            template_id = f"{intent}_v1"
            variables = _extract_variables(template_text)
            self._templates[intent] = PromptTemplate(
                template_id=template_id,
                intent=intent,
                template_text=template_text,
                version=1,
                variables=variables,
            )
            self._versions[intent] = 1

        logger.info(
            "prompt_templates_loaded",
            intent_count=len(self._templates),
        )

    def get_template(self, intent: str) -> PromptTemplate:
        """Get the template for a given intent.

        If the intent is not recognized, returns a default generic
        template (BC-008: never crash on unknown intent).

        Args:
            intent: The intent name (e.g. ``refund``, ``technical``).

        Returns:
            PromptTemplate for the intent, or a default template.
        """
        template = self._templates.get(intent)
        if template is not None:
            return template

        # BC-008: Return default template for unknown intents
        logger.info(
            "prompt_template_unknown_intent_using_default",
            intent=intent,
        )
        variables = _extract_variables(_DEFAULT_TEMPLATE)
        return PromptTemplate(
            template_id="default_v1",
            intent=intent,
            template_text=_DEFAULT_TEMPLATE,
            version=1,
            variables=variables,
        )

    def render_template(
        self,
        intent: str,
        variables: Optional[Dict[str, str]] = None,
    ) -> str:
        """Render a template by substituting ``{{variables}}``.

        D6-GAP-06 FIX: Handle None or empty variables dict gracefully.
        Missing variables are left as-is and a warning is logged.

        Args:
            intent: The intent name.
            variables: Mapping of variable name to value. None treated as {}.

        Returns:
            Rendered string with variables substituted.
        """
        try:
            template = self.get_template(intent)
            # D6-GAP-06: Normalize None to empty dict
            safe_variables = variables if variables else {}
            # Ensure all values are strings (BC-008)
            safe_variables = {k: str(v) for k, v in safe_variables.items()}
            return _render_variables(template.template_text, safe_variables)
        except Exception as exc:
            # BC-008: Never crash
            logger.error(
                "render_template_failed",
                intent=intent,
                error=str(exc),
            )
            safe_variables = variables if variables else {}
            safe_variables = {k: str(v) for k, v in safe_variables.items()}
            return _render_variables(_DEFAULT_TEMPLATE, safe_variables)

    def add_template(self, template: PromptTemplate) -> None:
        """Add or update a template for an intent.

        If a template already exists for the intent, the version is
        auto-incremented.

        Args:
            template: The PromptTemplate to add.
        """
        try:
            current_version = self._versions.get(template.intent, 0)
            new_version = current_version + 1
            template.version = new_version

            # Re-extract variables if not provided
            if not template.variables and template.template_text:
                template.variables = _extract_variables(
                    template.template_text,
                )

            self._templates[template.intent] = template
            self._versions[template.intent] = new_version

            logger.info(
                "prompt_template_added",
                intent=template.intent,
                version=new_version,
                variable_count=len(template.variables),
            )
        except Exception as exc:
            # BC-008: Never crash
            logger.error(
                "add_template_failed",
                intent=template.intent,
                error=str(exc),
            )

    def list_intents(self) -> List[str]:
        """List all intents with registered templates.

        Returns:
            Sorted list of intent names.
        """
        return sorted(self._templates.keys())

    def list_templates(self) -> List[PromptTemplate]:
        """List all registered templates.

        Returns:
            List of all PromptTemplate objects.
        """
        return list(self._templates.values())

    def get_version(self, intent: str) -> int:
        """Get the current version number for an intent's template.

        Args:
            intent: The intent name.

        Returns:
            Version number (0 if intent not found).
        """
        return self._versions.get(intent, 0)

    def has_template(self, intent: str) -> bool:
        """Check if a template exists for an intent.

        Args:
            intent: The intent name.

        Returns:
            True if a template exists for this intent.
        """
        return intent in self._templates
