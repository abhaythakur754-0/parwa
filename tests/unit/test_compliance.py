"""
Unit tests for the GDPR/CCPA compliance module.

Tests cover:
- PII masking (basic, nested, edge cases)
- Data portability reports
- Erasure request processing
- Compliance edge cases
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.core_functions.compliance import (
    mask_pii,
    generate_portability_report,
    process_erasure_request,
    PII_FIELDS,
)


class TestMaskPIIBasic:
    """Tests for basic PII masking functionality."""

    def test_mask_pii_basic_fields(self):
        """Test that explicit PII fields are redacted."""
        raw_data = {
            "user_id": "123",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
            "credit_card": "4111222233334444",
            "ssn": "000-00-0000",
            "address": "123 Main St",
            "favorite_color": "blue"
        }

        masked = mask_pii(raw_data)

        assert masked["user_id"] == "123"
        assert masked["favorite_color"] == "blue"

        # Check redacted fields
        assert masked["first_name"] == "[REDACTED]"
        assert masked["last_name"] == "[REDACTED]"
        assert masked["email"] == "[REDACTED]"
        assert masked["phone"] == "[REDACTED]"
        assert masked["credit_card"] == "[REDACTED]"
        assert masked["ssn"] == "[REDACTED]"
        assert masked["address"] == "[REDACTED]"

    def test_mask_pii_nested_dict(self):
        """Test that PII masking works recursively on nested dictionaries."""
        raw_data = {
            "user_id": "123",
            "profile": {
                "email": "test@test.com",
                "settings": {
                    "theme": "dark",
                    "phone": "555-5555"
                }
            }
        }

        masked = mask_pii(raw_data)

        assert masked["user_id"] == "123"
        assert masked["profile"]["settings"]["theme"] == "dark"
        assert masked["profile"]["email"] == "[REDACTED]"
        assert masked["profile"]["settings"]["phone"] == "[REDACTED]"

    def test_mask_pii_invalid_input(self):
        """Test that masking rejects non-dictionary inputs."""
        with pytest.raises(TypeError):
            mask_pii("not a dict")


class TestMaskPIIEdgeCases:
    """Tests for PII masking edge cases."""

    def test_mask_pii_empty_dict(self):
        """Test masking an empty dictionary."""
        masked = mask_pii({})
        assert masked == {}

    def test_mask_pii_none_values(self):
        """Test that None values in PII fields remain None."""
        raw_data = {
            "email": None,
            "phone": None,
            "name": "John"
        }
        masked = mask_pii(raw_data)
        # None values should not be redacted
        assert masked["email"] is None
        assert masked["phone"] is None
        assert masked["name"] == "John"

    def test_mask_pii_case_insensitive(self):
        """Test that PII field matching is case-insensitive."""
        raw_data = {
            "Email": "test@test.com",
            "EMAIL": "another@test.com",
            "PHONE": "555-5555",
            "phoneNumber": "123-456-7890",  # Not in PII_FIELDS
        }
        masked = mask_pii(raw_data)
        assert masked["Email"] == "[REDACTED]"
        assert masked["EMAIL"] == "[REDACTED]"
        assert masked["PHONE"] == "[REDACTED]"
        assert masked["phoneNumber"] == "123-456-7890"

    def test_mask_pii_deeply_nested(self):
        """Test PII masking in deeply nested structures."""
        raw_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "email": "deep@nested.com",
                        "data": "safe"
                    }
                }
            }
        }
        masked = mask_pii(raw_data)
        assert masked["level1"]["level2"]["level3"]["email"] == "[REDACTED]"
        assert masked["level1"]["level2"]["level3"]["data"] == "safe"

    def test_mask_pii_list_values(self):
        """Test that lists are processed correctly."""
        raw_data = {
            "emails": ["a@test.com", "b@test.com"],  # List not a dict, won't mask individual items
            "email": "main@test.com"
        }
        masked = mask_pii(raw_data)
        # List items themselves are not individually masked (list is not a dict)
        assert masked["emails"] == ["a@test.com", "b@test.com"]
        assert masked["email"] == "[REDACTED]"

    def test_mask_pii_preserves_original(self):
        """Test that masking doesn't modify original dictionary."""
        raw_data = {"email": "test@test.com", "name": "John"}
        original_email = raw_data["email"]
        masked = mask_pii(raw_data)

        # Original should be unchanged (copy was made)
        assert raw_data["email"] == original_email
        assert masked["email"] == "[REDACTED]"

    def test_mask_pii_all_pii_fields(self):
        """Test that all defined PII fields are masked."""
        raw_data = {field: f"test_{field}_value" for field in PII_FIELDS}
        masked = mask_pii(raw_data)

        for field in PII_FIELDS:
            assert masked[field] == "[REDACTED]", f"Field {field} should be redacted"


class TestGeneratePortabilityReport:
    """Tests for GDPR portability report generation."""

    def test_generate_portability_report(self):
        """Test generating a GDPR portability report."""
        def mock_fetcher(uid):
            return {"orders": [1, 2], "name": "Jane"}

        report = generate_portability_report("user_456", mock_fetcher)

        assert report["user_id"] == "user_456"
        assert report["metadata"]["report_type"] == "GDPR_PORTABILITY"
        assert "orders" in report["data"]
        assert report["data"]["name"] == "Jane"

    def test_generate_portability_report_without_fetcher(self):
        """Test portability report without custom fetcher."""
        report = generate_portability_report("user_123")

        assert report["user_id"] == "user_123"
        assert report["metadata"]["report_type"] == "GDPR_PORTABILITY"
        assert report["metadata"]["version"] == "1.0"

    def test_generate_portability_report_empty_user_id(self):
        """Test that empty user_id raises error."""
        with pytest.raises(ValueError):
            generate_portability_report("")

    def test_generate_portability_report_metadata(self):
        """Test portability report metadata structure."""
        report = generate_portability_report("user_test")

        assert "metadata" in report
        assert "report_type" in report["metadata"]
        assert "version" in report["metadata"]
        assert report["metadata"]["report_type"] == "GDPR_PORTABILITY"

    def test_generate_portability_report_with_complex_data(self):
        """Test portability report with complex nested data."""
        def mock_fetcher(uid):
            return {
                "profile": {"name": "John", "email": "john@test.com"},
                "orders": [{"id": 1, "total": 100}, {"id": 2, "total": 200}],
                "preferences": {"theme": "dark", "notifications": True}
            }

        report = generate_portability_report("complex_user", mock_fetcher)

        assert len(report["data"]["orders"]) == 2
        assert report["data"]["profile"]["name"] == "John"


class TestProcessErasureRequest:
    """Tests for GDPR erasure request processing."""

    def test_process_erasure_request_success(self):
        """Test successful erasure request processing."""
        def mock_deleter(uid):
            return True

        result = process_erasure_request("user_789", mock_deleter)
        assert result is True

    def test_process_erasure_request_failure(self):
        """Test failed erasure request handling."""
        def mock_deleter(uid):
            return False

        result = process_erasure_request("user_789", mock_deleter)
        assert result is False

    def test_process_erasure_request_invalid_id(self):
        """Test erasure request validates user_id."""
        with pytest.raises(ValueError):
            process_erasure_request("", None)

        with pytest.raises(TypeError):
            process_erasure_request(123, None)  # Must be a string

    def test_process_erasure_request_without_deleter(self):
        """Test erasure request without deleter function."""
        result = process_erasure_request("user_test", None)
        # Should succeed (just logs the audit)
        assert result is True

    def test_process_erasure_request_logs_audit(self):
        """Test that erasure request logs an audit trail."""
        # This test verifies the function completes without error
        # Actual logging verification would require log capture
        result = process_erasure_request("audit_test_user")
        assert result is True


class TestPIIFields:
    """Tests for PII field configuration."""

    def test_pii_fields_not_empty(self):
        """Test that PII_FIELDS is not empty."""
        assert len(PII_FIELDS) > 0

    def test_pii_fields_contains_expected(self):
        """Test that PII_FIELDS contains expected fields."""
        expected_fields = {"email", "phone", "ssn", "credit_card", "address"}
        assert expected_fields.issubset(PII_FIELDS)

    def test_pii_fields_is_set(self):
        """Test that PII_FIELDS is a set."""
        assert isinstance(PII_FIELDS, set)


class TestComplianceIntegration:
    """Integration tests for compliance module."""

    def test_mask_and_portability_workflow(self):
        """Test workflow combining masking and portability."""
        # Simulate fetching user data
        def mock_fetcher(uid):
            return {
                "email": "user@test.com",
                "phone": "555-5555",
                "preferences": {"theme": "dark"},
                "orders": [1, 2, 3]
            }

        # Generate portability report
        report = generate_portability_report("workflow_user", mock_fetcher)

        # Mask PII for safe display
        masked_data = mask_pii(report["data"])

        assert masked_data["email"] == "[REDACTED]"
        assert masked_data["phone"] == "[REDACTED]"
        assert masked_data["preferences"]["theme"] == "dark"
        assert masked_data["orders"] == [1, 2, 3]

    def test_full_gdpr_workflow(self):
        """Test complete GDPR workflow: portability -> erasure."""
        user_id = "gdpr_test_user"

        # Step 1: Generate portability report
        report = generate_portability_report(user_id)
        assert report["user_id"] == user_id

        # Step 2: Process erasure request
        result = process_erasure_request(user_id)
        assert result is True
