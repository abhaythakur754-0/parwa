"""
Jarvis Auth — Role-Based Command Authorization

Wires into the existing PARWA auth system (access_control.py).
Checks if a user's role can execute a given intent.
Every authorization decision is logged to the audit trail.

Role hierarchy (highest to lowest):
  owner > supervisor > admin > team_member > viewer

Owner-only:   emergency_shutdown, create_agent
Admin+:       all control commands, teach_skill
All roles:    all query intents, explain intents
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from .command_parser import (
    requires_admin,
    requires_owner,
    is_query_intent,
    is_emergency_intent,
)
from .jarvis_db import get_db, ADMIN_ROLES

logger = logging.getLogger("jarvis.auth")

# ── Role Hierarchy ───────────────────────────────────────────

ROLE_LEVELS = {
    "owner": 5,
    "supervisor": 4,
    "admin": 3,
    "team_member": 2,
    "viewer": 1,
}

# ── Auth Result ──────────────────────────────────────────────


class AuthResult:
    """Result of an authorization check."""

    __slots__ = (
        "authorized", "role", "email", "reason",
        "intent", "tenant_id",
    )

    def __init__(
        self,
        authorized: bool,
        role: str,
        email: str,
        reason: str,
        intent: str = "",
        tenant_id: str = "",
    ):
        self.authorized = authorized
        self.role = role
        self.email = email
        self.reason = reason
        self.intent = intent
        self.tenant_id = tenant_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized": self.authorized,
            "role": self.role,
            "email": self.email,
            "reason": self.reason,
        }

    def __bool__(self):
        return self.authorized


# ── Main Authorization Function ──────────────────────────────

async def authorize_command(
    intent: str,
    user_context: Dict[str, Any],
    tenant_id: str,
) -> AuthResult:
    """Check if the user can execute this intent.

    Args:
        intent: The classified intent from command_parser
        user_context: Dict with at least 'email' and 'role'
        tenant_id: The tenant making the request

    Returns:
        AuthResult with authorized=True/False and reason
    """
    email = user_context.get("email", "unknown")
    role = user_context.get("role", "viewer").lower()

    # Normalize role
    if role not in ROLE_LEVELS:
        role = "viewer"

    role_level = ROLE_LEVELS[role]

    # 1. Check owner-only commands
    if requires_owner(intent) and role_level < ROLE_LEVELS["owner"]:
        result = AuthResult(
            authorized=False, role=role, email=email,
            reason=f"'{intent}' requires owner role. Your role: {role}.",
            intent=intent, tenant_id=tenant_id,
        )
        await _log_auth_decision(result, intent, tenant_id)
        return result

    # 2. Check admin+ commands
    if requires_admin(intent) and role_level < ROLE_LEVELS["admin"]:
        result = AuthResult(
            authorized=False, role=role, email=email,
            reason=f"'{intent}' requires admin+ role. Your role: {role}.",
            intent=intent, tenant_id=tenant_id,
        )
        await _log_auth_decision(result, intent, tenant_id)
        return result

    # 3. All other intents — any authenticated role can use
    if role_level < ROLE_LEVELS["viewer"]:
        result = AuthResult(
            authorized=False, role=role, email=email,
            reason="Unrecognized role. Must be authenticated.",
            intent=intent, tenant_id=tenant_id,
        )
        await _log_auth_decision(result, intent, tenant_id)
        return result

    # 4. Authorized
    result = AuthResult(
        authorized=True, role=role, email=email,
        reason="OK",
        intent=intent, tenant_id=tenant_id,
    )
    await _log_auth_decision(result, intent, tenant_id)
    return result


def authorize_command_sync(
    intent: str,
    user_context: Dict[str, Any],
    tenant_id: str,
) -> AuthResult:
    """Synchronous version — no audit logging. For testing."""
    email = user_context.get("email", "unknown")
    role = user_context.get("role", "viewer").lower()
    if role not in ROLE_LEVELS:
        role = "viewer"

    role_level = ROLE_LEVELS[role]

    if requires_owner(intent) and role_level < ROLE_LEVELS["owner"]:
        return AuthResult(False, role, email,
                          f"'{intent}' requires owner role.", intent, tenant_id)
    if requires_admin(intent) and role_level < ROLE_LEVELS["admin"]:
        return AuthResult(False, role, email,
                          f"'{intent}' requires admin+ role.", intent, tenant_id)
    if role_level < ROLE_LEVELS["viewer"]:
        return AuthResult(False, role, email, "Unrecognized role.", intent, tenant_id)

    return AuthResult(True, role, email, "OK", intent, tenant_id)


# ── Audit Logging ────────────────────────────────────────────

async def _log_auth_decision(
    result: AuthResult,
    intent: str,
    tenant_id: str,
):
    """Log every auth decision to the audit trail."""
    try:
        db = get_db()
        await db.create_audit_entry(
            tenant_id=tenant_id,
            action=f"auth_{intent}" if result.authorized else f"auth_denied_{intent}",
            actor_email=result.email,
            target_type="command",
            target_id=intent,
            payload={
                "role": result.role,
                "authorized": result.authorized,
                "reason": result.reason,
            },
        )
    except Exception as e:
        logger.warning("Failed to log auth audit: %s", e)


# ── User Context Helpers ─────────────────────────────────────

def make_user_context(
    email: str,
    role: str = "admin",
    user_id: Optional[str] = None,
    auth_method: str = "api_key",
) -> Dict[str, Any]:
    """Build a user context dict. Used in tests and when
    constructing context from JWT/API key validation."""
    ctx = {
        "email": email,
        "role": role,
        "auth_method": auth_method,
    }
    if user_id:
        ctx["user_id"] = user_id
    return ctx


# ── Quick Role Check ─────────────────────────────────────────

def can_execute(intent: str, role: str) -> bool:
    """Quick synchronous check: can this role execute this intent?"""
    role = role.lower()
    if role not in ROLE_LEVELS:
        return False
    if requires_owner(intent):
        return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS["owner"]
    if requires_admin(intent):
        return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS["admin"]
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS["viewer"]