"""
PARWA Demo Service - Variant-Aware Demo System

Pre-purchase demo experience that lets potential customers test variant capabilities.

Features:
- Free chat demo (up to 20 messages) for all variants
- Variant-specific demo scenarios
- Demo results tracking
- Integration with Twilio SMS and Brevo Email for demo notifications

INTEGRATIONS:
- AI Chat: z-ai-web-dev-sdk
- SMS: Twilio (demo notifications)
- Email: Brevo (demo follow-up)
- Web Search: z-ai-web-dev-sdk

VARIANTS:
- mini_parwa: Basic AI, 3 demo scenarios, no voice
- parwa: Standard AI, 10 demo scenarios, voice preview
- high_parwa: Premium AI, 20 demo scenarios, full voice demo
"""

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import subprocess

from app.logger import get_logger

logger = get_logger("demo_service")


# ── Enums ────────────────────────────────────────────────────────────────


class DemoVariant(str, Enum):
    """Demo variant types for pre-purchase testing."""

    MINI_PARWA = "mini_parwa"
    PARWA = "parwa"
    HIGH_PARWA = "high_parwa"


class DemoStatus(str, Enum):
    """Demo session status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


# ── Variant Capabilities ───────────────────────────────────────────────────

VARIANT_DEMO_CAPABILITIES = {
    DemoVariant.MINI_PARWA: {
        "display_name": "Mini Parwa",
        "price_monthly": Decimal("999.00"),
        "max_demo_messages": 20,
        "max_demo_minutes": 10,
        "features": [
            "Basic AI Chat",
            "FAQ Handling",
            "Simple Routing",
            "Email Support",
        ],
        "demo_scenarios": ["basic_faq", "order_tracking", "simple_refund"],
        "ai_model_tier": "light",
        "rag_depth": 3,
        "voice_enabled": False,
        "web_search_enabled": False,
        "image_gen_enabled": False,
    },
    DemoVariant.PARWA: {
        "display_name": "Parwa",
        "price_monthly": Decimal("2499.00"),
        "max_demo_messages": 50,
        "max_demo_minutes": 20,
        "features": [
            "Advanced AI Chat",
            "Multi-channel Support",
            "Smart Routing",
            "SMS Integration",
            "Voice Preview",
            "Knowledge Base",
        ],
        "demo_scenarios": [
            "basic_faq",
            "order_tracking",
            "simple_refund",
            "complex_refund",
            "billing_dispute",
            "product_recommendation",
            "technical_support",
            "shipping_inquiry",
            "payment_issues",
            "account_management",
        ],
        "ai_model_tier": "medium",
        "rag_depth": 5,
        "voice_enabled": True,
        "web_search_enabled": True,
        "image_gen_enabled": False,
    },
    DemoVariant.HIGH_PARWA: {
        "display_name": "High Parwa",
        "price_monthly": Decimal("3999.00"),
        "max_demo_messages": 100,
        "max_demo_minutes": 30,
        "features": [
            "Premium AI Chat",
            "All Channels",
            "Priority Routing",
            "Full Voice Demo",
            "Web Search",
            "Image Generation",
            "Advanced Analytics",
            "Custom Guardrails",
            "Brand Voice",
        ],
        "demo_scenarios": [
            "basic_faq",
            "order_tracking",
            "simple_refund",
            "complex_refund",
            "billing_dispute",
            "product_recommendation",
            "technical_support",
            "shipping_inquiry",
            "payment_issues",
            "account_management",
            "gdpr_request",
            "api_troubleshooting",
            "international_shipping",
            "customs_inquiry",
            "fleet_management",
            "inventory_check",
            "prescription_refill",
            "insurance_verification",
            "appointment_scheduling",
            "telehealth_setup",
        ],
        "ai_model_tier": "heavy",
        "rag_depth": 10,
        "voice_enabled": True,
        "web_search_enabled": True,
        "image_gen_enabled": True,
    },
}


# ── Data Classes ─────────────────────────────────────────────────────────


@dataclass
class DemoSession:
    """Demo session for pre-purchase testing."""

    session_id: str
    visitor_email: Optional[str] = None
    visitor_phone: Optional[str] = None
    variant: DemoVariant = DemoVariant.PARWA
    status: DemoStatus = DemoStatus.ACTIVE
    industry: str = "ecommerce"
    message_count: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    scenarios_completed: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        # Set expiry based on variant (30 minutes from now)
        if self.expires_at is None:
            from datetime import timedelta

            self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)


@dataclass
class DemoResult:
    """Result of a demo interaction."""

    success: bool
    message: str = ""
    ai_response: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0
    features_used: List[str] = field(default_factory=list)
    variant_capabilities: Dict[str, Any] = field(default_factory=dict)


# ── AI Integration ─────────────────────────────────────────────────────────


def _get_ai_response(
    message: str,
    variant: DemoVariant,
    industry: str,
    conversation_history: List[Dict[str, str]],
) -> str:
    """Get AI response using z-ai-web-dev-sdk.

    Uses variant-specific system prompts and capabilities.
    """
    capabilities = VARIANT_DEMO_CAPABILITIES.get(variant, {})
    model_tier = capabilities.get("ai_model_tier", "medium")

    # Variant-specific system prompts
    system_prompts = {
        DemoVariant.MINI_PARWA: """You are a helpful AI assistant for PARWA demo.
You are demonstrating the Mini Parwa tier capabilities.
Industry context: {industry}

Keep responses concise and focused on FAQ handling and simple tasks.
For complex issues, recommend upgrading to Parwa or High Parwa.
Max response length: 200 characters.""",
        DemoVariant.PARWA: """You are an advanced AI assistant for PARWA demo.
You are demonstrating the Parwa tier capabilities.
Industry context: {industry}

Provide detailed, helpful responses with knowledge base integration.
You can handle multi-step issues and provide personalized recommendations.
Max response length: 500 characters.""",
        DemoVariant.HIGH_PARWA: """You are a premium AI assistant for PARWA demo.
You are demonstrating the High Parwa tier capabilities.
Industry context: {industry}

Provide comprehensive, expert-level responses with citations.
Handle complex multi-step issues autonomously.
Apply brand voice and custom guardrails.
Max response length: 1000 characters.""",
    }

    system_prompt = system_prompts.get(variant, system_prompts[DemoVariant.PARWA])

    # Build messages for AI
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-10:]:  # Last 10 messages for context
        messages.append(msg)
    messages.append({"role": "user", "content": message})

    try:
        # Use z-ai-web-dev-sdk via Node.js
        node_script = """
const ZAI = require('z-ai-web-dev-sdk').default;
(async () => {{
    const zai = await ZAI.create();
    const completion = await zai.chat.completions.create({{
        messages: {json.dumps(messages)},
        temperature: 0.7,
        max_tokens: {500 if model_tier == 'heavy' else 300 if model_tier == 'medium' else 150}
    }});
    console.log(completion.choices[0].message.content);
}})().catch(e => console.error(e.message));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/home/z/my-project/parwa",
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

    except Exception as e:
        logger.warning("ai_response_failed", error=str(e)[:100])

    # Fallback response based on variant
    fallbacks = {
        DemoVariant.MINI_PARWA: "I can help with basic questions. For more advanced features, consider upgrading to Parwa!",
        DemoVariant.PARWA: "I'm here to help! I can assist with orders, billing, and product recommendations.",
        DemoVariant.HIGH_PARWA: "As your premium AI assistant, I can handle complex issues and provide detailed analysis. How can I assist you today?",
    }
    return fallbacks.get(variant, "I'm here to help!")


def _get_web_search_results(query: str) -> List[Dict[str, str]]:
    """Get web search results using z-ai-web-dev-sdk (High Parwa only)."""
    try:
        node_script = """
const ZAI = require('z-ai-web-dev-sdk').default;
(async () => {{
    const zai = await ZAI.create();
    const results = await zai.functions.invoke('web_search', {{
        query: {json.dumps(query)},
        num: 3
    }});
    console.log(JSON.stringify(results.slice(0, 3)));
}})().catch(e => console.error(e.message));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/home/z/my-project/parwa",
        )

        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())

    except Exception as e:
        logger.warning("web_search_failed", error=str(e)[:100])

    return []


# ── Demo Service ──────────────────────────────────────────────────────────


class DemoService:
    """Variant-aware demo service for pre-purchase testing."""

    def __init__(self):
        self._sessions: Dict[str, DemoSession] = {}
        self._lock = threading.Lock()

    def create_demo_session(
        self,
        variant: DemoVariant = DemoVariant.PARWA,
        industry: str = "ecommerce",
        visitor_email: Optional[str] = None,
        visitor_phone: Optional[str] = None,
    ) -> DemoSession:
        """Create a new demo session for a potential customer."""
        session = DemoSession(
            session_id=str(uuid.uuid4()),
            variant=variant,
            industry=industry,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
            status=DemoStatus.ACTIVE,
        )

        with self._lock:
            self._sessions[session.session_id] = session

        logger.info(
            "demo_session_created",
            session_id=session.session_id,
            variant=variant.value,
            industry=industry,
        )

        return session

    def get_demo_session(self, session_id: str) -> Optional[DemoSession]:
        """Get a demo session by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                # Check if expired
                if datetime.now(timezone.utc) > session.expires_at:
                    session.status = DemoStatus.EXPIRED
            return session

    def send_demo_message(
        self,
        session_id: str,
        message: str,
    ) -> DemoResult:
        """Send a message in the demo session with variant-aware capabilities."""
        session = self.get_demo_session(session_id)
        if not session:
            return DemoResult(
                success=False,
                message="Demo session not found. Please start a new demo.",
            )

        if session.status != DemoStatus.ACTIVE:
            return DemoResult(
                success=False,
                message=f"Demo session is {
                    session.status.value}. Please start a new demo.",
            )

        capabilities = VARIANT_DEMO_CAPABILITIES.get(session.variant, {})
        max_messages = capabilities.get("max_demo_messages", 20)

        # Check message limit
        if session.message_count >= max_messages:
            session.status = DemoStatus.COMPLETED
            return DemoResult(
                success=False,
                message=f"Demo message limit ({max_messages}) reached. Sign up for unlimited access!",
                variant_capabilities=capabilities,
            )

        # Build conversation history
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in session.messages[-10:]
        ]

        start_time = time.monotonic()

        # Get AI response based on variant
        ai_response = _get_ai_response(
            message=message,
            variant=session.variant,
            industry=session.industry,
            conversation_history=conversation_history,
        )

        latency_ms = (time.monotonic() - start_time) * 1000

        # Track features used
        features_used = ["ai_chat"]

        # Web search (High Parwa only)
        web_search_enabled = capabilities.get("web_search_enabled", False)
        web_results = []
        if web_search_enabled and any(
            kw in message.lower() for kw in ["search", "find", "lookup", "compare"]
        ):
            web_results = _get_web_search_results(message)
            if web_results:
                features_used.append("web_search")

        # Update session
        session.message_count += 1
        session.messages.append(
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        session.messages.append(
            {
                "role": "assistant",
                "content": ai_response,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": latency_ms,
            }
        )

        # Calculate confidence based on variant
        confidence_scores = {
            DemoVariant.MINI_PARWA: 0.70,
            DemoVariant.PARWA: 0.85,
            DemoVariant.HIGH_PARWA: 0.95,
        }

        return DemoResult(
            success=True,
            message="Response generated successfully.",
            ai_response=ai_response,
            confidence=confidence_scores.get(session.variant, 0.80),
            latency_ms=latency_ms,
            features_used=features_used,
            variant_capabilities={
                "variant": session.variant.value,
                "display_name": capabilities.get("display_name", "Parwa"),
                "features": capabilities.get("features", []),
                "remaining_messages": max_messages - session.message_count,
                "voice_enabled": capabilities.get("voice_enabled", False),
                "web_search_enabled": web_search_enabled,
                "web_results": web_results[:3] if web_results else None,
            },
        )

    def get_demo_scenarios(
        self,
        variant: DemoVariant,
        industry: str,
    ) -> List[Dict[str, Any]]:
        """Get demo scenarios available for a variant."""
        capabilities = VARIANT_DEMO_CAPABILITIES.get(variant, {})
        scenario_ids = capabilities.get("demo_scenarios", [])

        # Load demo scenarios from knowledge base
        scenarios_path = "/home/z/my-project/parwa/backend/app/data/jarvis_knowledge/06_demo_scenarios.json"
        all_scenarios = []

        try:
            with open(scenarios_path, "r") as f:
                data = json.load(f)
                all_scenarios = data.get("scenarios", [])
        except Exception as e:
            logger.warning("failed_to_load_scenarios", error=str(e)[:100])

        # Filter scenarios by industry and variant availability
        filtered = []
        for scenario in all_scenarios:
            if industry in ["ecommerce", "saas", "logistics", "healthcare"]:
                if (
                    scenario.get("industry") == industry
                    or scenario.get("industry") == "ecommerce"
                ):
                    filtered.append(
                        {
                            "id": scenario.get("id"),
                            "title": scenario.get("title"),
                            "difficulty": scenario.get("difficulty"),
                            "preview": scenario.get("customer_message", "")[:100]
                            + "...",
                            "talking_points": scenario.get("talking_points", [])[:2],
                        }
                    )

        # Limit by variant
        max_scenarios = len(scenario_ids) if scenario_ids else 5
        return filtered[:max_scenarios]

    def get_variant_comparison(self) -> Dict[str, Any]:
        """Get comparison of all variants for the demo page."""
        return {
            variant.value: {
                "display_name": caps.get("display_name"),
                "price_monthly": str(caps.get("price_monthly", "0")),
                "max_demo_messages": caps.get("max_demo_messages"),
                "features": caps.get("features", []),
                "voice_enabled": caps.get("voice_enabled", False),
                "web_search_enabled": caps.get("web_search_enabled", False),
                "image_gen_enabled": caps.get("image_gen_enabled", False),
            }
            for variant, caps in VARIANT_DEMO_CAPABILITIES.items()
        }

    def complete_demo_session(
        self,
        session_id: str,
        collect_feedback: bool = True,
    ) -> Dict[str, Any]:
        """Complete a demo session and collect results."""
        session = self.get_demo_session(session_id)
        if not session:
            return {"success": False, "message": "Session not found"}

        session.status = DemoStatus.COMPLETED

        capabilities = VARIANT_DEMO_CAPABILITIES.get(session.variant, {})

        # Send follow-up email if email provided
        if session.visitor_email:
            self._send_demo_followup_email(
                email=session.visitor_email,
                variant=session.variant,
                industry=session.industry,
            )

        # Send SMS if phone provided and variant supports it
        if session.visitor_phone and capabilities.get("voice_enabled", False):
            self._send_demo_followup_sms(
                phone=session.visitor_phone,
                variant=session.variant,
            )

        logger.info(
            "demo_session_completed",
            session_id=session_id,
            variant=session.variant.value,
            message_count=session.message_count,
        )

        return {
            "success": True,
            "message": "Demo completed successfully!",
            "summary": {
                "variant_tested": session.variant.value,
                "variant_display_name": capabilities.get("display_name", "Parwa"),
                "messages_sent": session.message_count,
                "features_tested": list(
                    set(
                        feature
                        for msg in session.messages
                        if msg["role"] == "assistant"
                        for feature in ["ai_chat"]  # Could extract from metadata
                    )
                ),
                "upgrade_options": [
                    {
                        "variant": v.value,
                        "display_name": VARIANT_DEMO_CAPABILITIES[v].get(
                            "display_name"
                        ),
                        "price": str(VARIANT_DEMO_CAPABILITIES[v].get("price_monthly")),
                    }
                    for v in DemoVariant
                    if VARIANT_DEMO_CAPABILITIES[v].get("price_monthly", 0)
                    > capabilities.get("price_monthly", 0)
                ],
            },
        }

    def _send_demo_followup_email(
        self,
        email: str,
        variant: DemoVariant,
        industry: str,
    ) -> bool:
        """Send demo follow-up email via Brevo."""
        try:
            from app.services.email_service import send_email

            capabilities = VARIANT_DEMO_CAPABILITIES.get(variant, {})
            display_name = capabilities.get("display_name", "Parwa")
            price = capabilities.get("price_monthly", Decimal("0"))

            subject = f"Thanks for trying {display_name} - Your PARWA Demo Results"
            html_content = """
            <h2>Thanks for trying PARWA!</h2>
            <p>You tested the <strong>{display_name}</strong> tier with our AI assistant.</p>
            <p>Monthly price: ${price}/month</p>
            <h3>Features you experienced:</h3>
            <ul>
                {''.join(f'<li>{f}</li>' for f in capabilities.get('features', []))}
            </ul>
            <p><a href="https://parwa.ai/pricing">Sign up now</a> to get started!</p>
            """

            # Use Brevo integration from email_service
            return send_email(
                to=email,
                subject=subject,
                html_content=html_content,
            )

        except Exception as e:
            logger.warning("demo_followup_email_failed", error=str(e)[:100])
            return False

    def _send_demo_followup_sms(
        self,
        phone: str,
        variant: DemoVariant,
    ) -> bool:
        """Send demo follow-up SMS via Twilio."""
        try:
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
            twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER", "")

            if not all([account_sid, auth_token, twilio_phone]):
                return False

            import httpx
            import base64

            capabilities = VARIANT_DEMO_CAPABILITIES.get(variant, {})
            display_name = capabilities.get("display_name", "Parwa")

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()

            body = f"Thanks for trying PARWA {display_name}! Ready to transform your customer support? Sign up at parwa.ai/pricing"

            response = httpx.post(
                url,
                data={"From": twilio_phone, "To": phone, "Body": body},
                headers={"Authorization": f"Basic {auth}"},
                timeout=10.0,
            )
            return response.status_code in (200, 201)

        except Exception as e:
            logger.warning("demo_followup_sms_failed", error=str(e)[:100])
            return False


# ── Module-level singleton ────────────────────────────────────────────────

_demo_service: Optional[DemoService] = None
_demo_lock = threading.Lock()


def get_demo_service() -> DemoService:
    """Get the module-level DemoService singleton."""
    global _demo_service
    if _demo_service is None:
        with _demo_lock:
            if _demo_service is None:
                _demo_service = DemoService()
    return _demo_service
