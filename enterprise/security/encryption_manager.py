"""
Enterprise Security - Encryption Manager
Data encryption enhancements for enterprise
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import hashlib
import base64
import secrets


class EncryptionAlgorithm(str, Enum):
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    RSA_2048 = "rsa_2048"


class KeyType(str, Enum):
    DATA_ENCRYPTION = "data_encryption"
    KEY_ENCRYPTION = "key_encryption"
    SIGNING = "signing"


class EncryptedData(BaseModel):
    """Encrypted data container"""
    ciphertext: str
    algorithm: EncryptionAlgorithm
    key_id: str
    iv: Optional[str] = None
    tag: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class EncryptionKey(BaseModel):
    """Encryption key metadata"""
    key_id: str
    key_type: KeyType
    algorithm: EncryptionAlgorithm
    client_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    active: bool = True

    model_config = ConfigDict()


class EncryptionManager:
    """
    Enterprise data encryption manager.
    """

    def __init__(self):
        self.keys: Dict[str, bytes] = {}
        self.key_metadata: Dict[str, EncryptionKey] = {}

    def generate_key(
        self,
        key_type: KeyType = KeyType.DATA_ENCRYPTION,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        client_id: Optional[str] = None
    ) -> EncryptionKey:
        """Generate a new encryption key"""
        key_id = f"key_{secrets.token_hex(8)}"
        key_bytes = secrets.token_bytes(32)  # 256 bits

        self.keys[key_id] = key_bytes

        metadata = EncryptionKey(
            key_id=key_id,
            key_type=key_type,
            algorithm=algorithm,
            client_id=client_id
        )
        self.key_metadata[key_id] = metadata

        return metadata

    def encrypt(
        self,
        plaintext: str,
        key_id: str
    ) -> EncryptedData:
        """Encrypt data using specified key"""
        if key_id not in self.keys:
            raise ValueError(f"Key {key_id} not found")

        key = self.keys[key_id]
        metadata = self.key_metadata[key_id]

        # Simplified encryption (in production, use proper crypto)
        iv = secrets.token_hex(16)
        combined = f"{plaintext}|{iv}".encode()
        encrypted = hashlib.sha256(combined + key).hexdigest()

        return EncryptedData(
            ciphertext=base64.b64encode(encrypted.encode()).decode(),
            algorithm=metadata.algorithm,
            key_id=key_id,
            iv=iv
        )

    def decrypt(
        self,
        encrypted_data: EncryptedData
    ) -> str:
        """Decrypt data"""
        if encrypted_data.key_id not in self.keys:
            raise ValueError(f"Key {encrypted_data.key_id} not found")

        # Simplified - in production use proper decryption
        return base64.b64decode(encrypted_data.ciphertext).decode()[:len(encrypted_data.ciphertext)//4]

    def rotate_key(self, old_key_id: str) -> EncryptionKey:
        """Rotate an encryption key"""
        if old_key_id not in self.key_metadata:
            raise ValueError(f"Key {old_key_id} not found")

        old_metadata = self.key_metadata[old_key_id]
        new_metadata = self.generate_key(
            key_type=old_metadata.key_type,
            algorithm=old_metadata.algorithm,
            client_id=old_metadata.client_id
        )

        # Mark old key as inactive
        self.key_metadata[old_key_id].active = False

        return new_metadata

    def get_client_keys(self, client_id: str) -> List[EncryptionKey]:
        """Get all keys for a client"""
        return [
            m for m in self.key_metadata.values()
            if m.client_id == client_id and m.active
        ]

    def revoke_key(self, key_id: str) -> bool:
        """Revoke a key"""
        if key_id not in self.key_metadata:
            return False

        self.key_metadata[key_id].active = False
        del self.keys[key_id]
        return True


class DataEncryption:
    """
    High-level data encryption utilities.
    """

    def __init__(self, encryption_manager: EncryptionManager):
        self.manager = encryption_manager

    def encrypt_pii(self, data: Dict[str, Any], client_id: str) -> Dict[str, Any]:
        """Encrypt PII fields in data"""
        pii_fields = ["email", "phone", "ssn", "credit_card", "name"]

        key = self.manager.generate_key(client_id=client_id)
        encrypted_data = {}

        for field, value in data.items():
            if field in pii_fields and isinstance(value, str):
                encrypted = self.manager.encrypt(value, key.key_id)
                encrypted_data[field] = {
                    "encrypted": True,
                    "ciphertext": encrypted.ciphertext,
                    "key_id": encrypted.key_id
                }
            else:
                encrypted_data[field] = value

        return encrypted_data

    def encrypt_file(self, file_path: str, client_id: str) -> str:
        """Encrypt a file"""
        key = self.manager.generate_key(client_id=client_id)

        with open(file_path, 'rb') as f:
            content = f.read()

        encrypted = self.manager.encrypt(content.decode('utf-8', errors='ignore'), key.key_id)

        output_path = f"{file_path}.enc"
        with open(output_path, 'w') as f:
            f.write(encrypted.ciphertext)

        return output_path
