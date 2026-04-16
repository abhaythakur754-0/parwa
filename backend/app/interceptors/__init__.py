"""
Shadow Mode Channel Interceptors

Channel-specific interceptors for the Shadow Mode dual-control system.
Each interceptor evaluates outbound actions and determines whether they
require manager approval (shadow/supervised) or can auto-execute (graduated).

Available Interceptors:
    - EmailShadowInterceptor: Email channel
    - SMSShadowInterceptor: SMS channel
    - ChatShadowInterceptor: Chat widget

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

from app.interceptors.base_interceptor import ShadowInterceptor
from app.interceptors.email_shadow import EmailShadowInterceptor
from app.interceptors.sms_shadow import SMSShadowInterceptor
from app.interceptors.chat_shadow import ChatShadowInterceptor

__all__ = [
    "ShadowInterceptor",
    "EmailShadowInterceptor",
    "SMSShadowInterceptor",
    "ChatShadowInterceptor",
]
