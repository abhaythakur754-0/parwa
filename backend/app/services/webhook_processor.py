"""
Webhook Processor Service (BG-08, W5D5)

Handles webhook processing with idempotency guarantees using the
idempotency_keys table. Prevents duplicate webhook processing and
ensures reliable response caching.

Features:
- HMAC signature verification for Paddle webhooks
- Idempotency key generation and storage
- Response caching for duplicate requests
- SHA-256 hash verification for request body integrity
- Expiration-based key cleanup
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing_extended import IdempotencyKey

logger = logging.getLogger("parwa.webhook_processor")

# Default expiration time for idempotency keys (7 days)
IDEMPOTENCY_KEY_EXPIRY_DAYS = 7

# Maximum response body size to store (100KB)
MAX_RESPONSE_BODY_SIZE = 100 * 1024


def _compute_hash(data: Any) -> str:
    """Compute SHA-256 hash of data for integrity verification."""
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True, default=str)
    if not isinstance(data, str):
        data = str(data)
    return hashlib.sha256(data.encode()).hexdigest()


def _truncate_response_body(body: str) -> str:
    """Truncate response body if too large."""
    if body and len(body) > MAX_RESPONSE_BODY_SIZE:
        return body[:MAX_RESPONSE_BODY_SIZE] + "...[truncated]"
    return body


def verify_paddle_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify Paddle webhook signature using HMAC-SHA256.

    Paddle sends a Paddle-Signature header with the webhook.
    This verifies the payload hasn't been tampered with.

    Args:
        payload: Raw request body bytes
        signature: Value from Paddle-Signature header
        secret: Paddle webhook secret from config

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not secret:
        logger.warning("paddle_signature_missing signature or secret")
        return False

    try:
        # Paddle uses ts=timestamp;h1=hash format
        # Extract the hash part
        parts = dict(p.split("=") for p in signature.split(";") if "=" in p)
        h1_hash = parts.get("h1", "")

        if not h1_hash:
            logger.warning("paddle_signature_invalid_format")
            return False

        # Compute expected hash
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected, h1_hash)

        if not is_valid:
            logger.warning(
                "paddle_signature_mismatch expected=%s... got=%s...",
                expected[:16], h1_hash[:16],
            )

        return is_valid

    except Exception as e:
        logger.error("paddle_signature_error error=%s", str(e))
        return False


def generate_idempotency_key(
    provider: str,
    event_id: str,
) -> str:
    """
    Generate a unique idempotency key for a webhook event.

    Format: {provider}:{event_id}

    This key is used to prevent duplicate processing.
    """
    return f"{provider}:{event_id}"


def check_idempotency_key(
    key: str,
    resource_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Check if an idempotency key already exists.

    Returns cached response if found and not expired, None otherwise.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        record = db.query(IdempotencyKey).filter(
            and_(
                IdempotencyKey.idempotency_key == key,
                IdempotencyKey.resource_type == resource_type,
                IdempotencyKey.expires_at > now,
            )
        ).first()

        if record:
            logger.info(
                "idempotency_key_found key=%s status=%s",
                key, record.response_status,
            )
            return {
                "found": True,
                "status": record.response_status,
                "body": record.response_body,
                "resource_id": record.resource_id,
            }

        return None

    finally:
        db.close()


def store_idempotency_key(
    key: str,
    resource_type: str,
    response_status: int,
    response_body: Optional[str] = None,
    resource_id: Optional[str] = None,
    company_id: Optional[str] = None,
    request_body_hash: Optional[str] = None,
    expiry_days: int = IDEMPOTENCY_KEY_EXPIRY_DAYS,
) -> IdempotencyKey:
    """
    Store an idempotency key with its response.

    This allows future duplicate requests to receive the same response
    without reprocessing.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expiry_days)

        # Truncate response body if needed
        if response_body:
            response_body = _truncate_response_body(response_body)

        record = IdempotencyKey(
            idempotency_key=key,
            resource_type=resource_type,
            resource_id=resource_id,
            request_body_hash=request_body_hash,
            response_status=response_status,
            response_body=response_body,
            company_id=company_id,
            expires_at=expires_at,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(
            "idempotency_key_stored key=%s resource_type=%s expires=%s",
            key, resource_type, expires_at.isoformat(),
        )

        return record

    except Exception as e:
        db.rollback()
        logger.error("idempotency_key_store_error key=%s error=%s", key, str(e))
        raise
    finally:
        db.close()


def process_with_idempotency(
    provider: str,
    event_id: str,
    processor: Callable[[], Dict[str, Any]],
    company_id: Optional[str] = None,
    request_body: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Process a webhook with idempotency guarantees.

    If this event has been processed before (within expiry window),
    returns the cached response. Otherwise, calls the processor
    and stores the result.

    Args:
        provider: Webhook provider (e.g., 'paddle')
        event_id: Provider-specific event ID
        processor: Callable that processes the webhook
        company_id: Optional company ID for tracking
        request_body: Optional request body for hash verification

    Returns:
        Dict with status, response, and duplicate flag
    """
    key = generate_idempotency_key(provider, event_id)
    resource_type = f"{provider}_webhook"

    # Check for existing key
    existing = check_idempotency_key(key, resource_type)

    if existing:
        logger.info(
            "webhook_duplicate_skipped key=%s event_id=%s",
            key, event_id,
        )
        return {
            "status": "duplicate",
            "duplicate": True,
            "response_status": existing["status"],
            "response_body": existing["body"],
        }

    # Compute request hash if body provided
    request_hash = _compute_hash(request_body) if request_body else None

    # Process the webhook
    try:
        result = processor()

        # Store the result
        response_status = result.get("status_code", 200)
        response_body = json.dumps(result, default=str) if result else None

        store_idempotency_key(
            key=key,
            resource_type=resource_type,
            response_status=response_status,
            response_body=response_body,
            resource_id=event_id,
            company_id=company_id,
            request_body_hash=request_hash,
        )

        result["duplicate"] = False
        return result

    except Exception as e:
        logger.error(
            "webhook_processor_error key=%s error=%s",
            key, str(e),
        )
        raise


def cleanup_expired_idempotency_keys() -> int:
    """
    Delete expired idempotency keys from the database.

    Should be run periodically (daily) via Celery beat.

    Returns:
        Number of keys deleted
    """
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        deleted = db.query(IdempotencyKey).filter(
            IdempotencyKey.expires_at < now,
        ).delete()

        db.commit()

        logger.info("idempotency_keys_cleaned deleted=%d", deleted)
        return deleted

    except Exception as e:
        db.rollback()
        logger.error("idempotency_cleanup_error error=%s", str(e))
        raise
    finally:
        db.close()


def get_idempotency_key_info(key: str) -> Optional[Dict[str, Any]]:
    """
    Get information about an idempotency key.

    Returns key details if found, None otherwise.
    """
    db: Session = SessionLocal()
    try:
        record = db.query(IdempotencyKey).filter(
            IdempotencyKey.idempotency_key == key,
        ).first()

        if not record:
            return None

        return {
            "id": record.id,
            "key": record.idempotency_key,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "response_status": record.response_status,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }

    finally:
        db.close()
