"""
Secrets Manager - Week 54 Advanced Security Hardening
Comprehensive secrets management with leasing and automatic rotation.
"""

import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import logging
from pathlib import Path

from .encryption_manager import EncryptionManager, EncryptionAlgorithm, EncryptedData

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets."""
    API_KEY = "api_key"
    PASSWORD = "password"
    CERTIFICATE = "certificate"
    TOKEN = "token"
    DATABASE_CREDENTIAL = "database_credential"
    OAUTH_SECRET = "oauth_secret"
    SSH_KEY = "ssh_key"
    CUSTOM = "custom"


class SecretStatus(Enum):
    """Status of a secret."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_ROTATION = "pending_rotation"


@dataclass
class Secret:
    """
    Represents a secret with metadata.
    """
    name: str
    value: bytes  # The actual secret value (encrypted)
    secret_type: SecretType = SecretType.CUSTOM
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    rotation_interval_days: Optional[int] = None
    last_rotated_at: Optional[datetime] = None
    status: SecretStatus = SecretStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    lease_id: Optional[str] = None
    
    def to_dict(self, include_value: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "secret_type": self.secret_type.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "rotation_interval_days": self.rotation_interval_days,
            "last_rotated_at": self.last_rotated_at.isoformat() if self.last_rotated_at else None,
            "status": self.status.value,
            "metadata": self.metadata,
            "tags": self.tags,
            "lease_id": self.lease_id
        }
        if include_value:
            result["value"] = self.value.decode('utf-8') if isinstance(self.value, bytes) else self.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Secret':
        """Create instance from dictionary."""
        value = data.get("value", b"")
        if isinstance(value, str):
            value = value.encode('utf-8')
        
        return cls(
            name=data["name"],
            value=value,
            secret_type=SecretType(data.get("secret_type", "custom")),
            version=data.get("version", 1),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            rotation_interval_days=data.get("rotation_interval_days"),
            last_rotated_at=datetime.fromisoformat(data["last_rotated_at"]) if data.get("last_rotated_at") else None,
            status=SecretStatus(data.get("status", "active")),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            lease_id=data.get("lease_id")
        )
    
    def is_valid(self) -> bool:
        """Check if secret is valid for use."""
        if self.status != SecretStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def needs_rotation(self) -> bool:
        """Check if secret needs rotation."""
        if self.rotation_interval_days is None:
            return False
        if self.last_rotated_at is None:
            return True
        rotation_due = self.last_rotated_at + timedelta(days=self.rotation_interval_days)
        return datetime.utcnow() > rotation_due


@dataclass
class SecretLease:
    """
    Represents a lease on a secret.
    """
    lease_id: str
    secret_name: str
    issued_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    client_id: Optional[str] = None
    renewable: bool = True
    max_ttl_seconds: int = 3600  # 1 hour default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lease_id": self.lease_id,
            "secret_name": self.secret_name,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "client_id": self.client_id,
            "renewable": self.renewable,
            "max_ttl_seconds": self.max_ttl_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecretLease':
        """Create from dictionary."""
        return cls(
            lease_id=data["lease_id"],
            secret_name=data["secret_name"],
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            client_id=data.get("client_id"),
            renewable=data.get("renewable", True),
            max_ttl_seconds=data.get("max_ttl_seconds", 3600)
        )
    
    def is_valid(self) -> bool:
        """Check if lease is still valid."""
        if self.expires_at is None:
            return True
        return datetime.utcnow() < self.expires_at


class SecretsManager:
    """
    Comprehensive secrets management system.
    
    Features:
    - Secure secret storage with encryption
    - Secret versioning
    - Secret leasing with TTL
    - Automatic rotation support
    - Environment-based retrieval
    """
    
    def __init__(
        self,
        encryption_manager: Optional[EncryptionManager] = None,
        storage_path: Optional[str] = None,
        default_lease_ttl: int = 3600,
        max_lease_ttl: int = 86400,
        auto_rotate_enabled: bool = True
    ):
        """
        Initialize the secrets manager.
        
        Args:
            encryption_manager: Encryption manager for secret encryption
            storage_path: Optional path for persistent storage
            default_lease_ttl: Default lease TTL in seconds
            max_lease_ttl: Maximum lease TTL in seconds
            auto_rotate_enabled: Enable automatic rotation checks
        """
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.storage_path = storage_path
        self.default_lease_ttl = default_lease_ttl
        self.max_lease_ttl = max_lease_ttl
        self.auto_rotate_enabled = auto_rotate_enabled
        
        # Initialize encryption if not already done
        if not self.encryption_manager._keys:
            self.encryption_manager.generate_key()
        
        # In-memory storage
        self._secrets: Dict[str, Secret] = {}
        self._leases: Dict[str, SecretLease] = {}
        self._secret_versions: Dict[str, List[Secret]] = {}
        self._audit_log: List[Dict[str, Any]] = []
        
        # Load from storage if path provided
        if storage_path and os.path.exists(storage_path):
            self._load_from_storage()
    
    def _generate_lease_id(self) -> str:
        """Generate a unique lease ID."""
        return f"lease_{secrets.token_hex(8)}"
    
    def _log_audit(
        self,
        action: str,
        secret_name: str,
        client_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """Log an audit entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "secret_name": secret_name,
            "client_id": client_id,
            "details": details or {},
            "success": success
        }
        self._audit_log.append(entry)
        logger.debug(f"Audit: {action} on secret {secret_name}")
    
    def _encrypt_value(self, value: Union[str, bytes]) -> bytes:
        """Encrypt a secret value."""
        if isinstance(value, str):
            value = value.encode('utf-8')
        
        encrypted = self.encryption_manager.encrypt(value)
        return encrypted.to_json().encode('utf-8')
    
    def _decrypt_value(self, encrypted_value: bytes) -> bytes:
        """Decrypt a secret value."""
        encrypted_data = EncryptedData.from_json(encrypted_value.decode('utf-8'))
        return self.encryption_manager.decrypt(encrypted_data)
    
    def create_secret(
        self,
        name: str,
        value: Union[str, bytes],
        secret_type: SecretType = SecretType.CUSTOM,
        expires_in_days: Optional[int] = None,
        rotation_interval_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        client_id: Optional[str] = None
    ) -> Secret:
        """
        Create a new secret.
        
        Args:
            name: Secret name (must be unique)
            value: Secret value
            secret_type: Type of secret
            expires_in_days: Optional expiration period
            rotation_interval_days: Optional rotation interval
            metadata: Optional metadata
            tags: Optional tags
            client_id: Client creating the secret
            
        Returns:
            Created Secret instance
            
        Raises:
            ValueError: If secret with name already exists
        """
        if name in self._secrets:
            self._log_audit("create_secret", name, client_id, success=False)
            raise ValueError(f"Secret already exists: {name}")
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Encrypt the value
        encrypted_value = self._encrypt_value(value)
        
        # Create secret
        secret = Secret(
            name=name,
            value=encrypted_value,
            secret_type=secret_type,
            expires_at=expires_at,
            rotation_interval_days=rotation_interval_days,
            last_rotated_at=datetime.utcnow(),
            metadata=metadata or {},
            tags=tags or []
        )
        
        self._secrets[name] = secret
        self._secret_versions[name] = [secret]
        
        self._log_audit(
            action="create_secret",
            secret_name=name,
            client_id=client_id,
            details={"secret_type": secret_type.value},
            success=True
        )
        
        logger.info(f"Created secret: {name}")
        return secret
    
    def get_secret(
        self,
        name: str,
        version: Optional[int] = None,
        client_id: Optional[str] = None,
        create_lease: bool = False,
        lease_ttl: Optional[int] = None
    ) -> tuple[str, Secret]:
        """
        Retrieve a secret value.
        
        Args:
            name: Secret name
            version: Optional specific version (default: latest)
            client_id: Client retrieving the secret
            create_lease: Create a lease for the secret
            lease_ttl: Lease TTL in seconds
            
        Returns:
            Tuple of (decrypted_value, secret_metadata)
            
        Raises:
            KeyError: If secret not found or invalid
        """
        if name not in self._secrets:
            self._log_audit("get_secret", name, client_id, success=False)
            raise KeyError(f"Secret not found: {name}")
        
        # Get specific version or latest
        if version:
            versions = self._secret_versions.get(name, [])
            secret = next((s for s in versions if s.version == version), None)
            if not secret:
                raise KeyError(f"Secret version not found: {name} v{version}")
        else:
            secret = self._secrets[name]
        
        if not secret.is_valid():
            self._log_audit("get_secret", name, client_id, success=False)
            raise KeyError(f"Secret is not valid: {name}")
        
        # Check if rotation is needed
        if self.auto_rotate_enabled and secret.needs_rotation():
            secret.status = SecretStatus.PENDING_ROTATION
            logger.info(f"Secret {name} is pending rotation")
        
        # Decrypt value
        decrypted_value = self._decrypt_value(secret.value).decode('utf-8')
        
        # Create lease if requested
        lease_id = None
        if create_lease:
            lease = self._create_lease(name, client_id, lease_ttl)
            lease_id = lease.lease_id
        
        self._log_audit(
            action="get_secret",
            secret_name=name,
            client_id=client_id,
            details={"version": secret.version, "lease_id": lease_id},
            success=True
        )
        
        logger.info(f"Retrieved secret: {name} v{secret.version}")
        return decrypted_value, secret
    
    def update_secret(
        self,
        name: str,
        value: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        client_id: Optional[str] = None,
        increment_version: bool = True
    ) -> Secret:
        """
        Update a secret.
        
        Args:
            name: Secret name
            value: New secret value
            metadata: Optional new metadata (merged with existing)
            tags: Optional new tags
            client_id: Client updating the secret
            increment_version: Whether to increment version
            
        Returns:
            Updated Secret instance
        """
        if name not in self._secrets:
            self._log_audit("update_secret", name, client_id, success=False)
            raise KeyError(f"Secret not found: {name}")
        
        old_secret = self._secrets[name]
        
        # Encrypt new value
        encrypted_value = self._encrypt_value(value)
        
        # Determine new version
        new_version = old_secret.version + 1 if increment_version else old_secret.version
        
        # Create updated secret
        new_secret = Secret(
            name=name,
            value=encrypted_value,
            secret_type=old_secret.secret_type,
            version=new_version,
            created_at=old_secret.created_at,
            updated_at=datetime.utcnow(),
            expires_at=old_secret.expires_at,
            rotation_interval_days=old_secret.rotation_interval_days,
            last_rotated_at=old_secret.last_rotated_at,
            status=SecretStatus.ACTIVE,
            metadata={**old_secret.metadata, **(metadata or {})},
            tags=tags if tags is not None else old_secret.tags
        )
        
        self._secrets[name] = new_secret
        
        # Add to version history
        if increment_version:
            self._secret_versions[name].append(new_secret)
        
        self._log_audit(
            action="update_secret",
            secret_name=name,
            client_id=client_id,
            details={"old_version": old_secret.version, "new_version": new_version},
            success=True
        )
        
        logger.info(f"Updated secret: {name} to v{new_version}")
        return new_secret
    
    def delete_secret(
        self,
        name: str,
        soft_delete: bool = True,
        client_id: Optional[str] = None
    ) -> None:
        """
        Delete a secret.
        
        Args:
            name: Secret name
            soft_delete: If True, mark as revoked instead of removing
            client_id: Client deleting the secret
        """
        if name not in self._secrets:
            self._log_audit("delete_secret", name, client_id, success=False)
            raise KeyError(f"Secret not found: {name}")
        
        if soft_delete:
            self._secrets[name].status = SecretStatus.REVOKED
            self._log_audit("soft_delete_secret", name, client_id, success=True)
            logger.info(f"Soft deleted (revoked) secret: {name}")
        else:
            del self._secrets[name]
            # Keep version history for audit
            self._log_audit("hard_delete_secret", name, client_id, success=True)
            logger.info(f"Hard deleted secret: {name}")
    
    def _create_lease(
        self,
        secret_name: str,
        client_id: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> SecretLease:
        """Create a lease for a secret."""
        ttl = ttl or self.default_lease_ttl
        ttl = min(ttl, self.max_lease_ttl)
        
        lease_id = self._generate_lease_id()
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        lease = SecretLease(
            lease_id=lease_id,
            secret_name=secret_name,
            client_id=client_id,
            expires_at=expires_at,
            max_ttl_seconds=self.max_lease_ttl
        )
        
        self._leases[lease_id] = lease
        self._secrets[secret_name].lease_id = lease_id
        
        return lease
    
    def renew_lease(
        self,
        lease_id: str,
        ttl: Optional[int] = None,
        client_id: Optional[str] = None
    ) -> SecretLease:
        """
        Renew a lease.
        
        Args:
            lease_id: Lease ID to renew
            ttl: New TTL (default: original TTL)
            client_id: Client renewing
            
        Returns:
            Renewed SecretLease
        """
        if lease_id not in self._leases:
            raise KeyError(f"Lease not found: {lease_id}")
        
        lease = self._leases[lease_id]
        
        if not lease.renewable:
            raise ValueError(f"Lease is not renewable: {lease_id}")
        
        if not lease.is_valid():
            raise ValueError(f"Lease has expired: {lease_id}")
        
        # Calculate new TTL
        ttl = ttl or self.default_lease_ttl
        ttl = min(ttl, self.max_lease_ttl)
        
        # Calculate new expiration
        new_expires_at = lease.expires_at + timedelta(seconds=ttl)
        max_expires_at = lease.issued_at + timedelta(seconds=lease.max_ttl_seconds)
        
        if new_expires_at > max_expires_at:
            new_expires_at = max_expires_at
        
        lease.expires_at = new_expires_at
        
        self._log_audit(
            action="renew_lease",
            secret_name=lease.secret_name,
            client_id=client_id,
            details={"lease_id": lease_id},
            success=True
        )
        
        return lease
    
    def revoke_lease(self, lease_id: str, client_id: Optional[str] = None) -> None:
        """
        Revoke a lease.
        
        Args:
            lease_id: Lease ID to revoke
            client_id: Client revoking
        """
        if lease_id not in self._leases:
            raise KeyError(f"Lease not found: {lease_id}")
        
        lease = self._leases[lease_id]
        lease.expires_at = datetime.utcnow()  # Expire immediately
        
        # Clear lease from secret
        if lease.secret_name in self._secrets:
            self._secrets[lease.secret_name].lease_id = None
        
        self._log_audit(
            action="revoke_lease",
            secret_name=lease.secret_name,
            client_id=client_id,
            details={"lease_id": lease_id},
            success=True
        )
        
        logger.info(f"Revoked lease: {lease_id}")
    
    def rotate_secret(
        self,
        name: str,
        new_value: Optional[Union[str, bytes]] = None,
        client_id: Optional[str] = None
    ) -> Secret:
        """
        Rotate a secret.
        
        Args:
            name: Secret name
            new_value: Optional new value (auto-generated if not provided)
            client_id: Client rotating
            
        Returns:
            New Secret instance
        """
        if name not in self._secrets:
            raise KeyError(f"Secret not found: {name}")
        
        old_secret = self._secrets[name]
        
        # Generate new value if not provided
        if new_value is None:
            new_value = secrets.token_urlsafe(32)
        
        # Encrypt new value
        encrypted_value = self._encrypt_value(new_value)
        
        # Create new version
        new_secret = Secret(
            name=name,
            value=encrypted_value,
            secret_type=old_secret.secret_type,
            version=old_secret.version + 1,
            created_at=old_secret.created_at,
            updated_at=datetime.utcnow(),
            expires_at=old_secret.expires_at,
            rotation_interval_days=old_secret.rotation_interval_days,
            last_rotated_at=datetime.utcnow(),
            status=SecretStatus.ACTIVE,
            metadata=old_secret.metadata.copy(),
            tags=old_secret.tags.copy()
        )
        
        # Mark old secret as inactive
        old_secret.status = SecretStatus.REVOKED
        
        self._secrets[name] = new_secret
        self._secret_versions[name].append(new_secret)
        
        self._log_audit(
            action="rotate_secret",
            secret_name=name,
            client_id=client_id,
            details={"old_version": old_secret.version, "new_version": new_secret.version},
            success=True
        )
        
        logger.info(f"Rotated secret: {name} to v{new_secret.version}")
        return new_secret
    
    def get_secret_versions(self, name: str) -> List[Secret]:
        """Get all versions of a secret."""
        return self._secret_versions.get(name, [])
    
    def get_environment_secret(
        self,
        name: str,
        env_var: Optional[str] = None,
        default: Optional[str] = None
    ) -> Optional[str]:
        """
        Get a secret or fall back to environment variable.
        
        Args:
            name: Secret name
            env_var: Environment variable name (default: uppercase secret name)
            default: Default value if neither secret nor env var exists
            
        Returns:
            Secret value, env var value, or default
        """
        # Try to get from secrets manager
        try:
            value, _ = self.get_secret(name)
            return value
        except KeyError:
            pass
        
        # Fall back to environment variable
        env_var = env_var or name.upper().replace('-', '_')
        env_value = os.environ.get(env_var)
        
        if env_value:
            return env_value
        
        return default
    
    def set_environment_secret(
        self,
        name: str,
        env_var: Optional[str] = None
    ) -> None:
        """
        Set an environment variable from a secret.
        
        Args:
            name: Secret name
            env_var: Environment variable name (default: uppercase secret name)
        """
        value, _ = self.get_secret(name)
        env_var = env_var or name.upper().replace('-', '_')
        os.environ[env_var] = value
        logger.info(f"Set environment variable: {env_var}")
    
    def list_secrets(
        self,
        status: Optional[SecretStatus] = None,
        secret_type: Optional[SecretType] = None,
        tags: Optional[List[str]] = None,
        include_values: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List secrets.
        
        Args:
            status: Filter by status
            secret_type: Filter by type
            tags: Filter by tags
            include_values: Include decrypted values
            
        Returns:
            List of secret dictionaries
        """
        secrets_list = []
        
        for name, secret in self._secrets.items():
            if status and secret.status != status:
                continue
            if secret_type and secret.secret_type != secret_type:
                continue
            if tags and not all(t in secret.tags for t in tags):
                continue
            
            secret_dict = secret.to_dict(include_value=False)
            if include_values and secret.is_valid():
                try:
                    secret_dict["value"] = self._decrypt_value(secret.value).decode('utf-8')
                except Exception:
                    secret_dict["value"] = "[decryption_failed]"
            
            secrets_list.append(secret_dict)
        
        return secrets_list
    
    def check_rotations(self) -> List[str]:
        """
        Check for secrets that need rotation.
        
        Returns:
            List of secret names that need rotation
        """
        pending = []
        
        for name, secret in self._secrets.items():
            if secret.needs_rotation() and secret.status == SecretStatus.ACTIVE:
                secret.status = SecretStatus.PENDING_ROTATION
                pending.append(name)
                self._log_audit(
                    action="rotation_check",
                    secret_name=name,
                    details={"needs_rotation": True},
                    success=True
                )
        
        return pending
    
    def expire_secrets(self) -> List[str]:
        """
        Mark expired secrets.
        
        Returns:
            List of expired secret names
        """
        expired = []
        now = datetime.utcnow()
        
        for name, secret in self._secrets.items():
            if secret.expires_at and now > secret.expires_at and secret.status == SecretStatus.ACTIVE:
                secret.status = SecretStatus.EXPIRED
                expired.append(name)
                self._log_audit(
                    action="auto_expire",
                    secret_name=name,
                    details={"expired_at": secret.expires_at.isoformat()},
                    success=True
                )
        
        return expired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get secrets manager statistics."""
        active = sum(1 for s in self._secrets.values() if s.status == SecretStatus.ACTIVE)
        expired = sum(1 for s in self._secrets.values() if s.status == SecretStatus.EXPIRED)
        revoked = sum(1 for s in self._secrets.values() if s.status == SecretStatus.REVOKED)
        pending_rotation = sum(1 for s in self._secrets.values() if s.status == SecretStatus.PENDING_ROTATION)
        
        active_leases = sum(1 for l in self._leases.values() if l.is_valid())
        
        return {
            "total_secrets": len(self._secrets),
            "active_secrets": active,
            "expired_secrets": expired,
            "revoked_secrets": revoked,
            "pending_rotation": pending_rotation,
            "total_leases": len(self._leases),
            "active_leases": active_leases,
            "total_audit_entries": len(self._audit_log),
            "secret_types": {
                st.value: sum(1 for s in self._secrets.values() if s.secret_type == st)
                for st in SecretType
            }
        }
    
    def get_audit_log(
        self,
        secret_name: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        entries = self._audit_log.copy()
        
        if secret_name:
            entries = [e for e in entries if e.get("secret_name") == secret_name]
        if action:
            entries = [e for e in entries if e.get("action") == action]
        
        return entries[-limit:]
    
    def save_to_storage(self) -> None:
        """Save secrets to storage."""
        if not self.storage_path:
            raise ValueError("No storage path configured")
        
        data = {
            "secrets": {k: v.to_dict(include_value=True) for k, v in self._secrets.items()},
            "secret_versions": {
                k: [s.to_dict(include_value=True) for s in versions]
                for k, versions in self._secret_versions.items()
            },
            "leases": {k: v.to_dict() for k, v in self._leases.items()},
            "audit_log": self._audit_log[-1000:]  # Keep last 1000 entries
        }
        
        os.makedirs(os.path.dirname(self.storage_path) if os.path.dirname(self.storage_path) else '.', exist_ok=True)
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved secrets to: {self.storage_path}")
    
    def _load_from_storage(self) -> None:
        """Load secrets from storage."""
        if not os.path.exists(self.storage_path):
            return
        
        with open(self.storage_path, 'r') as f:
            data = json.load(f)
        
        self._secrets = {k: Secret.from_dict(v) for k, v in data.get("secrets", {}).items()}
        self._secret_versions = {
            k: [Secret.from_dict(s) for s in versions]
            for k, versions in data.get("secret_versions", {}).items()
        }
        self._leases = {k: SecretLease.from_dict(v) for k, v in data.get("leases", {}).items()}
        self._audit_log = data.get("audit_log", [])
        
        logger.info(f"Loaded secrets from: {self.storage_path}")
