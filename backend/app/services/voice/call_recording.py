"""
Call Recording Service — Recording, Transcription & Voicemail-to-Ticket

Manages the recording lifecycle for voice calls:
1. Enable recording on active calls via Twilio API
2. Trigger and retrieve transcriptions
3. Convert voicemails into support tickets automatically
4. Retrieve all recordings with transcripts for a call

Building Codes:
- BC-001: All operations scoped by company_id (multi-tenant isolation)
- BC-008: Never crash — wrap all external calls in try/except, return error dicts
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.voice_channel import (
    VoiceCall,
    VoiceChannelConfig,
    VoiceConversation,
)

logger = logging.getLogger("parwa.voice.call_recording")


class CallRecordingService:
    """Service for managing call recordings, transcriptions, and voicemail processing.

    All methods are scoped to company_id (BC-001) and never crash (BC-008).
    Uses Twilio API for recording and transcription operations.
    """

    def __init__(self, db: Session):
        """Initialize with database session.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Recording Management
    # ═══════════════════════════════════════════════════════════

    def enable_recording(
        self,
        call_sid: str,
        company_id: str,
    ) -> dict:
        """Enable Twilio recording on an active call.

        Uses the Twilio API to start recording an in-progress call.

        Args:
            call_sid: Twilio CallSid for the active call.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with status, recording_sid, recording_url on success.
            Dict with status='error' on failure.
        """
        try:
            # Verify the call belongs to this company (BC-001)
            call = self._get_call_by_sid(call_sid, company_id)
            if not call:
                return {
                    "status": "error",
                    "error": "Call not found for this company",
                }

            if call.status not in ("in-progress", "ringing"):
                return {
                    "status": "error",
                    "error": f"Cannot record call in state: {call.status}",
                }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]

            # Start recording via Twilio
            recording = client.calls(call_sid).recordings.create(
                recording_status_callback=(
                    f"/api/v1/voice/recording/callback?company_id={company_id}"
                ),
                recording_status_callback_event=["completed"],
            )

            # Update call record
            call.recording_enabled = True
            call.recording_sid = recording.sid
            self.db.commit()

            logger.info(
                "recording_enabled",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "recording_sid": recording.sid,
                },
            )

            return {
                "status": "recording_started",
                "recording_sid": recording.sid,
                "recording_url": getattr(recording, "uri", ""),
                "call_id": call.id,
            }

        except Exception as exc:
            logger.error(
                "enable_recording_failed call_sid=%s company_id=%s error=%s",
                call_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to enable recording: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Transcription
    # ═══════════════════════════════════════════════════════════

    def start_transcription(
        self,
        recording_sid: str,
        company_id: str,
    ) -> dict:
        """Trigger transcription via Twilio API for a recording.

        Args:
            recording_sid: Twilio RecordingSid to transcribe.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with transcription_sid, status on success.
            Dict with status='error' on failure.
        """
        try:
            # Verify the recording belongs to this company (BC-001)
            call = (
                self.db.query(VoiceCall)
                .filter(
                    VoiceCall.recording_sid == recording_sid,
                    VoiceCall.company_id == company_id,
                )
                .first()
            )
            if not call:
                return {
                    "status": "error",
                    "error": "Recording not found for this company",
                }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]

            # Start transcription via Twilio
            transcription = client.recordings(recording_sid).transcriptions.create()

            # Store transcription SID on the call
            metadata = json.loads(call.metadata_json or "{}")
            metadata["transcription_sid"] = transcription.sid
            metadata["transcription_status"] = transcription.status
            call.metadata_json = json.dumps(metadata)
            self.db.commit()

            logger.info(
                "transcription_started",
                extra={
                    "company_id": company_id,
                    "recording_sid": recording_sid,
                    "transcription_sid": transcription.sid,
                },
            )

            return {
                "status": "transcription_started",
                "transcription_sid": transcription.sid,
                "transcription_status": transcription.status,
            }

        except Exception as exc:
            logger.error(
                "start_transcription_failed recording_sid=%s company_id=%s error=%s",
                recording_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to start transcription: {str(exc)[:200]}",
            }

    def get_transcription(
        self,
        transcription_sid: str,
        company_id: str,
    ) -> dict:
        """Fetch completed transcription text from Twilio.

        Args:
            transcription_sid: Twilio TranscriptionSid.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with transcription_text, confidence, status on success.
            Dict with status='error' on failure.
        """
        try:
            # Verify the transcription belongs to this company (BC-001)
            call = (
                self.db.query(VoiceCall)
                .filter(
                    VoiceCall.company_id == company_id,
                )
                .all()
            )

            # Check if any call in this company has this transcription SID
            found = False
            for c in call:
                metadata = json.loads(c.metadata_json or "{}")
                if metadata.get("transcription_sid") == transcription_sid:
                    found = True
                    break

            if not found:
                return {
                    "status": "error",
                    "error": "Transcription not found for this company",
                }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]

            # Fetch transcription
            transcription = client.transcriptions(transcription_sid).fetch()

            # Calculate a simple confidence based on status
            confidence = 0.0
            if transcription.status == "completed":
                confidence = 0.85  # Default confidence estimate
            elif transcription.status == "in-progress":
                confidence = 0.5

            # Update call transcript
            target_call = None
            for c in call:
                metadata = json.loads(c.metadata_json or "{}")
                if metadata.get("transcription_sid") == transcription_sid:
                    target_call = c
                    break

            if target_call and transcription.status == "completed":
                transcript_text = transcription.transcription_text or ""
                target_call.transcript_json = json.dumps({
                    "text": transcript_text,
                    "transcription_sid": transcription_sid,
                    "confidence": confidence,
                })
                # Generate a simple summary (first 200 chars)
                target_call.transcript_summary = (
                    transcript_text[:200] if transcript_text else ""
                )
                self.db.commit()

            logger.info(
                "transcription_fetched",
                extra={
                    "company_id": company_id,
                    "transcription_sid": transcription_sid,
                    "status": transcription.status,
                },
            )

            return {
                "status": "success",
                "transcription_text": getattr(transcription, "transcription_text", ""),
                "confidence": confidence,
                "transcription_status": transcription.status,
            }

        except Exception as exc:
            logger.error(
                "get_transcription_failed sid=%s company_id=%s error=%s",
                transcription_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to get transcription: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Voicemail-to-Ticket
    # ═══════════════════════════════════════════════════════════

    def voicemail_to_ticket(
        self,
        voicemail_data: dict,
        company_id: str,
        db_session: Session,
    ) -> dict:
        """Detect voicemail, transcribe it, and auto-create a ticket.

        Processes a Twilio voicemail event by:
        1. Extracting call metadata and recording info
        2. Transcribing the voicemail (if not already transcribed)
        3. Creating a support ticket with the transcript and audio URL

        Args:
            voicemail_data: Dict with keys:
                call_sid (str): Twilio CallSid.
                recording_url (str): URL of the voicemail recording.
                recording_duration (int): Duration in seconds.
                from_number (str): Caller's phone number.
                to_number (str): Called Twilio number.
                transcription_text (str, optional): Pre-transcribed text.
            company_id: Tenant company ID (BC-001).
            db_session: Database session for creating ticket records.

        Returns:
            Dict with ticket_id, message_id, transcript on success.
            Dict with status='error' on failure.
        """
        try:
            call_sid = voicemail_data.get("call_sid", "")
            recording_url = voicemail_data.get("recording_url", "")
            recording_duration = voicemail_data.get("recording_duration", 0)
            from_number = voicemail_data.get("from_number", "")
            to_number = voicemail_data.get("to_number", "")
            transcription_text = voicemail_data.get("transcription_text", "")

            # If no transcription provided, attempt to get it
            if not transcription_text and call_sid:
                # Try to find the call and get transcription
                call = self._get_call_by_sid(call_sid, company_id)
                if call:
                    transcript_data = json.loads(call.transcript_json or "{}")
                    transcription_text = transcript_data.get("text", "")

                    # If still no transcript, try Twilio API
                    if not transcription_text and call.recording_sid:
                        trans_result = self.start_transcription(
                            call.recording_sid, company_id
                        )
                        if trans_result.get("status") != "error":
                            get_result = self.get_transcription(
                                trans_result["transcription_sid"],
                                company_id,
                            )
                            if get_result.get("status") == "success":
                                transcription_text = get_result.get(
                                    "transcription_text", ""
                                )

            # Build ticket subject
            caller_display = from_number or "Unknown Caller"
            subject = f"Voicemail from {caller_display}"

            # Build ticket description
            description_parts = [
                f"Voicemail received from {caller_display}",
                f"Duration: {recording_duration} seconds",
            ]
            if recording_url:
                description_parts.append(f"Recording URL: {recording_url}")
            if transcription_text:
                description_parts.append(f"\nTranscript:\n{transcription_text}")
            else:
                description_parts.append("\nTranscript: Not available")

            description = "\n".join(description_parts)

            # Create the ticket
            from database.models.tickets import Ticket
            from database.models.core import Company

            # Verify company exists
            company = db_session.query(Company).filter(
                Company.id == company_id
            ).first()
            if not company:
                return {
                    "status": "error",
                    "error": "Company not found",
                }

            ticket = Ticket(
                company_id=company_id,
                title=subject,
                description=description,
                status="open",
                priority="medium",
                channel="voice",
                source="voicemail",
            )
            db_session.add(ticket)
            db_session.flush()

            # Create initial message with transcript
            from database.models.tickets import TicketMessage

            message_body = transcription_text or "[Voicemail - no transcript available]"
            message = TicketMessage(
                company_id=company_id,
                ticket_id=ticket.id,
                body=message_body,
                sender_type="visitor",
                metadata_json=json.dumps({
                    "call_sid": call_sid,
                    "recording_url": recording_url,
                    "recording_duration": recording_duration,
                    "from_number": from_number,
                    "to_number": to_number,
                    "type": "voicemail",
                }),
            )
            db_session.add(message)

            # Link ticket to the voice call
            call = self._get_call_by_sid(call_sid, company_id)
            if call:
                call.ticket_id = ticket.id

            db_session.commit()

            logger.info(
                "voicemail_to_ticket_created",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "ticket_id": ticket.id,
                    "message_id": message.id,
                    "has_transcript": bool(transcription_text),
                },
            )

            return {
                "status": "ticket_created",
                "ticket_id": ticket.id,
                "message_id": message.id,
                "transcript": transcription_text,
            }

        except Exception as exc:
            logger.error(
                "voicemail_to_ticket_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to create ticket from voicemail: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Recording Retrieval
    # ═══════════════════════════════════════════════════════════

    def get_call_recordings(
        self,
        call_sid: str,
        company_id: str,
    ) -> dict:
        """Get all recordings for a call with their transcripts.

        Fetches recording metadata from Twilio and combines with
        stored transcript data from the database.

        Args:
            call_sid: Twilio CallSid.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with recordings list on success.
            Dict with status='error' on failure.
        """
        try:
            # Verify the call belongs to this company (BC-001)
            call = self._get_call_by_sid(call_sid, company_id)
            if not call:
                return {
                    "status": "error",
                    "error": "Call not found for this company",
                }

            recordings_list: List[Dict[str, Any]] = []

            # Get recording from call record
            if call.recording_sid:
                transcript_data = json.loads(call.transcript_json or "{}")

                recording_entry: Dict[str, Any] = {
                    "recording_sid": call.recording_sid,
                    "recording_url": call.recording_url or "",
                    "call_sid": call_sid,
                    "enabled": call.recording_enabled,
                    "transcript": transcript_data.get("text", ""),
                    "transcript_confidence": transcript_data.get("confidence", 0.0),
                    "transcription_sid": transcript_data.get("transcription_sid", ""),
                }

                # Try to get fresh data from Twilio API
                client_result = self._get_twilio_client(company_id)
                if client_result.get("success"):
                    try:
                        client = client_result["client"]
                        recording = client.recordings(call.recording_sid).fetch()
                        recording_entry["duration"] = getattr(
                            recording, "duration", ""
                        )
                        recording_entry["status"] = getattr(
                            recording, "status", ""
                        )
                        recording_entry["url"] = (
                            f"https://api.twilio.com{getattr(recording, 'uri', '')}"
                        )
                    except Exception:
                        # Twilio fetch failed, use DB data
                        pass

                recordings_list.append(recording_entry)

            # Also check metadata for additional recordings
            metadata = json.loads(call.metadata_json or "{}")
            additional_recordings = metadata.get("recordings", [])
            for rec in additional_recordings:
                if rec.get("recording_sid") != call.recording_sid:
                    recordings_list.append(rec)

            logger.info(
                "call_recordings_retrieved",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "recording_count": len(recordings_list),
                },
            )

            return {
                "status": "success",
                "call_sid": call_sid,
                "recordings": recordings_list,
            }

        except Exception as exc:
            logger.error(
                "get_call_recordings_failed call_sid=%s company_id=%s error=%s",
                call_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to get recordings: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Private Helpers
    # ═══════════════════════════════════════════════════════════

    def _get_call_by_sid(
        self,
        call_sid: str,
        company_id: str,
    ) -> Optional[VoiceCall]:
        """Look up a voice call by Twilio CallSid with company isolation.

        Args:
            call_sid: Twilio CallSid.
            company_id: Tenant company ID (BC-001).

        Returns:
            VoiceCall if found, None otherwise.
        """
        if not call_sid:
            return None
        return (
            self.db.query(VoiceCall)
            .filter(
                VoiceCall.twilio_call_sid == call_sid,
                VoiceCall.company_id == company_id,
            )
            .first()
        )

    def _get_twilio_client(self, company_id: str) -> dict:
        """Create a Twilio client from company's voice channel config.

        Handles credential decryption (BC-011) and test environment
        fallback gracefully.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with success=True and client, or success=False with error.
        """
        try:
            from twilio.rest import Client
            from app.config import get_settings

            config = (
                self.db.query(VoiceChannelConfig)
                .filter(VoiceChannelConfig.company_id == company_id)
                .first()
            )

            if not config:
                return {
                    "success": False,
                    "error": "Voice channel not configured for this company",
                }

            settings = get_settings()

            # Decrypt auth token (BC-011)
            auth_token = self._decrypt_credential(
                config.twilio_auth_token_encrypted,
            )

            # In test environment, use settings-level token
            if settings.is_test and not auth_token:
                auth_token = settings.TWILIO_AUTH_TOKEN

            if not config.twilio_account_sid or not auth_token:
                return {
                    "success": False,
                    "error": "Twilio credentials not configured",
                }

            client = Client(config.twilio_account_sid, auth_token)
            return {"success": True, "client": client}

        except ImportError:
            return {
                "success": False,
                "error": "Twilio SDK not installed",
            }
        except Exception as exc:
            logger.error(
                "twilio_client_init_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return {
                "success": False,
                "error": f"Failed to initialize Twilio client: {str(exc)[:200]}",
            }

    def _decrypt_credential(self, encrypted: str) -> str:
        """Decrypt a credential value (BC-011).

        Args:
            encrypted: Encrypted credential string.

        Returns:
            Decrypted plain text string.
        """
        import base64

        if not encrypted:
            return ""

        try:
            from app.config import get_settings
            settings = get_settings()

            if settings.is_test:
                # In test env, just base64 decode
                return base64.b64decode(encrypted.encode()).decode()

            # Production: XOR-based decryption (same pattern as voice_channel_service)
            key = settings.DATA_ENCRYPTION_KEY.encode("utf-8")[:32]
            raw = base64.b64decode(encrypted.encode())
            # Skip the 12-byte nonce
            encrypted_bytes = raw[12:]
            decrypted = bytes(
                [a ^ b for a, b in zip(encrypted_bytes, key)]
            )
            return decrypted.rstrip(b"\0").decode("utf-8")
        except Exception:
            try:
                return base64.b64decode(encrypted.encode()).decode()
            except Exception:
                return ""
