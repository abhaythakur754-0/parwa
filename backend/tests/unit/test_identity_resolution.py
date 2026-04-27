"""
Unit Tests for Identity Resolution Service - Day 4

Tests cover:
- Email matching (exact and fuzzy)
- Phone matching with normalization
- Social ID matching
- Device ID matching
- Duplicate detection
- Merge operations
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from app.services.identity_resolution_service import IdentityResolutionService
from app.services.customer_service import CustomerService
from database.models.tickets import Customer, CustomerChannel, IdentityMatchLog


class TestIdentityResolutionService:
    """Tests for IdentityResolutionService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create service instance."""
        return IdentityResolutionService(mock_db, "company-123")

    # ── EMAIL MATCHING ────────────────────────────────────────────────────────

    def test_match_by_email_exact(self, service, mock_db):
        """Test exact email match."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.email = "test@example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = customer

        result = service._match_by_email("test@example.com")

        assert result is not None
        assert result["customer_id"] == "customer-1"
        assert result["method"] == "email"
        assert result["confidence"] == 0.9

    def test_match_by_email_case_insensitive(self, service, mock_db):
        """Test case-insensitive email match."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.email = "Test@Example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = customer

        result = service._match_by_email("test@example.com")

        assert result is not None
        assert result["customer_id"] == "customer-1"

    def test_match_by_email_normalization(self, service, mock_db):
        """Test email normalization (whitespace)."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.email = "test@example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = customer

        result = service._match_by_email("  test@example.com  ")

        assert result is not None
        assert result["customer_id"] == "customer-1"

    def test_match_by_email_no_match(self, service, mock_db):
        """Test no email match found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = service._match_by_email("nonexistent@example.com")

        assert result is None

    def test_match_by_email_fuzzy(self, service, mock_db):
        """Test fuzzy email matching."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.email = "test.user@example.com"

        # No exact match
        mock_db.query.return_value.filter.return_value.first.return_value = None
        # Return customers for fuzzy matching
        mock_db.query.return_value.filter.return_value.all.return_value = [customer]

        # Similar email (typo)
        result = service._match_by_email("test-uer@example.com")

        assert result is not None
        assert result["method"] == "email_fuzzy"

    # ── PHONE MATCHING ─────────────────────────────────────────────────────────

    def test_match_by_phone_exact(self, service, mock_db):
        """Test exact phone match."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.phone = "+1234567890"

        mock_db.query.return_value.filter.return_value.first.return_value = customer

        result = service._match_by_phone("+1234567890")

        assert result is not None
        assert result["customer_id"] == "customer-1"
        assert result["method"] == "phone"
        assert result["confidence"] == 0.8

    def test_match_by_phone_normalization(self, service, mock_db):
        """Test phone normalization removes formatting."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.phone = "1234567890"

        mock_db.query.return_value.filter.return_value.first.return_value = customer

        # Phone with formatting should match
        result = service._match_by_phone("(123) 456-7890")

        assert result is not None
        assert result["customer_id"] == "customer-1"

    def test_normalize_phone(self, service):
        """Test phone number normalization."""
        assert service._normalize_phone("(123) 456-7890") == "1234567890"
        assert service._normalize_phone("+1-234-567-890") == "+1234567890"
        assert service._normalize_phone("123 456 7890") == "1234567890"

    # ── SOCIAL ID MATCHING ─────────────────────────────────────────────────────

    def test_match_by_social_id_no_social_channels(self, service):
        """Social media channels removed — method returns None."""
        result = service._match_by_social_id("any-social-id")
        assert result is None

    # ── RESOLVE IDENTITY ────────────────────────────────────────────────────────

    def test_resolve_identity_email_match(self, service, mock_db):
        """Test identity resolution with email match."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"
        customer.email = "test@example.com"

        # Mock email match
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            customer,  # Email match
            None,  # Phone match
            None,  # Social match
            None,  # Device match
        ]

        # Mock log creation
        log_entry = Mock(spec=IdentityMatchLog)
        with patch.object(service, '_log_resolution_attempt', return_value=log_entry):
            result = service.resolve_identity(email="test@example.com")

        assert result["matched_customer_id"] == "customer-1"
        assert result["match_method"] == "email"

    def test_resolve_identity_create_new(self, service, mock_db):
        """Test creating new customer when no match."""
        # No matches found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock log creation
        log_entry = Mock(spec=IdentityMatchLog)
        with patch.object(service, '_log_resolution_attempt', return_value=log_entry):
            with patch.object(service.customer_service, 'create_customer') as mock_create:
                new_customer = Mock(spec=Customer)
                new_customer.id = "new-customer-1"
                mock_create.return_value = new_customer

                result = service.resolve_identity(
                    email="new@example.com",
                    auto_create=True
                )

        assert result["action_taken"] == "created"
        assert result["matched_customer_id"] == "new-customer-1"

    def test_resolve_identity_no_auto_create(self, service, mock_db):
        """Test not creating customer when auto_create=False."""
        # No matches found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock log creation
        log_entry = Mock(spec=IdentityMatchLog)
        with patch.object(service, '_log_resolution_attempt', return_value=log_entry):
            result = service.resolve_identity(
                email="new@example.com",
                auto_create=False
            )

        assert result["action_taken"] == "none"
        assert result["matched_customer_id"] is None

    def test_resolve_identity_highest_confidence(self, service, mock_db):
        """Test selecting match with highest confidence."""
        # Set up multiple matches
        email_customer = Mock(spec=Customer)
        email_customer.id = "email-customer"
        email_customer.email = "test@example.com"

        phone_customer = Mock(spec=Customer)
        phone_customer.id = "phone-customer"

        # Email has higher confidence (0.9) than phone (0.8)
        def mock_query_filter(*args):
            mock = MagicMock()
            if "email" in str(args):
                mock.first.return_value = email_customer
            elif "phone" in str(args):
                mock.first.return_value = phone_customer
            else:
                mock.first.return_value = None
            return mock

        mock_db.query.return_value.filter.side_effect = mock_query_filter

        # Log mock
        log_entry = Mock(spec=IdentityMatchLog)
        with patch.object(service, '_log_resolution_attempt', return_value=log_entry):
            result = service.resolve_identity(
                email="test@example.com",
                phone="+1234567890"
            )

        # Email match should win (higher confidence)
        assert result["matched_customer_id"] == "email-customer"

    # ── DUPLICATE DETECTION ─────────────────────────────────────────────────────

    def test_find_potential_duplicates_email(self, service, mock_db):
        """Test finding duplicates by email."""
        c1 = Mock(spec=Customer)
        c1.id = "customer-1"
        c1.email = "test@example.com"
        c1.phone = None
        c1.name = "Test User"

        c2 = Mock(spec=Customer)
        c2.id = "customer-2"
        c2.email = "test@example.com"  # Same email
        c2.phone = None
        c2.name = "Test User 2"

        with patch.object(service.customer_service, 'get_customer', return_value=c1):
            mock_db.query.return_value.filter.return_value.all.return_value = [c1, c2]

            duplicates = service.find_potential_duplicates(customer_id="customer-1")

        assert len(duplicates) > 0
        assert duplicates[0]["match_method"] == "email_exact"

    def test_find_potential_duplicates_phone(self, service, mock_db):
        """Test finding duplicates by phone."""
        c1 = Mock(spec=Customer)
        c1.id = "customer-1"
        c1.email = None
        c1.phone = "+1234567890"
        c1.name = "Test User"

        c2 = Mock(spec=Customer)
        c2.id = "customer-2"
        c2.email = None
        c2.phone = "1234567890"  # Same phone, different format
        c2.name = "Test User 2"

        with patch.object(service.customer_service, 'get_customer', return_value=c1):
            mock_db.query.return_value.filter.return_value.all.return_value = [c1, c2]

            duplicates = service.find_potential_duplicates(customer_id="customer-1")

        assert len(duplicates) > 0

    def test_find_potential_duplicates_min_confidence(self, service, mock_db):
        """Test filtering duplicates by minimum confidence."""
        c1 = Mock(spec=Customer)
        c1.id = "customer-1"
        c1.email = "test1@example.com"
        c1.phone = None
        c1.name = "User One"

        c2 = Mock(spec=Customer)
        c2.id = "customer-2"
        c2.email = "test2@example.com"  # Different email
        c2.phone = None
        c2.name = "Completely Different"

        with patch.object(service.customer_service, 'get_customer', return_value=c1):
            mock_db.query.return_value.filter.return_value.all.return_value = [c1, c2]

            # High threshold should filter out low-confidence matches
            duplicates = service.find_potential_duplicates(
                customer_id="customer-1",
                min_confidence=0.9
            )

        # Low confidence matches should be filtered
        assert len(duplicates) == 0

    # ── CONFIDENCE SCORES ───────────────────────────────────────────────────────

    def test_confidence_scores(self, service):
        """Test confidence score constants."""
        assert service.CONFIDENCE_EMAIL == 0.9
        assert service.CONFIDENCE_EMAIL_FUZZY == 0.7
        assert service.CONFIDENCE_PHONE == 0.8
        assert service.CONFIDENCE_SOCIAL == 0.7
        assert service.CONFIDENCE_DEVICE == 0.5

    def test_auto_link_threshold(self, service):
        """Test auto-link threshold."""
        assert service.AUTO_LINK_THRESHOLD == 0.85


class TestCustomerService:
    """Tests for CustomerService merge functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create service instance."""
        return CustomerService(mock_db, "company-123")

    # ── CUSTOMER MERGE ─────────────────────────────────────────────────────────

    def test_merge_customers_basic(self, service, mock_db):
        """Test basic customer merge."""
        primary = Mock(spec=Customer)
        primary.id = "primary-1"
        primary.email = "primary@example.com"
        primary.phone = "+1111111111"
        primary.name = "Primary User"
        primary.metadata_json = "{}"

        secondary = Mock(spec=Customer)
        secondary.id = "secondary-1"
        secondary.email = "secondary@example.com"
        secondary.phone = "+2222222222"
        secondary.name = "Secondary User"
        secondary.metadata_json = "{}"

        with patch.object(service, 'get_customer', side_effect=[primary, secondary]):
            result = service.merge_customers(
                primary_customer_id="primary-1",
                merged_customer_ids=["secondary-1"],
                reason="Duplicate accounts",
                user_id="admin-1"
            )

        # Check primary was returned
        assert result.id == "primary-1"

        # Check tickets were reassigned
        mock_db.query.return_value.filter.return_value.update.assert_called()

    def test_merge_customers_validation_self_merge(self, service):
        """Test that merging customer into itself is rejected."""
        with pytest.raises(Exception):  # ValidationError
            service.merge_customers(
                primary_customer_id="customer-1",
                merged_customer_ids=["customer-1"],  # Same ID
            )

    def test_merge_customers_validation_duplicates(self, service):
        """Test that duplicate IDs in merge list are rejected."""
        with pytest.raises(Exception):  # ValidationError
            service.merge_customers(
                primary_customer_id="customer-1",
                merged_customer_ids=["customer-2", "customer-2"],  # Duplicate
            )

    # ── CHANNEL LINKING ────────────────────────────────────────────────────────

    def test_link_channel_email(self, service, mock_db):
        """Test linking email channel."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"

        with patch.object(service, 'get_customer', return_value=customer):
            mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing

            from app.schemas.customer import ChannelType
            channel = service.link_channel(
                customer_id="customer-1",
                channel_type=ChannelType.EMAIL,
                external_id="test@example.com",
                is_verified=False
            )

        assert channel is not None
        mock_db.add.assert_called()

    def test_link_channel_already_exists(self, service, mock_db):
        """Test that linking duplicate channel is rejected."""
        customer = Mock(spec=Customer)
        customer.id = "customer-1"

        existing_channel = Mock(spec=CustomerChannel)
        existing_channel.id = "existing-1"

        with patch.object(service, 'get_customer', return_value=customer):
            mock_db.query.return_value.filter.return_value.first.return_value = existing_channel

            from app.schemas.customer import ChannelType
            from app.exceptions import ValidationError

            with pytest.raises(ValidationError):
                service.link_channel(
                    customer_id="customer-1",
                    channel_type=ChannelType.EMAIL,
                    external_id="test@example.com"
                )

    def test_get_customer_channels(self, service, mock_db):
        """Test getting all channels for a customer."""
        channels = [
            Mock(spec=CustomerChannel, channel_type="email", external_id="test@example.com"),
            Mock(spec=CustomerChannel, channel_type="phone", external_id="+1234567890"),
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = channels

        result = service.get_customer_channels("customer-1")

        assert len(result) == 2


class TestIdentityMatchLog:
    """Tests for identity match logging."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return IdentityResolutionService(mock_db, "company-123")

    def test_log_resolution_attempt(self, service, mock_db):
        """Test that resolution attempts are logged."""
        log_entry = service._log_resolution_attempt(
            email="test@example.com",
            phone="+1234567890",
            matches=[{"customer_id": "c1", "method": "email", "confidence": 0.9}]
        )

        assert log_entry is not None
        assert log_entry.input_email == "test@example.com"
        assert log_entry.input_phone == "+1234567890"
        mock_db.add.assert_called()

    def test_get_match_logs_pagination(self, service, mock_db):
        """Test getting match logs with pagination."""
        logs = [Mock(spec=IdentityMatchLog) for _ in range(5)]

        mock_db.query.return_value.filter.return_value.count.return_value = 25
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = logs

        result, total = service.get_match_logs(page=2, page_size=5)

        assert len(result) == 5
        assert total == 25
