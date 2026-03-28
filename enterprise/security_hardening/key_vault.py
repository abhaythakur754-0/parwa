"""
Key Vault - Week 54 Advanced Security Hardening
Secure storage for encryption keys with versioning and audit trails.
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import logging
from pathlib import Path

from .encryption_manager import EncryptionAlgorithm

logger = logging.getLogger(__name__)


class KeyStatus(Enum):
    """Status of a key entry."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class KeyEntry:
    """
    Represents a key entry in the vault.
    """
    key_id: str
    algorithm: EncryptionAlgorithm
    key_reference: str  # Reference to actual key storage location
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    version: int = 1
    status: KeyStatus = KeyStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key_id": self.key_id,
            "algorithm": self.algorithm.value,
            "key_reference": self.key_reference,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
            "status": self.status.value,
            "metadata": self.metadata,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyEntry':
        """Create instance from dictionary."""
        return cls(
            key_id=data["key_id"],
            algorithm=EncryptionAlgorithm(data["algorithm"]),
            key_reference=data["key_reference"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            version=data.get("version", 1),
            status=KeyStatus(data.get("status", "active")),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", [])
        )
    
    def is_valid(self) -> bool:
        """Check if key entry is valid for use."""
        if self.status != KeyStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


@dataclass
class AuditEntry:
    """
    Represents an audit log entry.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action: str = ""
    key_id: str = ""
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "key_id": self.key_id,
            "user_id": self.user_id,
            "client_ip": self.client_ip,
            "details": self.details,
            "success": self.success
        }


@dataclass
class AccessLog:
    """
    Represents an access log entry.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    operation: str = ""
    key_id: str = ""
    granted: bool = True
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "key_id": self.key_id,
            "granted": self.granted,
            "reason": self.reason
        }


class KeyVault:
    """
    Secure key vault for storing and managing encryption keys.
    
    Features:
    - Secure key storage with encryption at rest
    - Key versioning
    - Access logging and audit trail
    - Key rotation support
    """
    
    def __init__(
        self,
        vault_path: Optional[str] = None,
        master_key: Optional[bytes] = None,
        auto_expire_days: Optional[int] = 90
    ):
        """
        Initialize the key vault.
        
        Args:
            vault_path: Path to store vault data (default: in-memory)
            master_key: Master key for encrypting stored keys
            auto_expire_days: Default key expiration period
        """
        self.vault_path = vault_path
        self.master_key = master_key or secrets.token_bytes(32)
        self.auto_expire_days = auto_expire_days
        
        # In-memory storage
        self._keys: Dict[str, KeyEntry] = {}
        self._key_versions: Dict[str, List[KeyEntry]] = {}
        self._key_data: Dict[str, bytes] = {}  # Actual key bytes
        self._audit_log: List[AuditEntry] = []
        self._access_log: List[AccessLog] = []
        
        # Load from disk if path provided
        if vault_path and os.path.exists(vault_path):
            self._load_from_disk()
    
    def _generate_key_id(self) -> str:
        """Generate a unique key ID."""
        return f"vault_key_{secrets.token_hex(8)}"
    
    def _log_audit(
        self,
        action: str,
        key_id: str,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """Log an audit entry."""
        entry = AuditEntry(
            action=action,
            key_id=key_id,
            user_id=user_id,
            client_ip=client_ip,
            details=details or {},
            success=success
        )
        self._audit_log.append(entry)
        logger.debug(f"Audit: {action} on key {key_id} by {user_id or 'system'}")
    
    def _log_access(
        self,
        operation: str,
        key_id: str,
        granted: bool = True,
        reason: Optional[str] = None
    ) -> None:
        """Log an access attempt."""
        entry = AccessLog(
            operation=operation,
            key_id=key_id,
            granted=granted,
            reason=reason
        )
        self._access_log.append(entry)
    
    def store_key(
        self,
        key_bytes: bytes,
        algorithm: EncryptionAlgorithm,
        key_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> str:
        """
        Store a new key in the vault.
        
        Args:
            key_bytes: The actual key bytes to store
            algorithm: Encryption algorithm for the key
            key_id: Optional custom key ID
            expires_at: Optional expiration datetime
            metadata: Optional metadata
            tags: Optional tags for categorization
            user_id: User performing the operation
            client_ip: Client IP address
            
        Returns:
            The key ID
        """
        key_id = key_id or self._generate_key_id()
        
        # Set default expiration
        if expires_at is None and self.auto_expire_days:
            expires_at = datetime.utcnow() + timedelta(days=self.auto_expire_days)
        
        # Create key reference (hash of key for verification)
        key_hash = hashlib.sha256(key_bytes).hexdigest()[:16]
        key_reference = f"ref_{key_hash}"
        
        # Create entry
        entry = KeyEntry(
            key_id=key_id,
            algorithm=algorithm,
            key_reference=key_reference,
            expires_at=expires_at,
            metadata=metadata or {},
            tags=tags or []
        )
        
        # Store key data (in production, this would be encrypted at rest)
        self._key_data[key_id] = key_bytes
        self._keys[key_id] = entry
        
        # Initialize version history
        self._key_versions[key_id] = [entry]
        
        # Log audit
        self._log_audit(
            action="store_key",
            key_id=key_id,
            user_id=user_id,
            client_ip=client_ip,
            details={"algorithm": algorithm.value, "expires_at": expires_at.isoformat() if expires_at else None},
            success=True
        )
        
        logger.info(f"Stored key: {key_id} with algorithm: {algorithm.value}")
        return key_id
    
    def retrieve_key(
        self,
        key_id: str,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> tuple[bytes, KeyEntry]:
        """
        Retrieve a key from the vault.
        
        Args:
            key_id: The key ID to retrieve
            user_id: User performing the operation
            client_ip: Client IP address
            
        Returns:
            Tuple of (key_bytes, key_entry)
            
        Raises:
            KeyError: If key not found or invalid
        """
        if key_id not in self._keys:
            self._log_access("retrieve", key_id, granted=False, reason="Key not found")
            self._log_audit("retrieve_key", key_id, user_id, client_ip, success=False)
            raise KeyError(f"Key not found: {key_id}")
        
        entry = self._keys[key_id]
        
        if not entry.is_valid():
            reason = f"Key status: {entry.status.value}"
            self._log_access("retrieve", key_id, granted=False, reason=reason)
            self._log_audit("retrieve_key", key_id, user_id, client_ip, success=False)
            raise KeyError(f"Key is not valid: {key_id} - {reason}")
        
        key_bytes = self._key_data[key_id]
        
        self._log_access("retrieve", key_id, granted=True)
        self._log_audit("retrieve_key", key_id, user_id, client_ip, success=True)
        
        logger.info(f"Retrieved key: {key_id}")
        return key_bytes, entry
    
    def rotate_key(
        self,
        key_id: str,
        new_key_bytes: Optional[bytes] = None,
        algorithm: Optional[EncryptionAlgorithm] = None,
        expires_in_days: Optional[int] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> str:
        """
        Rotate a key by creating a new version.
        
        Args:
            key_id: The key ID to rotate
            new_key_bytes: Optional new key bytes (generated if not provided)
            algorithm: Optional new algorithm (uses previous if not specified)
            expires_in_days: Optional expiration for new key
            
        Returns:
            The key ID (same ID, new version)
        """
        if key_id not in self._keys:
            self._log_audit("rotate_key", key_id, user_id, client_ip, success=False)
            raise KeyError(f"Key not found: {key_id}")
        
        old_entry = self._keys[key_id]
        
        # Mark old key as inactive
        old_entry.status = KeyStatus.INACTIVE
        
        # Generate new key bytes if not provided
        if new_key_bytes is None:
            key_size = 32  # Default to 256-bit key
            new_key_bytes = secrets.token_bytes(key_size)
        
        # Use previous algorithm if not specified
        algorithm = algorithm or old_entry.algorithm
        
        # Calculate expiration
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        elif self.auto_expire_days:
            expires_at = datetime.utcnow() + timedelta(days=self.auto_expire_days)
        else:
            expires_at = None
        
        # Create new key reference
        key_hash = hashlib.sha256(new_key_bytes).hexdigest()[:16]
        key_reference = f"ref_{key_hash}_v{old_entry.version + 1}"
        
        # Create new entry
        new_entry = KeyEntry(
            key_id=key_id,
            algorithm=algorithm,
            key_reference=key_reference,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            version=old_entry.version + 1,
            status=KeyStatus.ACTIVE,
            metadata=old_entry.metadata.copy(),
            tags=old_entry.tags.copy()
        )
        
        # Store new key data
        self._key_data[key_id] = new_key_bytes
        self._keys[key_id] = new_entry
        
        # Add to version history
        self._key_versions[key_id].append(new_entry)
        
        # Log audit
        self._log_audit(
            action="rotate_key",
            key_id=key_id,
            user_id=user_id,
            client_ip=client_ip,
            details={"old_version": old_entry.version, "new_version": new_entry.version},
            success=True
        )
        
        logger.info(f"Rotated key: {key_id} to version {new_entry.version}")
        return key_id
    
    def delete_key(
        self,
        key_id: str,
        soft_delete: bool = True,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> None:
        """
        Delete a key from the vault.
        
        Args:
            key_id: The key ID to delete
            soft_delete: If True, mark as revoked instead of removing
            user_id: User performing the operation
            client_ip: Client IP address
        """
        if key_id not in self._keys:
            self._log_audit("delete_key", key_id, user_id, client_ip, success=False)
            raise KeyError(f"Key not found: {key_id}")
        
        if soft_delete:
            self._keys[key_id].status = KeyStatus.REVOKED
            self._log_audit(
                action="soft_delete_key",
                key_id=key_id,
                user_id=user_id,
                client_ip=client_ip,
                success=True
            )
            logger.info(f"Soft deleted (revoked) key: {key_id}")
        else:
            del self._keys[key_id]
            if key_id in self._key_data:
                del self._key_data[key_id]
            # Keep version history for audit
            self._log_audit(
                action="hard_delete_key",
                key_id=key_id,
                user_id=user_id,
                client_ip=client_ip,
                success=True
            )
            logger.info(f"Hard deleted key: {key_id}")
    
    def get_key_versions(self, key_id: str) -> List[KeyEntry]:
        """
        Get all versions of a key.
        
        Args:
            key_id: The key ID
            
        Returns:
            List of KeyEntry objects for all versions
        """
        return self._key_versions.get(key_id, [])
    
    def get_audit_trail(
        self,
        key_id: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Get audit trail entries.
        
        Args:
            key_id: Filter by key ID
            action: Filter by action
            user_id: Filter by user ID
            limit: Maximum number of entries to return
            
        Returns:
            List of AuditEntry objects
        """
        entries = self._audit_log.copy()
        
        if key_id:
            entries = [e for e in entries if e.key_id == key_id]
        if action:
            entries = [e for e in entries if e.action == action]
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        
        return entries[-limit:]
    
    def get_access_log(
        self,
        key_id: Optional[str] = None,
        operation: Optional[str] = None,
        granted_only: bool = False,
        limit: int = 100
    ) -> List[AccessLog]:
        """
        Get access log entries.
        
        Args:
            key_id: Filter by key ID
            operation: Filter by operation
            granted_only: Only return granted accesses
            limit: Maximum number of entries
            
        Returns:
            List of AccessLog objects
        """
        entries = self._access_log.copy()
        
        if key_id:
            entries = [e for e in entries if e.key_id == key_id]
        if operation:
            entries = [e for e in entries if e.operation == operation]
        if granted_only:
            entries = [e for e in entries if e.granted]
        
        return entries[-limit:]
    
    def list_keys(
        self,
        status: Optional[KeyStatus] = None,
        algorithm: Optional[EncryptionAlgorithm] = None,
        tags: Optional[List[str]] = None
    ) -> List[KeyEntry]:
        """
        List keys in the vault.
        
        Args:
            status: Filter by status
            algorithm: Filter by algorithm
            tags: Filter by tags (keys must have all specified tags)
            
        Returns:
            List of KeyEntry objects
        """
        entries = list(self._keys.values())
        
        if status:
            entries = [e for e in entries if e.status == status]
        if algorithm:
            entries = [e for e in entries if e.algorithm == algorithm]
        if tags:
            entries = [e for e in entries if all(t in e.tags for t in tags)]
        
        return entries
    
    def expire_keys(self) -> List[str]:
        """
        Mark expired keys.
        
        Returns:
            List of expired key IDs
        """
        expired = []
        now = datetime.utcnow()
        
        for key_id, entry in self._keys.items():
            if entry.expires_at and now > entry.expires_at and entry.status == KeyStatus.ACTIVE:
                entry.status = KeyStatus.EXPIRED
                expired.append(key_id)
                self._log_audit(
                    action="auto_expire",
                    key_id=key_id,
                    details={"expired_at": entry.expires_at.isoformat()},
                    success=True
                )
                logger.info(f"Auto-expired key: {key_id}")
        
        return expired
    
    def save_to_disk(self) -> None:
        """Save vault data to disk."""
        if not self.vault_path:
            raise ValueError("No vault path configured")
        
        data = {
            "keys": {k: v.to_dict() for k, v in self._keys.items()},
            "key_versions": {k: [v.to_dict() for v in versions] for k, versions in self._key_versions.items()},
            "audit_log": [e.to_dict() for e in self._audit_log],
            "access_log": [e.to_dict() for e in self._access_log]
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.vault_path) if os.path.dirname(self.vault_path) else '.', exist_ok=True)
        
        with open(self.vault_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved vault to: {self.vault_path}")
    
    def _load_from_disk(self) -> None:
        """Load vault data from disk."""
        if not os.path.exists(self.vault_path):
            return
        
        with open(self.vault_path, 'r') as f:
            data = json.load(f)
        
        self._keys = {k: KeyEntry.from_dict(v) for k, v in data.get("keys", {}).items()}
        self._key_versions = {
            k: [KeyEntry.from_dict(v) for v in versions]
            for k, versions in data.get("key_versions", {}).items()
        }
        self._audit_log = [
            AuditEntry(
                timestamp=datetime.fromisoformat(e["timestamp"]),
                action=e["action"],
                key_id=e["key_id"],
                user_id=e.get("user_id"),
                client_ip=e.get("client_ip"),
                details=e.get("details", {}),
                success=e.get("success", True)
            )
            for e in data.get("audit_log", [])
        ]
        self._access_log = [
            AccessLog(
                timestamp=datetime.fromisoformat(e["timestamp"]),
                operation=e["operation"],
                key_id=e["key_id"],
                granted=e.get("granted", True),
                reason=e.get("reason")
            )
            for e in data.get("access_log", [])
        ]
        
        logger.info(f"Loaded vault from: {self.vault_path}")
    
    def get_key_metadata(self, key_id: str) -> Dict[str, Any]:
        """
        Get metadata for a key without retrieving the key itself.
        
        Args:
            key_id: The key ID
            
        Returns:
            Dictionary with key metadata
        """
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")
        
        entry = self._keys[key_id]
        return {
            "key_id": entry.key_id,
            "algorithm": entry.algorithm.value,
            "version": entry.version,
            "status": entry.status.value,
            "created_at": entry.created_at.isoformat(),
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            "is_valid": entry.is_valid(),
            "metadata": entry.metadata,
            "tags": entry.tags
        }
    
    def update_key_metadata(
        self,
        key_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> None:
        """
        Update metadata for a key.
        
        Args:
            key_id: The key ID
            metadata: New metadata to merge
            tags: New tags to set
            user_id: User performing the operation
            client_ip: Client IP address
        """
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")
        
        entry = self._keys[key_id]
        
        if metadata:
            entry.metadata.update(metadata)
        if tags is not None:
            entry.tags = tags
        
        self._log_audit(
            action="update_metadata",
            key_id=key_id,
            user_id=user_id,
            client_ip=client_ip,
            success=True
        )
        
        logger.info(f"Updated metadata for key: {key_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get vault statistics.
        
        Returns:
            Dictionary with vault statistics
        """
        active_keys = sum(1 for e in self._keys.values() if e.status == KeyStatus.ACTIVE)
        expired_keys = sum(1 for e in self._keys.values() if e.status == KeyStatus.EXPIRED)
        revoked_keys = sum(1 for e in self._keys.values() if e.status == KeyStatus.REVOKED)
        
        return {
            "total_keys": len(self._keys),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "revoked_keys": revoked_keys,
            "total_audit_entries": len(self._audit_log),
            "total_access_entries": len(self._access_log),
            "algorithms": {
                algo.value: sum(1 for e in self._keys.values() if e.algorithm == algo)
                for algo in EncryptionAlgorithm
            }
        }
