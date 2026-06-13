"""Node 17v2: RESPONSE_FORMATTER_V2 — Context-aware, persona-based response builder.

Replaces the old rule-based response formatter with a system that:
- Determines customer persona from REAL CRM data (tier, LTV, sentiment)
- Builds responses using REAL customer data (names, orders, payments, tickets)
- Includes REAL action results (refund IDs, amounts, tracking numbers)
- Surfaces REAL FAQ/KB content (actual policy text, not generic filler)
- Weaves proactive insights naturally into responses
- Adapts tone and formality to customer tier and sentiment
- Handles Mini PARWA recommendations with human-readable approval requests
- Calm reassurance with specific escalation ticket IDs for escalated tickets
- Falls back gracefully when CRM data is unavailable

Phase 10: Persona-aware, CRM-grounded response generation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.response_formatter_v2")


# ─── Tier-based persona mapping ──────────────────────────────────────────────

_TIER_PERSONA: dict[str, str] = {
    "standard": "casual_friendly",
    "premium": "professional_attentive",
    "enterprise": "executive_formal",
}

# Sentiment-based tone mapping
_SENTIMENT_TONE: dict[str, str] = {
    "happy": "warm",
    "neutral": "professional",
    "frustrated": "empathetic_urgent",
    "angry": "calm_reassuring",
}

# LTV thresholds for proactive handling
_HIGH_LTV_THRESHOLD = 5000.0
_VERY_HIGH_LTV_THRESHOLD = 25000.0


# ─── CustomerPersona ─────────────────────────────────────────────────────────

@dataclass
class CustomerPersona:
    """Determines communication persona from CRM customer data.

    The persona controls:
    - Greeting style (casual vs formal)
    - Level of detail in responses
    - Whether proactive offers are included
    - Closing style and next-step suggestions
    - Tone adjustment based on sentiment

    Attributes:
        persona: The base communication style (casual_friendly, professional_attentive, executive_formal).
        tone: The sentiment-adjusted tone (warm, professional, empathetic_urgent, calm_reassuring).
        is_high_ltv: Whether the customer has high lifetime value.
        is_very_high_ltv: Whether the customer has very high lifetime value.
        tier: The raw CRM tier string.
        sentiment: The detected sentiment string.
        customer_name: The customer's first name for personalization.
        include_proactive_offers: Whether to include proactive suggestions/offers.
    """

    persona: str = "casual_friendly"
    tone: str = "professional"
    is_high_ltv: bool = False
    is_very_high_ltv: bool = False
    tier: str = "standard"
    sentiment: str = "neutral"
    customer_name: str = ""
    include_proactive_offers: bool = False

    @classmethod
    def from_crm_data(
        cls,
        customer: dict[str, Any] | None,
        sentiment: str = "neutral",
    ) -> "CustomerPersona":
        """Build a CustomerPersona from CRM customer data and pipeline sentiment.

        Args:
            customer: The CRM customer dict (from FakeCRM.get_customer), or None.
            sentiment: The sentiment detected by the pipeline.

        Returns:
            A fully populated CustomerPersona.
        """
        if customer is None:
            return cls(
                persona="casual_friendly",
                tone=_SENTIMENT_TONE.get(sentiment, "professional"),
                sentiment=sentiment,
            )

        tier = customer.get("tier", "standard")
        ltv = customer.get("lifetime_value", 0.0)
        name = customer.get("name", "")
        first_name = name.split()[0] if name else ""

        is_high_ltv = ltv >= _HIGH_LTV_THRESHOLD
        is_very_high_ltv = ltv >= _VERY_HIGH_LTV_THRESHOLD

        # Tier → persona
        persona = _TIER_PERSONA.get(tier, "casual_friendly")

        # Sentiment → tone
        tone = _SENTIMENT_TONE.get(sentiment, "professional")

        # High LTV customers get proactive offers and more detail
        include_proactive_offers = is_high_ltv

        return cls(
            persona=persona,
            tone=tone,
            is_high_ltv=is_high_ltv,
            is_very_high_ltv=is_very_high_ltv,
            tier=tier,
            sentiment=sentiment,
            customer_name=first_name,
            include_proactive_offers=include_proactive_offers,
        )


# ─── PersonaEngine ────────────────────────────────────────────────────────────

class PersonaEngine:
    """Builds persona-aware text fragments for response composition.

    The engine provides greeting, closing, amount formatting, and
    order status formatting — all adapted to the customer's persona.
    """

    # Greeting templates by persona
    _GREETINGS: dict[str, dict[str, str]] = {
        "casual_friendly": {
            "warm": "Hi {name}! Great to hear from you.",
            "professional": "Hi {name},",
            "empathetic_urgent": "Hi {name}, I completely understand your concern and I'm on it right away.",
            "calm_reassuring": "Hi {name}, I hear you and I'm here to help sort this out.",
        },
        "professional_attentive": {
            "warm": "Hello {name}, thank you for reaching out. It's a pleasure to assist you.",
            "professional": "Hello {name}, thank you for contacting us.",
            "empathetic_urgent": "Hello {name}, I understand the urgency of your concern. Let me address this immediately.",
            "calm_reassuring": "Hello {name}, I understand your frustration and I'm committed to resolving this for you.",
        },
        "executive_formal": {
            "warm": "Good day, {name}. Thank you for your continued partnership.",
            "professional": "Good day, {name}. Thank you for reaching out.",
            "empathetic_urgent": "Good day, {name}. I recognize the importance of this matter and am prioritizing it accordingly.",
            "calm_reassuring": "Good day, {name}. Please be assured that we are giving this matter our full attention.",
        },
    }

    # Fallback greetings when no name is available
    _GREETINGS_NO_NAME: dict[str, dict[str, str]] = {
        "casual_friendly": {
            "warm": "Hi there! Great to hear from you.",
            "professional": "Hi there,",
            "empathetic_urgent": "I understand your concern and I'm on it right away.",
            "calm_reassuring": "I hear you and I'm here to help sort this out.",
        },
        "professional_attentive": {
            "warm": "Thank you for reaching out. It's a pleasure to assist you.",
            "professional": "Thank you for contacting us.",
            "empathetic_urgent": "I understand the urgency of your concern. Let me address this immediately.",
            "calm_reassuring": "I understand your frustration and I'm committed to resolving this for you.",
        },
        "executive_formal": {
            "warm": "Thank you for your continued partnership.",
            "professional": "Thank you for reaching out.",
            "empathetic_urgent": "I recognize the importance of this matter and am prioritizing it accordingly.",
            "calm_reassuring": "Please be assured that we are giving this matter our full attention.",
        },
    }

    # Closing templates by persona
    _CLOSINGS: dict[str, dict[str, str]] = {
        "casual_friendly": {
            "default": "Let me know if there's anything else I can help with!",
            "with_insight": "Also, {insight} Let me know if you'd like more details!",
            "high_ltv": "As a valued customer, I want to make sure you're taken care of. {insight} Feel free to reach out anytime!",
        },
        "professional_attentive": {
            "default": "Please don't hesitate to reach out if you need any further assistance.",
            "with_insight": "Additionally, {insight} Please let me know if you'd like me to look into this for you.",
            "high_ltv": "As a Premium member, your satisfaction is our priority. {insight} I'm here whenever you need assistance.",
        },
        "executive_formal": {
            "default": "Should you require any further assistance, please do not hesitate to reach out.",
            "with_insight": "I would also like to note that {insight} Please let me know if you would like us to pursue this.",
            "high_ltv": "As a valued Enterprise partner, your account team remains at your disposal. {insight} We are committed to your continued success.",
        },
    }

    def __init__(self, persona: CustomerPersona) -> None:
        self.persona = persona

    def build_greeting(self, persona: CustomerPersona | None = None, customer_name: str = "") -> str:
        """Build an appropriate greeting based on persona and tone.

        Args:
            persona: Override persona (uses self.persona if None).
            customer_name: Override customer name (uses persona.customer_name if empty).

        Returns:
            A personalized greeting string.
        """
        p = persona or self.persona
        name = customer_name or p.customer_name
        templates = self._GREETINGS if name else self._GREETINGS_NO_NAME

        persona_templates = templates.get(p.persona, templates["casual_friendly"])
        greeting = persona_templates.get(p.tone, persona_templates.get("professional", ""))

        if name:
            greeting = greeting.format(name=name)

        return greeting

    def build_closing(self, persona: CustomerPersona | None = None, proactive_insights: list[dict] | None = None) -> str:
        """Build a proactive closing with next steps.

        The closing naturally weaves in proactive insights when available
        and the customer's persona supports it (high LTV always gets them).

        Args:
            persona: Override persona (uses self.persona if None).
            proactive_insights: List of proactive insight dicts from the pipeline.

        Returns:
            A closing string, possibly with proactive suggestions.
        """
        p = persona or self.persona
        insights = proactive_insights or []

        closings = self._CLOSINGS.get(p.persona, self._CLOSINGS["casual_friendly"])

        # Build insight text from the top insight (if any)
        insight_text = ""
        if insights:
            top = insights[0]
            desc = top.get("description", "")
            if desc and top.get("confidence", 0) > 0.4:
                insight_text = desc.rstrip(".") + "."

        # Pick closing template
        if insight_text and (p.include_proactive_offers or p.is_high_ltv):
            closing = closings.get("high_ltv" if p.is_high_ltv else "with_insight", closings["default"])
            closing = closing.format(insight=insight_text)
        elif insight_text:
            closing = closings["with_insight"].format(insight=insight_text)
        else:
            closing = closings["default"]

        return closing

    @staticmethod
    def format_amount(amount: float | int | str) -> str:
        """Format a numeric amount as proper currency.

        Args:
            amount: The amount to format (float, int, or string representation).

        Returns:
            A properly formatted currency string like "$189.99".
        """
        try:
            val = float(amount)
            return f"${val:,.2f}"
        except (ValueError, TypeError):
            return str(amount)

    @staticmethod
    def format_order_status(order: dict[str, Any]) -> str:
        """Format a detailed order status with all available data.

        Includes order ID, items, status, tracking number, estimated delivery.

        Args:
            order: An order dict from the CRM.

        Returns:
            A human-readable order status string.
        """
        parts: list[str] = []

        order_id = order.get("order_id", "")
        if order_id:
            parts.append(f"Order {order_id}")

        items = order.get("items", [])
        if items:
            item_str = ", ".join(items)
            if len(item_str) > 80:
                item_str = item_str[:77] + "..."
            parts.append(f"Items: {item_str}")

        status = order.get("status", "unknown")
        status_display = status.replace("_", " ").title()
        parts.append(f"Status: {status_display}")

        tracking = order.get("tracking")
        if tracking:
            parts.append(f"Tracking: {tracking}")

        est_delivery = order.get("estimated_delivery")
        if est_delivery:
            parts.append(f"Estimated delivery: {est_delivery}")

        total = order.get("total")
        if total is not None:
            parts.append(f"Total: {PersonaEngine.format_amount(total)}")

        return " | ".join(parts)


# ─── ContextAwareResponse ────────────────────────────────────────────────────

class ContextAwareResponse:
    """Builds context-aware responses using real CRM data and pipeline results.

    This is the core response builder. It takes the pipeline state, CRM
    customer data, and persona to produce a response that includes:
    - Real customer data (name, orders, payments, tickets)
    - Real action results (refund amounts, payment IDs, cancellation confirmations)
    - Real FAQ/KB content (actual policy text)
    - Real proactive insights (shipping delays, related issues)
    """

    def __init__(self, state: dict[str, Any], persona: CustomerPersona) -> None:
        self.state = state
        self.persona = persona
        self.engine = PersonaEngine(persona)

        # Extract commonly used state fields
        self.intent = state.get("intent", "general_inquiry")
        self.execution_results = state.get("execution_results", [])
        self.recommendation = state.get("recommendation")
        self.proactive_insights = state.get("proactive_insights", [])
        self.reasoning_conclusion = state.get("reasoning_conclusion", "")
        self.variant = state.get("variant", "parwa")
        self.customer_id = state.get("customer_id", "")

        # Load CRM data
        self.customer: dict[str, Any] | None = None
        self._load_crm_data()

    def _load_crm_data(self) -> None:
        """Load customer data from CRM. Sets self.customer to None on failure."""
        if not self.customer_id or self.customer_id == "default":
            return

        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            self.customer = crm.get_customer(self.customer_id)
        except (ImportError, ValueError, Exception) as exc:
            logger.warning("response_formatter_v2: Could not load CRM data for %s: %s", self.customer_id, exc)
            self.customer = None

    def _get_first_name(self) -> str:
        """Get the customer's first name, with fallback."""
        name = ""
        if self.customer:
            name = self.customer.get("name", "")
        if not name:
            name = self.persona.customer_name
        return name.split()[0] if name else ""

    def _find_execution_result(self, action_type: str) -> dict[str, Any] | None:
        """Find the first execution result matching an action type."""
        for r in self.execution_results:
            if r.get("action_type") == action_type:
                return r
        return None

    def _get_relevant_order(self) -> dict[str, Any] | None:
        """Get the most relevant order for the current intent from CRM data."""
        if not self.customer:
            return None

        orders = self.customer.get("orders", [])
        if not orders:
            return None

        # For order_status/cancellation, find the most recent non-delivered order
        if self.intent in ("order_status", "cancellation"):
            for order in reversed(orders):
                if order.get("status") in ("processing", "shipped"):
                    return order
            # Fall back to most recent
            return orders[-1]

        # For billing/refund, find orders with payments
        return orders[-1]

    def _get_relevant_payment(self) -> dict[str, Any] | None:
        """Get the most relevant payment from CRM data."""
        if not self.customer:
            return None

        payments = self.customer.get("payments", [])
        if not payments:
            return None

        # For refund: find duplicate or failed payments
        if self.intent == "refund_request":
            try:
                from parwa.fake_crm.database import get_crm
                crm = get_crm()
                duplicates = crm.find_duplicate_payments(self.customer_id)
                if duplicates:
                    return duplicates[0][1]  # Second payment in the duplicate pair
            except Exception:
                pass
            # Fall back to most recent completed payment
            for p in reversed(payments):
                if p.get("status") == "completed":
                    return p

        # For billing: find failed or pending payments
        if self.intent == "billing_issue":
            for p in reversed(payments):
                if p.get("status") in ("failed", "pending"):
                    return p

        # Default: most recent payment
        return payments[-1]

    def _get_escalation_ticket_id(self) -> str:
        """Get the escalation ticket ID from execution results."""
        esc_result = self._find_execution_result("escalate_to_human")
        if esc_result:
            details = esc_result.get("details", {})
            tid = details.get("escalation_ticket_id")
            if tid:
                return tid
        # Generate a stable one from state if not found
        return f"ESC-{uuid.uuid4().hex[:6].upper()}"

    def _get_faq_content(self) -> str:
        """Get actual FAQ answer text from execution results or CRM search."""
        # First check execution results for shared FAQ content
        faq_result = self._find_execution_result("share_faq")
        if faq_result:
            params = faq_result.get("parameters", {})
            content = params.get("content", "")
            if content and len(content) > 20:
                return content

        # Check KB results in state
        kb_results = self.state.get("kb_results", [])
        if kb_results:
            best = kb_results[0] if isinstance(kb_results[0], dict) else {}
            content = best.get("content", "")
            if content and len(content) > 20:
                return content

        # Search CRM FAQs using the customer's actual question
        # (not just the intent label, which won't match FAQ keywords)
        if self.customer_id and self.customer_id != "default":
            try:
                from parwa.fake_crm.database import get_crm
                crm = get_crm()
                # Use the raw message as the FAQ search query — it contains
                # the actual question the customer is asking
                raw_msg = self.state.get("raw_message", "")
                query = raw_msg[:100] if raw_msg else self.intent.replace("_", " ")
                faqs = crm.search_faqs(query, top_k=1)
                if faqs:
                    return faqs[0].get("answer", "")
            except Exception:
                pass

        return ""

    def _get_kb_troubleshooting(self) -> str:
        """Get KB troubleshooting steps for technical support intents."""
        # Check KB results in state
        kb_results = self.state.get("kb_results", [])
        if kb_results:
            for result in kb_results:
                result_dict = result if isinstance(result, dict) else {}
                content = result_dict.get("content", "")
                if content and len(content) > 20:
                    title = result_dict.get("title", "")
                    if title:
                        return f"**{title}**: {content}"
                    return content

        # Search CRM KB
        if self.customer_id and self.customer_id != "default":
            try:
                from parwa.fake_crm.database import get_crm
                crm = get_crm()
                raw_msg = self.state.get("raw_message", "")
                query = raw_msg[:100] if raw_msg else self.intent.replace("_", " ")
                articles = crm.search_kb(query, top_k=1)
                if articles:
                    article = articles[0]
                    title = article.get("title", "")
                    content = article.get("content", "")
                    if title and content:
                        return f"**{title}**: {content}"
                    if content:
                        return content
            except Exception:
                pass

        return ""

    def _get_product_name_from_message(self) -> str:
        """Try to extract a product name from the customer's message or orders."""
        if self.customer:
            orders = self.customer.get("orders", [])
            for order in reversed(orders):
                items = order.get("items", [])
                if items:
                    return items[0]

        # Try matching known products from the message
        raw = self.state.get("raw_message", "").lower()
        known_products = [
            "Premium Headphones", "USB-C Cable", "Wireless Charger", "Laptop Stand",
            "Bluetooth Speaker", "Smart Watch", "Mechanical Keyboard", "Mouse Pad",
            "Portable Monitor", "Design Software License", "Plugin Pack",
            "Cloud Storage",
        ]
        for product in known_products:
            if product.lower() in raw:
                return product

        return "your product"

    # ─── Intent-specific response builders ─────────────────────────────────

    def _build_refund_response(self) -> str:
        """Build response for refund_request intent using real CRM data."""
        parts: list[str] = []
        name = self._get_first_name()
        p = self.persona

        # Greeting
        parts.append(self.engine.build_greeting())

        # Core refund info
        refund_result = self._find_execution_result("process_refund")
        payment = self._get_relevant_payment()

        if self.recommendation and self.recommendation.get("pending_approval"):
            # Mini PARWA: pending approval
            amount = self.recommendation.get("parameters", {}).get("amount", 0)
            amount_str = self.engine.format_amount(amount)
            reason = self.recommendation.get("parameters", {}).get("reason", "duplicate charge")

            if reason == "duplicate_charge" and payment:
                parts.append(
                    f"I've confirmed the duplicate charge of {amount_str} on your "
                    f"payment ({payment.get('payment_id', 'N/A')}) from "
                    f"{payment.get('date', 'recently')}. "
                    f"I've submitted a refund for your approval — once approved, "
                    f"the {amount_str} will be returned to your original payment method "
                    f"within 3-5 business days."
                )
            else:
                parts.append(
                    f"I've verified your eligibility for a refund of {amount_str} "
                    f"and submitted it for approval. You'll receive confirmation within 2 hours."
                )
        elif refund_result and refund_result.get("status") == "executed":
            # Full PARWA: refund was actually executed
            details = refund_result.get("details", {})
            refund_id = details.get("refund_id", "")
            amount = details.get("amount", 0)
            payment_id = details.get("payment_id", "")
            amount_str = self.engine.format_amount(amount)

            core = f"Your refund of {amount_str} has been processed"
            if payment_id:
                core += f" (reference: {payment_id})"
            core += "."

            if refund_id:
                core += f" Refund ID: {refund_id}."

            core += " The refund will appear on your statement within 3-5 business days."
            parts.append(core)

            # High LTV: add proactive goodwill
            if p.is_high_ltv:
                parts.append(
                    "As a valued customer, we want to make this right. "
                    "If you have any questions about the refund timeline, I'm happy to follow up personally."
                )
        elif refund_result and refund_result.get("status") == "failed":
            already = refund_result.get("message", "")
            if "already" in already.lower():
                parts.append(f"Good news — it looks like this refund has already been processed. {already}")
            else:
                parts.append(
                    f"I attempted to process your refund but encountered an issue: {already} "
                    f"I've flagged this for our team to resolve manually."
                )
        else:
            # Fallback: no execution result, use CRM data
            if payment:
                amount_str = self.engine.format_amount(payment.get("amount", 0))
                parts.append(
                    f"I've reviewed your account and found the payment of {amount_str} "
                    f"from {payment.get('date', 'recently')}. "
                    f"Your refund request is being processed and will be reflected within 3-5 business days."
                )
            else:
                parts.append(
                    "Your refund request has been received and is being processed. "
                    "The refund will appear on your statement within 3-5 business days."
                )

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_order_status_response(self) -> str:
        """Build response for order_status intent using real CRM data."""
        parts: list[str] = []

        # Greeting
        parts.append(self.engine.build_greeting())

        order = self._get_relevant_order()

        if order:
            order_status = self.engine.format_order_status(order)
            status = order.get("status", "unknown")

            if status == "delivered":
                parts.append(f"Great news! Your order has been delivered. Here are the details: {order_status}")
            elif status == "shipped":
                tracking = order.get("tracking", "")
                est = order.get("estimated_delivery", "")
                msg = f"Your order is on its way! {order_status}"
                if est:
                    msg += f" You can expect delivery by {est}."
                parts.append(msg)
            elif status == "processing":
                parts.append(
                    f"Your order is currently being prepared. {order_status} "
                    f"You'll receive a tracking number once it ships."
                )
            elif status == "cancelled":
                parts.append(f"This order has been cancelled. {order_status}")
            elif status == "returned":
                parts.append(f"This order was returned. {order_status}")
            else:
                parts.append(f"Here's the latest on your order: {order_status}")
        else:
            # Try to get order status from execution results
            status_result = self._find_execution_result("cancel_order")
            if not status_result:
                # Use integration_data from the pipeline
                integration_data = self.state.get("integration_data", {})
                orders_data = integration_data.get("orders", [])
                if orders_data:
                    o = orders_data[0]
                    parts.append(
                        f"Here's the latest on your order: "
                        f"Order {o.get('order_id', 'N/A')} — Status: {o.get('status', 'unknown').title()}"
                    )
                else:
                    parts.append(
                        "I've looked into your order status. Based on our records, "
                        "your order is being processed. I'll make sure you get a tracking "
                        "update as soon as it ships."
                    )

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_cancellation_response(self) -> str:
        """Build response for cancellation intent using real CRM data."""
        parts: list[str] = []
        p = self.persona

        # Greeting
        parts.append(self.engine.build_greeting())

        cancel_result = self._find_execution_result("cancel_order")
        order = self._get_relevant_order()

        if self.recommendation and self.recommendation.get("pending_approval"):
            # Mini PARWA: pending approval
            order_id = self.recommendation.get("parameters", {}).get("order_id", "")
            if not order_id and order:
                order_id = order.get("order_id", "")

            items_str = ""
            if order:
                items_str = " (" + ", ".join(order.get("items", [])) + ")"

            parts.append(
                f"I've submitted your cancellation request for order {order_id}{items_str} "
                f"for approval. You'll be notified once it's processed."
            )

            # Mention refund if applicable
            if order and order.get("total"):
                amount_str = self.engine.format_amount(order["total"])
                parts.append(
                    f"Upon approval, a refund of {amount_str} will be issued to your original payment method."
                )

        elif cancel_result and cancel_result.get("status") == "executed":
            order_id = ""
            items_str = ""
            total_str = ""

            if order:
                order_id = order.get("order_id", "")
                items_str = ", ".join(order.get("items", []))
                if order.get("total"):
                    total_str = self.engine.format_amount(order["total"])

            # Try to get order_id from result
            if not order_id:
                params = cancel_result.get("parameters", {})
                order_id = params.get("order_id", "")

            msg = "Your order has been cancelled successfully."
            if order_id:
                msg = f"Order {order_id} has been cancelled successfully."
            if items_str:
                msg = f"Your order for {items_str} (Order {order_id}) has been cancelled successfully."
            parts.append(msg)

            if total_str:
                parts.append(
                    f"A refund of {total_str} will be processed and returned to your "
                    f"original payment method within 3-5 business days."
                )

            # High LTV: offer alternatives
            if p.include_proactive_offers:
                parts.append(
                    "If you'd like to place a new order or explore alternatives, "
                    "I'd be happy to help."
                )

        elif cancel_result and cancel_result.get("status") == "failed":
            reason = cancel_result.get("message", "the order cannot be cancelled at this stage")
            parts.append(
                f"I wasn't able to cancel the order: {reason} "
                f"I've flagged this for our team to review and they'll follow up with you."
            )
        else:
            parts.append(
                "Your cancellation request has been received. We'll process it and "
                "send you a confirmation email shortly."
            )

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_account_modification_response(self) -> str:
        """Build response for account_modification intent using real CRM data."""
        parts: list[str] = []

        # Greeting
        parts.append(self.engine.build_greeting())

        mod_result = self._find_execution_result("modify_account")

        if self.recommendation and self.recommendation.get("pending_approval"):
            params = self.recommendation.get("parameters", {})
            changes_desc = self._describe_account_changes(params)
            parts.append(
                f"I've submitted your account modification request ({changes_desc}) "
                f"for approval. You'll be notified once it's processed."
            )

        elif mod_result and mod_result.get("status") == "executed":
            details = mod_result.get("details", [])
            if isinstance(details, list) and details:
                change_list = "; ".join(str(d) for d in details)
                parts.append(f"Your account has been updated: {change_list}")
            else:
                # Build from parameters
                params = mod_result.get("parameters", {})
                changes_desc = self._describe_account_changes(params)
                parts.append(f"Your account has been updated successfully: {changes_desc}")

            # Confirmation for specific changes
            params = mod_result.get("parameters", {})
            if "email" in params:
                parts.append(f"Your email has been changed to {params['email']}.")
            if "phone" in params:
                parts.append(f"Your phone number has been updated to {params['phone']}.")
            if "plan" in params:
                parts.append(f"Your subscription plan has been changed to {params['plan']}.")
            if "reactivate" in params:
                parts.append("Your account has been reactivated and is now active.")
            if "reset_password" in params:
                parts.append("A password reset link has been sent to your registered email address.")

        elif mod_result and mod_result.get("status") == "failed":
            parts.append(
                "I encountered an issue updating your account. "
                "Our team has been notified and will follow up with you shortly."
            )
        else:
            parts.append("Your account modification has been processed successfully.")

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_billing_issue_response(self) -> str:
        """Build response for billing_issue intent using real CRM data."""
        parts: list[str] = []
        p = self.persona

        # Greeting
        parts.append(self.engine.build_greeting())

        payment = self._get_relevant_payment()

        if payment:
            amount_str = self.engine.format_amount(payment.get("amount", 0))
            method = payment.get("method", "").replace("_", " ")
            card_last4 = payment.get("card_last4", "")
            status = payment.get("status", "")
            date = payment.get("date", "recently")
            failure_reason = payment.get("failure_reason", "")

            if status == "failed":
                msg = (
                    f"I can see the failed payment of {amount_str} on {date} "
                    f"via {method}"
                )
                if card_last4:
                    msg += f" ending in {card_last4}"
                msg += "."
                if failure_reason:
                    msg += f" The reason was: {failure_reason}."
                parts.append(msg)

                # Offer resolution
                if card_last4:
                    parts.append(
                        f"I'd recommend updating the card ending in {card_last4} or "
                        f"trying an alternative payment method."
                    )

                # Check if account is suspended
                if self.customer and self.customer.get("account_status") == "suspended":
                    parts.append(
                        "I also see your account is currently suspended due to the payment failure. "
                        "Once the payment issue is resolved, I can reactivate your account immediately."
                    )

            elif status == "pending":
                parts.append(
                    f"I can see a pending payment of {amount_str} on your account from {date} "
                    f"via {method}. This is still being processed."
                )
            else:
                parts.append(
                    f"I've reviewed your billing. The most recent payment of {amount_str} "
                    f"on {date} via {method} shows as {status}."
                )
                if card_last4:
                    parts.append(f"The charge was on card ending in {card_last4}.")

            # High LTV: proactive credit offer
            if p.is_high_ltv and status == "failed":
                parts.append(
                    "As a valued customer, I'd like to offer a complimentary month of service "
                    "while we get this resolved. Shall I apply that to your account?"
                )
        else:
            parts.append(
                "I've reviewed your billing concerns. Our team will investigate the charges "
                "and get back to you within 24 hours with a detailed breakdown."
            )

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_technical_support_response(self) -> str:
        """Build response for technical_support intent using real CRM data."""
        parts: list[str] = []
        p = self.persona

        # Greeting
        parts.append(self.engine.build_greeting())

        # Identify the specific product
        product = self._get_product_name_from_message()

        parts.append(f"I understand you're having an issue with {product}. Let me help you with this.")

        # Get KB troubleshooting steps
        troubleshooting = self._get_kb_troubleshooting()
        if troubleshooting:
            parts.append(f"Here's what I found that should help: {troubleshooting}")
        else:
            parts.append(
                "I've analyzed the issue and our team is working on a resolution. "
                "Here are some initial steps you can try:"
            )
            parts.append(
                "1. Make sure you're using the latest version.\n"
                "2. Try clearing your cache and restarting.\n"
                "3. If the issue persists, let me know and I'll escalate to our technical team."
            )

        # Check for open tickets about the same issue
        if self.customer:
            open_tickets = [
                t for t in self.customer.get("tickets", [])
                if t.get("status") == "open"
            ]
            if open_tickets:
                ticket_ids = ", ".join(t.get("ticket_id", "") for t in open_tickets)
                parts.append(
                    f"I also see you have open ticket(s) ({ticket_ids}) related to this — "
                    f"I'll make sure they're connected so our team has full context."
                )

        # High LTV: priority support
        if p.is_high_ltv:
            parts.append(
                "As a priority customer, I've flagged this for our senior technical team "
                "who will follow up with you directly."
            )

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_faq_response(self) -> str:
        """Build response for faq_question intent using real FAQ content."""
        parts: list[str] = []

        # Greeting
        parts.append(self.engine.build_greeting())

        # Get actual FAQ answer text
        faq_content = self._get_faq_content()

        if faq_content:
            parts.append(faq_content)
        else:
            parts.append(
                "I've looked into your question. While I don't have a specific article for that, "
                "I'm happy to help — could you provide a bit more detail so I can give you the most accurate answer?"
            )

        # Closing
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    def _build_complaint_response(self) -> str:
        """Build response for complaint intent with empathy and specific acknowledgment."""
        parts: list[str] = []
        p = self.persona

        # Greeting (always empathetic for complaints)
        parts.append(self.engine.build_greeting())

        # Acknowledge the specific issue
        raw_msg = self.state.get("raw_message", "")
        issue_summary = self._extract_issue_summary(raw_msg)

        if issue_summary:
            # Clean up the summary so it reads naturally in context
            clean_summary = issue_summary.rstrip(".!? ")
            parts.append(
                f"I'm truly sorry about {clean_summary}. This isn't the experience we want you to have, "
                f"and I take this seriously."
            )
        else:
            parts.append(
                "I'm truly sorry for the experience you've had. This isn't the standard we hold ourselves to, "
                "and I want to make this right."
            )

        # Add specific acknowledgment from CRM data
        if self.customer:
            open_tickets = [
                t for t in self.customer.get("tickets", [])
                if t.get("status") == "open"
            ]
            if len(open_tickets) > 1:
                parts.append(
                    f"I can see you have {len(open_tickets)} open tickets, and I understand "
                    f"how frustrating it must be to deal with multiple unresolved issues. "
                    f"I'm going to make sure these are all addressed together."
                )

            # LTV-aware: high value customers get more proactive resolution
            if p.is_high_ltv:
                notes = self.customer.get("notes", [])
                if notes:
                    parts.append(
                        "I've reviewed your account history and I can see this has been an ongoing concern. "
                        "Let me personally ensure this gets resolved to your satisfaction."
                    )

        # Promise specific action
        if self.recommendation and self.recommendation.get("pending_approval"):
            parts.append(
                "I've already initiated steps to address this and am seeking approval to take action. "
                "You'll hear back from us within 2 hours."
            )
        elif self.execution_results:
            for r in self.execution_results:
                if r.get("status") == "executed":
                    action = r.get("action_type", "").replace("_", " ")
                    parts.append(f"I've already taken action ({action}) to address your concern.")

        # Closing — warm and committed for complaints
        parts.append(
            "Please don't hesitate to follow up if there's anything else. "
            "I'm committed to making sure this is fully resolved for you."
        )

        return " ".join(parts)

    def _build_escalation_response(self) -> str:
        """Build response for escalation intent with calm reassurance and ticket ID."""
        parts: list[str] = []
        p = self.persona

        # Greeting — always calm_reassuring for escalations
        calm_persona = CustomerPersona(
            persona=p.persona,
            tone="calm_reassuring",
            is_high_ltv=p.is_high_ltv,
            is_very_high_ltv=p.is_very_high_ltv,
            tier=p.tier,
            sentiment=p.sentiment,
            customer_name=p.customer_name,
            include_proactive_offers=p.include_proactive_offers,
        )
        calm_engine = PersonaEngine(calm_persona)
        parts.append(calm_engine.build_greeting())

        # Get specific escalation ticket ID
        esc_ticket_id = self._get_escalation_ticket_id()

        parts.append(
            "I understand this matter is important to you and I want to make sure "
            "it gets the attention it deserves. I've escalated your case to our specialist team."
        )

        # Specific ticket ID
        parts.append(
            f"Your escalation ticket ID is **{esc_ticket_id}**. You can reference this number "
            f"for any follow-up communications."
        )

        # Specific next steps based on tier
        if p.tier == "enterprise":
            parts.append(
                "Given your enterprise account, a dedicated account manager will reach out to you "
                "within the hour. They'll have full context on your case."
            )
        elif p.tier == "premium":
            parts.append(
                "A senior support specialist will contact you within 2 hours. "
                "They'll have your complete case history and will work with you directly to resolve this."
            )
        else:
            parts.append(
                "A member of our specialist team will reach out to you within 4 business hours. "
                "They'll have your full case details and will work with you to find a resolution."
            )

        # Calm reassurance closing
        parts.append(
            "In the meantime, please know that your case is a priority for us. "
            "If you have any additional information to add, just reply and it will be attached to your ticket."
        )

        return " ".join(parts)

    def _build_general_inquiry_response(self) -> str:
        """Build response for general_inquiry intent with proactive suggestions."""
        parts: list[str] = []

        # Greeting
        parts.append(self.engine.build_greeting())

        # Use reasoning conclusion if available and clean
        conclusion = self._clean_structured_output(self.reasoning_conclusion)
        if conclusion:
            parts.append(conclusion)
        else:
            parts.append("Thanks for reaching out! I'm happy to help with your question.")

        # Proactive suggestions from CRM data
        if self.customer and self.persona.include_proactive_offers:
            # Suggest based on account status
            subscription = self.customer.get("subscription")
            if subscription and subscription.get("status") == "active":
                plan = subscription.get("plan", "")
                parts.append(
                    f"I see you're currently on the {plan} plan. "
                    f"Let me know if you'd like to explore any upgrades or additional features."
                )

            # Mention upcoming renewal if close
            if subscription:
                renewal = subscription.get("renewal_date", "")
                if renewal:
                    parts.append(
                        f"Your next renewal is on {renewal}. "
                        f"I'm here if you have any questions about your subscription."
                    )

        # Closing with proactive insights
        parts.append(self.engine.build_closing(proactive_insights=self.proactive_insights))

        return " ".join(parts)

    # ─── Helper methods ───────────────────────────────────────────────────

    @staticmethod
    def _describe_account_changes(params: dict[str, Any]) -> str:
        """Describe account modification parameters in human-readable form."""
        changes: list[str] = []
        if "email" in params:
            changes.append(f"email to {params['email']}")
        if "phone" in params:
            changes.append(f"phone to {params['phone']}")
        if "plan" in params:
            changes.append(f"plan to {params['plan']}")
        if "add_seats" in params:
            changes.append(f"add {params['add_seats']} seats")
        if "reactivate" in params:
            changes.append("reactivate account")
        if "reset_password" in params:
            changes.append("password reset")
        return "; ".join(changes) if changes else "account update"

    @staticmethod
    def _extract_issue_summary(raw_message: str) -> str:
        """Extract a brief summary of the issue from the customer message.

        For complaints, we want to capture the substantive issue, not
        just expressions of frustration like 'This is unacceptable.'
        We skip over pure-emotion sentences and look for the concrete
        problem description.
        """
        if not raw_message:
            return ""

        # Split into sentences
        sentences: list[str] = []
        current = []
        for char in raw_message:
            current.append(char)
            if char in ".!?":
                s = "".join(current).strip()
                if s:
                    sentences.append(s)
                current = []
        if current:
            s = "".join(current).strip()
            if s:
                sentences.append(s)

        # Filter out pure-emotion/evaluative sentences — we want
        # the sentence that describes the actual issue
        _pure_emotion_phrases = [
            "unacceptable", "ridiculous", "terrible", "worst", "disgusted",
            "furious", "outraged", "disappointed", "not happy",
        ]
        substantive_sentences: list[str] = []
        for s in sentences:
            lower = s.lower().strip()
            # Skip very short sentences that are just exclamations
            if len(lower) < 15:
                continue
            # Check if this is a pure emotion sentence (no concrete details)
            is_pure_emotion = False
            # A sentence is pure emotion if it's very short AND only contains
            # evaluative language without specific details
            stripped = lower.rstrip(".!? ")
            if any(stripped == phrase or stripped == f"this is {phrase}" for phrase in _pure_emotion_phrases):
                is_pure_emotion = True
            if not is_pure_emotion:
                substantive_sentences.append(s)

        # If we found substantive sentences, use the first one
        if substantive_sentences:
            summary = substantive_sentences[0]
        elif sentences:
            # Fall back to the first sentence that's not too short
            for s in sentences:
                if len(s) >= 15:
                    summary = s
                    break
            else:
                summary = sentences[0]
        else:
            summary = raw_message[:100].strip()
            if len(raw_message) > 100:
                summary += "..."

        # Remove leading pleasantry words
        for prefix in ("Hi ", "Hello ", "Hey ", "Dear "):
            if summary.lower().startswith(prefix.lower()):
                comma = summary.find(",")
                period = summary.find(".")
                cut = min(x for x in [comma, period, len(summary)] if x > 0)
                summary = summary[cut + 1:].strip()
                break

        return summary

    @staticmethod
    def _clean_structured_output(text: str) -> str:
        """Remove structured/pipe-delimited output that leaked from other nodes.

        Handles:
        - "no_match|0.00|"
        - "true|legal_threat" / "false|"
        - "refund_policy|0.90|content"
        - "refund_request|0.97"
        - "frustrated|0.85"
        - "85|accurate,complete"
        """
        import re

        if not text or not isinstance(text, str):
            return ""

        text = text.strip()

        if text.startswith("no_match"):
            return ""
        if text.startswith("true|") or text.startswith("false|"):
            return ""

        _KNOWN_INTENTS = {
            "refund_request", "cancellation", "order_status", "billing_issue",
            "technical_support", "faq_question", "account_modification",
            "escalation", "complaint", "general_inquiry",
        }
        for intent_name in _KNOWN_INTENTS:
            if text.startswith(intent_name + "|"):
                return ""

        _KNOWN_SENTIMENTS = {"happy", "neutral", "frustrated", "angry"}
        for sent in _KNOWN_SENTIMENTS:
            if text.startswith(sent + "|"):
                return ""

        if re.match(r"^\d+\.?\d*\|", text):
            return ""

        if text.count("|") >= 2:
            parts = text.split("|")
            last_part = parts[-1].strip()
            if last_part and len(last_part) > 20 and " " in last_part:
                return last_part
            return ""

        if text.startswith("{") or text.startswith("["):
            return ""

        # Strip embedded structured output
        cleaned = re.sub(
            r'\b(?:refund_request|cancellation|order_status|billing_issue|'
            r'technical_support|faq_question|account_modification|escalation|complaint|'
            r'general_inquiry|no_match|happy|neutral|frustrated|angry|true|false)'
            r'\|[\d.]*\|?[^\.;!?]*',
            '',
            text
        ).strip()

        if cleaned and len(cleaned) > 10:
            return cleaned

        if len(text) > 15 and " " in text and not text.startswith(("true", "false", "no_match")):
            return text

        return ""

    # ─── Main build method ────────────────────────────────────────────────

    def build(self) -> str:
        """Build the complete response based on intent, CRM data, and persona.

        Returns:
            The final customer-facing response string.
        """
        builders = {
            "refund_request": self._build_refund_response,
            "order_status": self._build_order_status_response,
            "cancellation": self._build_cancellation_response,
            "account_modification": self._build_account_modification_response,
            "billing_issue": self._build_billing_issue_response,
            "technical_support": self._build_technical_support_response,
            "faq_question": self._build_faq_response,
            "complaint": self._build_complaint_response,
            "escalation": self._build_escalation_response,
            "general_inquiry": self._build_general_inquiry_response,
        }

        builder = builders.get(self.intent, self._build_general_inquiry_response)

        try:
            response = builder()
        except Exception as exc:
            logger.warning("response_formatter_v2: intent builder %s failed: %s", self.intent, exc)
            # Graceful fallback
            name = self._get_first_name()
            if name:
                response = f"Hi {name}, thank you for reaching out. We've reviewed your request and are working on a resolution."
            else:
                response = "Thank you for reaching out. We've reviewed your request and are working on a resolution."

        return response


# ─── Main entry point ─────────────────────────────────────────────────────────

@safe_node(
    "RESPONSE_FORMATTER_V2",
    fallback={
        "final_response": "We apologize, but we encountered an issue processing your request. A human agent will follow up shortly.",
        "active_frameworks": [],
        "response_version": "v2",
    },
)
async def format_response_v2(state: dict[str, Any]) -> dict[str, Any]:
    """Build a context-aware, persona-based response using real CRM data.

    This is the v2 response formatter that replaces the old rule-based
    formatter. It:
    - Reads full CRM customer data (name, orders, payments, tickets)
    - Determines customer persona from tier + sentiment + LTV
    - Builds context-aware responses with real data
    - Includes proactive insights naturally (not forced)
    - Creates human-readable approval requests for Mini PARWA
    - Provides calm reassurance with specific escalation ticket IDs
    - Falls back gracefully if CRM data is unavailable

    Reads:
        intent, sentiment, customer_id, execution_results, recommendation,
        proactive_insights, reasoning_conclusion, variant, raw_message,
        kb_results, integration_data

    Writes:
        final_response, active_frameworks (append), response_version
    """
    # ─── Guard: ensure types ──────────────────────────────────────────────
    intent = state.get("intent", "general_inquiry")
    if not isinstance(intent, str):
        intent = "general_inquiry"

    sentiment = state.get("sentiment", "neutral")
    if not isinstance(sentiment, str):
        sentiment = "neutral"

    customer_id = state.get("customer_id", "")
    if not isinstance(customer_id, str):
        customer_id = ""

    execution_results = state.get("execution_results", [])
    if not isinstance(execution_results, list):
        execution_results = []

    recommendation = state.get("recommendation")
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None

    proactive_insights = state.get("proactive_insights", [])
    if not isinstance(proactive_insights, list):
        proactive_insights = []

    variant = state.get("variant", "parwa")
    if not isinstance(variant, str):
        variant = "parwa"

    # ─── Load CRM customer data ──────────────────────────────────────────
    customer: dict[str, Any] | None = None
    if customer_id and customer_id != "default":
        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            customer = crm.get_customer(customer_id)
        except (ImportError, ValueError, Exception) as exc:
            logger.warning("response_formatter_v2: CRM load failed for %s: %s", customer_id, exc)
            customer = None

    # ─── Determine persona ───────────────────────────────────────────────
    persona = CustomerPersona.from_crm_data(customer, sentiment)

    # ─── Build context-aware response ────────────────────────────────────
    # Use a cleaned copy of state with guarded types
    clean_state = {
        **state,
        "intent": intent,
        "sentiment": sentiment,
        "customer_id": customer_id,
        "execution_results": execution_results,
        "recommendation": recommendation,
        "proactive_insights": proactive_insights,
        "variant": variant,
    }

    response_builder = ContextAwareResponse(clean_state, persona)
    response = response_builder.build()

    # ─── Track frameworks used ────────────────────────────────────────────
    new_frameworks = ["persona_engine_v2"]
    existing = state.get("active_frameworks", [])
    frameworks_to_add = [fw for fw in new_frameworks if fw not in existing]

    return {
        "final_response": response,
        "active_frameworks": frameworks_to_add,
        "response_version": "v2",
    }
