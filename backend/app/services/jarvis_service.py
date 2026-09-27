"""
Jarvis Service — Re-export hub.

This file was originally 4,763 lines. It has been split into
focused submodules under app.services.jarvis.* for maintainability.

All functions are re-exported here so that the 84 files that import
from app.services.jarvis_service continue to work without changes.

Submodules:
  - jarvis.chat: Session management, message sending, AI provider calls
  - jarvis.payment: OTP, demo packs, Paddle payments, demo calls
  - jarvis.tickets: Ticket CRUD + Jarvis ticket wrappers + automation
  - jarvis.handoff: Onboarding-to-CustomerCare handoff + onboarding steps
  - jarvis.utils: Analytics, leads, usage, audit, notifications, PII
"""

# Re-export everything from the jarvis package
from app.services.jarvis import *  # noqa: F401,F403

# Also export the shared infrastructure
from app.services.jarvis._shared import (
    _service_cache,
    _get_service,
    _get_service_module,
    _clear_service_cache,
    logger,
)
