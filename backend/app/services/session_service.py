"""
PARWA Session Service (F-017)

Business logic for session management.
- List active sessions for a user
- Revoke individual sessions
- Revoke all other sessions (keep current)
- Max 5 sessions enforced (BC-011)
"""

from datetime import timezone

from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.logger import get_logger
from database.models.core import RefreshToken

logger = get_logger("session_service")


# Mask IP: show only first 3 octets (e.g. 192.168.1.xxx)
def _mask_ip(ip: str) -> str:
    """Mask the last octet of an IP address."""
    if not ip:
        return ""
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".xxx"
    return ip[: max(1, len(ip) - 3)] + "..."


def list_sessions(
    db: Session,
    user_id: str,
    current_token_hash: str | None = None,
) -> list[dict]:
    """List all active sessions for a user.

    F-017: Returns session details with masked IP.
    Marks current session.

    Args:
        db: Database session.
        user_id: User's UUID.
        current_token_hash: Hash of current refresh token
            (to mark as current session).

    Returns:
        List of session dicts.
    """
    sessions = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
        )
        .order_by(RefreshToken.created_at.desc())
        .all()
    )

    result = []
    for s in sessions:
        device_info = s.device_info or "Unknown device"
        ip_addr = s.ip_address or ""
        last_active = ""
        if s.created_at:
            dt = s.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            last_active = dt.isoformat()

        is_current = False
        if current_token_hash and s.token_hash == current_token_hash:
            is_current = True

        result.append(
            {
                "id": s.id,
                "device_info": device_info,
                "ip_address": _mask_ip(ip_addr),
                "last_active": last_active,
                "is_current": is_current,
            }
        )

    return result


def revoke_session(
    db: Session,
    user_id: str,
    session_id: str,
    current_token_hash: str | None = None,
) -> dict:
    """Revoke a specific session.

    F-017: Cannot revoke own current session.

    Args:
        db: Database session.
        user_id: User's UUID.
        session_id: Refresh token UUID to revoke.
        current_token_hash: Hash of current token (prevent self-revoke).

    Returns:
        Dict with status.

    Raises:
        ValidationError: If trying to revoke current session.
        NotFoundError: If session not found.
    """
    session = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == session_id,
            RefreshToken.user_id == user_id,
        )
        .first()
    )

    if not session:
        raise NotFoundError(message="Session not found")

    # Prevent self-revocation
    if current_token_hash and session.token_hash == current_token_hash:
        raise ValidationError(message="Cannot revoke your current session")

    db.delete(session)
    db.commit()

    logger.info(
        "session_revoked",
        user_id=user_id,
        session_id=session_id,
    )

    return {
        "status": "revoked",
        "message": "Session revoked successfully",
    }


def revoke_other_sessions(
    db: Session,
    user_id: str,
    current_token_hash: str,
) -> dict:
    """Revoke all sessions except the current one.

    F-017: Keeps the current session active.

    Args:
        db: Database session.
        user_id: User's UUID.
        current_token_hash: Hash of current refresh token.

    Returns:
        Dict with status and count.
    """
    others = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash != current_token_hash,
        )
        .all()
    )

    count = len(others)
    for s in others:
        db.delete(s)

    db.commit()

    logger.info(
        "other_sessions_revoked",
        user_id=user_id,
        count=count,
    )

    return {
        "status": "all_other_sessions_revoked",
        "count": count,
        "message": f"All other sessions revoked ({count} sessions)",
    }
