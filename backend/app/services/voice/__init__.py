"""
Voice Deep Services — Day 6 Voice Module

Provides advanced voice channel capabilities:
- IVRBuilder: Dynamic TwiML IVR menu generation
- CallRecordingService: Recording, transcription, voicemail-to-ticket
- CallTransferService: Cold/warm transfers and conference calls
- VoiceSentimentAnalyzer: Real-time sentiment and urgency analysis

Building Codes:
- BC-001: All operations scoped by company_id
- BC-008: Never crash — return error dicts instead of raising
"""

from app.services.voice.ivr_builder import IVRBuilder
from app.services.voice.call_recording import CallRecordingService
from app.services.voice.call_transfer import CallTransferService
from app.services.voice.voice_sentiment import VoiceSentimentAnalyzer

__all__ = [
    "IVRBuilder",
    "CallRecordingService",
    "CallTransferService",
    "VoiceSentimentAnalyzer",
]
