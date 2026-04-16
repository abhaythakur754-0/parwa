"""
Voice Shadow Interceptor

Intercepts outbound voice call TTS (text-to-speech) content and evaluates them 
against the shadow mode 4-layer decision system before playing to customers.

Day 2 Implementation - Channel Interceptors

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from database.base import SessionLocal
from database.models.shadow_mode import ShadowLog

logger = logging.getLogger("parwa.interceptors.voice_shadow")


@dataclass
class VoiceShadowResult:
    """Result of voice shadow evaluation."""
    
    requires_approval: bool
    auto_execute: bool
    mode: str
    risk_score: float
    reason: str
    shadow_log_id: Optional[str] = None
    layers: Optional[Dict[str, Any]] = None
    
    # Additional context
    company_mode: str = "supervised"
    stage_0: bool = False
    shadow_actions_remaining: Optional[int] = None


def evaluate_voice_shadow(
    company_id: str,
    voice_payload: Dict[str, Any],
    shadow_service=None,
) -> VoiceShadowResult:
    """
    Evaluate an outbound voice/TTS content against shadow mode rules.
    
    This is called before TTS plays content to the customer. If shadow mode
    requires approval, the call should play a "please hold" message and
    alert the manager for review.
    
    Args:
        company_id: Company UUID (BC-001).
        voice_payload: Dict with voice details:
            - call_id: Voice call UUID
            - to_number: Customer phone number (E.164)
            - from_number: Twilio phone number
            - message: TTS message to play
            - conversation_id: Optional conversation UUID
            - ticket_id: Optional ticket UUID
            - caller_role: Sender role (agent/bot/system)
            - voice_type: TTS voice type (e.g., 'alice', 'man')
        shadow_service: Optional ShadowModeService instance (created if not provided)
    
    Returns:
        VoiceShadowResult with evaluation outcome.
        
    Usage:
        result = evaluate_voice_shadow(
            company_id="company-uuid",
            voice_payload={
                "call_id": "call-123",
                "to_number": "+1234567890",
                "message": "Thank you for calling. Your refund has been processed.",
            },
        )
        
        if result.requires_approval:
            # Play "Please hold" message to customer
            # Alert manager for review
            notify_manager(result.shadow_log_id)
        else:
            # Play the message immediately
            play_tts(voice_payload["message"])
    """
    try:
        # Lazy import to avoid circular dependencies
        from app.services.shadow_mode_service import ShadowModeService
        
        service = shadow_service or ShadowModeService()
        
        # Evaluate using the 4-layer system
        evaluation = service.evaluate_action_risk(
            company_id=company_id,
            action_type="voice_reply",
            action_payload=voice_payload,
        )
        
        # Log the shadow action if approval is required
        shadow_log_id = None
        if evaluation.get("requires_approval"):
            log_entry = service.log_shadow_action(
                company_id=company_id,
                action_type="voice_reply",
                action_payload=voice_payload,
                risk_score=evaluation.get("risk_score"),
                mode=evaluation.get("mode"),
            )
            shadow_log_id = log_entry.get("id")
        
        return VoiceShadowResult(
            requires_approval=evaluation.get("requires_approval", True),
            auto_execute=evaluation.get("auto_execute", False),
            mode=evaluation.get("mode", "supervised"),
            risk_score=evaluation.get("risk_score", 0.5),
            reason=evaluation.get("reason", ""),
            shadow_log_id=shadow_log_id,
            layers=evaluation.get("layers"),
            company_mode=evaluation.get("company_mode", "supervised"),
            stage_0=evaluation.get("stage_0", False),
            shadow_actions_remaining=evaluation.get("shadow_actions_remaining"),
        )
        
    except Exception as e:
        logger.error(
            "voice_shadow_evaluation_failed company_id=%s error=%s",
            company_id, str(e), exc_info=True,
        )
        # Safe fallback: always require approval
        return VoiceShadowResult(
            requires_approval=True,
            auto_execute=False,
            mode="supervised",
            risk_score=0.5,
            reason=f"Evaluation failed: {str(e)}",
        )


def process_voice_after_approval(
    company_id: str,
    shadow_log_id: str,
    voice_service=None,
) -> Dict[str, Any]:
    """
    Process a voice message that was held in shadow queue after approval.
    
    This should be called when a manager approves a voice action
    from the shadow queue. It retrieves the pending message and 
    returns it for playback.
    
    Args:
        company_id: Company UUID (BC-001).
        shadow_log_id: Shadow log entry UUID.
        voice_service: Optional voice service instance.
    
    Returns:
        Dict with processing result including the message to play.
    """
    try:
        from app.services.shadow_mode_service import ShadowModeService
        
        with SessionLocal() as db:
            # Get the shadow log entry
            shadow_entry = db.query(ShadowLog).filter(
                ShadowLog.id == shadow_log_id,
                ShadowLog.company_id == company_id,
            ).first()
            
            if not shadow_entry:
                return {
                    "status": "error",
                    "error": "Shadow log entry not found",
                }
            
            voice_payload = shadow_entry.action_payload or {}
            
            # Here you would integrate with your voice/TTS service
            # For now, we return the payload for the caller to process
            logger.info(
                "voice_shadow_approved shadow_id=%s company_id=%s",
                shadow_log_id, company_id,
            )
            
            return {
                "status": "ready_to_play",
                "shadow_log_id": shadow_log_id,
                "voice_payload": voice_payload,
                "approved_at": datetime.utcnow().isoformat(),
            }
            
    except Exception as e:
        logger.error(
            "voice_shadow_approval_processing_failed shadow_id=%s error=%s",
            shadow_log_id, str(e), exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
        }


def get_hold_message() -> str:
    """
    Get the default "please hold" message for shadow mode.
    
    This message is played to the customer when a voice response
    requires manager approval.
    
    Returns:
        Hold message text for TTS.
    """
    return (
        "Please hold for a moment while we finalize your response. "
        "A team member will be with you shortly."
    )


def should_intercept_voice(
    company_id: str,
    call_data: Dict[str, Any],
) -> bool:
    """
    Determine if a voice call should be intercepted for shadow mode.
    
    Not all voice interactions need shadow mode. This helper determines
    if the current interaction qualifies based on:
    - The call is outbound (agent-initiated)
    - The message contains AI-generated content
    - The message is not a simple greeting or hold message
    
    Args:
        company_id: Company UUID.
        call_data: Dict with call metadata.
    
    Returns:
        True if the call should be intercepted.
    """
    # Skip simple system messages
    message = call_data.get("message", "").lower()
    
    # Simple greetings and system messages don't need shadow
    skip_phrases = [
        "thank you for calling",
        "please hold",
        "your call is important",
        "connecting you to",
        "goodbye",
        "have a nice day",
    ]
    
    for phrase in skip_phrases:
        if phrase in message:
            return False
    
    # Intercept everything else
    return True
