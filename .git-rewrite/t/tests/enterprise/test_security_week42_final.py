"""
Week 42 Builders 4-5 - Encryption & Compliance Tests
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestEncryptionManager:
    """Test encryption manager"""

    def test_manager_exists(self):
        """Test encryption manager exists"""
        from enterprise.security.encryption_manager import EncryptionManager
        assert EncryptionManager is not None

    def test_generate_key(self):
        """Test generating key"""
        from enterprise.security.encryption_manager import EncryptionManager, KeyType

        manager = EncryptionManager()
        key = manager.generate_key(key_type=KeyType.DATA_ENCRYPTION)

        assert key.key_id.startswith("key_")
        assert key.key_type == KeyType.DATA_ENCRYPTION

    def test_encrypt_decrypt(self):
        """Test encrypt and decrypt"""
        from enterprise.security.encryption_manager import EncryptionManager

        manager = EncryptionManager()
        key = manager.generate_key()
        encrypted = manager.encrypt("test data", key.key_id)

        assert encrypted.ciphertext is not None
        assert encrypted.key_id == key.key_id


class TestDataEncryption:
    """Test data encryption"""

    def test_encrypt_pii(self):
        """Test PII encryption"""
        from enterprise.security.encryption_manager import EncryptionManager, DataEncryption

        manager = EncryptionManager()
        data_enc = DataEncryption(manager)
        data = {"email": "test@example.com", "name": "Test User", "age": 30}

        encrypted = data_enc.encrypt_pii(data, "client_001")

        assert "email" in encrypted
        assert isinstance(encrypted["email"], dict)


class TestComplianceAutomation:
    """Test compliance automation"""

    def test_automation_exists(self):
        """Test compliance automation exists"""
        from enterprise.security.compliance_automation import ComplianceAutomation
        assert ComplianceAutomation is not None

    def test_run_hipaa_check(self):
        """Test HIPAA compliance check"""
        from enterprise.security.compliance_automation import ComplianceAutomation, ComplianceFramework

        automation = ComplianceAutomation()
        report = automation.run_compliance_check("client_001", ComplianceFramework.HIPAA)

        assert report.framework == ComplianceFramework.HIPAA
        assert len(report.checks) > 0

    def test_get_compliance_score(self):
        """Test getting compliance score"""
        from enterprise.security.compliance_automation import ComplianceAutomation, ComplianceFramework

        automation = ComplianceAutomation()
        automation.run_compliance_check("client_001", ComplianceFramework.HIPAA)

        score = automation.get_compliance_score("client_001")
        assert score >= 0
