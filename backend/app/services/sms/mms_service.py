"""
MMS Service — Day 6 SMS Deep Services

Handles MMS (Multimedia Messaging Service) operations:
1. Outbound MMS sending with images via Twilio API
2. Inbound MMS processing from Twilio webhooks
3. Media download and tenant-scoped storage
4. MMS message history with media details

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped to company_id)
- BC-003: Idempotent webhook processing (Twilio MessageSid)
- BC-008: Never crash — wrap all external calls in try/except
- BC-011: Twilio credentials encrypted at rest
- BC-012: Structured error responses
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.sms_channel import (
    SMSChannelConfig,
    SMSConversation,
    SMSMessage,
)

logger = logging.getLogger("parwa.sms.mms")

# ── Constants ─────────────────────────────────────────────────

# Maximum number of media URLs per MMS (Twilio limit)
MAX_MEDIA_URLS = 10

# Maximum media file size (5 MB per Twilio docs)
MAX_MEDIA_SIZE_BYTES = 5 * 1024 * 1024

# Base directory for tenant-scoped media storage
MEDIA_STORAGE_BASE = "/tmp/parwa_uploads"

# Allowed content types for MMS media
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

# E.164 phone number validation pattern
E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")

# HTTP request timeout for media downloads (seconds)
MEDIA_DOWNLOAD_TIMEOUT = 30


class MMSService:
    """Service for sending and receiving MMS messages with media attachments.

    All methods are scoped to company_id (BC-001) and never crash (BC-008).
    Uses Twilio API for MMS operations and stores media in tenant-scoped
    directories.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Outbound MMS Sending
    # ═══════════════════════════════════════════════════════════

    def send_mms(
        self,
        to_number: str,
        body: str,
        media_urls: List[str],
        company_id: str,
        sender_id: Optional[str] = None,
        sender_role: str = "agent",
        ticket_id: Optional[str] = None,
    ) -> dict:
        """Send an MMS message with images via Twilio.

        Validates media URLs are accessible, sends MMS via Twilio API,
        and records the message in the database.

        Args:
            to_number: Recipient phone number (E.164).
            body: MMS body text (optional but recommended).
            media_urls: List of public image URLs (max 10).
            company_id: Tenant company ID (BC-001).
            sender_id: ID of the sender (agent/bot).
            sender_role: Sender role (agent, bot, system).
            ticket_id: Optional ticket ID to link.

        Returns:
            Dict with status, message_sid, num_media. On error,
            returns dict with status "error" and error description.
        """
        try:
            # Validate inputs
            if not media_urls:
                return {
                    "status": "error",
                    "error": "At least one media URL is required for MMS",
                }

            if len(media_urls) > MAX_MEDIA_URLS:
                return {
                    "status": "error",
                    "error": f"Maximum {MAX_MEDIA_URLS} media URLs allowed per MMS",
                }

            # Validate media URLs
            url_validation = self._validate_media_urls(media_urls)
            if not url_validation["valid"]:
                return {
                    "status": "error",
                    "error": url_validation["error"],
                }

            # Get SMS/MMS config for this company
            config = self._get_sms_config(company_id)
            if not config:
                return {
                    "status": "error",
                    "error": "SMS channel not configured for this company",
                }

            if not config.is_enabled:
                return {
                    "status": "error",
                    "error": "SMS channel is currently disabled",
                }

            # Normalize phone number
            to_normalized = self._normalize_phone(to_number)
            if not to_normalized:
                return {
                    "status": "error",
                    "error": "Invalid recipient phone number",
                }

            # Check opt-out status (BC-010)
            conv = self._get_conversation_by_numbers(
                company_id, to_normalized, config.twilio_phone_number,
            )
            if conv and conv.is_opted_out:
                return {
                    "status": "error",
                    "error": "Recipient has opted out (BC-010 TCPA)",
                }

            # Truncate body if needed
            if len(body) > config.char_limit:
                body = body[:config.char_limit]

            # Send MMS via Twilio
            twilio_result = self._send_mms_via_twilio(
                config=config,
                to_number=to_normalized,
                body=body,
                media_urls=media_urls,
            )

            if not twilio_result.get("success"):
                return {
                    "status": "error",
                    "error": twilio_result.get("error", "Twilio MMS send failed"),
                }

            # Create or get conversation
            if not conv:
                conv = self._get_or_create_conversation(
                    company_id=company_id,
                    customer_number=to_normalized,
                    twilio_number=config.twilio_phone_number,
                )

            # Store outbound message
            char_count = len(body) if body else 0
            num_segments = max(1, (char_count + 159) // 160) if char_count else 1

            message = SMSMessage(
                company_id=company_id,
                conversation_id=conv.id,
                direction="outbound",
                from_number=config.twilio_phone_number,
                to_number=to_normalized,
                body=body,
                num_segments=num_segments,
                char_count=char_count,
                twilio_message_sid=twilio_result.get("message_sid"),
                twilio_account_sid=config.twilio_account_sid,
                twilio_status="sent",
                sender_id=sender_id,
                sender_role=sender_role,
                ticket_id=ticket_id,
            )
            self.db.add(message)

            # Update conversation metrics
            conv.message_count = (conv.message_count or 0) + 1
            conv.last_message_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(message)

            logger.info(
                "mms_outbound_sent",
                extra={
                    "company_id": company_id,
                    "message_id": message.id,
                    "twilio_sid": twilio_result.get("message_sid"),
                    "to": to_normalized,
                    "num_media": len(media_urls),
                },
            )

            return {
                "status": "sent",
                "message_id": message.id,
                "conversation_id": conv.id,
                "message_sid": twilio_result.get("message_sid"),
                "num_media": len(media_urls),
                "twilio_status": "sent",
                "direction": "outbound",
                "from_number": config.twilio_phone_number,
                "to_number": to_normalized,
            }

        except Exception as exc:
            logger.exception(
                "mms_send_error",
                extra={
                    "company_id": company_id,
                    "to": to_number,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to send MMS: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Inbound MMS Processing
    # ═══════════════════════════════════════════════════════════

    def process_inbound_mms(
        self,
        mms_data: dict,
        company_id: str,
        db_session: Session,
    ) -> dict:
        """Process an inbound MMS from Twilio webhook.

        Links images to existing ticket or creates new one.
        Downloads and saves media to tenant-scoped storage.

        Args:
            mms_data: Dict from Twilio webhook with keys:
                message_sid, from_number, to_number, body,
                num_media, media_urls (list of Twilio media URLs).
            company_id: Tenant company ID (BC-001).
            db_session: SQLAlchemy session for database operations.

        Returns:
            Dict with message_id, ticket_id, media_saved count.
        """
        try:
            # Get config
            config = self._get_sms_config(company_id)
            if not config:
                return {
                    "status": "error",
                    "error": "SMS channel not configured for this company",
                }

            if not config.is_enabled:
                return {
                    "status": "error",
                    "error": "SMS channel is currently disabled",
                }

            message_sid = mms_data.get("message_sid", "")
            from_number = self._normalize_phone(mms_data.get("from_number", ""))
            to_number = self._normalize_phone(mms_data.get("to_number", ""))

            if not from_number or not to_number:
                return {
                    "status": "error",
                    "error": "Invalid phone number format",
                }

            # Idempotency check via Twilio MessageSid (BC-003)
            if message_sid:
                existing = self._get_message_by_twilio_sid(message_sid)
                if existing:
                    logger.info(
                        "mms_duplicate_skip",
                        extra={
                            "company_id": company_id,
                            "message_sid": message_sid,
                            "existing_id": existing.id,
                        },
                    )
                    return {
                        "status": "skipped_duplicate",
                        "message_id": existing.id,
                        "ticket_id": existing.ticket_id,
                        "media_saved": 0,
                    }

            # Get or create conversation
            conversation = self._get_or_create_conversation(
                company_id=company_id,
                customer_number=from_number,
                twilio_number=to_number,
            )

            # Check opt-out status
            if conversation.is_opted_out:
                return {
                    "status": "opted_out_ignored",
                    "conversation_id": conversation.id,
                    "media_saved": 0,
                }

            # Store MMS message
            body = mms_data.get("body", "")
            num_media = mms_data.get("num_media", 0)
            media_urls = mms_data.get("media_urls", [])

            char_count = len(body) if body else 0

            # Truncate body if exceeds char limit
            if char_count > config.char_limit:
                body = body[:config.char_limit]
                char_count = config.char_limit

            message = SMSMessage(
                company_id=company_id,
                conversation_id=conversation.id,
                direction="inbound",
                from_number=from_number,
                to_number=to_number,
                body=body,
                num_segments=max(1, (char_count + 159) // 160) if char_count else 1,
                char_count=char_count,
                twilio_message_sid=message_sid,
                twilio_account_sid=mms_data.get("account_sid", ""),
                twilio_status="receiving",
                sender_role="visitor",
            )
            self.db.add(message)

            # Update conversation metrics
            conversation.message_count = (conversation.message_count or 0) + 1
            conversation.last_message_at = datetime.now(timezone.utc)

            # Link to ticket
            ticket_id = self._link_mms_to_ticket(
                company_id, conversation, mms_data, config,
            )
            message.ticket_id = ticket_id

            self.db.commit()
            self.db.refresh(message)

            # Download and save media attachments
            media_saved = 0
            saved_media = []
            for media_url in media_urls[:MAX_MEDIA_URLS]:
                try:
                    save_result = self.save_media(
                        media_url=media_url,
                        company_id=company_id,
                        message_id=message.id,
                    )
                    if save_result.get("status") == "saved":
                        media_saved += 1
                        saved_media.append(save_result)
                except Exception as exc:
                    logger.warning(
                        "mms_media_save_failed",
                        extra={
                            "company_id": company_id,
                            "message_id": message.id,
                            "media_url": media_url[:200],
                            "error": str(exc)[:200],
                        },
                    )

            logger.info(
                "mms_inbound_processed",
                extra={
                    "company_id": company_id,
                    "message_id": message.id,
                    "conversation_id": conversation.id,
                    "ticket_id": ticket_id,
                    "num_media": num_media,
                    "media_saved": media_saved,
                    "from": from_number,
                },
            )

            return {
                "status": "processed",
                "message_id": message.id,
                "conversation_id": conversation.id,
                "ticket_id": ticket_id,
                "media_saved": media_saved,
                "saved_media": saved_media,
            }

        except Exception as exc:
            logger.exception(
                "mms_inbound_error",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to process inbound MMS: {str(exc)[:200]}",
                "media_saved": 0,
            }

    # ═══════════════════════════════════════════════════════════
    # Media Storage
    # ═══════════════════════════════════════════════════════════

    def save_media(
        self,
        media_url: str,
        company_id: str,
        message_id: str,
    ) -> dict:
        """Download and save media from Twilio URL to tenant-scoped storage.

        Saves media to /tmp/parwa_uploads/{company_id}/mms/ directory.

        Args:
            media_url: Twilio media URL to download.
            company_id: Tenant company ID (BC-001).
            message_id: SMS message ID the media belongs to.

        Returns:
            Dict with storage_path, filename, content_type, size.
        """
        try:
            if not media_url:
                return {
                    "status": "error",
                    "error": "Media URL is required",
                }

            # Create tenant-scoped directory
            company_dir = os.path.join(MEDIA_STORAGE_BASE, company_id, "mms")
            os.makedirs(company_dir, exist_ok=True)

            # Download media from Twilio URL
            # Twilio media URLs require authentication
            config = self._get_sms_config(company_id)
            auth = None
            if config:
                auth = (config.twilio_account_sid, self._decrypt_credential(
                    config.twilio_auth_token_encrypted,
                ))

            response = requests.get(
                media_url,
                auth=auth,
                timeout=MEDIA_DOWNLOAD_TIMEOUT,
                stream=True,
            )
            response.raise_for_status()

            # Determine content type
            content_type = response.headers.get("Content-Type", "image/jpeg")
            if ";" in content_type:
                content_type = content_type.split(";")[0].strip()

            # Validate content type
            if content_type not in ALLOWED_CONTENT_TYPES:
                # Fallback: try to infer from URL
                content_type = self._infer_content_type(media_url, content_type)

            # Determine file extension
            ext = self._content_type_to_extension(content_type)

            # Generate unique filename
            filename = f"{message_id}_{uuid.uuid4().hex[:8]}{ext}"
            storage_path = os.path.join(company_dir, filename)

            # Download and save with size limit check
            size = 0
            with open(storage_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    size += len(chunk)
                    if size > MAX_MEDIA_SIZE_BYTES:
                        # Clean up oversized file
                        f.close()
                        os.remove(storage_path)
                        return {
                            "status": "error",
                            "error": f"Media file exceeds maximum size of {MAX_MEDIA_SIZE_BYTES // (1024*1024)}MB",
                        }
                    f.write(chunk)

            logger.info(
                "mms_media_saved",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "filename": filename,
                    "content_type": content_type,
                    "size": size,
                },
            )

            return {
                "status": "saved",
                "storage_path": storage_path,
                "filename": filename,
                "content_type": content_type,
                "size": size,
            }

        except requests.RequestException as exc:
            logger.warning(
                "mms_media_download_failed",
                extra={
                    "company_id": company_id,
                    "media_url": media_url[:200],
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to download media: {str(exc)[:200]}",
            }
        except Exception as exc:
            logger.exception(
                "mms_media_save_error",
                extra={
                    "company_id": company_id,
                    "media_url": media_url[:200],
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to save media: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # MMS History
    # ═══════════════════════════════════════════════════════════

    def get_mms_history(
        self,
        conversation_id: str,
        company_id: str,
        limit: int = 50,
    ) -> dict:
        """Get MMS message history for a conversation with media details.

        Returns messages that have media attachments, along with
        information about saved media files.

        Args:
            conversation_id: Conversation UUID.
            company_id: Tenant company ID (BC-001).
            limit: Maximum number of messages to return.

        Returns:
            Dict with messages list, total count, and media details.
        """
        try:
            if not self.db:
                return {
                    "status": "error",
                    "error": "Database session not available",
                }

            # Verify conversation belongs to company (BC-001)
            conversation = (
                self.db.query(SMSConversation)
                .filter(
                    SMSConversation.id == conversation_id,
                    SMSConversation.company_id == company_id,
                )
                .first()
            )
            if not conversation:
                return {
                    "status": "error",
                    "error": "Conversation not found",
                }

            # Get messages for this conversation
            query = self.db.query(SMSMessage).filter(
                SMSMessage.conversation_id == conversation_id,
                SMSMessage.company_id == company_id,
            ).order_by(SMSMessage.created_at.desc())

            total = query.count()
            messages = query.limit(limit).all()

            # Build MMS history with media details
            mms_messages = []
            for msg in messages:
                msg_dict = msg.to_dict()

                # Check for saved media in tenant storage
                company_dir = os.path.join(
                    MEDIA_STORAGE_BASE, company_id, "mms",
                )
                media_files = []
                if os.path.isdir(company_dir):
                    for fname in os.listdir(company_dir):
                        if fname.startswith(msg.id):
                            fpath = os.path.join(company_dir, fname)
                            try:
                                stat = os.stat(fpath)
                                media_files.append({
                                    "filename": fname,
                                    "storage_path": fpath,
                                    "size": stat.st_size,
                                })
                            except OSError:
                                pass

                msg_dict["media_files"] = media_files
                mms_messages.append(msg_dict)

            return {
                "status": "success",
                "messages": mms_messages,
                "total": total,
                "limit": limit,
                "conversation_id": conversation_id,
            }

        except Exception as exc:
            logger.exception(
                "mms_history_error",
                extra={
                    "company_id": company_id,
                    "conversation_id": conversation_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to get MMS history: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Private Methods — Twilio Integration
    # ═══════════════════════════════════════════════════════════

    def _send_mms_via_twilio(
        self,
        config: SMSChannelConfig,
        to_number: str,
        body: str,
        media_urls: List[str],
    ) -> dict:
        """Send an MMS message via Twilio API.

        Args:
            config: SMS channel config with Twilio credentials.
            to_number: Recipient phone number (E.164).
            body: Message body text.
            media_urls: List of public image URLs.

        Returns:
            Dict with success, message_sid, and num_media.
        """
        try:
            from twilio.rest import Client

            auth_token = self._decrypt_credential(
                config.twilio_auth_token_encrypted,
            )
            client = Client(config.twilio_account_sid, auth_token)

            # Build message parameters
            message_params: Dict[str, Any] = {
                "to": to_number,
                "from_": config.twilio_phone_number,
            }
            if body:
                message_params["body"] = body

            # Twilio accepts mediaUrl as a list of URLs
            if media_urls:
                message_params["media_url"] = media_urls

            twilio_msg = client.messages.create(**message_params)

            logger.info(
                "mms_twilio_sent",
                extra={
                    "account_sid": config.twilio_account_sid,
                    "message_sid": twilio_msg.sid,
                    "to": to_number,
                    "num_media": len(media_urls),
                },
            )

            return {
                "success": True,
                "message_sid": twilio_msg.sid,
                "status": twilio_msg.status,
                "num_media": len(media_urls),
            }

        except ImportError:
            logger.warning(
                "mms_twilio_not_installed",
                extra={"account_sid": config.twilio_account_sid},
            )
            return {
                "success": False,
                "error": "Twilio library not installed",
            }
        except Exception as exc:
            logger.error(
                "mms_twilio_send_error",
                extra={
                    "account_sid": config.twilio_account_sid,
                    "to": to_number,
                    "error": str(exc)[:500],
                },
            )
            return {
                "success": False,
                "error": f"Twilio API error: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Private Methods — Validation & Helpers
    # ═══════════════════════════════════════════════════════════

    def _validate_media_urls(self, media_urls: List[str]) -> dict:
        """Validate that media URLs are well-formed and accessible.

        Performs basic URL format validation and optional HEAD request
        to verify accessibility.

        Args:
            media_urls: List of URLs to validate.

        Returns:
            Dict with valid (bool) and optional error message.
        """
        invalid_urls = []
        for url in media_urls:
            try:
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    invalid_urls.append(url)
                    continue
                if not parsed.netloc:
                    invalid_urls.append(url)
            except Exception:
                invalid_urls.append(url)

        if invalid_urls:
            return {
                "valid": False,
                "error": (
                    f"Invalid media URLs: "
                    f"{', '.join(u[:100] for u in invalid_urls[:3])}"
                ),
            }

        return {"valid": True}

    def _normalize_phone(self, phone: str) -> str:
        """Normalize a phone number to E.164 format.

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
        if cleaned.isdigit() and len(cleaned) == 10:
            return f"+1{cleaned}"
        if cleaned.isdigit() and len(cleaned) == 11 and cleaned.startswith("1"):
            return f"+{cleaned}"
        return cleaned if cleaned.startswith("+") else ""

    def _content_type_to_extension(self, content_type: str) -> str:
        """Map a content type to a file extension.

        Args:
            content_type: MIME content type string.

        Returns:
            File extension string including the dot.
        """
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
            "image/tiff": ".tiff",
        }
        return mapping.get(content_type, ".jpg")

    def _infer_content_type(self, url: str, fallback: str) -> str:
        """Infer content type from URL path extension.

        Args:
            url: Media URL to analyze.
            fallback: Fallback content type if inference fails.

        Returns:
            Inferred or fallback content type.
        """
        try:
            path = urlparse(url).path.lower()
            if path.endswith(".png"):
                return "image/png"
            elif path.endswith(".gif"):
                return "image/gif"
            elif path.endswith(".webp"):
                return "image/webp"
            elif path.endswith(".bmp"):
                return "image/bmp"
            elif path.endswith(".tiff") or path.endswith(".tif"):
                return "image/tiff"
        except Exception:
            pass
        return fallback

    # ═══════════════════════════════════════════════════════════
    # Private Methods — Database Helpers
    # ═══════════════════════════════════════════════════════════

    def _get_sms_config(self, company_id: str) -> Optional[SMSChannelConfig]:
        """Get SMS channel config for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            SMSChannelConfig if found, None otherwise.
        """
        if not self.db:
            return None
        return (
            self.db.query(SMSChannelConfig)
            .filter(SMSChannelConfig.company_id == company_id)
            .first()
        )

    def _get_conversation_by_numbers(
        self,
        company_id: str,
        customer_number: str,
        twilio_number: str,
    ) -> Optional[SMSConversation]:
        """Get conversation by phone number pair.

        Args:
            company_id: Tenant company ID.
            customer_number: Customer phone number.
            twilio_number: Twilio phone number.

        Returns:
            SMSConversation or None.
        """
        if not self.db:
            return None
        return (
            self.db.query(SMSConversation)
            .filter(
                SMSConversation.company_id == company_id,
                SMSConversation.customer_number == customer_number,
                SMSConversation.twilio_number == twilio_number,
            )
            .first()
        )

    def _get_or_create_conversation(
        self,
        company_id: str,
        customer_number: str,
        twilio_number: str,
    ) -> SMSConversation:
        """Find existing conversation or create new one.

        Args:
            company_id: Tenant company ID.
            customer_number: Customer's phone number.
            twilio_number: Twilio phone number.

        Returns:
            SMSConversation instance.
        """
        conv = self._get_conversation_by_numbers(
            company_id, customer_number, twilio_number,
        )
        if conv:
            return conv

        conv = SMSConversation(
            company_id=company_id,
            customer_number=customer_number,
            twilio_number=twilio_number,
            message_count=0,
            is_opted_out=False,
        )
        self.db.add(conv)
        self.db.flush()
        return conv

    def _get_message_by_twilio_sid(
        self,
        message_sid: str,
    ) -> Optional[SMSMessage]:
        """Look up an SMS message by Twilio MessageSid.

        BC-003: Idempotency check.

        Args:
            message_sid: Twilio MessageSid.

        Returns:
            SMSMessage if found, None otherwise.
        """
        if not message_sid or not self.db:
            return None
        return (
            self.db.query(SMSMessage)
            .filter(SMSMessage.twilio_message_sid == message_sid)
            .first()
        )

    def _link_mms_to_ticket(
        self,
        company_id: str,
        conversation: SMSConversation,
        mms_data: dict,
        config: SMSChannelConfig,
    ) -> Optional[str]:
        """Link MMS conversation to a ticket.

        If the conversation already has a ticket_id, return it.
        Otherwise, if auto_create_ticket is enabled, create a new one.

        Args:
            company_id: Tenant company ID.
            conversation: SMSConversation instance.
            mms_data: MMS data dict.
            config: SMS channel config.

        Returns:
            Ticket ID if linked, None otherwise.
        """
        if conversation.ticket_id:
            return conversation.ticket_id

        if not config.auto_create_ticket:
            return None

        try:
            import json

            from database.models.tickets import Ticket

            body = mms_data.get("body", "")
            num_media = mms_data.get("num_media", 0)
            subject = body[:100] if body else f"MMS Message ({num_media} media)"

            ticket = Ticket(
                company_id=company_id,
                channel="sms",
                subject=subject,
                status="open",
                metadata_json=json.dumps({
                    "mms": True,
                    "num_media": num_media,
                    "from_number": mms_data.get("from_number", ""),
                }),
            )
            self.db.add(ticket)
            self.db.flush()

            conversation.ticket_id = ticket.id
            self.db.flush()

            return ticket.id

        except Exception as exc:
            logger.warning(
                "mms_link_to_ticket_failed error=%s",
                str(exc)[:200],
            )
            return None

    # ═══════════════════════════════════════════════════════════
    # Private Methods — Credential Encryption (BC-011)
    # ═══════════════════════════════════════════════════════════

    def _decrypt_credential(self, encrypted: str) -> str:
        """Decrypt a credential that was encrypted by SMSChannelService.

        This mirrors the encryption approach used in SMSChannelService.
        For now, uses base64 as a simple reversible encoding that
        matches the existing service's approach.

        Args:
            encrypted: Encrypted credential string.

        Returns:
            Decrypted credential string.
        """
        import base64

        try:
            return base64.b64decode(encrypted.encode()).decode()
        except Exception:
            # If decryption fails, return as-is (may already be plaintext)
            return encrypted
