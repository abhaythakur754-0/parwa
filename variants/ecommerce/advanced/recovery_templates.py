"""Recovery Message Templates.

Provides template management:
- Dynamic template generation
- Personalization tokens
- A/B template variants
- Multi-language support
- Brand customization
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import re

from variants.ecommerce.advanced.cart_recovery import RecoveryChannel


class TemplateVariant(str, Enum):
    """Template variant for A/B testing."""
    CONTROL = "control"
    URGENCY = "urgency"
    DISCOUNT = "discount"
    SOCIAL_PROOF = "social_proof"


@dataclass
class Template:
    """Message template."""
    template_id: str
    name: str
    channel: RecoveryChannel
    variant: TemplateVariant
    subject_template: str
    body_template: str
    language: str = "en"


class RecoveryTemplates:
    """Recovery message templates manager."""

    # Default templates by variant
    DEFAULT_TEMPLATES = {
        TemplateVariant.CONTROL: Template(
            template_id="default_control",
            name="Standard Recovery",
            channel=RecoveryChannel.EMAIL,
            variant=TemplateVariant.CONTROL,
            subject_template="You left items in your cart",
            body_template="""
Hi {{customer_name}},

You have {{item_count}} items waiting in your cart:
{{items_list}}

Total: {{cart_total}}

Complete your purchase: {{checkout_url}}

Thanks,
{{brand_name}}
"""
        ),
        TemplateVariant.URGENCY: Template(
            template_id="default_urgency",
            name="Urgency Recovery",
            channel=RecoveryChannel.EMAIL,
            variant=TemplateVariant.URGENCY,
            subject_template="Don't miss out! Your cart is waiting",
            body_template="""
Hi {{customer_name}},

Your items are selling fast! {{item_count}} items are still in your cart:
{{items_list}}

Total: {{cart_total}}

Act now before they're gone: {{checkout_url}}

{{brand_name}}
"""
        ),
        TemplateVariant.DISCOUNT: Template(
            template_id="default_discount",
            name="Discount Recovery",
            channel=RecoveryChannel.EMAIL,
            variant=TemplateVariant.DISCOUNT,
            subject_template="Complete your order with {{discount_percent}}% off!",
            body_template="""
Hi {{customer_name}},

We saved your cart! Use code {{discount_code}} for {{discount_percent}}% off:

{{items_list}}

Total: {{cart_total}}
You pay: {{discounted_total}}

Claim your discount: {{checkout_url}}

{{brand_name}}
"""
        ),
        TemplateVariant.SOCIAL_PROOF: Template(
            template_id="default_social",
            name="Social Proof Recovery",
            channel=RecoveryChannel.EMAIL,
            variant=TemplateVariant.SOCIAL_PROOF,
            subject_template="Popular items in your cart",
            body_template="""
Hi {{customer_name}},

These items are trending! Complete your order:

{{items_list}}
{{#items}}
- {{name}} ({{times_viewed}} people viewing)
{{/items}}

Total: {{cart_total}}

Join {{purchased_count}} happy customers: {{checkout_url}}

{{brand_name}}
"""
        )
    }

    # SMS templates (shorter)
    SMS_TEMPLATES = {
        TemplateVariant.CONTROL: Template(
            template_id="sms_control",
            name="SMS Standard",
            channel=RecoveryChannel.SMS,
            variant=TemplateVariant.CONTROL,
            subject_template="Cart Reminder",
            body_template="{{brand_name}}: You have {{item_count}} items in cart. Total: {{cart_total}}. Complete: {{checkout_url}}"
        ),
        TemplateVariant.URGENCY: Template(
            template_id="sms_urgency",
            name="SMS Urgency",
            channel=RecoveryChannel.SMS,
            variant=TemplateVariant.URGENCY,
            subject_template="Cart Expiring",
            body_template="{{brand_name}}: Your cart expires soon! {{item_count}} items waiting. {{checkout_url}}"
        ),
        TemplateVariant.DISCOUNT: Template(
            template_id="sms_discount",
            name="SMS Discount",
            channel=RecoveryChannel.SMS,
            variant=TemplateVariant.DISCOUNT,
            subject_template="Your Discount",
            body_template="{{brand_name}}: Use {{discount_code}} for {{discount_percent}}% off your cart! {{checkout_url}}"
        )
    }

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize template manager.

        Args:
            client_id: Client identifier
            config: Optional configuration
        """
        self.client_id = client_id
        self.config = config or {}
        self.brand_name = self.config.get("brand_name", "Our Store")
        self.default_language = self.config.get("language", "en")
        self._custom_templates: Dict[str, Template] = {}

    def get_template(
        self,
        channel: RecoveryChannel,
        variant: TemplateVariant,
        language: Optional[str] = None
    ) -> Template:
        """Get template for channel and variant.

        Args:
            channel: Communication channel
            variant: Template variant
            language: Language code

        Returns:
            Template
        """
        lang = language or self.default_language

        # Check custom templates first
        key = f"{channel.value}_{variant.value}_{lang}"
        if key in self._custom_templates:
            return self._custom_templates[key]

        # Get default template
        if channel == RecoveryChannel.SMS:
            return self.SMS_TEMPLATES.get(variant, self.SMS_TEMPLATES[TemplateVariant.CONTROL])

        return self.DEFAULT_TEMPLATES.get(variant, self.DEFAULT_TEMPLATES[TemplateVariant.CONTROL])

    def render_template(
        self,
        template: Template,
        context: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Render template with context.

        Args:
            template: Template to render
            context: Template context variables

        Returns:
            Tuple of (subject, body)
        """
        # Add brand name if not provided
        if "brand_name" not in context:
            context["brand_name"] = self.brand_name

        # Render subject
        subject = self._render_string(template.subject_template, context)

        # Render body
        body = self._render_string(template.body_template, context)

        return subject, body

    def add_custom_template(
        self,
        template: Template
    ) -> None:
        """Add custom template.

        Args:
            template: Custom template to add
        """
        key = f"{template.channel.value}_{template.variant.value}_{template.language}"
        self._custom_templates[key] = template

    def get_available_variants(
        self,
        channel: RecoveryChannel
    ) -> List[TemplateVariant]:
        """Get available template variants for channel.

        Args:
            channel: Communication channel

        Returns:
            List of available variants
        """
        if channel == RecoveryChannel.SMS:
            return list(self.SMS_TEMPLATES.keys())
        return list(self.DEFAULT_TEMPLATES.keys())

    def select_variant(
        self,
        customer_id: str,
        cart_value: float,
        attempt: int
    ) -> TemplateVariant:
        """Select best variant based on context.

        Args:
            customer_id: Customer identifier
            customer_id: Customer identifier
            cart_value: Cart total value
            attempt: Recovery attempt number

        Returns:
            Selected template variant
        """
        # A/B test assignment based on customer ID
        hash_val = hash(customer_id) % 4

        if attempt >= 2:
            # Use discount for later attempts
            return TemplateVariant.DISCOUNT

        if cart_value > 200:
            # High value: use urgency
            return TemplateVariant.URGENCY

        # Use hash-based selection for A/B test
        variants = [
            TemplateVariant.CONTROL,
            TemplateVariant.URGENCY,
            TemplateVariant.DISCOUNT,
            TemplateVariant.SOCIAL_PROOF
        ]
        return variants[hash_val]

    def _render_string(
        self,
        template_str: str,
        context: Dict[str, Any]
    ) -> str:
        """Render template string with context."""
        result = template_str

        # Simple mustache-style replacement
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))

        # Handle conditional blocks (simplified)
        # {{#key}}...{{/key}}
        for key in context.keys():
            start_marker = "{{#" + key + "}}"
            end_marker = "{{/" + key + "}}"

            if start_marker in result and end_marker in result:
                if context.get(key):
                    # Remove markers but keep content
                    result = result.replace(start_marker, "")
                    result = result.replace(end_marker, "")
                else:
                    # Remove entire block
                    start_idx = result.find(start_marker)
                    end_idx = result.find(end_marker) + len(end_marker)
                    result = result[:start_idx] + result[end_idx:]

        return result.strip()
