"""
PARWA API Key Management (BC-011)

Secure API key generation, hashing, scope validation, and rotation.
API keys are never stored in plain text - only SHA-256 hashes.

BC-011 Requirements:
- API key uses cryptographically secure random generation
- API key is hashed (SHA-256) before storing in DB
- Scopes enforced: read can't write, write can't admin
- Key rotation invalidates old key immediately
- Constant-time comparison to prevent timing attacks
- API key is associated with company_id (BC-001)
"""

import enum
import hashlib
import secrets
import time
from typing import Optional

from shared.utils.security import constant_time_compare


class APIKeyScope(str, enum.Enum):
    """API key permission scopes (BC-011)."""

    READ = "read"  # Read-only access to data
    WRITE = "write"  # Read + create/update data
    ADMIN = "admin"  # Full access including delete/settings
    APPROVAL = "approval"  # Approve/reject actions only


# Scope hierarchy: higher scope includes lower scopes
SCOPE_HIERARCHY = {
    APIKeyScope.READ: {APIKeyScope.READ},
    APIKeyScope.WRITE: {APIKeyScope.READ, APIKeyScope.WRITE},
    APIKeyScope.ADMIN: {
        APIKeyScope.READ,
        APIKeyScope.WRITE,
        APIKeyScope.ADMIN,
    },
    APIKeyScope.APPROVAL: {APIKeyScope.APPROVAL},
}


class APIKeyStatus(str, enum.Enum):
    """API key lifecycle status."""

    ACTIVE = "active"
    ROTATED = "rotated"  # Old key after rotation
    REVOKED = "revoked"  # Permanently disabled
    EXPIRED = "expired"  # Past expiration date


class APIKey:
    """Represents an API key with its metadata.

    This is the in-memory representation.
    The database stores only the hash, never the raw key.
    """

    def __init__(
        self,
        key_hash: str,
        key_prefix: str,
        company_id: str,
        scopes: list,
        name: str = "",
        status: str = APIKeyStatus.ACTIVE.value,
        created_by: Optional[str] = None,
        expires_at: Optional[float] = None,
        rotated_at: Optional[float] = None,
        id: Optional[str] = None,
    ):
        self.id = id or secrets.token_hex(8)
        self.key_hash = key_hash
        self.key_prefix = key_prefix  # First 8 chars for identification
        self.company_id = company_id  # BC-001: tenant isolation
        self.scopes = scopes
        self.name = name
        self.status = status
        self.created_by = created_by
        self.expires_at = expires_at
        self.rotated_at = rotated_at
        self.created_at = time.time()

    def is_active(self) -> bool:
        """Check if the key is currently active."""
        if self.status != APIKeyStatus.ACTIVE.value:
            return False
        if self.expires_at is not None and time.time() > self.expires_at:
            return False
        return True

    def has_scope(self, required_scope: str) -> bool:
        """Check if the key has the required scope (BC-011).

        Uses scope hierarchy: WRITE includes READ, ADMIN includes all.
        APPROVAL is a separate scope (not in hierarchy).
        """
        if not self.is_active():
            return False

        if required_scope == APIKeyScope.APPROVAL.value:
            return APIKeyScope.APPROVAL.value in self.scopes

        # Map required scope to enum
        try:
            required = APIKeyScope(required_scope)
        except ValueError:
            return False

        # Check each scope the key has
        for scope_str in self.scopes:
            try:
                scope = APIKeyScope(scope_str)
                allowed = SCOPE_HIERARCHY.get(scope, set())
                if required in allowed:
                    return True
            except ValueError:
                continue

        return False

    def to_dict(self) -> dict:
        """Convert to dictionary (never includes raw key)."""
        return {
            "id": self.id,
            "key_prefix": self.key_prefix,
            "company_id": self.company_id,
            "scopes": self.scopes,
            "name": self.name,
            "status": self.status,
            "created_by": self.created_by,
            "expires_at": self.expires_at,
            "rotated_at": self.rotated_at,
            "created_at": self.created_at,
        }


def generate_raw_key() -> str:
    """Generate a secure random API key.

    Uses 32 bytes of cryptographically secure random data,
    encoded as base64url (URL-safe, no padding).
    Total: 43 characters.

    BC-011: Secure random, not predictable.
    """
    raw = secrets.token_bytes(32)
    return "pk_" + base64_urlsafe_encode(raw)


def base64_urlsafe_encode(data: bytes) -> str:
    """Encode bytes as URL-safe base64 without padding."""
    import base64

    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256.

    BC-011: Never store raw keys. Only store the hash.

    Args:
        raw_key: The raw API key string.

    Returns:
        SHA-256 hex digest of the key.

    Raises:
        ValueError: If raw_key is empty.
    """
    if not raw_key:
        raise ValueError("API key must not be empty")
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verify an API key against a stored hash.

    Uses constant-time comparison to prevent timing attacks.
    Hashes the raw key and compares with stored hash.

    Args:
        raw_key: The raw API key from the request header.
        key_hash: The stored SHA-256 hash.

    Returns:
        True if the key matches, False otherwise.
    """
    if not raw_key or not key_hash:
        return False
    try:
        computed_hash = hash_api_key(raw_key)
    except ValueError:
        return False
    return constant_time_compare(computed_hash, key_hash)


def validate_scopes(granted_scopes: list, required_scope: str) -> bool:
    """Check if granted scopes include the required scope.

    BC-011: Scope isolation — read can't write, write can't admin.

    Args:
        granted_scopes: List of scopes granted to the API key.
        required_scope: The scope needed for the operation.

    Returns:
        True if the required scope is covered by granted scopes.
    """
    if not granted_scopes:
        return False

    if required_scope == APIKeyScope.APPROVAL.value:
        return APIKeyScope.APPROVAL.value in granted_scopes

    try:
        required = APIKeyScope(required_scope)
    except ValueError:
        return False

    for scope_str in granted_scopes:
        try:
            scope = APIKeyScope(scope_str)
            allowed = SCOPE_HIERARCHY.get(scope, set())
            if required in allowed:
                return True
        except ValueError:
            continue

    return False


def create_api_key(
    company_id: str,
    scopes: list,
    name: str = "",
    created_by: Optional[str] = None,
    expires_in_seconds: Optional[int] = None,
) -> tuple:
    """Create a new API key.

    Generates a raw key, hashes it, and returns both the raw key
    (for one-time display to user) and the APIKey object (for DB storage).

    Args:
        company_id: Tenant ID (BC-001).
        scopes: List of scope strings.
        name: Human-readable name for the key.
        created_by: User ID who created the key.
        expires_in_seconds: Optional expiration time.

    Returns:
        Tuple of (raw_key, APIKey object).
        raw_key should be shown to user ONCE and never stored.
    """
    raw_key = generate_raw_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:12]  # "pk_" + first 9 chars

    expires_at = None
    if expires_in_seconds is not None:
        expires_at = time.time() + expires_in_seconds

    # Validate scopes
    for scope in scopes:
        if scope not in [s.value for s in APIKeyScope]:
            raise ValueError(f"Invalid scope: {scope}")

    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        company_id=company_id,
        scopes=scopes,
        name=name,
        status=APIKeyStatus.ACTIVE.value,
        created_by=created_by,
        expires_at=expires_at,
    )

    return raw_key, api_key


def rotate_api_key(
    existing_key: APIKey,
    new_scopes: Optional[list] = None,
    name: Optional[str] = None,
) -> tuple:
    """Rotate an existing API key.

    Invalidates the old key (sets status to ROTATED) and generates
    a new one. The old key's hash is kept for audit purposes.

    BC-011: Key rotation invalidates old key immediately.

    Args:
        existing_key: The API key object to rotate.
        new_scopes: Optional new scopes (defaults to existing).
        name: Optional new name (defaults to existing).

    Returns:
        Tuple of (new_raw_key, new_APIKey, updated_old_APIKey).
    """
    # Mark old key as rotated
    existing_key.status = APIKeyStatus.ROTATED.value
    existing_key.rotated_at = time.time()

    # Generate new key with same or updated params
    # Calculate remaining time from existing expiration
    expires_in = None
    if existing_key.expires_at is not None:
        remaining = existing_key.expires_at - time.time()
        if remaining > 0:
            expires_in = int(remaining)

    raw_key, new_api_key = create_api_key(
        company_id=existing_key.company_id,
        scopes=new_scopes or existing_key.scopes,
        name=name or existing_key.name,
        created_by=existing_key.created_by,
        expires_in_seconds=expires_in,
    )

    return raw_key, new_api_key, existing_key
