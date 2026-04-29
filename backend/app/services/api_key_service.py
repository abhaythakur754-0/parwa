"""
PARWA API Key Service (F-019)

DB-backed API key CRUD with rotation, revocation, and audit logging.
Max 10 keys per tenant. Key format: parwa_live_<32-char-random>.
Uses existing security/api_keys.py functions for hashing/verification.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.logger import get_logger
from database.models.api_key_audit import APIKeyAuditLog
from database.models.core import APIKey
from security.api_keys import (
    APIKeyScope,
    hash_api_key,
)

logger = get_logger("api_key_service")

MAX_KEYS_PER_TENANT = 10
GRACE_PERIOD_HOURS = 24


def _uuid() -> str:
    import uuid
    return str(uuid.uuid4())


def _generate_raw_key(prefix: str = "parwa_live_") -> str:
    """Generate a raw API key with given prefix."""
    random_part = secrets.token_hex(16)  # 32 chars
    return f"{prefix}{random_part}"


def create_key(
    db: Session,
    company_id: str,
    user_id: Optional[str],
    name: str,
    scopes: list,
    expires_days: Optional[int] = None,
) -> tuple:
    """Create a new API key.

    Returns (raw_key, APIKey db record).
    Max 10 keys per tenant (F-019).
    """
    count = db.query(APIKey).filter(
        APIKey.company_id == company_id,
        APIKey.revoked.is_(False),
    ).count()
    if count >= MAX_KEYS_PER_TENANT:
        raise ValueError(
            f"Maximum {MAX_KEYS_PER_TENANT} keys per tenant"
        )

    raw_key = _generate_raw_key("parwa_live_")
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:20]

    expires_at = None
    if expires_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=expires_days
        )

    # Validate scopes
    valid_scopes = [s.value for s in APIKeyScope]
    for s in scopes:
        if s not in valid_scopes:
            raise ValueError(f"Invalid scope: {s}")

    scopes_json = json.dumps(scopes)

    record = APIKey(
        id=_uuid(),
        company_id=company_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scope=scopes[0] if scopes else "read",
        scopes=scopes_json,
        is_active=True,
        revoked=False,
        created_by=user_id,
        last_used_at=None,
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()

    # Audit log
    _create_audit(
        db, record.id, company_id, "created", None, None,
    )

    return raw_key, record


def list_keys(
    db: Session, company_id: str,
) -> list:
    """List all keys for a tenant (without hashes)."""
    records = db.query(APIKey).filter(
        APIKey.company_id == company_id,
    ).order_by(APIKey.created_at.desc()).all()
    results = []
    for r in records:
        results.append({
            "id": r.id,
            "name": r.name,
            "key_prefix": r.key_prefix,
            "scopes": _parse_scopes(r),
            "created_at": (
                r.created_at.isoformat()
                if r.created_at else None
            ),
            "last_used_at": (
                r.last_used_at.isoformat()
                if r.last_used_at else None
            ),
            "expires_at": (
                r.expires_at.isoformat()
                if r.expires_at else None
            ),
            "revoked": r.revoked,
        })
    return results


def rotate_key(
    db: Session,
    company_id: str,
    key_id: str,
    user_id: Optional[str],
) -> tuple:
    """Rotate an API key.

    Generates new key, old key valid for 24h grace period.
    Returns (new_raw_key, new_APIKey, old_APIKey).
    """
    old_record = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.company_id == company_id,
    ).first()
    if not old_record:
        raise ValueError("API key not found")
    if old_record.revoked:
        raise ValueError("Cannot rotate a revoked key")

    raw_key = _generate_raw_key("parwa_live_")
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:20]

    expires_at = old_record.expires_at

    new_record = APIKey(
        id=_uuid(),
        company_id=company_id,
        name=old_record.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scope=old_record.scope,
        scopes=old_record.scopes,
        is_active=True,
        revoked=False,
        rotated_from_id=old_record.id,
        created_by=user_id,
        expires_at=expires_at,
    )
    db.add(new_record)

    # Old key stays active for 24h grace, then auto-expires
    grace_ends = datetime.now(timezone.utc) + timedelta(
        hours=GRACE_PERIOD_HOURS
    )
    old_record.is_active = True
    old_record.grace_ends_at = grace_ends
    db.flush()
    _create_audit(
        db, new_record.id, company_id, "rotated", None, None,
    )

    return raw_key, new_record, old_record, grace_ends


def revoke_key(
    db: Session,
    company_id: str,
    key_id: str,
    user_id: Optional[str],
) -> APIKey:
    """Revoke an API key immediately."""
    record = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.company_id == company_id,
    ).first()
    if not record:
        raise ValueError("API key not found")
    record.revoked = True
    record.revoked_at = datetime.now(timezone.utc)
    record.is_active = False
    db.flush()

    _create_audit(
        db, record.id, company_id, "revoked", None, None,
    )
    return record


def validate_key(
    db: Session, raw_key: str,
    company_id: Optional[str] = None,
) -> Optional[APIKey]:
    """Validate a raw API key against the database.

    Checks hash, expiration, and revocation (BC-001).
    Returns the APIKey record or None.
    """
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    query = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
    )
    if company_id:
        query = query.filter(
            APIKey.company_id == company_id,
        )
    record = query.first()
    if not record:
        return None
    if record.revoked:
        return None
    if not record.is_active:
        return None
    if record.expires_at and datetime.now(timezone.utc) > record.expires_at:
        return None
    # L18: Enforce grace period — rotated keys expire after grace_ends_at
    if record.grace_ends_at and datetime.now(
            timezone.utc) > record.grace_ends_at:
        return None
    return record


def update_last_used(
    db: Session,
    key_id: str,
    endpoint: Optional[str],
    ip_address: Optional[str],
    company_id: Optional[str] = None,
) -> None:
    """Update last_used_at and create audit log entry."""
    query = db.query(APIKey).filter(
        APIKey.id == key_id,
    )
    if company_id:
        query = query.filter(
            APIKey.company_id == company_id,
        )
    record = query.first()
    if record:
        record.last_used_at = datetime.now(timezone.utc)
        db.flush()
        _create_audit(
            db, key_id, record.company_id,
            "used", endpoint, ip_address,
        )


def _parse_scopes(record: APIKey) -> list:
    """Parse scopes from a record."""
    if record.scopes:
        try:
            return json.loads(record.scopes)
        except (json.JSONDecodeError, TypeError):
            pass
    if record.scope:
        return [record.scope]
    return ["read"]


def _create_audit(
    db: Session,
    api_key_id: str,
    company_id: str,
    action: str,
    endpoint: Optional[str],
    ip_address: Optional[str],
) -> None:
    """Create an audit log entry."""
    log = APIKeyAuditLog(
        id=_uuid(),
        api_key_id=api_key_id,
        company_id=company_id,
        action=action,
        endpoint=endpoint,
        ip_address=ip_address,
    )
    db.add(log)
    db.flush()
