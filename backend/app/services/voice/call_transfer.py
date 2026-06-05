"""
Call Transfer Service — Cold Transfer, Warm Handoff & Conference

Manages call transfer operations via Twilio API:
1. Cold (blind) transfer: Immediately redirect to a new number
2. Warm handoff: Call agent first, play whisper, then connect
3. Conference call: Create multi-party conferences
4. Cancel transfer: Abort a pending warm handoff

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

logger = logging.getLogger("parwa.voice.call_transfer")

# ── Constants ─────────────────────────────────────────────────

# Conference settings
CONFERENCE_MAX_PARTICIPANTS = 10
CONFERENCE_TIMEOUT_SECONDS = 30

# Transfer states stored in call metadata
TRANSFER_STATE_PENDING = "pending"
TRANSFER_STATE_CONNECTED = "connected"
TRANSFER_STATE_CANCELLED = "cancelled"
TRANSFER_STATE_FAILED = "failed"


class CallTransferService:
    """Service for transferring calls via Twilio API.

    Supports cold transfers (blind), warm handoffs (with whisper),
    and multi-party conference calls. All methods scoped by
    company_id (BC-001) and never crash (BC-008).
    """

    def __init__(self, db: Session):
        """Initialize with database session.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Cold Transfer (Blind Transfer)
    # ═══════════════════════════════════════════════════════════

    def cold_transfer(
        self,
        call_sid: str,
        to_number: str,
        company_id: str,
    ) -> dict:
        """Perform a blind (cold) transfer — immediately redirect the call.

        Redirects the active call to a new number without first
        consulting the target agent. The caller hears hold music
        briefly while the redirect takes effect.

        Args:
            call_sid: Twilio CallSid of the active call.
            to_number: Phone number to transfer to (E.164).
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with status, transferred_to on success.
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

            if call.status != "in-progress":
                return {
                    "status": "error",
                    "error": f"Call is not in-progress (current: {call.status})",
                }

            # Validate target number
            if not to_number or not to_number.startswith("+"):
                return {
                    "status": "error",
                    "error": "Invalid target phone number (must be E.164 format)",
                }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]

            # Perform cold transfer via TwiML redirect
            twiml = (
                f'<Response>'
                f'<Say>Transferring your call now.</Say>'
                f'<Dial timeout="30">{to_number}</Dial>'
                f'</Response>'
            )

            twilio_call = client.calls(call_sid).update(twiml=twiml)

            # Update call metadata
            metadata = json.loads(call.metadata_json or "{}")
            metadata["transfer_type"] = "cold"
            metadata["transferred_to"] = to_number
            metadata["transferred_at"] = datetime.now(timezone.utc).isoformat()
            metadata["transfer_status"] = TRANSFER_STATE_CONNECTED
            call.metadata_json = json.dumps(metadata)
            self.db.commit()

            logger.info(
                "cold_transfer_completed",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "transferred_to": to_number,
                },
            )

            return {
                "status": "transferred",
                "transferred_to": to_number,
                "transfer_type": "cold",
                "call_id": call.id,
            }

        except Exception as exc:
            logger.error(
                "cold_transfer_failed call_sid=%s company_id=%s error=%s",
                call_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to perform cold transfer: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Warm Handoff (Attended Transfer)
    # ═══════════════════════════════════════════════════════════

    def warm_handoff(
        self,
        call_sid: str,
        to_number: str,
        whisper_message: str,
        company_id: str,
    ) -> dict:
        """Perform a warm transfer — call the agent first, then connect.

        Places the original caller on hold, dials the target agent,
        plays a whisper message to the agent, and upon answer bridges
        the two calls together via a Twilio conference.

        Args:
            call_sid: Twilio CallSid of the active call.
            to_number: Agent's phone number to call (E.164).
            whisper_message: Message to whisper to the agent before bridging.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with status, conference_sid on success.
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

            if call.status != "in-progress":
                return {
                    "status": "error",
                    "error": f"Call is not in-progress (current: {call.status})",
                }

            # Validate target number
            if not to_number or not to_number.startswith("+"):
                return {
                    "status": "error",
                    "error": "Invalid agent phone number (must be E.164 format)",
                }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]
            config = self._get_voice_config(company_id)
            if not config:
                return {
                    "status": "error",
                    "error": "Voice config not found",
                }

            # Generate a unique conference ID
            conference_friendly_name = (
                f"parwa-warm-{company_id[:8]}-{call_sid[:8]}"
            )

            # Step 1: Move the original caller into a conference (on hold)
            caller_twiml = (
                f'<Response>'
                f'<Say>Please hold while we connect you to an agent.</Say>'
                f'<Dial>'
                f'<Conference '
                f'waitUrl="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical" '
                f'startConferenceOnEnter="true" '
                f'endConferenceOnExit="true">'
                f'{conference_friendly_name}'
                f'</Conference>'
                f'</Dial>'
                f'</Response>'
            )

            client.calls(call_sid).update(twiml=caller_twiml)

            # Step 2: Call the agent, whisper, then add to same conference
            # Escape XML in whisper message
            whisper_escaped = (
                whisper_message
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )

            agent_twiml = (
                f'<Response>'
                f'<Say>{whisper_escaped}</Say>'
                f'<Dial>'
                f'<Conference '
                f'startConferenceOnEnter="true" '
                f'endConferenceOnExit="false">'
                f'{conference_friendly_name}'
                f'</Conference>'
                f'</Dial>'
                f'</Response>'
            )

            agent_call = client.calls.create(
                to=to_number,
                from_=config.twilio_phone_number,
                twiml=agent_twiml,
            )

            # Update call metadata
            metadata = json.loads(call.metadata_json or "{}")
            metadata["transfer_type"] = "warm"
            metadata["transferred_to"] = to_number
            metadata["transferred_at"] = datetime.now(timezone.utc).isoformat()
            metadata["transfer_status"] = TRANSFER_STATE_PENDING
            metadata["conference_name"] = conference_friendly_name
            metadata["agent_call_sid"] = agent_call.sid
            metadata["whisper_message"] = whisper_message
            call.metadata_json = json.dumps(metadata)
            self.db.commit()

            logger.info(
                "warm_handoff_initiated",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "transferred_to": to_number,
                    "conference_name": conference_friendly_name,
                    "agent_call_sid": agent_call.sid,
                },
            )

            return {
                "status": "warm_handoff_initiated",
                "conference_sid": conference_friendly_name,
                "agent_call_sid": agent_call.sid,
                "transferred_to": to_number,
                "transfer_type": "warm",
                "call_id": call.id,
            }

        except Exception as exc:
            logger.error(
                "warm_handoff_failed call_sid=%s company_id=%s error=%s",
                call_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to perform warm handoff: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Conference Call
    # ═══════════════════════════════════════════════════════════

    def conference_call(
        self,
        call_sid: str,
        participant_numbers: list,
        company_id: str,
    ) -> dict:
        """Create a conference with multiple participants.

        Moves the original caller into a conference room and
        dials each participant, adding them to the same conference.

        Args:
            call_sid: Twilio CallSid of the original call.
            participant_numbers: List of phone numbers to add (E.164).
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with conference_sid, participant_sids on success.
            Dict with status='error' on failure.
        """
        try:
            # Validate participant list
            if not participant_numbers or not isinstance(participant_numbers, list):
                return {
                    "status": "error",
                    "error": "At least one participant number is required",
                }

            if len(participant_numbers) > CONFERENCE_MAX_PARTICIPANTS:
                return {
                    "status": "error",
                    "error": (
                        f"Maximum {CONFERENCE_MAX_PARTICIPANTS} participants allowed, "
                        f"got {len(participant_numbers)}"
                    ),
                }

            # Verify the call belongs to this company (BC-001)
            call = self._get_call_by_sid(call_sid, company_id)
            if not call:
                return {
                    "status": "error",
                    "error": "Call not found for this company",
                }

            if call.status != "in-progress":
                return {
                    "status": "error",
                    "error": f"Call is not in-progress (current: {call.status})",
                }

            # Validate all participant numbers
            for num in participant_numbers:
                if not num or not num.startswith("+"):
                    return {
                        "status": "error",
                        "error": f"Invalid participant number: {num}",
                    }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]
            config = self._get_voice_config(company_id)
            if not config:
                return {
                    "status": "error",
                    "error": "Voice config not found",
                }

            # Generate conference room name
            conference_name = (
                f"parwa-conf-{company_id[:8]}-{call_sid[:8]}"
            )

            # Step 1: Move original caller into the conference
            caller_twiml = (
                f'<Response>'
                f'<Say>You are being added to a conference call.</Say>'
                f'<Dial>'
                f'<Conference '
                f'waitUrl="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical" '
                f'startConferenceOnEnter="true" '
                f'endConferenceOnExit="true">'
                f'{conference_name}'
                f'</Conference>'
                f'</Dial>'
                f'</Response>'
            )

            client.calls(call_sid).update(twiml=caller_twiml)

            # Step 2: Dial each participant into the same conference
            participant_sids: List[str] = []
            participant_twiml = (
                f'<Response>'
                f'<Say>You are being added to a conference call.</Say>'
                f'<Dial>'
                f'<Conference '
                f'startConferenceOnEnter="true" '
                f'endConferenceOnExit="false">'
                f'{conference_name}'
                f'</Conference>'
                f'</Dial>'
                f'</Response>'
            )

            for number in participant_numbers:
                try:
                    participant_call = client.calls.create(
                        to=number,
                        from_=config.twilio_phone_number,
                        twiml=participant_twiml,
                    )
                    participant_sids.append({
                        "number": number,
                        "call_sid": participant_call.sid,
                    })
                except Exception as dial_exc:
                    logger.warning(
                        "conference_participant_dial_failed number=%s error=%s",
                        number, str(dial_exc)[:200],
                    )
                    participant_sids.append({
                        "number": number,
                        "call_sid": None,
                        "error": str(dial_exc)[:200],
                    })

            # Update call metadata
            metadata = json.loads(call.metadata_json or "{}")
            metadata["conference_name"] = conference_name
            metadata["conference_participants"] = participant_sids
            metadata["conference_created_at"] = datetime.now(timezone.utc).isoformat()
            call.metadata_json = json.dumps(metadata)
            self.db.commit()

            successful_participants = [
                p for p in participant_sids if p.get("call_sid")
            ]

            logger.info(
                "conference_call_created",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "conference_name": conference_name,
                    "participant_count": len(successful_participants),
                    "total_attempted": len(participant_numbers),
                },
            )

            return {
                "status": "conference_created",
                "conference_sid": conference_name,
                "participant_sids": participant_sids,
                "successful_participants": len(successful_participants),
                "total_attempted": len(participant_numbers),
                "call_id": call.id,
            }

        except Exception as exc:
            logger.error(
                "conference_call_failed call_sid=%s company_id=%s error=%s",
                call_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to create conference call: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Cancel Transfer
    # ═══════════════════════════════════════════════════════════

    def cancel_transfer(
        self,
        call_sid: str,
        company_id: str,
    ) -> dict:
        """Cancel a pending warm handoff before the agent answers.

        If the target agent has not yet answered, this will hang up
        the agent call and return the original caller from hold.

        Args:
            call_sid: Twilio CallSid of the original call.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with status on success.
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

            metadata = json.loads(call.metadata_json or "{}")
            transfer_status = metadata.get("transfer_status", "")
            agent_call_sid = metadata.get("agent_call_sid", "")

            # Check if there's a pending warm handoff
            if not agent_call_sid:
                return {
                    "status": "error",
                    "error": "No pending transfer found for this call",
                }

            if transfer_status == TRANSFER_STATE_CONNECTED:
                return {
                    "status": "error",
                    "error": "Transfer already connected — cannot cancel",
                }

            if transfer_status == TRANSFER_STATE_CANCELLED:
                return {
                    "status": "error",
                    "error": "Transfer already cancelled",
                }

            # Get Twilio client
            client_result = self._get_twilio_client(company_id)
            if not client_result.get("success"):
                return {
                    "status": "error",
                    "error": client_result.get("error", "Twilio not configured"),
                }

            client = client_result["client"]

            # Hang up the agent call
            try:
                client.calls(agent_call_sid).update(status="completed")
            except Exception as hangup_exc:
                logger.warning(
                    "cancel_transfer_agent_hangup_failed sid=%s error=%s",
                    agent_call_sid, str(hangup_exc)[:200],
                )

            # Return the original caller from hold
            try:
                config = self._get_voice_config(company_id)
                greeting = "The transfer was cancelled. How else can I help you?"
                caller_twiml = f'<Response><Say>{greeting}</Say></Response>'
                client.calls(call_sid).update(twiml=caller_twiml)
            except Exception as update_exc:
                logger.warning(
                    "cancel_transfer_caller_update_failed sid=%s error=%s",
                    call_sid, str(update_exc)[:200],
                )

            # Update call metadata
            metadata["transfer_status"] = TRANSFER_STATE_CANCELLED
            metadata["transfer_cancelled_at"] = (
                datetime.now(timezone.utc).isoformat()
            )
            call.metadata_json = json.dumps(metadata)
            self.db.commit()

            logger.info(
                "transfer_cancelled",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "agent_call_sid": agent_call_sid,
                },
            )

            return {
                "status": "transfer_cancelled",
                "call_id": call.id,
            }

        except Exception as exc:
            logger.error(
                "cancel_transfer_failed call_sid=%s company_id=%s error=%s",
                call_sid, company_id, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to cancel transfer: {str(exc)[:200]}",
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

    def _get_voice_config(self, company_id: str) -> Optional[VoiceChannelConfig]:
        """Get voice channel config for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            VoiceChannelConfig if found, None otherwise.
        """
        return (
            self.db.query(VoiceChannelConfig)
            .filter(VoiceChannelConfig.company_id == company_id)
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

            config = self._get_voice_config(company_id)
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
                return base64.b64decode(encrypted.encode()).decode()

            key = settings.DATA_ENCRYPTION_KEY.encode("utf-8")[:32]
            raw = base64.b64decode(encrypted.encode())
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
