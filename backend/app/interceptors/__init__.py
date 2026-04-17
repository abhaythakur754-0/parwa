"""
Shadow Mode Interceptors

Intercepts AI actions on all channels (Email, SMS, Voice, Chat) and
evaluates them against the 4-layer shadow mode decision system.

Day 2 Implementation - Channel Interceptors

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

from app.interceptors.email_shadow import (
    evaluate_email_shadow,
    EmailShadowResult,
    process_email_after_approval,
)
from app.interceptors.sms_shadow import (
    evaluate_sms_shadow,
    SMSShadowResult,
    process_sms_after_approval,
)
from app.interceptors.voice_shadow import (
    evaluate_voice_shadow,
    VoiceShadowResult,
    process_voice_after_approval,
    get_hold_message,
    should_intercept_voice,
)
from app.interceptors.chat_shadow import (
    ChatShadowInterceptor,
    ChatShadowQueue,
)
from app.interceptors.base_interceptor import ShadowInterceptor

__all__ = [
    # Base
    "ShadowInterceptor",
    # Email
    "evaluate_email_shadow",
    "EmailShadowResult",
    "process_email_after_approval",
    # SMS
    "evaluate_sms_shadow",
    "SMSShadowResult",
    "process_sms_after_approval",
    # Voice
    "evaluate_voice_shadow",
    "VoiceShadowResult",
    "process_voice_after_approval",
    "get_hold_message",
    "should_intercept_voice",
    # Chat
    "ChatShadowInterceptor",
    "ChatShadowQueue",
]
