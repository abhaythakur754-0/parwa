"""
Tests for Week 54 Advanced Security Hardening - Encryption Manager
Tests for encryption_manager.py, key_vault.py, and secrets_manager.py
"""

import os
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile

from enterprise.security_hardening.encryption_manager import (
    EncryptionManager,
    EncryptionAlgorithm,
    EncryptedData,
    EncryptionKey,
    generate_encryption_key,
    encrypt_string,
    decrypt_string
)

from enterprise.security_hardening.key_vault import (
    KeyVault,
    KeyEntry,
    KeyStatus,
    AuditEntry,
    AccessLog
)

from enterprise.security_hardening.secrets_manager import (
    SecretsManager,
    Secret,
    SecretType,
    SecretStatus,
    SecretLease
)


# ============================================================================
# EncryptionManager Tests (10 tests)
# ============================================================================

class TestEncryptionManager:
    """Tests for EncryptionManager class."""
    
    def test_generate_key_aes256gcm(self):
        """Test generating an AES-256-GCM key."""
        manager = EncryptionManager()
        key_id = manager.generate_key(algorithm=EncryptionAlgorithm.AES_256_GCM)
        
        assert key_id is not None
        assert key_id.startswith("key_")
        assert key_id in manager._keys
        assert manager._current_key_id == key_id
    
    def test_generate_key_chacha20(self):
        """Test generating a ChaCha20-Poly1305 key."""
        manager = EncryptionManager()
        key_id = manager.generate_key(algorithm=EncryptionAlgorithm.CHACHA20_POLY1305)
        
        assert key_id is not None
        key = manager.get_key(key_id)
        assert key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305
    
    def test_generate_key_rsa(self):
        """Test generating an RSA key."""
        manager = EncryptionManager()
        key_id = manager.generate_key(algorithm=EncryptionAlgorithm.RSA_2048)
        
        assert key_id is not None
        key = manager.get_key(key_id)
        assert key.algorithm == EncryptionAlgorithm.RSA_2048
    
    def test_encrypt_decrypt_aes256gcm(self):
        """Test AES-256-GCM encryption and decryption."""
        manager = EncryptionManager()
        manager.generate_key(algorithm=EncryptionAlgorithm.AES_256_GCM)
        
        plaintext = "Hello, World! This is a secret message."
        encrypted = manager.encrypt(plaintext)
        
        assert encrypted.algorithm == EncryptionAlgorithm.AES_256_GCM
        assert encrypted.ciphertext != plaintext.encode('utf-8')
        assert encrypted.iv is not None
        assert encrypted.tag is not None
        
        decrypted = manager.decrypt(encrypted)
        assert decrypted.decode('utf-8') == plaintext
    
    def test_encrypt_decrypt_chacha20(self):
        """Test ChaCha20-Poly1305 encryption and decryption."""
        manager = EncryptionManager()
        manager.generate_key(algorithm=EncryptionAlgorithm.CHACHA20_POLY1305)
        
        plaintext = "ChaCha20 test message"
        encrypted = manager.encrypt(plaintext)
        
        assert encrypted.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305
        
        decrypted = manager.decrypt(encrypted)
        assert decrypted.decode('utf-8') == plaintext
    
    def test_encrypt_decrypt_rsa(self):
        """Test RSA encryption and decryption."""
        manager = EncryptionManager()
        manager.generate_key(algorithm=EncryptionAlgorithm.RSA_2048)
        
        # RSA has size limitations
        plaintext = "RSA test"
        encrypted = manager.encrypt(plaintext)
        
        assert encrypted.algorithm == EncryptionAlgorithm.RSA_2048
        assert encrypted.tag is None  # RSA doesn't use auth tags
        
        decrypted = manager.decrypt(encrypted)
        assert decrypted.decode('utf-8') == plaintext
    
    def test_key_rotation(self):
        """Test key rotation functionality."""
        manager = EncryptionManager()
        old_key_id = manager.generate_key()
        
        # Encrypt with old key
        plaintext = "Data encrypted with old key"
        encrypted = manager.encrypt(plaintext, key_id=old_key_id)
        
        # Rotate key
        new_key_id = manager.rotate_key(old_key_id)
        
        assert new_key_id != old_key_id
        assert manager._current_key_id == new_key_id
        
        # Old key should be inactive
        old_key = manager._keys[old_key_id]
        assert old_key.is_active == False
        
        # Should still be able to decrypt old data
        decrypted = manager.decrypt(encrypted)
        assert decrypted.decode('utf-8') == plaintext
    
    def test_re_encrypt(self):
        """Test re-encrypting data with a new key."""
        manager = EncryptionManager()
        key_id_1 = manager.generate_key()
        
        plaintext = "Data to re-encrypt"
        encrypted = manager.encrypt(plaintext, key_id=key_id_1)
        
        # Generate new key and re-encrypt
        key_id_2 = manager.generate_key()
        re_encrypted = manager.re_encrypt(encrypted, new_key_id=key_id_2)
        
        assert re_encrypted.key_id == key_id_2
        
        decrypted = manager.decrypt(re_encrypted)
        assert decrypted.decode('utf-8') == plaintext
    
    def test_encrypted_data_serialization(self):
        """Test EncryptedData serialization to JSON and back."""
        manager = EncryptionManager()
        manager.generate_key()
        
        plaintext = "Serialization test"
        encrypted = manager.encrypt(plaintext)
        
        # Serialize to JSON
        json_str = encrypted.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize
        restored = EncryptedData.from_json(json_str)
        assert restored.ciphertext == encrypted.ciphertext
        assert restored.iv == encrypted.iv
        assert restored.tag == encrypted.tag
        assert restored.algorithm == encrypted.algorithm
    
    def test_list_keys(self):
        """Test listing all keys."""
        manager = EncryptionManager()
        manager.generate_key(algorithm=EncryptionAlgorithm.AES_256_GCM)
        manager.generate_key(algorithm=EncryptionAlgorithm.CHACHA20_POLY1305)
        
        keys = manager.list_keys()
        
        assert len(keys) == 2
        algorithms = [k["algorithm"] for k in keys.values()]
        assert "AES-256-GCM" in algorithms
        assert "ChaCha20-Poly1305" in algorithms


# ============================================================================
# KeyVault Tests (8 tests)
# ============================================================================

class TestKeyVault:
    """Tests for KeyVault class."""
    
    def test_store_key(self):
        """Test storing a key in the vault."""
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(
            key_bytes=key_bytes,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            tags=["production", "api"]
        )
        
        assert key_id is not None
        assert key_id in vault._keys
    
    def test_retrieve_key(self):
        """Test retrieving a key from the vault."""
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(
            key_bytes=key_bytes,
            algorithm=EncryptionAlgorithm.AES_256_GCM
        )
        
        retrieved_bytes, entry = vault.retrieve_key(key_id)
        
        assert retrieved_bytes == key_bytes
        assert entry.key_id == key_id
        assert entry.algorithm == EncryptionAlgorithm.AES_256_GCM
    
    def test_retrieve_nonexistent_key(self):
        """Test retrieving a non-existent key raises error."""
        vault = KeyVault()
        
        with pytest.raises(KeyError):
            vault.retrieve_key("nonexistent_key")
    
    def test_rotate_key(self):
        """Test key rotation in vault."""
        vault = KeyVault()
        old_key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(
            key_bytes=old_key_bytes,
            algorithm=EncryptionAlgorithm.AES_256_GCM
        )
        
        # Rotate with new key
        new_key_bytes = generate_encryption_key()
        vault.rotate_key(key_id, new_key_bytes=new_key_bytes)
        
        # Check version incremented
        entry = vault._keys[key_id]
        assert entry.version == 2
        
        # Retrieved key should be new key
        retrieved_bytes, _ = vault.retrieve_key(key_id)
        assert retrieved_bytes == new_key_bytes
    
    def test_delete_key_soft(self):
        """Test soft delete (revoking) a key."""
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(key_bytes=key_bytes, algorithm=EncryptionAlgorithm.AES_256_GCM)
        vault.delete_key(key_id, soft_delete=True)
        
        # Key should still exist but be revoked
        assert key_id in vault._keys
        assert vault._keys[key_id].status == KeyStatus.REVOKED
        
        # Should not be retrievable
        with pytest.raises(KeyError):
            vault.retrieve_key(key_id)
    
    def test_delete_key_hard(self):
        """Test hard delete of a key."""
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(key_bytes=key_bytes, algorithm=EncryptionAlgorithm.AES_256_GCM)
        vault.delete_key(key_id, soft_delete=False)
        
        # Key should be completely removed
        assert key_id not in vault._keys
        assert key_id not in vault._key_data
    
    def test_key_versioning(self):
        """Test key version history."""
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(key_bytes=key_bytes, algorithm=EncryptionAlgorithm.AES_256_GCM)
        
        # Rotate multiple times
        for i in range(3):
            vault.rotate_key(key_id, new_key_bytes=generate_encryption_key())
        
        versions = vault.get_key_versions(key_id)
        
        assert len(versions) == 4  # Initial + 3 rotations
        assert versions[-1].version == 4
    
    def test_audit_trail(self):
        """Test audit trail logging."""
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        
        key_id = vault.store_key(key_bytes=key_bytes, algorithm=EncryptionAlgorithm.AES_256_GCM, user_id="user123")
        vault.retrieve_key(key_id, user_id="user456")
        
        audit = vault.get_audit_trail()
        
        assert len(audit) == 2
        actions = [a.action for a in audit]
        assert "store_key" in actions
        assert "retrieve_key" in actions


# ============================================================================
# SecretsManager Tests (10 tests)
# ============================================================================

class TestSecretsManager:
    """Tests for SecretsManager class."""
    
    def test_create_secret(self):
        """Test creating a secret."""
        manager = SecretsManager()
        
        secret = manager.create_secret(
            name="api_key",
            value="my-super-secret-api-key",
            secret_type=SecretType.API_KEY
        )
        
        assert secret.name == "api_key"
        assert secret.secret_type == SecretType.API_KEY
        assert secret.version == 1
        assert secret.status == SecretStatus.ACTIVE
    
    def test_get_secret(self):
        """Test retrieving a secret."""
        manager = SecretsManager()
        
        manager.create_secret(
            name="password",
            value="my-password-123"
        )
        
        value, secret = manager.get_secret("password")
        
        assert value == "my-password-123"
        assert secret.name == "password"
    
    def test_get_nonexistent_secret(self):
        """Test retrieving a non-existent secret raises error."""
        manager = SecretsManager()
        
        with pytest.raises(KeyError):
            manager.get_secret("nonexistent")
    
    def test_update_secret(self):
        """Test updating a secret."""
        manager = SecretsManager()
        
        manager.create_secret(name="token", value="old-token")
        updated = manager.update_secret(name="token", value="new-token")
        
        assert updated.version == 2
        
        value, _ = manager.get_secret("token")
        assert value == "new-token"
    
    def test_delete_secret_soft(self):
        """Test soft delete of a secret."""
        manager = SecretsManager()
        
        manager.create_secret(name="secret1", value="value1")
        manager.delete_secret("secret1", soft_delete=True)
        
        # Secret should still exist but be revoked
        assert "secret1" in manager._secrets
        assert manager._secrets["secret1"].status == SecretStatus.REVOKED
        
        with pytest.raises(KeyError):
            manager.get_secret("secret1")
    
    def test_delete_secret_hard(self):
        """Test hard delete of a secret."""
        manager = SecretsManager()
        
        manager.create_secret(name="secret2", value="value2")
        manager.delete_secret("secret2", soft_delete=False)
        
        assert "secret2" not in manager._secrets
    
    def test_secret_lease(self):
        """Test secret leasing."""
        manager = SecretsManager()
        
        manager.create_secret(name="db_password", value="db-pass")
        
        value, secret = manager.get_secret(
            "db_password",
            create_lease=True,
            lease_ttl=300
        )
        
        assert secret.lease_id is not None
        assert secret.lease_id in manager._leases
    
    def test_renew_lease(self):
        """Test renewing a lease."""
        manager = SecretsManager()
        
        manager.create_secret(name="api_token", value="token123")
        _, secret = manager.get_secret("api_token", create_lease=True)
        
        lease = manager.renew_lease(secret.lease_id, ttl=600)
        
        assert lease is not None
        assert lease.lease_id == secret.lease_id
    
    def test_rotate_secret(self):
        """Test rotating a secret."""
        manager = SecretsManager()
        
        manager.create_secret(
            name="rotate_test",
            value="original-value",
            rotation_interval_days=30
        )
        
        new_secret = manager.rotate_secret("rotate_test", new_value="new-value")
        
        assert new_secret.version == 2
        assert new_secret.last_rotated_at is not None
        
        value, _ = manager.get_secret("rotate_test")
        assert value == "new-value"
    
    def test_secret_versioning(self):
        """Test secret version history."""
        manager = SecretsManager()
        
        manager.create_secret(name="versioned", value="v1")
        manager.update_secret("versioned", value="v2")
        manager.update_secret("versioned", value="v3")
        
        versions = manager.get_secret_versions("versioned")
        
        assert len(versions) == 3
        
        # Get specific version
        v1_value, _ = manager.get_secret("versioned", version=1)
        assert v1_value == "v1"


# ============================================================================
# Integration Tests (5 tests)
# ============================================================================

class TestIntegration:
    """Integration tests for all three modules working together."""
    
    def test_end_to_end_encryption_workflow(self):
        """Test complete workflow: key vault -> encryption -> secrets."""
        # Create vault and store key
        vault = KeyVault()
        key_bytes = generate_encryption_key()
        key_id = vault.store_key(key_bytes, EncryptionAlgorithm.AES_256_GCM)
        
        # Create encryption manager with key from vault
        enc_manager = EncryptionManager()
        retrieved_key, _ = vault.retrieve_key(key_id)
        enc_manager.register_key("vault_key", retrieved_key, EncryptionAlgorithm.AES_256_GCM)
        
        # Create secrets manager with encryption manager
        secrets_mgr = SecretsManager(encryption_manager=enc_manager)
        
        # Create and retrieve secret
        secrets_mgr.create_secret("test_secret", "sensitive_data")
        value, _ = secrets_mgr.get_secret("test_secret")
        
        assert value == "sensitive_data"
    
    def test_key_vault_audit_trail_integration(self):
        """Test that all vault operations are properly audited."""
        vault = KeyVault()
        
        key_id = vault.store_key(
            key_bytes=generate_encryption_key(),
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            user_id="admin",
            client_ip="192.168.1.1"
        )
        
        vault.retrieve_key(key_id, user_id="app", client_ip="192.168.1.2")
        vault.rotate_key(key_id, user_id="admin")
        vault.delete_key(key_id, user_id="admin")
        
        audit = vault.get_audit_trail()
        
        assert len(audit) >= 4
        actions = [a.action for a in audit]
        assert "store_key" in actions
        assert "retrieve_key" in actions
        assert "rotate_key" in actions
        assert "soft_delete_key" in actions
    
    def test_secrets_manager_with_multiple_algorithms(self):
        """Test secrets manager with different encryption algorithms."""
        enc_manager = EncryptionManager()
        
        # Generate keys for different algorithms
        aes_key_id = enc_manager.generate_key(algorithm=EncryptionAlgorithm.AES_256_GCM)
        chacha_key_id = enc_manager.generate_key(algorithm=EncryptionAlgorithm.CHACHA20_POLY1305)
        
        secrets_mgr = SecretsManager(encryption_manager=enc_manager)
        
        # Create secrets
        secrets_mgr.create_secret("aes_secret", "data_for_aes")
        
        # Switch key and create another secret
        enc_manager.set_current_key(chacha_key_id)
        secrets_mgr.create_secret("chacha_secret", "data_for_chacha")
        
        # Both should be retrievable
        val1, _ = secrets_mgr.get_secret("aes_secret")
        val2, _ = secrets_mgr.get_secret("chacha_secret")
        
        assert val1 == "data_for_aes"
        assert val2 == "data_for_chacha"
    
    def test_secrets_manager_rotation_check(self):
        """Test automatic rotation detection."""
        secrets_mgr = SecretsManager(auto_rotate_enabled=True)
        
        # Create secret with 0 rotation interval (needs rotation immediately)
        secrets_mgr.create_secret(
            name="rotate_me",
            value="value",
            rotation_interval_days=0
        )
        
        # Set last_rotated_at to past
        secrets_mgr._secrets["rotate_me"].last_rotated_at = datetime.utcnow() - timedelta(days=1)
        
        # Get secret should mark it as pending rotation
        secrets_mgr.get_secret("rotate_me")
        
        assert secrets_mgr._secrets["rotate_me"].status == SecretStatus.PENDING_ROTATION
    
    def test_persistence_workflow(self):
        """Test saving and loading from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = os.path.join(tmpdir, "vault.json")
            secrets_path = os.path.join(tmpdir, "secrets.json")
            
            # Create vault and secret
            vault = KeyVault(vault_path=vault_path)
            key_id = vault.store_key(
                key_bytes=generate_encryption_key(),
                algorithm=EncryptionAlgorithm.AES_256_GCM
            )
            vault.save_to_disk()
            
            enc_manager = EncryptionManager()
            key_bytes, _ = vault.retrieve_key(key_id)
            enc_manager.register_key("loaded_key", key_bytes, EncryptionAlgorithm.AES_256_GCM)
            
            secrets_mgr = SecretsManager(
                encryption_manager=enc_manager,
                storage_path=secrets_path
            )
            secrets_mgr.create_secret("persisted", "value123")
            secrets_mgr.save_to_storage()
            
            # Load fresh instances
            vault2 = KeyVault(vault_path=vault_path)
            assert key_id in vault2._keys
            
            # Note: SecretsManager needs same encryption key to decrypt
            secrets_mgr2 = SecretsManager(
                encryption_manager=enc_manager,
                storage_path=secrets_path
            )
            secrets_mgr2._load_from_storage()
            
            assert "persisted" in secrets_mgr2._secrets


# ============================================================================
# Edge Case Tests (5 tests)
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_plaintext_encryption(self):
        """Test encrypting empty data."""
        manager = EncryptionManager()
        manager.generate_key()
        
        encrypted = manager.encrypt("")
        decrypted = manager.decrypt(encrypted)
        
        assert decrypted.decode('utf-8') == ""
    
    def test_large_data_encryption(self):
        """Test encrypting large data."""
        manager = EncryptionManager()
        manager.generate_key()
        
        # 1MB of data
        large_data = "x" * (1024 * 1024)
        
        encrypted = manager.encrypt(large_data)
        decrypted = manager.decrypt(encrypted)
        
        assert decrypted.decode('utf-8') == large_data
    
    def test_key_expiration(self):
        """Test key expiration handling."""
        vault = KeyVault(auto_expire_days=None)
        
        key_id = vault.store_key(
            key_bytes=generate_encryption_key(),
            algorithm=EncryptionAlgorithm.AES_256_GCM
        )
        
        # Manually set expiration to past
        vault._keys[key_id].expires_at = datetime.utcnow() - timedelta(days=1)
        vault._keys[key_id].status = KeyStatus.ACTIVE
        
        # Expire keys
        expired = vault.expire_keys()
        
        assert key_id in expired
        assert vault._keys[key_id].status == KeyStatus.EXPIRED
    
    def test_secret_expiration(self):
        """Test secret expiration handling."""
        manager = SecretsManager()
        
        manager.create_secret(
            name="expiring",
            value="value",
            expires_in_days=-1  # Already expired
        )
        
        # Manually adjust for test
        manager._secrets["expiring"].expires_at = datetime.utcnow() - timedelta(seconds=1)
        
        expired = manager.expire_secrets()
        
        assert "expiring" in expired
        assert manager._secrets["expiring"].status == SecretStatus.EXPIRED
    
    def test_duplicate_secret_name(self):
        """Test that creating duplicate secret raises error."""
        manager = SecretsManager()
        
        manager.create_secret("duplicate", "value1")
        
        with pytest.raises(ValueError, match="already exists"):
            manager.create_secret("duplicate", "value2")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
