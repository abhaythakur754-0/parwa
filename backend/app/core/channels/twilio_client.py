"""
Twilio Client Wrapper (Day 7 - CHANNEL-2)

Provides a unified interface for Twilio operations:
- SMS sending with delivery tracking
- Voice call initiation
- Webhook signature verification (HMAC)
- Rate limiting integration
- TCPA compliance checks

Building Codes:
- BC-001: All operations scoped by company_id
- BC-003: Idempotent operations via Twilio SID tracking
- BC-006: Rate limiting (5 msgs/thread/24h)
- BC-010: TCPA compliance (opt-out checking)
- BC-011: Credentials encrypted at rest
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.security.hmac_verification import verify_twilio_signature

logger = logging.getLogger("parwa.channels.twilio")

# ── Constants ─────────────────────────────────────────────────────

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

# Rate limits (BC-006)
MAX_SMS_PER_THREAD_PER_DAY = 5
MAX_SMS_PER_HOUR = 100

# Message status values
SMS_STATUSES = ["queued", "sent", "delivered", "undelivered", "failed"]
CALL_STATUSES = [
    "queued",
    "ringing",
    "in-progress",
    "completed",
    "failed",
    "canceled"]


class TwilioClientError(Exception):
    """Base exception for Twilio client errors."""


class TwilioAuthError(TwilioClientError):
    """Authentication or signature verification failed."""


class TwilioRateLimitError(TwilioClientError):
    """Rate limit exceeded."""


class TwilioTCPAError(TwilioClientError):
    """TCPA compliance violation (opt-out)."""


class TwilioClient:
    """
    Twilio API client with HMAC verification and rate limiting.

    Usage:
        client = TwilioClient(
            account_sid="ACxxx",
            auth_token="yyy",
            phone_number="+1234567890",
        )

        # Send SMS
        result = await client.send_sms(
            to="+0987654321",
            body="Hello from PARWA!",
            company_id="company-uuid",
        )

        # Verify webhook signature
        is_valid = client.verify_webhook(
            url="https://app.parwa.ai/api/channels/sms/inbound",
            params=form_data,
            signature=request.headers.get("X-Twilio-Signature"),
        )
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None,
        db: Optional[Session] = None,
    ):
        """
        Initialize Twilio client.

        Args:
            account_sid: Twilio Account SID (falls back to env var).
            auth_token: Twilio Auth Token (falls back to env var).
            phone_number: Default Twilio phone number (falls back to env var).
            db: Optional database session for rate limiting.
        """
        self.account_sid = account_sid or os.environ.get(
            "TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.phone_number = phone_number or os.environ.get(
            "TWILIO_PHONE_NUMBER", "")
        self.db = db

        if not self.account_sid or not self.auth_token:
            logger.warning(
                "twilio_client_missing_credentials", extra={
                    "has_sid": bool(
                        self.account_sid), "has_token": bool(
                        self.auth_token)}, )

    @property
    def auth_header(self) -> Tuple[str, str]:
        """Return Basic auth header tuple for Twilio API."""
        import base64
        credentials = base64.b64encode(
            f"{self.account_sid}:{self.auth_token}".encode()
        ).decode()
        return ("Authorization", f"Basic {credentials}")

    # ── SMS Operations ───────────────────────────────────────────────

    async def send_sms(
        self,
        to: str,
        body: str,
        company_id: Optional[str] = None,
        from_number: Optional[str] = None,
        status_callback: Optional[str] = None,
        media_urls: Optional[List[str]] = None,
        validate_opt_out: bool = True,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Send an SMS message via Twilio.

        Args:
            to: Recipient phone number (E.164 format).
            body: SMS message body (max 1600 chars).
            company_id: Company UUID for rate limiting and opt-out checks.
            from_number: Sender phone number (defaults to client default).
            status_callback: URL for delivery status callbacks.
            media_urls: List of media URLs for MMS.
            validate_opt_out: Whether to check TCPA opt-out status.
            db: Database session (overrides instance db).

        Returns:
            Dict with success, message_sid, status, and other details.

        Raises:
            TwilioTCPAError: If recipient has opted out.
            TwilioRateLimitError: If rate limit exceeded.
            TwilioClientError: On API errors.
        """
        from_number = from_number or self.phone_number
        db = db or self.db

        # Validate phone number format
        to = self._normalize_phone(to)
        if not to:
            raise TwilioClientError("Invalid recipient phone number")

        # Truncate body if needed
        if len(body) > 1600:
            body = body[:1597] + "..."
            logger.warning(
                "twilio_sms_body_truncated",
                extra={"to": to, "original_len": len(body)},
            )

        # Check TCPA opt-out status (BC-010)
        if validate_opt_out and company_id and db:
            if self._is_opted_out(db, company_id, to):
                raise TwilioTCPAError(f"Recipient {to} has opted out (BC-010)")

        # Check rate limit (BC-006)
        if company_id and db:
            rate_check = self._check_rate_limit(db, company_id, to)
            if not rate_check["allowed"]:
                raise TwilioRateLimitError(
                    f"Rate limit exceeded: {rate_check['reason']}"
                )

        # Build request
        url = f"{TWILIO_API_BASE}/Accounts/{self.account_sid}/Messages.json"

        data = {
            "To": to,
            "From": from_number,
            "Body": body,
        }

        if status_callback:
            data["StatusCallback"] = status_callback

        if media_urls:
            for i, url in enumerate(media_urls[:10]):  # Twilio max 10
                data[f"MediaUrl{i}"] = url

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )

                if response.status_code == 201:
                    result = response.json()
                    logger.info(
                        "twilio_sms_sent",
                        extra={
                            "company_id": company_id,
                            "to": to,
                            "message_sid": result.get("sid"),
                            "status": result.get("status"),
                        },
                    )
                    return {
                        "success": True,
                        "message_sid": result.get("sid"),
                        "status": result.get("status"),
                        "to": to,
                        "from": from_number,
                        "body": body,
                        "num_segments": result.get("num_segments", 1),
                        "price": result.get("price"),
                        "error_code": None,
                    }
                else:
                    error_data = response.json() if response.content else {}
                    logger.error(
                        "twilio_sms_failed",
                        extra={
                            "company_id": company_id,
                            "to": to,
                            "status_code": response.status_code,
                            "error": error_data,
                        },
                    )
                    return {
                        "success": False,
                        "message_sid": None,
                        "status": "failed",
                        "error_code": error_data.get("code"),
                        "error_message": error_data.get("message"),
                    }

        except httpx.TimeoutException:
            logger.error(
                "twilio_sms_timeout",
                extra={"company_id": company_id, "to": to},
            )
            raise TwilioClientError("Twilio API timeout")

        except Exception as e:
            logger.error(
                "twilio_sms_exception",
                extra={"company_id": company_id, "to": to, "error": str(e)},
            )
            raise TwilioClientError(f"SMS send failed: {e}")

    async def get_message_status(
        self,
        message_sid: str,
    ) -> Dict[str, Any]:
        """
        Get the status of a sent message.

        Args:
            message_sid: Twilio Message SID.

        Returns:
            Dict with status, error_code, etc.
        """
        url = f"{TWILIO_API_BASE}/Accounts/{self.account_sid}/Messages/{message_sid}.json"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    auth=(self.account_sid, self.auth_token),
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message_sid": data.get("sid"),
                        "status": data.get("status"),
                        "error_code": data.get("error_code"),
                        "error_message": data.get("error_message"),
                        "to": data.get("to"),
                        "from": data.get("from"),
                        "body": data.get("body"),
                        "num_segments": data.get("num_segments"),
                        "price": data.get("price"),
                        "date_sent": data.get("date_sent"),
                        "date_updated": data.get("date_updated"),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            logger.error(
                "twilio_status_check_failed",
                extra={"message_sid": message_sid, "error": str(e)},
            )
            return {"success": False, "error": str(e)}

    # ── Voice Operations ─────────────────────────────────────────────

    async def make_call(
        self,
        to: str,
        url: Optional[str] = None,
        twiml: Optional[str] = None,
        application_sid: Optional[str] = None,
        company_id: Optional[str] = None,
        from_number: Optional[str] = None,
        status_callback: Optional[str] = None,
        status_callback_event: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound voice call.

        Args:
            to: Recipient phone number (E.164 format).
            url: URL for TwiML instructions.
            twiml: Inline TwiML (alternative to url).
            application_sid: Twilio Application SID.
            company_id: Company UUID for logging.
            from_number: Caller phone number.
            status_callback: URL for call status callbacks.
            status_callback_event: Events to trigger callback.

        Returns:
            Dict with call_sid, status, etc.
        """
        from_number = from_number or self.phone_number
        to = self._normalize_phone(to)

        if not to:
            raise TwilioClientError("Invalid recipient phone number")

        if not url and not twiml and not application_sid:
            raise TwilioClientError(
                "Must provide url, twiml, or application_sid")

        api_url = f"{TWILIO_API_BASE}/Accounts/{self.account_sid}/Calls.json"

        data = {
            "To": to,
            "From": from_number,
        }

        if url:
            data["Url"] = url
        if twiml:
            data["Twiml"] = twiml
        if application_sid:
            data["ApplicationSid"] = application_sid
        if status_callback:
            data["StatusCallback"] = status_callback
        if status_callback_event:
            data["StatusCallbackEvent"] = " ".join(status_callback_event)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    api_url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )

                if response.status_code == 201:
                    result = response.json()
                    logger.info(
                        "twilio_call_initiated",
                        extra={
                            "company_id": company_id,
                            "to": to,
                            "call_sid": result.get("sid"),
                        },
                    )
                    return {
                        "success": True,
                        "call_sid": result.get("sid"),
                        "status": result.get("status", "queued"),
                        "to": to,
                        "from": from_number,
                    }
                else:
                    error_data = response.json() if response.content else {}
                    return {
                        "success": False,
                        "error_code": error_data.get("code"),
                        "error_message": error_data.get("message"),
                    }

        except Exception as e:
            logger.error(
                "twilio_call_exception",
                extra={"company_id": company_id, "to": to, "error": str(e)},
            )
            raise TwilioClientError(f"Call failed: {e}")

    # ── Webhook Verification ─────────────────────────────────────────

    def verify_webhook(
        self,
        url: str,
        params: Dict[str, Any],
        signature: str,
    ) -> bool:
        """
        Verify Twilio webhook signature (HMAC-SHA1).

        Args:
            url: The full URL of the webhook endpoint.
            params: Dictionary of request parameters (form data).
            signature: The X-Twilio-Signature header value.

        Returns:
            True if signature is valid, False otherwise.
        """
        return verify_twilio_signature(
            url=url,
            params=params,
            twilio_signature=signature,
            auth_token=self.auth_token,
        )

    def verify_webhook_or_raise(
        self,
        url: str,
        params: Dict[str, Any],
        signature: str,
    ) -> None:
        """
        Verify webhook signature, raising on failure.

        Raises:
            TwilioAuthError: If signature verification fails.
        """
        if not self.verify_webhook(url, params, signature):
            raise TwilioAuthError("Invalid Twilio webhook signature")

    # ── Helper Methods ───────────────────────────────────────────────

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Normalize phone number to E.164 format."""
        import re
        if not phone:
            return None
        # Remove non-digits
        digits = re.sub(r"\D", "", phone)
        # Add + prefix if missing
        if not phone.startswith("+"):
            if len(digits) == 10:
                return f"+1{digits}"  # US number
            elif len(digits) == 11 and digits.startswith("1"):
                return f"+{digits}"
        return phone if phone.startswith("+") else f"+{digits}"

    def _is_opted_out(self, db: Session, company_id: str, phone: str) -> bool:
        """Check if phone number has opted out (BC-010)."""
        try:
            from database.models.sms_channel import SMSConversation

            conv = db.query(SMSConversation).filter(
                SMSConversation.company_id == company_id,
                SMSConversation.customer_number == phone,
                SMSConversation.is_opted_out == True,  # noqa: E712
            ).first()

            return conv is not None

        except Exception as e:
            logger.warning(
                "twilio_opt_out_check_failed",
                extra={
                    "company_id": company_id,
                    "phone": phone,
                    "error": str(e)},
            )
            # Fail-safe: allow the message if check fails
            return False

    def _check_rate_limit(
        self,
        db: Session,
        company_id: str,
        phone: str,
    ) -> Dict[str, Any]:
        """Check BC-006 rate limit: 5 messages per thread per 24 hours."""
        try:
            from database.models.sms_channel import SMSMessage

            since = datetime.utcnow() - timedelta(hours=24)

            # Count outbound messages in last 24h
            count = db.query(SMSMessage).filter(
                SMSMessage.company_id == company_id,
                SMSMessage.to_number == phone,
                SMSMessage.direction == "outbound",
                SMSMessage.created_at >= since,
            ).count()

            if count >= MAX_SMS_PER_THREAD_PER_DAY:
                return {
                    "allowed": False,
                    "reason": f"BC-006: Max {MAX_SMS_PER_THREAD_PER_DAY} messages per thread per 24 hours exceeded",
                    "count": count,
                    "limit": MAX_SMS_PER_THREAD_PER_DAY,
                }

            return {
                "allowed": True,
                "count": count,
                "remaining": MAX_SMS_PER_THREAD_PER_DAY - count,
            }

        except Exception as e:
            logger.warning(
                "twilio_rate_limit_check_failed",
                extra={
                    "company_id": company_id,
                    "phone": phone,
                    "error": str(e)},
            )
            # Fail-safe: allow the message if check fails
            return {
                "allowed": True,
                "count": 0,
                "remaining": MAX_SMS_PER_THREAD_PER_DAY}


# ── Factory Function ─────────────────────────────────────────────────

def get_twilio_client(
    company_id: str,
    db: Session,
) -> TwilioClient:
    """
    Get a Twilio client configured for a specific company.

    Uses company-specific credentials if configured,
    otherwise falls back to environment variables.

    Args:
        company_id: Company UUID.
        db: Database session.

    Returns:
        Configured TwilioClient instance.
    """
    try:
        from database.models.sms_channel import SMSChannelConfig

        config = db.query(SMSChannelConfig).filter(
            SMSChannelConfig.company_id == company_id,
        ).first()

        if config:
            # Decrypt auth token (BC-011)
            # In production, use proper decryption
            auth_token = config.twilio_auth_token_encrypted  # TODO: decrypt

            return TwilioClient(
                account_sid=config.twilio_account_sid,
                auth_token=auth_token,
                phone_number=config.twilio_phone_number,
                db=db,
            )

    except Exception as e:
        logger.warning(
            "twilio_company_config_failed",
            extra={"company_id": company_id, "error": str(e)},
        )

    # Fall back to environment variables
    return TwilioClient(db=db)
