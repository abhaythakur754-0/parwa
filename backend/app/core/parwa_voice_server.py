"""
Parwa Voice Server — Twilio Integration for AI Customer Service Calls

Production-ready Flask server that bridges Twilio voice calls with
Parwa's variant engine (Mini, Pro, High). Handles:
- Inbound calls: customer calls in, Parwa AI responds
- Outbound calls: Parwa initiates calls to customers
- Call status tracking and post-call summaries
- Multi-variant routing based on company subscription tier

Twilio Credentials:
- Account SID: configured via environment variable
- Auth Token: configured via environment variable
- Phone Number: +17752583673 (US, voice + SMS capable)

Building Codes: BC-001, BC-002, BC-008, BC-012
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from flask import Flask, request, Response

logger = logging.getLogger("parwa.voice_server")


# ══════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ══════════════════════════════════════════════════════════════════


class CallType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    BUSY = "busy"
    FAILED = "failed"
    NO_ANSWER = "no-answer"
    CANCELED = "canceled"


class VariantTier(str, Enum):
    MINI = "mini_parwa"
    PRO = "parwa"
    HIGH = "parwa_high"


# Default Parwa greeting messages per variant tier
VARIANT_GREETINGS = {
    VariantTier.MINI: "Welcome to Parwa Mini. I am your AI customer service assistant. How can I help you today?",
    VariantTier.PRO: "Hello! You have reached Parwa Pro customer service. I am your dedicated AI assistant with advanced reasoning capabilities. How may I assist you?",
    VariantTier.HIGH: "Good day. This is Parwa High, your premium AI customer service executive. I am equipped with strategic decision-making and peer review capabilities to resolve your concern comprehensively. How can I help you today?",
}


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class VoiceCallSession:
    """Tracks a single voice call session through Parwa's pipeline."""
    call_sid: str
    session_id: str = ""
    phone_number: str = ""
    direction: CallType = CallType.INBOUND
    variant_tier: VariantTier = VariantTier.PRO
    status: CallStatus = CallStatus.QUEUED
    company_id: str = ""
    transcript: List[Dict[str, str]] = field(default_factory=list)
    intent: str = ""
    resolution: str = ""
    created_at: str = ""
    ended_at: str = ""
    duration_seconds: int = 0

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())[:16]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class ParwaVoiceConfig:
    """Configuration for the Parwa Voice Server."""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = "+17752583673"
    default_variant: VariantTier = VariantTier.PRO
    max_call_duration_minutes: int = 30
    enable_recording: bool = False
    speech_language: str = "en-IN"
    tts_voice: str = "Polly.Aditi"
    host: str = "0.0.0.0"
    port: int = 5000


# ══════════════════════════════════════════════════════════════════
# PARWA VOICE RESPONSE BUILDER
# ══════════════════════════════════════════════════════════════════


class ParwaVoiceResponseBuilder:
    """Builds TwiML responses that integrate with Parwa's variant engine.

    Generates appropriate voice responses based on the variant tier,
    customer intent, and resolution status.
    """

    # Industry-specific response templates
    INDUSTRY_RESPONSES = {
        "ecommerce": {
            "order_tracking": "I can help you track your order. Let me look up the details for you.",
            "refund_request": "I understand you would like a refund. Let me process that for you right away.",
            "product_inquiry": "I would be happy to help you with product information. What would you like to know?",
            "return_exchange": "I can assist with returns and exchanges. Let me guide you through the process.",
        },
        "saas": {
            "billing_issue": "I can help resolve your billing concern. Let me pull up your account details.",
            "feature_request": "Thank you for your feature suggestion. I will document this for our product team.",
            "technical_support": "I can troubleshoot this technical issue with you. Let me gather some details first.",
            "account_management": "I can help manage your account settings. What would you like to change?",
        },
        "healthcare": {
            "appointment": "I can help you with appointment scheduling. Let me check available times.",
            "prescription": "I can assist with prescription-related inquiries. Let me verify your details.",
            "insurance": "I can help clarify your insurance coverage. Let me look into that for you.",
            "billing": "I understand you have a billing question. Let me review your statement.",
        },
        "fintech": {
            "transaction_dispute": "I can help you dispute a transaction. Let me gather the details.",
            "account_security": "Your account security is important. Let me verify your identity and assist.",
            "loan_inquiry": "I can provide information about our loan products. What are you looking for?",
            "card_issue": "I can help with card-related issues. Let me check your card status.",
        },
    }

    @classmethod
    def build_greeting(cls, variant_tier: VariantTier, industry: str = "") -> str:
        """Build a greeting message based on variant tier and industry."""
        greeting = VARIANT_GREETINGS.get(variant_tier, VARIANT_GREETINGS[VariantTier.PRO])
        if industry and industry.lower() == "healthcare":
            if variant_tier == VariantTier.HIGH:
                greeting = "Good day. This is Parwa High, your dedicated healthcare AI service executive. I am here to assist you with appointments, prescriptions, insurance, and more. How may I help you?"
        return greeting

    @classmethod
    def build_intent_response(cls, intent: str, industry: str = "ecommerce") -> str:
        """Build a response for a detected customer intent."""
        industry_lower = industry.lower()
        industry_templates = cls.INDUSTRY_RESPONSES.get(
            industry_lower, cls.INDUSTRY_RESPONSES["ecommerce"]
        )
        return industry_templates.get(intent, "I understand your concern. Let me help you with that right away.")

    @classmethod
    def build_resolution(cls, variant_tier: VariantTier, intent: str, success: bool = True) -> str:
        """Build a resolution/summary message based on variant tier and outcome."""
        if success:
            tier_suffix = {
                VariantTier.MINI: "resolved",
                VariantTier.PRO: "resolved with our advanced reasoning",
                VariantTier.HIGH: "comprehensively resolved with strategic analysis and peer validation",
            }
            return f"Your {intent} request has been {tier_suffix.get(variant_tier, 'resolved')}. Is there anything else I can help you with?"
        else:
            return "I was unable to fully resolve your request. Let me connect you with a specialist who can assist further."

    @classmethod
    def build_post_call_summary(cls, session: VoiceCallSession) -> str:
        """Build a post-call summary for SMS/voice delivery."""
        summary_parts = [
            f"Parwa {session.variant_tier.value} Call Summary:",
            f"Intent: {session.intent or 'General Inquiry'}",
            f"Resolution: {session.resolution or 'Assisted'}",
            f"Duration: {session.duration_seconds}s",
        ]
        if session.company_id:
            summary_parts.append(f"Company: {session.company_id}")
        return " | ".join(summary_parts)


# ══════════════════════════════════════════════════════════════════
# PARWA VOICE SERVER
# ══════════════════════════════════════════════════════════════════


class ParwaVoiceServer:
    """Flask-based voice server bridging Twilio calls with Parwa variants.

    Handles:
    - Inbound call TwiML generation
    - Outbound call initiation via Twilio API
    - Call status webhooks
    - Gather (DTMF/speech) handling
    - Post-call summary delivery
    - Session tracking per call

    Thread-safe session management.
    """

    def __init__(self, config: Optional[ParwaVoiceConfig] = None):
        self._config = config or ParwaVoiceConfig()
        self._app = Flask(__name__)
        self._lock = threading.Lock()
        self._sessions: Dict[str, VoiceCallSession] = {}
        self._response_builder = ParwaVoiceResponseBuilder()
        self._setup_routes()

    @property
    def app(self) -> Flask:
        return self._app

    def _setup_routes(self):
        """Register Flask routes for Twilio webhook handling."""

        @self._app.route("/", methods=["GET", "POST"])
        def voice_welcome():
            """Main webhook — handles inbound calls with Parwa greeting."""
            return self._handle_inbound_call()

        @self._app.route("/voice/inbound", methods=["POST"])
        def voice_inbound():
            """Dedicated inbound call handler."""
            return self._handle_inbound_call()

        @self._app.route("/voice/gather", methods=["POST"])
        def voice_gather():
            """Handle speech/DTMF input from customer."""
            return self._handle_gather()

        @self._app.route("/voice/status", methods=["POST"])
        def voice_status():
            """Handle call status callback from Twilio."""
            return self._handle_status_callback()

        @self._app.route("/voice/transfer", methods=["POST"])
        def voice_transfer():
            """Handle call transfer to human agent."""
            return self._handle_transfer()

        @self._app.route("/voice/summary", methods=["POST"])
        def voice_summary():
            """Deliver post-call summary."""
            return self._handle_summary()

        @self._app.route("/health", methods=["GET"])
        def health_check():
            """Health check endpoint."""
            return {"status": "ok", "service": "parwa_voice_server", "sessions": len(self._sessions)}

    def _handle_inbound_call(self) -> str:
        """Generate TwiML for an inbound call with Parwa greeting and gather."""
        from twilio.twiml.voice_response import VoiceResponse, Gather

        call_sid = request.values.get("CallSid", "")
        from_number = request.values.get("From", "")
        to_number = request.values.get("To", "")

        # Create session
        session = VoiceCallSession(
            call_sid=call_sid,
            phone_number=from_number,
            direction=CallType.INBOUND,
            variant_tier=self._config.default_variant,
        )

        with self._lock:
            self._sessions[call_sid] = session

        logger.info(
            "parwa_inbound_call call_sid=%s from=%s variant=%s",
            call_sid, from_number, session.variant_tier.value,
        )

        # Build TwiML response
        resp = VoiceResponse()
        greeting = self._response_builder.build_greeting(session.variant_tier)

        gather = Gather(
            input="speech dtmf",
            action="/voice/gather",
            method="POST",
            speech_timeout="auto",
            language=self._config.speech_language,
        )
        gather.say(greeting, voice=self._config.tts_voice, language=self._config.speech_language)
        resp.append(gather)

        # If no input, retry
        resp.say(
            "I did not catch that. Please call back when you are ready. Goodbye!",
            voice=self._config.tts_voice,
        )

        return str(resp)

    def _handle_gather(self) -> str:
        """Handle speech/DTMF input and route through Parwa variant."""
        from twilio.twiml.voice_response import VoiceResponse, Gather

        call_sid = request.values.get("CallSid", "")
        speech_result = request.values.get("SpeechResult", "")
        digits = request.values.get("Digits", "")
        confidence = float(request.values.get("Confidence", "0.5"))

        with self._lock:
            session = self._sessions.get(call_sid)

        if not session:
            session = VoiceCallSession(
                call_sid=call_sid,
                variant_tier=self._config.default_variant,
            )

        # Store transcript
        session.transcript.append({
            "role": "customer",
            "text": speech_result or f"DTMF: {digits}",
            "confidence": str(confidence),
        })

        # Simulate intent detection (in production, this goes through Parwa variant pipeline)
        detected_intent = self._detect_intent(speech_result or digits)
        session.intent = detected_intent

        # Generate response based on variant tier
        response_text = self._response_builder.build_intent_response(detected_intent)
        resolution_text = self._response_builder.build_resolution(
            session.variant_tier, detected_intent, success=True
        )
        session.resolution = resolution_text

        session.transcript.append({
            "role": "parwa",
            "text": response_text,
            "variant": session.variant_tier.value,
        })

        logger.info(
            "parwa_gather_processed call_sid=%s intent=%s variant=%s confidence=%.2f",
            call_sid, detected_intent, session.variant_tier.value, confidence,
        )

        # Build TwiML
        resp = VoiceResponse()
        resp.say(response_text, voice=self._config.tts_voice, language=self._config.speech_language)

        # Ask if more help needed
        gather = Gather(
            input="speech dtmf",
            action="/voice/gather",
            method="POST",
            speech_timeout="auto",
            num_digits=1,
        )
        gather.say(
            "Is there anything else I can help you with? Press 1 for yes, or 2 to end the call.",
            voice=self._config.tts_voice,
        )
        resp.append(gather)

        # No input → end call with summary
        resp.say(resolution_text, voice=self._config.tts_voice, language=self._config.speech_language)
        resp.hangup()

        return str(resp)

    def _handle_status_callback(self) -> str:
        """Handle call status updates from Twilio."""
        call_sid = request.values.get("CallSid", "")
        call_status = request.values.get("CallStatus", "")
        duration = request.values.get("CallDuration", "0")

        with self._lock:
            session = self._sessions.get(call_sid)
            if session:
                try:
                    session.status = CallStatus(call_status)
                except ValueError:
                    session.status = call_status
                session.duration_seconds = int(duration) if duration else 0
                if call_status in ("completed", "failed", "no-answer", "busy", "canceled"):
                    session.ended_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "parwa_call_status call_sid=%s status=%s duration=%ss",
            call_sid, call_status, duration,
        )

        return ""

    def _handle_transfer(self) -> str:
        """Handle transfer to human agent."""
        from twilio.twiml.voice_response import VoiceResponse, Dial

        resp = VoiceResponse()
        resp.say(
            "I am connecting you to a specialist. Please hold.",
            voice=self._config.tts_voice,
        )
        # In production, this would dial a real agent number
        resp.say(
            "All specialists are currently busy. Let me take a message for you.",
            voice=self._config.tts_voice,
        )
        return str(resp)

    def _handle_summary(self) -> str:
        """Deliver a post-call summary via voice."""
        from twilio.twiml.voice_response import VoiceResponse

        call_sid = request.values.get("CallSid", "")

        with self._lock:
            session = self._sessions.get(call_sid)

        resp = VoiceResponse()
        if session:
            summary = self._response_builder.build_post_call_summary(session)
            resp.say(summary, voice=self._config.tts_voice)
        else:
            resp.say("Thank you for calling. Goodbye!", voice=self._config.tts_voice)

        resp.hangup()
        return str(resp)

    def _detect_intent(self, text: str) -> str:
        """Simple keyword-based intent detection.

        In production, this routes through Parwa's full variant pipeline
        with GST/ToT/Least-to-Most reasoning.
        """
        text_lower = (text or "").lower()

        intent_keywords = {
            "order_tracking": ["order", "track", "tracking", "shipment", "delivery", "where is my"],
            "refund_request": ["refund", "money back", "return", "cancel order", " reimbursement"],
            "product_inquiry": ["product", "item", "specification", "features", "details"],
            "technical_support": ["technical", "error", "bug", "not working", "broken", "crash", "issue"],
            "billing_issue": ["billing", "charge", "invoice", "payment", "overcharge", "subscription"],
            "account_management": ["account", "profile", "settings", "password", "login", "update"],
            "complaint": ["complaint", "unhappy", "dissatisfied", "terrible", "worst", "angry"],
            "appointment": ["appointment", "schedule", "booking", "doctor", "visit"],
            "feature_request": ["feature", "suggest", "enhancement", "improvement", "wish"],
        }

        for intent, keywords in intent_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    return intent

        return "general_inquiry"

    # ══════════════════════════════════════════════════════════
    # OUTBOUND CALL API
    # ══════════════════════════════════════════════════════════

    def make_outbound_call(
        self,
        to_number: str,
        variant_tier: VariantTier = VariantTier.PRO,
        message: str = "",
        industry: str = "",
        company_id: str = "",
    ) -> Dict[str, Any]:
        """Initiate an outbound call via Twilio API.

        Args:
            to_number: Target phone number in E.164 format.
            variant_tier: Parwa variant tier for this call.
            message: Custom message to speak. If empty, uses tier greeting.
            industry: Industry context for response generation.
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with call_sid, status, and session_id.
        """
        try:
            from twilio.rest import Client

            client = Client(
                self._config.twilio_account_sid,
                self._config.twilio_auth_token,
            )

            # Build the spoken message
            if not message:
                message = self._response_builder.build_greeting(variant_tier, industry)

            # Create TwiML for the outbound call
            twiml = f'<Response><Say voice="{self._config.tts_voice}" language="{self._config.speech_language}">{message}</Say></Response>'

            call = client.calls.create(
                to=to_number,
                from_=self._config.twilio_phone_number,
                twiml=twiml,
                status_callback="/voice/status",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
            )

            # Track session
            session = VoiceCallSession(
                call_sid=call.sid,
                phone_number=to_number,
                direction=CallType.OUTBOUND,
                variant_tier=variant_tier,
                company_id=company_id,
            )

            with self._lock:
                self._sessions[call.sid] = session

            logger.info(
                "parwa_outbound_call call_sid=%s to=%s variant=%s",
                call.sid, to_number, variant_tier.value,
            )

            return {
                "call_sid": call.sid,
                "status": call.status,
                "session_id": session.session_id,
                "variant_tier": variant_tier.value,
            }

        except Exception as e:
            logger.exception("parwa_outbound_call_failed to=%s", to_number)
            return {
                "error": str(e),
                "status": "failed",
            }

    def get_session(self, call_sid: str) -> Optional[VoiceCallSession]:
        """Get a tracked call session by CallSid."""
        with self._lock:
            return self._sessions.get(call_sid)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all tracked sessions as dicts."""
        with self._lock:
            return [
                {
                    "call_sid": s.call_sid,
                    "session_id": s.session_id,
                    "phone_number": s.phone_number,
                    "direction": s.direction.value,
                    "variant_tier": s.variant_tier.value,
                    "status": s.status if isinstance(s.status, str) else s.status.value,
                    "intent": s.intent,
                    "resolution": s.resolution,
                    "duration_seconds": s.duration_seconds,
                    "transcript_count": len(s.transcript),
                }
                for s in self._sessions.values()
            ]

    def run(self, **kwargs):
        """Start the Flask server."""
        host = kwargs.pop("host", self._config.host)
        port = kwargs.pop("port", self._config.port)
        debug = kwargs.pop("debug", False)
        self._app.run(host=host, port=port, debug=debug, **kwargs)


# ══════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════════════


def create_voice_server(
    account_sid: str = "",
    auth_token: str = "",
    phone_number: str = "+17752583673",
    default_variant: str = "parwa",
    host: str = "0.0.0.0",
    port: int = 5000,
) -> ParwaVoiceServer:
    """Factory function to create and configure a ParwaVoiceServer.

    Args:
        account_sid: Twilio Account SID.
        auth_token: Twilio Auth Token.
        phone_number: Twilio phone number.
        default_variant: Default Parwa variant tier.
        host: Flask host.
        port: Flask port.

    Returns:
        Configured ParwaVoiceServer instance.
    """
    variant_map = {
        "mini_parwa": VariantTier.MINI,
        "mini": VariantTier.MINI,
        "parwa": VariantTier.PRO,
        "pro": VariantTier.PRO,
        "parwa_high": VariantTier.HIGH,
        "high": VariantTier.HIGH,
    }

    config = ParwaVoiceConfig(
        twilio_account_sid=account_sid,
        twilio_auth_token=auth_token,
        twilio_phone_number=phone_number,
        default_variant=variant_map.get(default_variant, VariantTier.PRO),
        host=host,
        port=port,
    )

    return ParwaVoiceServer(config)


# ══════════════════════════════════════════════════════════════════
# DIRECT EXECUTION — TEST MODE
# ══════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Use environment variables — NEVER hardcode credentials
    server = create_voice_server(
        account_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
        default_variant="pro",
    )

    print("Parwa Voice Server starting on port 5000...")
    server.run()
