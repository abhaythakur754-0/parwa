"""
PARWA Phase 3 — Twilio Voice Handler

Handles Twilio webhook endpoints for voice calls:
- /voice/inbound — Initial inbound call → returns TwiML with <Gather>
- /voice/gather — Process customer speech via GoogleVoiceAI → returns TwiML
- /voice/status — Call ended → store recording, create ticket

Architecture: HTTP-only loop (no WebSocket)
Each conversation turn = 1 HTTP request/response

CRITICAL RULES:
- BC-001: company_id from JWT/header for all operations
- BC-008: Never crash — always return valid TwiML
- Recording consent: play "This call may be recorded" before recording
- TCPA compliance: respect Do Not Call, time-of-day restrictions
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice Call Session (in-memory, production would use DB)
# ---------------------------------------------------------------------------

class VoiceCallSession:
    """Tracks a single voice call's state across turns."""

    def __init__(
        self,
        call_sid: str,
        company_id: str,
        from_number: str = "",
        to_number: str = "",
    ):
        self.call_sid = call_sid
        self.company_id = company_id
        self.from_number = from_number
        self.to_number = to_number
        self.status = "ringing"
        self.conversation_history: List[Dict] = []
        self.recording_enabled = True
        self.recording_url: Optional[str] = None
        self.recording_sid: Optional[str] = None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at: Optional[str] = None
        self.summary: Optional[str] = None
        self.tools_used: List[str] = []
        self.variant_tier: str = "parwa"

    def add_customer_turn(self, text: str, confidence: float = 1.0) -> None:
        """Record a customer speech turn."""
        self.conversation_history.append({
            "role": "customer",
            "text": text,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def add_assistant_turn(self, text: str, tools_used: Optional[List[str]] = None) -> None:
        """Record an assistant response turn."""
        self.conversation_history.append({
            "role": "assistant",
            "text": text,
            "tools_used": tools_used or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if tools_used:
            self.tools_used.extend(tools_used)

    def end_call(self, recording_url: Optional[str] = None) -> None:
        """Mark the call as completed."""
        self.status = "completed"
        self.ended_at = datetime.now(timezone.utc).isoformat()
        if recording_url:
            self.recording_url = recording_url

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict."""
        return {
            "call_sid": self.call_sid,
            "company_id": self.company_id,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "status": self.status,
            "conversation_history": self.conversation_history,
            "recording_enabled": self.recording_enabled,
            "recording_url": self.recording_url,
            "recording_sid": self.recording_sid,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "summary": self.summary,
            "tools_used": list(set(self.tools_used)),
            "variant_tier": self.variant_tier,
            "turn_count": len(self.conversation_history),
        }


# ---------------------------------------------------------------------------
# Session Storage (in-memory, production would use DB)
# ---------------------------------------------------------------------------

_call_sessions: Dict[str, VoiceCallSession] = {}


def get_session(call_sid: str) -> Optional[VoiceCallSession]:
    """Get a voice call session by CallSid."""
    return _call_sessions.get(call_sid)


def create_session(
    call_sid: str,
    company_id: str,
    from_number: str = "",
    to_number: str = "",
) -> VoiceCallSession:
    """Create a new voice call session."""
    session = VoiceCallSession(
        call_sid=call_sid,
        company_id=company_id,
        from_number=from_number,
        to_number=to_number,
    )
    _call_sessions[call_sid] = session
    return session


# ---------------------------------------------------------------------------
# TwiML Generation
# ---------------------------------------------------------------------------

def generate_gather_twiml(
    message: str = "Hello, how can I help you today?",
    gather_url: str = "/api/v1/voice/gather",
    language: str = "en-IN",
    use_play: bool = False,
    audio_url: str = "",
) -> str:
    """Generate TwiML for the initial <Gather> response.

    If use_play=True and audio_url is provided, uses <Play> instead of <Say>.
    """
    try:
        if use_play and audio_url:
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather input="speech" action="{gather_url}" speechTimeout="auto" language="{language}"/>
</Response>"""
        else:
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">{message}</Say>
    <Gather input="speech" action="{gather_url}" speechTimeout="auto" language="{language}"/>
</Response>"""
    except Exception as exc:
        logger.error("generate_gather_twiml failed: %s", exc)
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred.</Say></Response>'


def generate_recording_consent_twiml(gather_url: str = "/api/v1/voice/gather") -> str:
    """Generate TwiML that plays recording consent before the call starts."""
    try:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">This call may be recorded for quality purposes.</Say>
    <Say voice="Polly.Aditi">Hello, how can I help you today?</Say>
    <Gather input="speech" action="{gather_url}" speechTimeout="auto" language="en-IN"/>
</Response>"""
    except Exception as exc:
        logger.error("generate_recording_consent_twiml failed: %s", exc)
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred.</Say></Response>'


def generate_hangup_twiml(message: str = "Thank you for calling. Goodbye!") -> str:
    """Generate TwiML for ending the call."""
    try:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">{message}</Say>
    <Hangup/>
</Response>"""
    except Exception as exc:
        logger.error("generate_hangup_twiml failed: %s", exc)
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'


def generate_transfer_twiml(transfer_number: str) -> str:
    """Generate TwiML for transferring to a human agent."""
    try:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">Let me transfer you to a human agent. Please hold.</Say>
    <Dial>{transfer_number}</Dial>
</Response>"""
    except Exception as exc:
        logger.error("generate_transfer_twiml failed: %s", exc)
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Transfer unavailable.</Say></Response>'


# ---------------------------------------------------------------------------
# Voice Handler — Orchestrates the call flow
# ---------------------------------------------------------------------------

class TwilioVoiceHandler:
    """Handles Twilio voice webhook processing.

    Coordinates between:
    - Twilio (webhooks, TwiML responses)
    - GoogleVoiceAI (Gemini reasoning, TTS, STT)
    - RecordingStorageService (recording lifecycle)
    - ChannelExecutor (tool execution during calls)
    - ProviderBridge (real API calls)
    """

    def __init__(self, google_api_key: Optional[str] = None):
        try:
            from app.core.voice.google_voice_ai import GoogleVoiceAI
            self.voice_ai = GoogleVoiceAI(google_api_key=google_api_key)
        except Exception:
            self.voice_ai = None

    async def handle_inbound_call(
        self,
        call_sid: str,
        from_number: str,
        to_number: str,
        company_id: str,
        recording_enabled: bool = True,
    ) -> str:
        """Handle an inbound call from Twilio.

        Returns TwiML response with <Gather> for speech input.
        """
        try:
            # Create session
            session = create_session(
                call_sid=call_sid,
                company_id=company_id,
                from_number=from_number,
                to_number=to_number,
            )
            session.recording_enabled = recording_enabled
            session.status = "in-progress"

            # Generate TwiML
            if recording_enabled:
                return generate_recording_consent_twiml()
            else:
                return generate_gather_twiml()

        except Exception as exc:
            logger.error("handle_inbound_call failed: %s", exc)
            return generate_gather_twiml()

    async def handle_gather(
        self,
        call_sid: str,
        speech_result: str,
        confidence: float = 1.0,
    ) -> str:
        """Handle a <Gather> result — customer spoke.

        Process speech through GoogleVoiceAI and return TwiML response.
        """
        try:
            session = get_session(call_sid)
            if not session:
                return generate_hangup_twiml("I'm sorry, there was an error. Goodbye.")

            # Record customer turn
            session.add_customer_turn(speech_result, confidence)

            # Process through GoogleVoiceAI
            if self.voice_ai:
                result = await self.voice_ai.process_speech(
                    call_sid=call_sid,
                    speech_text=speech_result,
                    confidence=confidence,
                    conversation_history=session.conversation_history,
                    company_id=session.company_id,
                )

                response_text = result["response_text"]
                audio_url = result.get("audio_url", "")
                tools_used = result.get("tools_used", [])
                should_continue = result.get("should_continue", True)

                # Record assistant turn
                session.add_assistant_turn(response_text, tools_used)

                if not should_continue:
                    return generate_hangup_twiml(response_text)

                # Return TwiML with response + next <Gather>
                if audio_url:
                    return generate_gather_twiml(
                        use_play=True,
                        audio_url=audio_url,
                    )
                else:
                    return generate_gather_twiml(message=response_text)
            else:
                # Fallback without GoogleVoiceAI
                return generate_gather_twiml("I'm here to help. Could you tell me more?")

        except Exception as exc:
            logger.error("handle_gather failed: %s", exc)
            return generate_gather_twiml("I'm sorry, could you repeat that?")

    async def handle_call_ended(
        self,
        call_sid: str,
        call_status: str = "completed",
        recording_url: Optional[str] = None,
        recording_sid: Optional[str] = None,
        call_duration: int = 0,
    ) -> Dict[str, Any]:
        """Handle call status update (call ended).

        1. Update session status
        2. Store recording if available
        3. Generate call summary
        4. Create ticket with transcript
        """
        try:
            session = get_session(call_sid)
            if not session:
                return {"success": False, "error": "Session not found"}

            # End the session
            session.end_call(recording_url=recording_url)
            if recording_sid:
                session.recording_sid = recording_sid

            # Store recording if available
            recording_stored = False
            if recording_url:
                try:
                    from app.core.voice.recording_service import RecordingStorageService
                    storage = RecordingStorageService()
                    stored_path = await storage.download_and_store(
                        recording_url=recording_url,
                        call_sid=call_sid,
                        company_id=session.company_id,
                    )
                    recording_stored = bool(stored_path)
                except Exception as exc:
                    logger.error("Recording storage failed: %s", exc)

            # Generate call summary
            summary = ""
            if self.voice_ai and session.conversation_history:
                try:
                    summary = await self.voice_ai.generate_call_summary(
                        session.conversation_history
                    )
                    session.summary = summary
                except Exception as exc:
                    logger.error("Summary generation failed: %s", exc)
                    summary = f"Call with {len(session.conversation_history)} turns."

            # Return call result (caller creates the ticket)
            return {
                "success": True,
                "call_sid": call_sid,
                "company_id": session.company_id,
                "status": "completed",
                "duration_seconds": call_duration,
                "turn_count": len(session.conversation_history),
                "tools_used": list(set(session.tools_used)),
                "recording_stored": recording_stored,
                "summary": summary,
                "transcript": session.conversation_history,
            }

        except Exception as exc:
            logger.error("handle_call_ended failed: %s", exc)
            return {"success": False, "error": str(exc)}
