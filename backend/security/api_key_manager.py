"""
API Key Manager for Enterprise API Key Management.

This module provides API key management for enterprise clients,
including key generation, rotation, scoping, and permissions.
"""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from pydantic import BaseModel, Field


class APIKeyStatus(str, Enum):
    """API key status."""
    
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"


class APIKeyScope(BaseModel):
    """API key scope definition."""
    
    name: str
    description: str
    permissions: List[str] = Field(default_factory=list)


class EnterpriseAPIKey(BaseModel):
    """Enterprise API key model."""
    
    key_id: str = Field(default_factory=lambda: f"key_{secrets.token_hex(8)}")
    key_hash: str = ""  # Hashed key value
    key_prefix: str = ""  # First 8 chars for identification
    name: str
    tenant_id: str
    user_id: str
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    scopes: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    rate_limit: int = 1000  # requests per hour
    allowed_ips: List[str] = Field(default_factory=list)
    allowed_referrers: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    usage_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_active(self) -> bool:
        """Check if key is active."""
        return self.status == APIKeyStatus.ACTIVE and not self.is_expired()


class APIKeyManager:
    """
    API Key Manager for enterprise key management.
    
    Features:
    - Secure key generation
    - Key hashing for storage
    - Scope-based permissions
    - Key rotation
    - IP restrictions
    - Usage tracking
    """
    
    # Default scopes
    DEFAULT_SCOPES = {
        "read": APIKeyScope(
            name="read",
            description="Read-only access",
            permissions=["read:tickets", "read:users", "read:analytics"]
        ),
        "write": APIKeyScope(
            name="write",
            description="Read and write access",
            permissions=["read:tickets", "write:tickets", "read:users", "read:analytics"]
        ),
        "admin": APIKeyScope(
            name="admin",
            description="Full administrative access",
            permissions=["read:*", "write:*", "admin:*"]
        ),
        "webhook": APIKeyScope(
            name="webhook",
            description="Webhook delivery access",
            permissions=["webhook:send", "webhook:verify"]
        ),
        "analytics": APIKeyScope(
            name="analytics",
            description="Analytics access only",
            permissions=["read:analytics", "export:analytics"]
        )
    }
    
    def __init__(self):
        """Initialize API key manager."""
        self._keys: Dict[str, EnterpriseAPIKey] = {}
        self._tenant_keys: Dict[str, List[str]] = {}  # tenant_id -> [key_ids]
        self._custom_scopes: Dict[str, APIKeyScope] = {}
    
    def generate_key(self) -> str:
        """
        Generate a secure API key.
        
        Returns:
            Generated API key
        """
        return f"pk_live_{secrets.token_urlsafe(32)}"
    
    def _hash_key(self, key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def create_key(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        scopes: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        rate_limit: int = 1000,
        allowed_ips: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User creating the key
            name: Key name/description
            scopes: List of scope names
            expires_in_days: Days until expiration
            rate_limit: Rate limit (requests per hour)
            allowed_ips: Allowed IP addresses
            metadata: Additional metadata
            
        Returns:
            Dictionary with key_id and raw key (only shown once)
        """
        raw_key = self.generate_key()
        key_hash = self._hash_key(raw_key)
        
        # Resolve scopes to permissions
        permissions = set()
        resolved_scopes = scopes or ["read"]
        
        for scope_name in resolved_scopes:
            scope = self.DEFAULT_SCOPES.get(scope_name) or self._custom_scopes.get(scope_name)
            if scope:
                permissions.update(scope.permissions)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        api_key = EnterpriseAPIKey(
            key_hash=key_hash,
            key_prefix=raw_key[:12],
            name=name,
            tenant_id=tenant_id,
            user_id=user_id,
            scopes=resolved_scopes,
            permissions=list(permissions),
            rate_limit=rate_limit,
            allowed_ips=allowed_ips or [],
            metadata=metadata or {},
            expires_at=expires_at
        )
        
        self._keys[api_key.key_id] = api_key
        
        if tenant_id not in self._tenant_keys:
            self._tenant_keys[tenant_id] = []
        self._tenant_keys[tenant_id].append(api_key.key_id)
        
        return {
            "key_id": api_key.key_id,
            "key": raw_key,  # Only shown once!
            "key_prefix": api_key.key_prefix,
            "name": name,
            "scopes": resolved_scopes,
            "expires_at": expires_at.isoformat() if expires_at else None
        }
    
    def validate_key(
        self,
        key: str,
        required_permission: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate an API key.
        
        Args:
            key: API key to validate
            required_permission: Optional required permission
            ip_address: Optional IP address to check
            
        Returns:
            Validation result
        """
        key_hash = self._hash_key(key)
        
        result = {
            "valid": False,
            "reason": None,
            "key_info": None
        }
        
        # Find key by hash
        api_key = None
        for k in self._keys.values():
            if k.key_hash == key_hash:
                api_key = k
                break
        
        if not api_key:
            result["reason"] = "key_not_found"
            return result
        
        if api_key.status == APIKeyStatus.REVOKED:
            result["reason"] = "key_revoked"
            return result
        
        if api_key.is_expired():
            api_key.status = APIKeyStatus.EXPIRED
            result["reason"] = "key_expired"
            return result
        
        # Check IP restriction
        if ip_address and api_key.allowed_ips:
            if ip_address not in api_key.allowed_ips:
                result["reason"] = "ip_not_allowed"
                return result
        
        # Check permission
        if required_permission:
            if required_permission not in api_key.permissions:
                # Check wildcard
                wildcard = required_permission.split(":")[0] + ":*"
                if wildcard not in api_key.permissions and "*: *" not in api_key.permissions:
                    result["reason"] = "permission_denied"
                    return result
        
        # Update usage
        api_key.last_used_at = datetime.now(timezone.utc)
        api_key.last_used_ip = ip_address
        api_key.usage_count += 1
        
        result["valid"] = True
        result["key_info"] = {
            "key_id": api_key.key_id,
            "tenant_id": api_key.tenant_id,
            "user_id": api_key.user_id,
            "scopes": api_key.scopes,
            "permissions": api_key.permissions,
            "rate_limit": api_key.rate_limit
        }
        
        return result
    
    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if revoked
        """
        api_key = self._keys.get(key_id)
        if not api_key:
            return False
        
        api_key.status = APIKeyStatus.REVOKED
        return True
    
    def rotate_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        """
        Rotate an API key (create new, revoke old).
        
        Args:
            key_id: Key to rotate
            
        Returns:
            New key info or None
        """
        old_key = self._keys.get(key_id)
        if not old_key or old_key.status != APIKeyStatus.ACTIVE:
            return None
        
        # Create new key with same settings
        new_key_result = self.create_key(
            tenant_id=old_key.tenant_id,
            user_id=old_key.user_id,
            name=f"{old_key.name} (rotated)",
            scopes=old_key.scopes,
            rate_limit=old_key.rate_limit,
            allowed_ips=old_key.allowed_ips
        )
        
        # Revoke old key
        self.revoke_key(key_id)
        
        return new_key_result
    
    def get_key(self, key_id: str) -> Optional[EnterpriseAPIKey]:
        """Get key by ID."""
        return self._keys.get(key_id)
    
    def get_tenant_keys(self, tenant_id: str) -> List[EnterpriseAPIKey]:
        """Get all keys for a tenant."""
        key_ids = self._tenant_keys.get(tenant_id, [])
        return [self._keys[kid] for kid in key_ids if kid in self._keys]
    
    def get_user_keys(self, user_id: str) -> List[EnterpriseAPIKey]:
        """Get all keys for a user."""
        return [k for k in self._keys.values() if k.user_id == user_id]
    
    def update_key(
        self,
        key_id: str,
        name: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        rate_limit: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None
    ) -> Optional[EnterpriseAPIKey]:
        """
        Update an API key.
        
        Args:
            key_id: Key identifier
            name: New name
            scopes: New scopes
            rate_limit: New rate limit
            allowed_ips: New allowed IPs
            
        Returns:
            Updated key or None
        """
        api_key = self._keys.get(key_id)
        if not api_key:
            return None
        
        if name:
            api_key.name = name
        
        if scopes:
            permissions = set()
            for scope_name in scopes:
                scope = self.DEFAULT_SCOPES.get(scope_name) or self._custom_scopes.get(scope_name)
                if scope:
                    permissions.update(scope.permissions)
            api_key.scopes = scopes
            api_key.permissions = list(permissions)
        
        if rate_limit is not None:
            api_key.rate_limit = rate_limit
        
        if allowed_ips is not None:
            api_key.allowed_ips = allowed_ips
        
        return api_key
    
    def add_custom_scope(self, scope: APIKeyScope) -> None:
        """Add a custom scope."""
        self._custom_scopes[scope.name] = scope
    
    def cleanup_expired_keys(self) -> int:
        """Clean up expired keys."""
        expired = [
            kid for kid, k in self._keys.items()
            if k.is_expired()
        ]
        
        for kid in expired:
            self._keys[kid].status = APIKeyStatus.EXPIRED
        
        return len(expired)


# Global API key manager instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager
