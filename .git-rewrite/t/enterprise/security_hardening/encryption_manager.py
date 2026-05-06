"""
Encryption Manager - Week 54 Advanced Security Hardening
Provides encryption/decryption management with multiple algorithm support.
"""

import os
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, Tuple
import json
import logging

# Cryptography imports
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "AES-256-GCM"
    RSA_2048 = "RSA-2048"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"


@dataclass
class EncryptedData:
    """
    Container for encrypted data with all necessary components.
    """
    ciphertext: bytes
    iv: bytes  # Initialization vector or nonce
    tag: Optional[bytes] = None  # Authentication tag for AEAD ciphers
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode('utf-8'),
            "iv": base64.b64encode(self.iv).decode('utf-8'),
            "tag": base64.b64encode(self.tag).decode('utf-8') if self.tag else None,
            "algorithm": self.algorithm.value,
            "key_id": self.key_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedData':
        """Create instance from dictionary."""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            iv=base64.b64decode(data["iv"]),
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
            algorithm=EncryptionAlgorithm(data["algorithm"]),
            key_id=data.get("key_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
            metadata=data.get("metadata", {})
        )
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'EncryptedData':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class EncryptionKey:
    """
    Represents an encryption key with metadata.
    """
    def __init__(
        self,
        key_id: str,
        key_bytes: bytes,
        algorithm: EncryptionAlgorithm,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_active: bool = True
    ):
        self.key_id = key_id
        self.key_bytes = key_bytes
        self.algorithm = algorithm
        self.created_at = created_at or datetime.utcnow()
        self.expires_at = expires_at
        self.is_active = is_active
    
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if key is valid for use."""
        return self.is_active and not self.is_expired()


class EncryptionManager:
    """
    Main encryption manager supporting multiple algorithms and key rotation.
    """
    
    # Key sizes in bytes
    KEY_SIZES = {
        EncryptionAlgorithm.AES_256_GCM: 32,  # 256 bits
        EncryptionAlgorithm.CHACHA20_POLY1305: 32,  # 256 bits
        EncryptionAlgorithm.RSA_2048: 2048,  # bits for RSA
    }
    
    # IV/Nonce sizes in bytes
    IV_SIZES = {
        EncryptionAlgorithm.AES_256_GCM: 12,  # 96 bits recommended for GCM
        EncryptionAlgorithm.CHACHA20_POLY1305: 12,  # 96 bits
        EncryptionAlgorithm.RSA_2048: 0,  # RSA doesn't use IV
    }
    
    def __init__(self, default_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM):
        """
        Initialize the encryption manager.
        
        Args:
            default_algorithm: Default encryption algorithm to use
        """
        self.default_algorithm = default_algorithm
        self._keys: Dict[str, EncryptionKey] = {}
        self._current_key_id: Optional[str] = None
        self._key_history: Dict[str, list] = {}  # Track key rotation history
        
    def generate_key(
        self,
        algorithm: Optional[EncryptionAlgorithm] = None,
        key_id: Optional[str] = None,
        expires_in_days: Optional[int] = 90
    ) -> str:
        """
        Generate a new encryption key.
        
        Args:
            algorithm: Encryption algorithm for the key
            key_id: Optional custom key ID
            expires_in_days: Key expiration in days (None for no expiration)
            
        Returns:
            The key ID of the generated key
        """
        algorithm = algorithm or self.default_algorithm
        key_id = key_id or self._generate_key_id()
        
        if algorithm in (EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.CHACHA20_POLY1305):
            key_bytes = secrets.token_bytes(self.KEY_SIZES[algorithm])
        elif algorithm == EncryptionAlgorithm.RSA_2048:
            # For RSA, we store the private key bytes
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        key = EncryptionKey(
            key_id=key_id,
            key_bytes=key_bytes,
            algorithm=algorithm,
            expires_at=expires_at
        )
        
        self._keys[key_id] = key
        self._current_key_id = key_id
        self._key_history[key_id] = [{
            "action": "created",
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        logger.info(f"Generated new key: {key_id} for algorithm: {algorithm.value}")
        return key_id
    
    def _generate_key_id(self) -> str:
        """Generate a unique key ID."""
        return f"key_{secrets.token_hex(8)}"
    
    def register_key(
        self,
        key_id: str,
        key_bytes: bytes,
        algorithm: EncryptionAlgorithm,
        expires_at: Optional[datetime] = None
    ) -> None:
        """
        Register an existing key.
        
        Args:
            key_id: Key identifier
            key_bytes: The key bytes
            algorithm: Encryption algorithm
            expires_at: Optional expiration datetime
        """
        key = EncryptionKey(
            key_id=key_id,
            key_bytes=key_bytes,
            algorithm=algorithm,
            expires_at=expires_at
        )
        self._keys[key_id] = key
        self._key_history[key_id] = [{
            "action": "registered",
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        if self._current_key_id is None:
            self._current_key_id = key_id
    
    def get_key(self, key_id: Optional[str] = None, allow_inactive: bool = False) -> EncryptionKey:
        """
        Get a key by ID or the current default key.
        
        Args:
            key_id: Optional key ID (uses current key if not specified)
            allow_inactive: Allow inactive/expired keys (for decryption)
            
        Returns:
            EncryptionKey instance
            
        Raises:
            KeyError: If key not found or invalid
        """
        key_id = key_id or self._current_key_id
        if key_id is None:
            raise KeyError("No key available")
        
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")
        
        key = self._keys[key_id]
        if not allow_inactive and not key.is_valid():
            raise KeyError(f"Key is not valid: {key_id}")
        
        return key
    
    def encrypt(
        self,
        plaintext: Union[str, bytes],
        key_id: Optional[str] = None,
        algorithm: Optional[EncryptionAlgorithm] = None,
        associated_data: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EncryptedData:
        """
        Encrypt data using the specified or default algorithm.
        
        Args:
            plaintext: Data to encrypt
            key_id: Optional key ID to use
            algorithm: Optional algorithm (uses key's algorithm if not specified)
            associated_data: Optional associated data for AEAD
            metadata: Optional metadata to include
            
        Returns:
            EncryptedData instance
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        
        key = self.get_key(key_id)
        algorithm = algorithm or key.algorithm
        
        # If using a different algorithm, we might need a different key
        if algorithm != key.algorithm:
            raise ValueError(f"Algorithm mismatch: key is for {key.algorithm}, but {algorithm} requested")
        
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self._encrypt_aes_gcm(key, plaintext, associated_data, metadata)
        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            return self._encrypt_chacha20(key, plaintext, associated_data, metadata)
        elif algorithm == EncryptionAlgorithm.RSA_2048:
            return self._encrypt_rsa(key, plaintext, metadata)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def _encrypt_aes_gcm(
        self,
        key: EncryptionKey,
        plaintext: bytes,
        associated_data: Optional[bytes],
        metadata: Optional[Dict[str, Any]]
    ) -> EncryptedData:
        """Encrypt using AES-256-GCM."""
        iv = secrets.token_bytes(self.IV_SIZES[EncryptionAlgorithm.AES_256_GCM])
        aesgcm = AESGCM(key.key_bytes)
        
        ciphertext = aesgcm.encrypt(iv, plaintext, associated_data)
        
        # AES-GCM appends the tag to the ciphertext
        # Split them (tag is last 16 bytes)
        actual_ciphertext = ciphertext[:-16]
        tag = ciphertext[-16:]
        
        return EncryptedData(
            ciphertext=actual_ciphertext,
            iv=iv,
            tag=tag,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_id=key.key_id,
            metadata=metadata or {}
        )
    
    def _encrypt_chacha20(
        self,
        key: EncryptionKey,
        plaintext: bytes,
        associated_data: Optional[bytes],
        metadata: Optional[Dict[str, Any]]
    ) -> EncryptedData:
        """Encrypt using ChaCha20-Poly1305."""
        nonce = secrets.token_bytes(self.IV_SIZES[EncryptionAlgorithm.CHACHA20_POLY1305])
        chacha = ChaCha20Poly1305(key.key_bytes)
        
        ciphertext = chacha.encrypt(nonce, plaintext, associated_data)
        
        # ChaCha20-Poly1305 appends the tag to the ciphertext
        actual_ciphertext = ciphertext[:-16]
        tag = ciphertext[-16:]
        
        return EncryptedData(
            ciphertext=actual_ciphertext,
            iv=nonce,
            tag=tag,
            algorithm=EncryptionAlgorithm.CHACHA20_POLY1305,
            key_id=key.key_id,
            metadata=metadata or {}
        )
    
    def _encrypt_rsa(
        self,
        key: EncryptionKey,
        plaintext: bytes,
        metadata: Optional[Dict[str, Any]]
    ) -> EncryptedData:
        """Encrypt using RSA-2048."""
        private_key = serialization.load_pem_private_key(
            key.key_bytes,
            password=None,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        ciphertext = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=b'',  # RSA doesn't use IV
            tag=None,  # RSA doesn't use auth tags
            algorithm=EncryptionAlgorithm.RSA_2048,
            key_id=key.key_id,
            metadata=metadata or {}
        )
    
    def decrypt(
        self,
        encrypted_data: EncryptedData,
        associated_data: Optional[bytes] = None
    ) -> bytes:
        """
        Decrypt data.
        
        Args:
            encrypted_data: The encrypted data container
            associated_data: Optional associated data for AEAD
            
        Returns:
            Decrypted bytes
        """
        # Allow inactive keys for decryption (they may have been rotated)
        key = self.get_key(encrypted_data.key_id, allow_inactive=True)
        
        if encrypted_data.algorithm != key.algorithm:
            raise ValueError(
                f"Algorithm mismatch: data is encrypted with {encrypted_data.algorithm}, "
                f"but key is for {key.algorithm}"
            )
        
        if encrypted_data.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self._decrypt_aes_gcm(key, encrypted_data, associated_data)
        elif encrypted_data.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            return self._decrypt_chacha20(key, encrypted_data, associated_data)
        elif encrypted_data.algorithm == EncryptionAlgorithm.RSA_2048:
            return self._decrypt_rsa(key, encrypted_data)
        else:
            raise ValueError(f"Unsupported algorithm: {encrypted_data.algorithm}")
    
    def _decrypt_aes_gcm(
        self,
        key: EncryptionKey,
        encrypted_data: EncryptedData,
        associated_data: Optional[bytes]
    ) -> bytes:
        """Decrypt AES-256-GCM encrypted data."""
        aesgcm = AESGCM(key.key_bytes)
        
        # Reconstruct ciphertext with tag
        ciphertext_with_tag = encrypted_data.ciphertext + encrypted_data.tag
        
        return aesgcm.decrypt(encrypted_data.iv, ciphertext_with_tag, associated_data)
    
    def _decrypt_chacha20(
        self,
        key: EncryptionKey,
        encrypted_data: EncryptedData,
        associated_data: Optional[bytes]
    ) -> bytes:
        """Decrypt ChaCha20-Poly1305 encrypted data."""
        chacha = ChaCha20Poly1305(key.key_bytes)
        
        # Reconstruct ciphertext with tag
        ciphertext_with_tag = encrypted_data.ciphertext + encrypted_data.tag
        
        return chacha.decrypt(encrypted_data.iv, ciphertext_with_tag, associated_data)
    
    def _decrypt_rsa(
        self,
        key: EncryptionKey,
        encrypted_data: EncryptedData
    ) -> bytes:
        """Decrypt RSA encrypted data."""
        private_key = serialization.load_pem_private_key(
            key.key_bytes,
            password=None,
            backend=default_backend()
        )
        
        return private_key.decrypt(
            encrypted_data.ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    
    def rotate_key(
        self,
        old_key_id: Optional[str] = None,
        new_key_id: Optional[str] = None,
        algorithm: Optional[EncryptionAlgorithm] = None,
        expires_in_days: Optional[int] = 90
    ) -> str:
        """
        Rotate to a new encryption key.
        
        Args:
            old_key_id: ID of the key to rotate (current key if not specified)
            new_key_id: Optional ID for the new key
            algorithm: Algorithm for the new key (same as old if not specified)
            expires_in_days: New key expiration
            
        Returns:
            The new key ID
        """
        old_key_id = old_key_id or self._current_key_id
        if old_key_id and old_key_id in self._keys:
            old_key = self._keys[old_key_id]
            algorithm = algorithm or old_key.algorithm
            
            # Mark old key as inactive
            old_key.is_active = False
            
            # Record rotation in history
            if old_key_id in self._key_history:
                self._key_history[old_key_id].append({
                    "action": "rotated_from",
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # Generate new key
        new_key_id = self.generate_key(
            algorithm=algorithm,
            key_id=new_key_id,
            expires_in_days=expires_in_days
        )
        
        # Record rotation in new key history
        if new_key_id in self._key_history:
            self._key_history[new_key_id].append({
                "action": "rotated_to",
                "previous_key": old_key_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        logger.info(f"Rotated key from {old_key_id} to {new_key_id}")
        return new_key_id
    
    def re_encrypt(
        self,
        encrypted_data: EncryptedData,
        new_key_id: Optional[str] = None,
        associated_data: Optional[bytes] = None
    ) -> EncryptedData:
        """
        Re-encrypt data with a different key.
        
        Args:
            encrypted_data: The encrypted data to re-encrypt
            new_key_id: Target key ID (current key if not specified)
            associated_data: Optional associated data for AEAD
            
        Returns:
            New EncryptedData instance
        """
        # Decrypt with old key
        plaintext = self.decrypt(encrypted_data, associated_data)
        
        # Encrypt with new key
        return self.encrypt(
            plaintext,
            key_id=new_key_id,
            associated_data=associated_data,
            metadata=encrypted_data.metadata
        )
    
    def get_key_history(self, key_id: str) -> list:
        """Get the history of a key's lifecycle."""
        return self._key_history.get(key_id, [])
    
    def list_keys(self, include_inactive: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        List all registered keys.
        
        Args:
            include_inactive: Whether to include inactive keys
            
        Returns:
            Dictionary of key info
        """
        result = {}
        for key_id, key in self._keys.items():
            if include_inactive or key.is_active:
                result[key_id] = {
                    "algorithm": key.algorithm.value,
                    "created_at": key.created_at.isoformat(),
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "is_active": key.is_active,
                    "is_expired": key.is_expired()
                }
        return result
    
    def set_current_key(self, key_id: str) -> None:
        """Set the current default key."""
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")
        self._current_key_id = key_id
    
    def delete_key(self, key_id: str) -> None:
        """
        Delete a key (mark as inactive, keep for decryption of old data).
        
        Args:
            key_id: Key ID to delete
        """
        if key_id in self._keys:
            self._keys[key_id].is_active = False
            if key_id in self._key_history:
                self._key_history[key_id].append({
                    "action": "deleted",
                    "timestamp": datetime.utcnow().isoformat()
                })
            logger.info(f"Deleted key: {key_id}")


# Utility functions
def encrypt_string(plaintext: str, key: bytes, algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM) -> str:
    """
    Simple utility to encrypt a string and return base64 encoded result.
    
    Args:
        plaintext: String to encrypt
        key: Encryption key
        algorithm: Encryption algorithm
        
    Returns:
        Base64 encoded encrypted data
    """
    manager = EncryptionManager(default_algorithm=algorithm)
    manager.register_key("temp_key", key, algorithm)
    encrypted = manager.encrypt(plaintext)
    return encrypted.to_json()


def decrypt_string(encrypted_json: str, key: bytes) -> str:
    """
    Simple utility to decrypt a base64 encoded encrypted string.
    
    Args:
        encrypted_json: JSON string from encrypt_string
        key: Decryption key
        
    Returns:
        Decrypted string
    """
    encrypted_data = EncryptedData.from_json(encrypted_json)
    manager = EncryptionManager()
    manager.register_key("temp_key", key, encrypted_data.algorithm)
    decrypted = manager.decrypt(encrypted_data)
    return decrypted.decode('utf-8')


def generate_encryption_key(algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM) -> bytes:
    """
    Generate a raw encryption key for the specified algorithm.
    
    Args:
        algorithm: Encryption algorithm
        
    Returns:
        Raw key bytes
    """
    if algorithm in (EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.CHACHA20_POLY1305):
        return secrets.token_bytes(32)
    else:
        raise ValueError(f"Use EncryptionManager.generate_key() for {algorithm}")
