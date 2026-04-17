"""
Channel Infrastructure Modules

Provides client wrappers and utilities for communication channels:
- Twilio (SMS, Voice)
- Brevo (Email)
- Socket.io (Chat)
"""

from app.core.channels.twilio_client import TwilioClient

__all__ = ["TwilioClient"]
