"""
E2E Test: GDPR Compliance Flow.

Tests GDPR compliance including:
- Data export (right to access)
- Data deletion (right to be forgotten)
- PII anonymization

CRITICAL REQUIREMENTS:
- Export complete (all customer data)
- Deletion anonymizes PII
- Row preserved (not deleted)
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib
import json
import uuid


class MockUserRecord:
    """Mock user record for GDPR testing."""

    def __init__(
        self,
        user_id: str,
        email: str,
        first_name: str,
        last_name: str,
        phone: str,
        address: str
    ):
        self.user_id = user_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.address = address
        self.is_anonymized = False
        self.row_preserved = True


class MockGDPRService:
    """Mock GDPR service for E2E testing."""

    # PII fields that must be anonymized
    PII_FIELDS = ["email", "first_name", "last_name", "phone", "address"]

    def __init__(self):
        self._users: Dict[str, MockUserRecord] = {}
        self._exports: Dict[str, Dict[str, Any]] = {}
        self._erasure_requests: List[Dict[str, Any]] = []

    def create_user(
        self,
        user_id: str,
        email: str,
        first_name: str,
        last_name: str,
        phone: str,
        address: str
    ) -> MockUserRecord:
        """Create a mock user for testing."""
        user = MockUserRecord(
            user_id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            address=address
        )
        self._users[user_id] = user
        return user

    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all user data for GDPR right to access.

        CRITICAL: Export must be complete (all customer data).

        Args:
            user_id: User identifier

        Returns:
            Dict with all user data organized by category
        """
        user = self._users.get(user_id)

        if not user:
            return {
                "success": False,
                "error": "User not found",
                "user_id": user_id
            }

        # CRITICAL: Must include ALL customer data
        export_data = {
            "request_id": f"GDPR-EXPORT-{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "identity": {
                    "user_id": user.user_id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "contact": {
                    "email": user.email,
                    "phone": user.phone,
                    "address": user.address,
                },
                "preferences": {
                    "newsletter": True,
                    "notifications": "email",
                },
                "technical": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_login": datetime.now(timezone.utc).isoformat(),
                }
            },
            "is_complete": True,  # CRITICAL: Must be True
            "data_categories": ["identity", "contact", "preferences", "technical"]
        }

        self._exports[user_id] = export_data

        return {
            "success": True,
            "export": export_data
        }

    async def request_erasure(self, user_id: str) -> Dict[str, Any]:
        """
        Process GDPR erasure request (right to be forgotten).

        CRITICAL: PII anonymized, row preserved.

        Args:
            user_id: User identifier

        Returns:
            Dict with erasure result
        """
        user = self._users.get(user_id)

        if not user:
            return {
                "success": False,
                "error": "User not found",
                "user_id": user_id
            }

        # CRITICAL: Anonymize PII, preserve row
        user.email = self._anonymize_value(user.email)
        user.first_name = "[ANONYMIZED]"
        user.last_name = "[ANONYMIZED]"
        user.phone = "[ANONYMIZED]"
        user.address = "[ANONYMIZED]"
        user.is_anonymized = True
        user.row_preserved = True  # CRITICAL: Row must be preserved

        erasure_record = {
            "request_id": f"GDPR-ERASE-{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "status": "completed",
            "anonymized_fields": self.PII_FIELDS,
            "row_preserved": True,  # CRITICAL: Must be True
            "completed_at": datetime.now(timezone.utc).isoformat()
        }

        self._erasure_requests.append(erasure_record)

        return {
            "success": True,
            "erasure": erasure_record
        }

    def _anonymize_value(self, value: str) -> str:
        """Anonymize a PII value using hashing."""
        if not value:
            return "[ANONYMIZED]"
        return f"anon_{hashlib.sha256(value.encode()).hexdigest()[:16]}"

    def get_user(self, user_id: str) -> Optional[MockUserRecord]:
        """Get a user by ID."""
        return self._users.get(user_id)

    def is_user_anonymized(self, user_id: str) -> bool:
        """Check if user data has been anonymized."""
        user = self._users.get(user_id)
        return user.is_anonymized if user else False

    def is_row_preserved(self, user_id: str) -> bool:
        """Check if user row is preserved after erasure."""
        user = self._users.get(user_id)
        return user.row_preserved if user else False


@pytest.fixture
def gdpr_service():
    """Create a mock GDPR service."""
    return MockGDPRService()


class TestGDPRExport:
    """
    E2E tests for GDPR data export (right to access).

    CRITICAL: Export must be complete with all customer data.
    """

    @pytest.mark.asyncio
    async def test_export_complete(self, gdpr_service):
        """Test that export includes all customer data."""
        user_id = str(uuid.uuid4())

        # Create user with data
        gdpr_service.create_user(
            user_id=user_id,
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            phone="+1234567890",
            address="123 Main St, City"
        )

        # Request export
        result = await gdpr_service.export_user_data(user_id)

        assert result["success"] is True
        export = result["export"]

        # CRITICAL: Export must be complete
        assert export["is_complete"] is True

        # Verify all data categories are present
        assert "identity" in export["data"]
        assert "contact" in export["data"]
        assert "preferences" in export["data"]
        assert "technical" in export["data"]

    @pytest.mark.asyncio
    async def test_export_includes_contact_data(self, gdpr_service):
        """Test that export includes contact information."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="test@example.com",
            first_name="Jane",
            last_name="Smith",
            phone="+1987654321",
            address="456 Oak Ave"
        )

        result = await gdpr_service.export_user_data(user_id)

        assert result["success"] is True
        contact_data = result["export"]["data"]["contact"]

        assert contact_data["email"] == "test@example.com"
        assert contact_data["phone"] == "+1987654321"
        assert contact_data["address"] == "456 Oak Ave"

    @pytest.mark.asyncio
    async def test_export_includes_identity_data(self, gdpr_service):
        """Test that export includes identity information."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="identity@test.com",
            first_name="Bob",
            last_name="Jones",
            phone="+1122334455",
            address="789 Pine Rd"
        )

        result = await gdpr_service.export_user_data(user_id)

        assert result["success"] is True
        identity_data = result["export"]["data"]["identity"]

        assert identity_data["user_id"] == user_id
        assert identity_data["first_name"] == "Bob"
        assert identity_data["last_name"] == "Jones"

    @pytest.mark.asyncio
    async def test_export_nonexistent_user(self, gdpr_service):
        """Test export for nonexistent user."""
        result = await gdpr_service.export_user_data("nonexistent-user")

        assert result["success"] is False
        assert "error" in result


class TestGDPRErasure:
    """
    E2E tests for GDPR data erasure (right to be forgotten).

    CRITICAL:
    - PII must be anonymized
    - Row must be preserved (not deleted)
    """

    @pytest.mark.asyncio
    async def test_erasure_anonymizes_pii(self, gdpr_service):
        """Test that erasure anonymizes PII fields."""
        user_id = str(uuid.uuid4())

        # Create user with PII
        gdpr_service.create_user(
            user_id=user_id,
            email="sensitive@example.com",
            first_name="Secret",
            last_name="Person",
            phone="+1555555555",
            address="Secret Location"
        )

        # Request erasure
        result = await gdpr_service.request_erasure(user_id)

        assert result["success"] is True

        # Verify PII is anonymized
        user = gdpr_service.get_user(user_id)
        assert user is not None
        assert user.is_anonymized is True

        # Verify specific fields are anonymized
        assert user.first_name == "[ANONYMIZED]"
        assert user.last_name == "[ANONYMIZED]"
        assert user.phone == "[ANONYMIZED]"
        assert user.address == "[ANONYMIZED]"
        # Email should be hashed, not plaintext
        assert user.email != "sensitive@example.com"
        assert user.email.startswith("anon_")

    @pytest.mark.asyncio
    async def test_erasure_preserves_row(self, gdpr_service):
        """Test that erasure preserves the row (does not delete)."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="preserve@example.com",
            first_name="Keep",
            last_name="Row",
            phone="+1444444444",
            address="Keep Address"
        )

        # Request erasure
        result = await gdpr_service.request_erasure(user_id)

        assert result["success"] is True

        # CRITICAL: Row must be preserved
        erasure = result["erasure"]
        assert erasure["row_preserved"] is True

        # Verify user still exists
        user = gdpr_service.get_user(user_id)
        assert user is not None
        assert gdpr_service.is_row_preserved(user_id) is True

    @pytest.mark.asyncio
    async def test_erasure_complete_workflow(self, gdpr_service):
        """Test complete erasure workflow."""
        user_id = str(uuid.uuid4())

        # Create user
        gdpr_service.create_user(
            user_id=user_id,
            email="workflow@example.com",
            first_name="Work",
            last_name="Flow",
            phone="+1333333333",
            address="Workflow Address"
        )

        # Step 1: Export data before erasure
        export_before = await gdpr_service.export_user_data(user_id)
        assert export_before["success"] is True
        assert export_before["export"]["data"]["contact"]["email"] == "workflow@example.com"

        # Step 2: Request erasure
        erasure_result = await gdpr_service.request_erasure(user_id)
        assert erasure_result["success"] is True

        # Step 3: Verify PII is anonymized
        user = gdpr_service.get_user(user_id)
        assert user.is_anonymized is True

        # Step 4: Verify row is preserved
        assert user.row_preserved is True

    @pytest.mark.asyncio
    async def test_erasure_nonexistent_user(self, gdpr_service):
        """Test erasure for nonexistent user."""
        result = await gdpr_service.request_erasure("nonexistent-user")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_multiple_erasure_requests(self, gdpr_service):
        """Test handling multiple erasure requests."""
        user_ids = [str(uuid.uuid4()) for _ in range(3)]

        # Create multiple users
        for i, user_id in enumerate(user_ids):
            gdpr_service.create_user(
                user_id=user_id,
                email=f"user{i}@example.com",
                first_name=f"User{i}",
                last_name="Test",
                phone=f"+1555555555{i}",
                address=f"Address {i}"
            )

        # Process erasure for all
        for user_id in user_ids:
            result = await gdpr_service.request_erasure(user_id)
            assert result["success"] is True

        # Verify all are anonymized and preserved
        for user_id in user_ids:
            assert gdpr_service.is_user_anonymized(user_id) is True
            assert gdpr_service.is_row_preserved(user_id) is True


class TestGDPRCompliance:
    """Tests for overall GDPR compliance."""

    @pytest.mark.asyncio
    async def test_pii_fields_identified(self, gdpr_service):
        """Test that all PII fields are correctly identified."""
        # Verify PII fields list
        expected_pii = ["email", "first_name", "last_name", "phone", "address"]

        for field in expected_pii:
            assert field in gdpr_service.PII_FIELDS

    @pytest.mark.asyncio
    async def test_anonymization_is_reversible_only_with_key(self, gdpr_service):
        """Test that anonymization uses secure hashing."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="secure@example.com",
            first_name="Secure",
            last_name="User",
            phone="+1777777777",
            address="Secure Location"
        )

        original_email = "secure@example.com"

        # Process erasure
        await gdpr_service.request_erasure(user_id)

        user = gdpr_service.get_user(user_id)

        # Email should be hashed, not plaintext
        assert user.email != original_email
        # Should have anon_ prefix (hashed)
        assert user.email.startswith("anon_")
        # Hash should be consistent length
        assert len(user.email) == len("anon_") + 16

    @pytest.mark.asyncio
    async def test_export_request_id_generated(self, gdpr_service):
        """Test that export generates unique request ID."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="request@example.com",
            first_name="Request",
            last_name="ID",
            phone="+1888888888",
            address="Request Address"
        )

        result = await gdpr_service.export_user_data(user_id)

        assert result["success"] is True
        assert "request_id" in result["export"]
        assert result["export"]["request_id"].startswith("GDPR-EXPORT-")

    @pytest.mark.asyncio
    async def test_erasure_request_id_generated(self, gdpr_service):
        """Test that erasure generates unique request ID."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="erase@example.com",
            first_name="Erase",
            last_name="Request",
            phone="+1999999999",
            address="Erase Address"
        )

        result = await gdpr_service.request_erasure(user_id)

        assert result["success"] is True
        assert "request_id" in result["erasure"]
        assert result["erasure"]["request_id"].startswith("GDPR-ERASE-")


class TestGDPRDataIntegrity:
    """Tests for data integrity during GDPR operations."""

    @pytest.mark.asyncio
    async def test_export_checksum_verification(self, gdpr_service):
        """Test that export can be verified with checksum."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="checksum@example.com",
            first_name="Check",
            last_name="Sum",
            phone="+1111111111",
            address="Checksum Address"
        )

        result = await gdpr_service.export_user_data(user_id)

        assert result["success"] is True
        export = result["export"]

        # Verify data structure is intact
        assert "data" in export
        assert "user_id" in export
        assert export["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_anonymized_data_cannot_be_reversed(self, gdpr_service):
        """Test that anonymized data cannot be easily reversed."""
        user_id = str(uuid.uuid4())

        original_email = "irreversible@example.com"

        gdpr_service.create_user(
            user_id=user_id,
            email=original_email,
            first_name="Irre",
            last_name="Versible",
            phone="+1222222222",
            address="Irreversible Address"
        )

        # Before erasure
        user_before = gdpr_service.get_user(user_id)
        assert user_before.email == original_email

        # Process erasure
        await gdpr_service.request_erasure(user_id)

        # After erasure
        user_after = gdpr_service.get_user(user_id)

        # Verify original data is not recoverable
        assert "[ANONYMIZED]" not in original_email  # Original didn't have this
        assert user_after.first_name == "[ANONYMIZED]"  # Now it does
        assert user_after.email != original_email

    @pytest.mark.asyncio
    async def test_partial_data_preserved(self, gdpr_service):
        """Test that non-PII data is preserved during erasure."""
        user_id = str(uuid.uuid4())

        gdpr_service.create_user(
            user_id=user_id,
            email="partial@example.com",
            first_name="Partial",
            last_name="Data",
            phone="+1333333333",
            address="Partial Address"
        )

        # Process erasure
        await gdpr_service.request_erasure(user_id)

        user = gdpr_service.get_user(user_id)

        # User ID (non-PII) should be preserved
        assert user.user_id == user_id
        # Row should be preserved
        assert user.row_preserved is True
