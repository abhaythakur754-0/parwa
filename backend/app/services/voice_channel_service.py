"""
Voice Channel Service — Voice Call API

Handles the complete voice channel lifecycle:
1. Outbound call initiation with Twilio API
2. Inbound call processing with Twilio voice webhook
3. Call status updates from Twilio callbacks
4. Conversation threading by phone number pair
5. TCPA compliance with opt-out tracking (BC-010)
6. Rate limiting for outbound calls (BC-006)
7. Call recording and transcript management
8. Call transfer to human agents
9. Voice config management with encrypted credentials (BC-011)

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped to company_id)
- BC-003: Idempotent webhook processing (Twilio CallSid)
- BC-006: Rate limiting (configurable per hour/day limits)
- BC-010: TCPA compliance (opt-out tracking)
- BC-011: Twilio credentials encrypted at rest
- BC-012: Structured error responses
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from database.models.voice_channel import (
    VoiceCall,
    VoiceChannelConfig,
    VoiceConversation,
)

logger = logging.getLogger("parwa.voice_channel")

# ── Constants ─────────────────────────────────────────────────

# Rate limit window (BC-006)
RATE_LIMIT_HOUR_WINDOW = 60
RATE_LIMIT_DAY_WINDOW = 1440

# E.164 phone number validation pattern
E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")

# Valid call statuses for state transitions
VALID_CALL_STATUSES = {
    "queued", "ringing", "in-progress", "completed",
    "failed", "busy", "no-answer", "canceled",
}

# Valid variant tiers
VALID_VARIANT_TIERS = {"mini_parwa", "parwa", "parwa_high"}


class VoiceChannelService:
    """Service for processing voice calls and managing voice conversations.

    All methods are scoped to company_id (BC-001) and are idempotent
    where applicable (BC-003 via Twilio CallSid).
    """

    def __init__(self, db: Session):
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Outbound Call
    # ═══════════════════════════════════════════════════════════

    def initiate_outbound_call(
        self,
        company_id: str,
        to_number: str,
        variant_tier: str = "parwa",
        message: Optional[str] = None,
        sender_id: Optional[str] = None,
        sender_role: str = "agent",
        ticket_id: Optional[str] = None,
        enable_recording: Optional[bool] = None,
    ) -> dict:
        """Initiate an outbound voice call via Twilio.

        Validates rate limits (BC-006), opt-out status (BC-010),
        and sends via Twilio API.

        Args:
            company_id: Tenant company ID.
            to_number: Recipient phone number (E.164).
            variant_tier: AI variant tier (mini_parwa, parwa, parwa_high).
            message: Optional greeting message (overrides config).
            sender_id: ID of the caller (agent/bot).
            sender_role: Sender role (agent, bot, system).
            ticket_id: Optional ticket ID to link.
            enable_recording: Override config recording setting.

        Returns:
            Dict with status, call_id, twilio_call_sid.
        """
        # Get config
        config = self.get_voice_config(company_id)
        if not config:
            return {"status": "error", "error": "Voice channel not configured"}

        if not config.is_enabled:
            return {"status": "error", "error": "Voice channel is disabled"}

        # Validate variant tier
        if variant_tier not in VALID_VARIANT_TIERS:
            return {
                "status": "error",
                "error": f"Invalid variant_tier: {variant_tier}. "
                         f"Must be one of: {', '.join(VALID_VARIANT_TIERS)}",
            }

        # Normalize phone number
        to_normalized = self._normalize_phone(to_number)
        if not to_normalized:
            return {"status": "error", "error": "Invalid recipient phone number"}

        # Check opt-out status (BC-010)
        conv = self._get_conversation_by_numbers(
            company_id, to_normalized, config.twilio_phone_number,
        )
        if conv and conv.is_opted_out:
            return {
                "status": "error",
                "error": "Recipient has opted out of voice calls (BC-010 TCPA)",
            }

        # BC-006: Rate limit check
        rate_error = self._check_outbound_rate_limit(
            company_id, to_normalized, config,
        )
        if rate_error:
            return {"status": "error", "error": rate_error}

        # Resolve recording setting
        should_record = (
            enable_recording if enable_recording is not None
            else config.enable_recording
        )

        # Build TwiML for the call
        greeting = message or config.greeting_message or "Hello, this is a call from Parwa."
        twiml = self._build_outbound_twiml(greeting, config, variant_tier)

        # Build callback URL
        callback_url = self._get_callback_url(company_id)

        # Send call via Twilio
        twilio_result = self._send_call_via_twilio(
            config=config,
            to_number=to_normalized,
            twiml=twiml,
            callback_url=callback_url,
            enable_recording=should_record,
        )

        if not twilio_result.get("success"):
            return {
                "status": "error",
                "error": twilio_result.get("error", "Twilio call failed"),
            }

        # Create or get conversation
        if not conv:
            conv = self._get_or_create_conversation(
                company_id=company_id,
                customer_number=to_normalized,
                twilio_number=config.twilio_phone_number,
            )

        # Store call record
        call = VoiceCall(
            company_id=company_id,
            conversation_id=conv.id,
            ticket_id=ticket_id,
            twilio_call_sid=twilio_result.get("call_sid"),
            twilio_account_sid=config.twilio_account_sid,
            direction="outbound",
            from_number=config.twilio_phone_number,
            to_number=to_normalized,
            status="queued",
            variant_tier=variant_tier,
            recording_enabled=should_record,
            sender_id=sender_id,
            sender_role=sender_role,
        )
        self.db.add(call)

        # Update conversation metrics
        conv.call_count = (conv.call_count or 0) + 1
        conv.last_call_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(call)

        logger.info(
            "voice_outbound_initiated",
            extra={
                "company_id": company_id,
                "call_id": call.id,
                "twilio_call_sid": twilio_result.get("call_sid"),
                "to": to_normalized,
                "variant_tier": variant_tier,
            },
        )

        return {
            "status": "initiated",
            "call_id": call.id,
            "conversation_id": conv.id,
            "twilio_call_sid": twilio_result.get("call_sid"),
            "direction": "outbound",
            "from_number": config.twilio_phone_number,
            "to_number": to_normalized,
            "variant_tier": variant_tier,
            "recording_enabled": should_record,
        }

    # ═══════════════════════════════════════════════════════════
    # Inbound Call Processing
    # ═══════════════════════════════════════════════════════════

    def process_inbound_call(
        self,
        company_id: str,
        call_data: dict,
    ) -> dict:
        """Process an inbound call from Twilio voice webhook.

        Full pipeline:
        1. Look up voice channel config for the company
        2. Find or create voice conversation
        3. Check TCPA opt-out status (BC-010)
        4. Idempotency check via Twilio CallSid (BC-003)
        5. Store voice call record
        6. Generate TwiML response

        Args:
            company_id: Tenant company ID.
            call_data: Dict from Twilio webhook with keys:
                call_sid, account_sid, from_number, to_number,
                call_status.

        Returns:
            Dict with status, call_id, twiml.
        """
        # Step 1: Get voice config
        config = self.get_voice_config(company_id)
        if not config:
            logger.warning(
                "voice_no_config",
                extra={"company_id": company_id},
            )
            twiml = self._build_reject_twiml("Voice channel not configured")
            return {"status": "error", "error": "Voice channel not configured", "twiml": twiml}

        if not config.is_enabled:
            twiml = self._build_reject_twiml("Voice channel is disabled")
            return {"status": "error", "error": "Voice channel is disabled", "twiml": twiml}

        # Normalize phone numbers
        from_number = self._normalize_phone(call_data.get("from_number", ""))
        to_number = self._normalize_phone(call_data.get("to_number", ""))

        if not from_number or not to_number:
            twiml = self._build_reject_twiml("Invalid phone number")
            return {"status": "error", "error": "Invalid phone number", "twiml": twiml}

        # Step 2: Find or create conversation
        conversation = self._get_or_create_conversation(
            company_id=company_id,
            customer_number=from_number,
            twilio_number=to_number,
        )

        # Step 3: Check TCPA opt-out status (BC-010)
        if conversation.is_opted_out:
            twiml = self._build_reject_twiml(
                "This number has opted out of voice calls"
            )
            return {
                "status": "opted_out_rejected",
                "conversation_id": conversation.id,
                "twiml": twiml,
            }

        # Step 4: Idempotency check via Twilio CallSid (BC-003)
        call_sid = call_data.get("call_sid", "")
        if call_sid:
            existing = self._get_call_by_twilio_sid(call_sid)
            if existing:
                logger.info(
                    "voice_duplicate_skip",
                    extra={
                        "company_id": company_id,
                        "call_sid": call_sid,
                        "existing_id": existing.id,
                    },
                )
                # Return existing TwiML response
                greeting = config.greeting_message or "Hello, how can I help you today?"
                twiml = self._build_inbound_twiml(greeting, config)
                return {
                    "status": "skipped_duplicate",
                    "call_id": existing.id,
                    "conversation_id": existing.conversation_id,
                    "twiml": twiml,
                }

        # Step 5: Store call record
        call = VoiceCall(
            company_id=company_id,
            conversation_id=conversation.id,
            twilio_call_sid=call_sid,
            twilio_account_sid=call_data.get("account_sid", ""),
            direction="inbound",
            from_number=from_number,
            to_number=to_number,
            status="ringing",
            variant_tier=config.default_variant,
            recording_enabled=config.enable_recording,
            sender_role="visitor",
        )
        self.db.add(call)

        # Update conversation metrics
        conversation.call_count = (conversation.call_count or 0) + 1
        conversation.last_call_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(call)

        logger.info(
            "voice_inbound_processed",
            extra={
                "company_id": company_id,
                "call_id": call.id,
                "conversation_id": conversation.id,
                "from": from_number,
            },
        )

        # Step 6: Generate TwiML response
        greeting = config.greeting_message or "Hello, how can I help you today?"
        twiml = self._build_inbound_twiml(greeting, config)

        return {
            "status": "processed",
            "call_id": call.id,
            "conversation_id": conversation.id,
            "twiml": twiml,
        }

    # ═══════════════════════════════════════════════════════════
    # Call Status Updates (Twilio Callback)
    # ═══════════════════════════════════════════════════════════

    def update_call_status(
        self,
        company_id: str,
        call_sid: str,
        status: str,
        duration: Optional[int] = None,
        recording_url: Optional[str] = None,
        recording_sid: Optional[str] = None,
    ) -> dict:
        """Update voice call status from Twilio callback.

        Args:
            company_id: Tenant company ID.
            call_sid: Twilio CallSid.
            status: New call status.
            duration: Call duration in seconds (on completion).
            recording_url: URL of the recording (if recorded).
            recording_sid: Twilio RecordingSid.

        Returns:
            Dict with status.
        """
        call = (
            self.db.query(VoiceCall)
            .filter(
                VoiceCall.twilio_call_sid == call_sid,
                VoiceCall.company_id == company_id,
            )
            .first()
        )

        if not call:
            return {"status": "not_found"}

        # Update status
        if status in VALID_CALL_STATUSES:
            call.status = status

        # Update timing
        if status == "in-progress" and not call.started_at:
            call.started_at = datetime.now(timezone.utc)

        if status in ("completed", "failed", "busy", "no-answer", "canceled"):
            call.ended_at = datetime.now(timezone.utc)

        # Update duration
        if duration is not None:
            call.duration_seconds = duration

            # Update conversation total duration
            if call.conversation_id:
                conv = self.db.query(VoiceConversation).filter(
                    VoiceConversation.id == call.conversation_id,
                ).first()
                if conv:
                    conv.total_duration_seconds = (
                        (conv.total_duration_seconds or 0) + duration
                    )

        # Update recording
        if recording_url:
            call.recording_url = recording_url
        if recording_sid:
            call.recording_sid = recording_sid

        self.db.commit()

        logger.info(
            "voice_call_status_updated",
            extra={
                "company_id": company_id,
                "call_sid": call_sid,
                "status": status,
                "duration": duration,
            },
        )

        return {"status": "updated"}

    # ═══════════════════════════════════════════════════════════
    # Call Management
    # ═══════════════════════════════════════════════════════════

    def get_call(
        self,
        call_id: str,
        company_id: str,
    ) -> Optional[VoiceCall]:
        """Get a voice call with company_id isolation.

        Args:
            call_id: Call UUID.
            company_id: Tenant company ID.

        Returns:
            VoiceCall if found, None otherwise.
        """
        return (
            self.db.query(VoiceCall)
            .filter(
                VoiceCall.id == call_id,
                VoiceCall.company_id == company_id,
            )
            .first()
        )

    def list_calls(
        self,
        company_id: str,
        page: int = 1,
        page_size: int = 50,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """List voice calls with pagination and filters.

        Args:
            company_id: Tenant company ID.
            page: Page number (1-based).
            page_size: Items per page.
            direction: Filter by direction (inbound/outbound).
            status: Filter by call status.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        query = self.db.query(VoiceCall).filter(
            VoiceCall.company_id == company_id,
        )

        if direction:
            query = query.filter(VoiceCall.direction == direction)

        if status:
            query = query.filter(VoiceCall.status == status)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(VoiceCall.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def end_call(
        self,
        company_id: str,
        call_sid: str,
    ) -> dict:
        """Hang up an active call via Twilio API.

        Args:
            company_id: Tenant company ID.
            call_sid: Twilio CallSid to end.

        Returns:
            Dict with status.
        """
        call = (
            self.db.query(VoiceCall)
            .filter(
                VoiceCall.twilio_call_sid == call_sid,
                VoiceCall.company_id == company_id,
            )
            .first()
        )

        if not call:
            return {"status": "error", "error": "Call not found"}

        if call.status in ("completed", "failed", "busy", "no-answer", "canceled"):
            return {"status": "error", "error": f"Call already in terminal state: {call.status}"}

        # Hang up via Twilio API
        try:
            from twilio.rest import Client
            from app.config import get_settings

            config = self.get_voice_config(company_id)
            if not config:
                return {"status": "error", "error": "Voice config not found"}

            settings = get_settings()
            auth_token = self._decrypt_credential(
                config.twilio_auth_token_encrypted,
            )
            if settings.is_test and not auth_token:
                auth_token = settings.TWILIO_AUTH_TOKEN

            client = Client(config.twilio_account_sid, auth_token)
            twilio_call = client.calls(call_sid).update(status="completed")

            call.status = "completed"
            call.ended_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                "voice_call_ended",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                },
            )

            return {"status": "ended", "call_id": call.id}
        except Exception as exc:
            logger.error(
                "voice_end_call_failed call_sid=%s error=%s",
                call_sid, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to end call: {str(exc)[:200]}",
            }

    def transfer_call(
        self,
        company_id: str,
        call_sid: str,
        to_number: str,
    ) -> dict:
        """Warm transfer an active call to another number.

        Args:
            company_id: Tenant company ID.
            call_sid: Twilio CallSid to transfer.
            to_number: Number to transfer to.

        Returns:
            Dict with status.
        """
        call = (
            self.db.query(VoiceCall)
            .filter(
                VoiceCall.twilio_call_sid == call_sid,
                VoiceCall.company_id == company_id,
            )
            .first()
        )

        if not call:
            return {"status": "error", "error": "Call not found"}

        if call.status != "in-progress":
            return {
                "status": "error",
                "error": f"Call is not in-progress (current: {call.status})",
            }

        to_normalized = self._normalize_phone(to_number)
        if not to_normalized:
            return {"status": "error", "error": "Invalid transfer number"}

        # Transfer via Twilio API
        try:
            from twilio.rest import Client
            from app.config import get_settings

            config = self.get_voice_config(company_id)
            if not config:
                return {"status": "error", "error": "Voice config not found"}

            settings = get_settings()
            auth_token = self._decrypt_credential(
                config.twilio_auth_token_encrypted,
            )
            if settings.is_test and not auth_token:
                auth_token = settings.TWILIO_AUTH_TOKEN

            client = Client(config.twilio_account_sid, auth_token)

            # Warm transfer: dial the new number
            twiml = (
                f'<Response><Dial>{to_normalized}</Dial></Response>'
            )
            twilio_call = client.calls(call_sid).update(twiml=twiml)

            # Update metadata
            metadata = json.loads(call.metadata_json or "{}")
            metadata["transferred_to"] = to_normalized
            metadata["transferred_at"] = datetime.now(timezone.utc).isoformat()
            call.metadata_json = json.dumps(metadata)
            self.db.commit()

            logger.info(
                "voice_call_transferred",
                extra={
                    "company_id": company_id,
                    "call_sid": call_sid,
                    "transferred_to": to_normalized,
                },
            )

            return {
                "status": "transferred",
                "call_id": call.id,
                "transferred_to": to_normalized,
            }
        except Exception as exc:
            logger.error(
                "voice_transfer_failed call_sid=%s error=%s",
                call_sid, str(exc)[:200],
            )
            return {
                "status": "error",
                "error": f"Failed to transfer call: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Conversation Management
    # ═══════════════════════════════════════════════════════════

    def get_conversation(
        self,
        conversation_id: str,
        company_id: str,
    ) -> Optional[VoiceConversation]:
        """Get a voice conversation with company_id isolation.

        Args:
            conversation_id: Conversation UUID.
            company_id: Tenant company ID.

        Returns:
            VoiceConversation if found, None otherwise.
        """
        return (
            self.db.query(VoiceConversation)
            .filter(
                VoiceConversation.id == conversation_id,
                VoiceConversation.company_id == company_id,
            )
            .first()
        )

    def list_conversations(
        self,
        company_id: str,
        page: int = 1,
        page_size: int = 50,
        is_opted_out: Optional[bool] = None,
    ) -> dict:
        """List voice conversations with pagination and filters.

        Args:
            company_id: Tenant company ID.
            page: Page number (1-based).
            page_size: Items per page.
            is_opted_out: Filter by opt-out status.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        query = self.db.query(VoiceConversation).filter(
            VoiceConversation.company_id == company_id,
        )

        if is_opted_out is not None:
            query = query.filter(
                VoiceConversation.is_opted_out == is_opted_out,
            )

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(VoiceConversation.updated_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ═══════════════════════════════════════════════════════════
    # Call History
    # ═══════════════════════════════════════════════════════════

    def get_call_history(
        self,
        company_id: str,
        phone_number: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Get call history with optional filters.

        Args:
            company_id: Tenant company ID.
            phone_number: Filter by phone number (from or to).
            direction: Filter by direction.
            status: Filter by status.
            page: Page number.
            page_size: Items per page.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        query = self.db.query(VoiceCall).filter(
            VoiceCall.company_id == company_id,
        )

        if phone_number:
            normalized = self._normalize_phone(phone_number)
            if normalized:
                query = query.filter(
                    or_(
                        VoiceCall.from_number == normalized,
                        VoiceCall.to_number == normalized,
                    )
                )

        if direction:
            query = query.filter(VoiceCall.direction == direction)

        if status:
            query = query.filter(VoiceCall.status == status)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(VoiceCall.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ═══════════════════════════════════════════════════════════
    # Voice Config Management
    # ═══════════════════════════════════════════════════════════

    def get_voice_config(
        self,
        company_id: str,
    ) -> Optional[VoiceChannelConfig]:
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

    def create_voice_config(
        self,
        company_id: str,
        data: dict,
    ) -> dict:
        """Create voice channel config for a company.

        Encrypts Twilio auth token (BC-011).

        Args:
            company_id: Tenant company ID.
            data: Config data dict.

        Returns:
            Dict with status and config.
        """
        existing = self.get_voice_config(company_id)
        if existing:
            return {"status": "error", "error": "Voice config already exists"}

        encrypted_token = self._encrypt_credential(
            data.get("twilio_auth_token", ""),
        )

        config = VoiceChannelConfig(
            company_id=company_id,
            twilio_account_sid=data.get("twilio_account_sid", ""),
            twilio_auth_token_encrypted=encrypted_token,
            twilio_phone_number=data.get("twilio_phone_number", ""),
            is_enabled=data.get("is_enabled", True),
            default_variant=data.get("default_variant", "parwa"),
            max_call_duration_minutes=data.get("max_call_duration_minutes", 30),
            enable_recording=data.get("enable_recording", False),
            speech_language=data.get("speech_language", "en-IN"),
            tts_voice=data.get("tts_voice", "Polly.Aditi"),
            transfer_number=data.get("transfer_number"),
            max_calls_per_hour=data.get("max_calls_per_hour", 10),
            max_calls_per_day=data.get("max_calls_per_day", 100),
            greeting_message=data.get("greeting_message"),
            after_hours_message=data.get("after_hours_message"),
            business_hours_json=data.get("business_hours_json", "{}"),
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        logger.info(
            "voice_config_created",
            extra={"company_id": company_id},
        )

        return {"status": "created", "config": config.to_dict()}

    def update_voice_config(
        self,
        company_id: str,
        updates: dict,
    ) -> dict:
        """Update voice channel config (partial update).

        Args:
            company_id: Tenant company ID.
            updates: Dict of fields to update.

        Returns:
            Dict with status and updated config.
        """
        config = self.get_voice_config(company_id)
        if not config:
            return {"status": "error", "error": "Voice config not found"}

        allowed_fields = [
            "is_enabled", "default_variant", "max_call_duration_minutes",
            "enable_recording", "speech_language", "tts_voice",
            "transfer_number", "max_calls_per_hour", "max_calls_per_day",
            "greeting_message", "after_hours_message",
            "business_hours_json", "twilio_phone_number",
        ]

        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                setattr(config, field, updates[field])

        # Encrypt auth token if provided (BC-011)
        if "twilio_auth_token" in updates and updates["twilio_auth_token"]:
            config.twilio_auth_token_encrypted = (
                self._encrypt_credential(updates["twilio_auth_token"])
            )

        # Update account SID if provided
        if "twilio_account_sid" in updates and updates["twilio_account_sid"]:
            config.twilio_account_sid = updates["twilio_account_sid"]

        self.db.commit()
        self.db.refresh(config)

        logger.info(
            "voice_config_updated",
            extra={"company_id": company_id},
        )

        return {"status": "updated", "config": config.to_dict()}

    def delete_voice_config(
        self,
        company_id: str,
    ) -> dict:
        """Delete voice channel config for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with status.
        """
        config = self.get_voice_config(company_id)
        if not config:
            return {"status": "error", "error": "Voice config not found"}

        self.db.delete(config)
        self.db.commit()

        logger.info(
            "voice_config_deleted",
            extra={"company_id": company_id},
        )

        return {"status": "deleted"}

    # ═══════════════════════════════════════════════════════════
    # Private Methods
    # ═══════════════════════════════════════════════════════════

    def _normalize_phone(self, phone: str) -> str:
        """Normalize a phone number to E.164 format.

        Strips spaces, dashes, parens. Validates E.164 pattern.

        Args:
            phone: Raw phone number string.

        Returns:
            Normalized E.164 phone number or empty string.
        """
        if not phone:
            return ""
        cleaned = re.sub(r"[\s\-\(\)\.]", "", phone)
        if E164_PATTERN.match(cleaned):
            return cleaned
        # If no + prefix, try adding it (US numbers)
        if cleaned.isdigit() and len(cleaned) == 10:
            return f"+1{cleaned}"
        if cleaned.isdigit() and len(cleaned) == 11 and cleaned.startswith("1"):
            return f"+{cleaned}"
        return cleaned if cleaned.startswith("+") else ""

    def _get_or_create_conversation(
        self,
        company_id: str,
        customer_number: str,
        twilio_number: str,
    ) -> VoiceConversation:
        """Find existing conversation or create new one.

        Thread by unique phone number pair per company.

        Args:
            company_id: Tenant company ID.
            customer_number: Customer's phone number.
            twilio_number: Twilio phone number.

        Returns:
            VoiceConversation instance.
        """
        conv = (
            self.db.query(VoiceConversation)
            .filter(
                VoiceConversation.company_id == company_id,
                VoiceConversation.customer_number == customer_number,
                VoiceConversation.twilio_number == twilio_number,
            )
            .first()
        )

        if conv:
            return conv

        conv = VoiceConversation(
            company_id=company_id,
            customer_number=customer_number,
            twilio_number=twilio_number,
            call_count=0,
            total_duration_seconds=0,
            is_opted_out=False,
        )
        self.db.add(conv)
        self.db.flush()
        return conv

    def _get_conversation_by_numbers(
        self,
        company_id: str,
        customer_number: str,
        twilio_number: str,
    ) -> Optional[VoiceConversation]:
        """Get conversation by phone number pair.

        Args:
            company_id: Tenant company ID.
            customer_number: Customer phone number.
            twilio_number: Twilio phone number.

        Returns:
            VoiceConversation or None.
        """
        return (
            self.db.query(VoiceConversation)
            .filter(
                VoiceConversation.company_id == company_id,
                VoiceConversation.customer_number == customer_number,
                VoiceConversation.twilio_number == twilio_number,
            )
            .first()
        )

    def _get_call_by_twilio_sid(
        self,
        call_sid: str,
    ) -> Optional[VoiceCall]:
        """Look up a voice call by Twilio CallSid.

        BC-003: Idempotency check.

        Args:
            call_sid: Twilio CallSid.

        Returns:
            VoiceCall if found, None otherwise.
        """
        if not call_sid:
            return None
        return (
            self.db.query(VoiceCall)
            .filter(VoiceCall.twilio_call_sid == call_sid)
            .first()
        )

    def _check_outbound_rate_limit(
        self,
        company_id: str,
        to_number: str,
        config: VoiceChannelConfig,
    ) -> Optional[str]:
        """Check BC-006 outbound rate limit.

        Args:
            company_id: Tenant company ID.
            to_number: Recipient phone number.
            config: Voice channel config.

        Returns:
            Error message if exceeded, None otherwise.
        """
        now = datetime.now(timezone.utc)

        # Hourly check
        since_hour = now - timedelta(minutes=RATE_LIMIT_HOUR_WINDOW)
        hourly_count = (
            self.db.query(func.count(VoiceCall.id))
            .filter(
                VoiceCall.company_id == company_id,
                VoiceCall.direction == "outbound",
                VoiceCall.to_number == to_number,
                VoiceCall.created_at >= since_hour,
            )
            .scalar()
        ) or 0

        if hourly_count >= config.max_calls_per_hour:
            return (
                f"BC-006: Hourly call limit exceeded "
                f"({hourly_count}/{config.max_calls_per_hour})"
            )

        # Daily check
        since_day = now - timedelta(minutes=RATE_LIMIT_DAY_WINDOW)
        daily_count = (
            self.db.query(func.count(VoiceCall.id))
            .filter(
                VoiceCall.company_id == company_id,
                VoiceCall.direction == "outbound",
                VoiceCall.to_number == to_number,
                VoiceCall.created_at >= since_day,
            )
            .scalar()
        ) or 0

        if daily_count >= config.max_calls_per_day:
            return (
                f"BC-006: Daily call limit exceeded "
                f"({daily_count}/{config.max_calls_per_day})"
            )

        return None

    def _build_outbound_twiml(
        self,
        greeting: str,
        config: VoiceChannelConfig,
        variant_tier: str,
    ) -> str:
        """Build TwiML for an outbound call.

        Args:
            greeting: Greeting message.
            config: Voice channel config.
            variant_tier: Variant tier for the call.

        Returns:
            TwiML string.
        """
        # Escape XML special chars in greeting
        greeting_escaped = (
            greeting.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

        twiml = (
            f'<Response>'
            f'<Say language="{config.speech_language}" voice="{config.tts_voice}">'
            f'{greeting_escaped}'
            f'</Say>'
        )

        # If transfer number is configured and variant allows, add Dial
        if config.transfer_number:
            twiml += f'<Dial timeout="30">{config.transfer_number}</Dial>'

        twiml += '</Response>'
        return twiml

    def _build_inbound_twiml(
        self,
        greeting: str,
        config: VoiceChannelConfig,
    ) -> str:
        """Build TwiML for an inbound call.

        Args:
            greeting: Greeting message.
            config: Voice channel config.

        Returns:
            TwiML string.
        """
        greeting_escaped = (
            greeting.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

        twiml = (
            f'<Response>'
            f'<Say language="{config.speech_language}" voice="{config.tts_voice}">'
            f'{greeting_escaped}'
            f'</Say>'
            f'<Gather input="speech dtmf" timeout="10" numDigits="1" '
            f'speechTimeout="auto" language="{config.speech_language}">'
            f'<Say language="{config.speech_language}" voice="{config.tts_voice}">'
            f'Please speak or press a key to continue.'
            f'</Say>'
            f'</Gather>'
        )

        # Fallback if no input
        if config.transfer_number:
            twiml += (
                f'<Say language="{config.speech_language}" voice="{config.tts_voice}">'
                f'Connecting you to an agent.'
                f'</Say>'
                f'<Dial timeout="30">{config.transfer_number}</Dial>'
            )
        else:
            twiml += (
                f'<Say language="{config.speech_language}" voice="{config.tts_voice}">'
                f'Goodbye.'
                f'</Say>'
            )

        twiml += '</Response>'
        return twiml

    def _build_reject_twiml(self, reason: str) -> str:
        """Build TwiML to reject a call.

        Args:
            reason: Reason for rejection.

        Returns:
            TwiML string.
        """
        reason_escaped = (
            reason.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            f'<Response>'
            f'<Say>{reason_escaped}</Say>'
            f'<Hangup/>'
            f'</Response>'
        )

    def _get_callback_url(self, company_id: str) -> str:
        """Build the status callback URL for a company's calls.

        Args:
            company_id: Tenant company ID.

        Returns:
            Callback URL string.
        """
        from app.config import get_settings
        settings = get_settings()

        base_url = settings.FRONTEND_URL or "http://localhost:3000"
        # Use the API path that's routed through the gateway
        return f"{base_url}/api/v1/voice/webhook/status?company_id={company_id}"

    def _send_call_via_twilio(
        self,
        config: VoiceChannelConfig,
        to_number: str,
        twiml: str,
        callback_url: str,
        enable_recording: bool = False,
    ) -> dict:
        """Send a voice call via Twilio API.

        Args:
            config: Voice channel config with credentials.
            to_number: Recipient phone number.
            twiml: TwiML for the call.
            callback_url: Status callback URL.
            enable_recording: Whether to record the call.

        Returns:
            Dict with success, call_sid, error.
        """
        try:
            from twilio.rest import Client
            from app.config import get_settings

            settings = get_settings()
            auth_token = self._decrypt_credential(
                config.twilio_auth_token_encrypted,
            )

            # In test env, use settings-level token if available
            if settings.is_test and not auth_token:
                auth_token = settings.TWILIO_AUTH_TOKEN

            client = Client(
                config.twilio_account_sid,
                auth_token,
            )

            call = client.calls.create(
                to=to_number,
                from_=config.twilio_phone_number,
                twiml=twiml,
                status_callback=callback_url,
                status_callback_event=[
                    "initiated", "ringing", "answered", "completed",
                ],
                record=enable_recording,
            )

            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
            }
        except Exception as exc:
            error_str = str(exc)
            logger.error(
                "twilio_call_failed to=%s error=%s",
                to_number, error_str[:200],
            )
            return {
                "success": False,
                "error": error_str[:500],
            }

    def _encrypt_credential(self, value: str) -> str:
        """Encrypt a credential value at rest (BC-011).

        In test environment, returns base64-encoded placeholder.
        In production, uses XOR encryption via DATA_ENCRYPTION_KEY.

        Args:
            value: Plain text credential.

        Returns:
            Encrypted string.
        """
        import base64

        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.is_test:
                # In test env, just base64 encode
                return base64.b64encode(value.encode()).decode()

            # Production: XOR-based encryption (same as SMS channel)
            key = settings.DATA_ENCRYPTION_KEY.encode("utf-8")[:32]
            import os

            nonce = os.urandom(12)
            padded = value.encode("utf-8").ljust(32, b"\0")
            encrypted = bytes(
                [a ^ b for a, b in zip(padded, key)]
            )
            return base64.b64encode(nonce + encrypted).decode()
        except Exception:
            return base64.b64encode(value.encode()).decode()

    def _decrypt_credential(self, encrypted: str) -> str:
        """Decrypt a credential value (BC-011).

        Args:
            encrypted: Encrypted credential string.

        Returns:
            Decrypted plain text string.
        """
        import base64

        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.is_test:
                return base64.b64decode(encrypted.encode()).decode()

            key = settings.DATA_ENCRYPTION_KEY.encode("utf-8")[:32]
            decoded = base64.b64decode(encrypted.encode())
            nonce = decoded[:12]
            encrypted_data = decoded[12:44]
            decrypted = bytes(
                [a ^ b for a, b in zip(encrypted_data, key)]
            )
            return decrypted.rstrip(b"\0").decode("utf-8")
        except Exception:
            return base64.b64decode(encrypted.encode()).decode()
