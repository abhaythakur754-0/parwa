"""
PARWA Phase 3 — Voice Channel API

Endpoints for two-way voice AI:
- /voice/inbound — Handle inbound calls from Twilio
- /voice/gather — Process customer speech
- /voice/status — Handle call status updates
- /voice/recordings/{id} — Get recording playback URL
- /voice/recordings/{id}/transcript — Get recording transcript
- /voice/test-conversation — Test two-way conversation
- /voice/config — Get/update voice AI configuration

CRITICAL RULES:
- BC-001: company_id from JWT/header
- BC-008: Never crash — always return valid TwiML for voice endpoints
- Recording consent before recording starts
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_company_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class VoiceConfig(BaseModel):
    recording_enabled: bool = True
    voice_language: str = "en-IN"
    greeting_message: str = "Hello, how can I help you today?"
    transfer_number: str = ""
    consent_message: str = "This call may be recorded for quality purposes."


class VoiceConfigUpdate(BaseModel):
    recording_enabled: Optional[bool] = None
    voice_language: Optional[str] = None
    greeting_message: Optional[str] = None
    transfer_number: Optional[str] = None


class ConversationTestRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    call_sid: Optional[str] = None
    variant_tier: str = "parwa"


class ConversationTestResponse(BaseModel):
    response_text: str
    audio_available: bool = False
    tools_used: list[str] = []
    should_continue: bool = True


class RecordingResponse(BaseModel):
    recording_id: str
    call_sid: str
    playback_url: str
    duration_seconds: int = 0
    status: str


class TranscriptResponse(BaseModel):
    recording_id: str
    call_sid: str
    transcript: str
    summary: str = ""
    turn_count: int = 0


# ---------------------------------------------------------------------------
# In-memory voice config (production would use DB)
# ---------------------------------------------------------------------------

_company_voice_config: dict[str, VoiceConfig] = {}


def _get_voice_config(company_id: str) -> VoiceConfig:
    """Get or create voice config for a company."""
    if company_id not in _company_voice_config:
        _company_voice_config[company_id] = VoiceConfig()
    return _company_voice_config[company_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/inbound")
async def handle_inbound_call(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    company_id: str = Depends(get_current_company_id),
):
    """Handle inbound call from Twilio. Returns TwiML response."""
    try:
        from app.core.voice.twilio_voice_handler import TwilioVoiceHandler

        handler = TwilioVoiceHandler()
        config = _get_voice_config(company_id)

        twiml = await handler.handle_inbound_call(
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            company_id=company_id,
            recording_enabled=config.recording_enabled,
        )

        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        logger.error("handle_inbound_call failed: %s", exc)
        # Always return valid TwiML even on error
        error_twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred. Please try again.</Say></Response>'
        return Response(content=error_twiml, media_type="application/xml")


@router.post("/gather")
async def handle_gather(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    Confidence: float = Form(default=0.0),
    company_id: str = Depends(get_current_company_id),
):
    """Handle <Gather> result from Twilio — customer spoke."""
    try:
        from app.core.voice.twilio_voice_handler import TwilioVoiceHandler

        handler = TwilioVoiceHandler()

        if not SpeechResult:
            # No speech detected — ask again
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Aditi">I didn\'t catch that. Could you repeat?</Say><Gather input="speech" action="/api/v1/voice/gather" speechTimeout="auto" language="en-IN"/></Response>'
            return Response(content=twiml, media_type="application/xml")

        twiml = await handler.handle_gather(
            call_sid=CallSid,
            speech_result=SpeechResult,
            confidence=Confidence,
        )

        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        logger.error("handle_gather failed: %s", exc)
        error_twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Aditi">I\'m sorry, could you repeat that?</Say><Gather input="speech" action="/api/v1/voice/gather" speechTimeout="auto" language="en-IN"/></Response>'
        return Response(content=error_twiml, media_type="application/xml")


@router.post("/status")
async def handle_call_status(
    CallSid: str = Form(...),
    CallStatus: str = Form(default="completed"),
    RecordingUrl: Optional[str] = Form(default=None),
    RecordingSid: Optional[str] = Form(default=None),
    CallDuration: int = Form(default=0),
    company_id: str = Depends(get_current_company_id),
):
    """Handle call status update from Twilio (call ended)."""
    try:
        from app.core.voice.twilio_voice_handler import TwilioVoiceHandler

        handler = TwilioVoiceHandler()
        result = await handler.handle_call_ended(
            call_sid=CallSid,
            call_status=CallStatus,
            recording_url=RecordingUrl,
            recording_sid=RecordingSid,
            call_duration=CallDuration,
        )

        return result

    except Exception as exc:
        logger.error("handle_call_status failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.get("/config", response_model=VoiceConfig)
def get_voice_config_endpoint(
    company_id: str = Depends(get_current_company_id),
):
    """Get voice AI configuration for this company."""
    try:
        return _get_voice_config(company_id)
    except Exception as exc:
        logger.error("get_voice_config failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get voice config") from exc


@router.put("/config", response_model=VoiceConfig)
def update_voice_config(
    body: VoiceConfigUpdate,
    company_id: str = Depends(get_current_company_id),
):
    """Update voice AI configuration."""
    try:
        config = _get_voice_config(company_id)

        if body.recording_enabled is not None:
            config.recording_enabled = body.recording_enabled
        if body.voice_language is not None:
            config.voice_language = body.voice_language
        if body.greeting_message is not None:
            config.greeting_message = body.greeting_message
        if body.transfer_number is not None:
            config.transfer_number = body.transfer_number

        return config
    except Exception as exc:
        logger.error("update_voice_config failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update config") from exc


@router.post("/test-conversation", response_model=ConversationTestResponse)
async def test_conversation(
    body: ConversationTestRequest,
    company_id: str = Depends(get_current_company_id),
):
    """Test two-way conversation (for development/testing)."""
    try:
        from app.core.voice.google_voice_ai import GoogleVoiceAI

        voice_ai = GoogleVoiceAI()
        result = await voice_ai.process_speech(
            call_sid=body.call_sid or "test-call",
            speech_text=body.message,
            confidence=1.0,
            conversation_history=[],
            company_id=company_id,
        )

        return ConversationTestResponse(
            response_text=result["response_text"],
            audio_available=bool(result.get("audio_url")),
            tools_used=result.get("tools_used", []),
            should_continue=result.get("should_continue", True),
        )

    except Exception as exc:
        logger.error("test_conversation failed: %s", exc)
        return ConversationTestResponse(
            response_text="I'm here to help. Could you tell me more?",
            audio_available=False,
            tools_used=[],
            should_continue=True,
        )


@router.get("/recordings/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Get recording playback URL."""
    try:
        from app.core.voice.recording_service import RecordingPlaybackService

        playback = RecordingPlaybackService()
        url = await playback.get_playback_url(recording_id, company_id)

        return RecordingResponse(
            recording_id=recording_id,
            call_sid=recording_id,
            playback_url=url or "",
            status="available" if url else "not_found",
        )
    except Exception as exc:
        logger.error("get_recording failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get recording") from exc


@router.get("/recordings/{recording_id}/transcript", response_model=TranscriptResponse)
async def get_recording_transcript(
    recording_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Get recording transcript."""
    try:
        from app.core.voice.twilio_voice_handler import get_session

        # Try to find the session for this recording
        session = get_session(recording_id)

        if session and session.conversation_history:
            transcript_lines = []
            for turn in session.conversation_history:
                role = turn.get("role", "unknown").capitalize()
                text = turn.get("text", "")
                transcript_lines.append(f"{role}: {text}")

            return TranscriptResponse(
                recording_id=recording_id,
                call_sid=session.call_sid,
                transcript="\n".join(transcript_lines),
                summary=session.summary or "",
                turn_count=len(session.conversation_history),
            )

        return TranscriptResponse(
            recording_id=recording_id,
            call_sid=recording_id,
            transcript="No transcript available",
            summary="",
            turn_count=0,
        )
    except Exception as exc:
        logger.error("get_recording_transcript failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get transcript") from exc


# ---------------------------------------------------------------------------
# Import for Response
# ---------------------------------------------------------------------------
from fastapi.responses import Response
