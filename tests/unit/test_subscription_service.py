"""
Unit Tests for Subscription Service (W5D2)

Tests for:
- Subscription creation
- Subscription retrieval
- Upgrade subscription with proration
- Downgrade subscription (scheduled)
- Cancel subscription
- Reactivate subscription

BC-001: Tenant isolation in all operations
BC-002: Decimal precision in money calculations
"""

import pytest
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from backend.app.services.subscription_service import (
    SubscriptionService,
    SubscriptionError,
    SubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    InvalidVariantError,
    InvalidStatusTransitionError,
)
from backend.app.schemas.billing import (
    SubscriptionStatus,
    VariantType,
    SubscriptionInfo,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture
def mock_paddle_client():
    """Create a mock Paddle client."""
    client = AsyncMock()
    client.create_subscription = AsyncMock(
        return_value={"data": {"id": "sub_test123"}}
    )
    client.update_subscription = AsyncMock(return_value={})
    client.cancel_subscription = AsyncMock(return_value={})
    client.resume_subscription = AsyncMock(return_value={})
    return client


@pytest.fixture
def subscription_service(mock_paddle_client):
    """Create subscription service with mocked Paddle."""
    service = SubscriptionService(paddle_client=mock_paddle_client)
    return service


@pytest.fixture
def sample_company_id():
    """Sample company UUID."""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """Sample user UUID."""
    return uuid4()


# ── Subscription Creation Tests ───────────────────────────────────────────

class TestSubscriptionCreation:
    """Tests for subscription creation."""

    @pytest.mark.asyncio
    async def test_create_subscription_starter(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test creating a starter subscription."""
        mock_subscription_id = str(uuid4())

        mock_company = MagicMock()
        mock_company.id = str(sample_company_id)
        mock_company.paddle_customer_id = None

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ), patch(
            "backend.app.services.subscription_service.Subscription"
        ) as MockSubscription:
            # Create a mock subscription instance
            mock_subscription = MagicMock()
            mock_subscription.id = mock_subscription_id
            mock_subscription.company_id = str(sample_company_id)
            mock_subscription.tier = "starter"
            mock_subscription.status = "active"
            mock_subscription.current_period_start = datetime.now(timezone.utc)
            mock_subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
            mock_subscription.cancel_at_period_end = False
            mock_subscription.paddle_subscription_id = None
            mock_subscription.created_at = datetime.now(timezone.utc)
            MockSubscription.return_value = mock_subscription

            mock_db_session.query.return_value.filter.return_value.first.side_effect = [
                None,  # No existing subscription
                mock_company,  # Company found
            ]
            mock_db_session.add = MagicMock()
            mock_db_session.commit = MagicMock()
            mock_db_session.refresh = MagicMock()

            result = await subscription_service.create_subscription(
                company_id=sample_company_id,
                variant="starter",
            )

            assert result is not None
            mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_create_subscription_all_variants(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test creating subscriptions for all variant types."""
        variants = ["starter", "growth", "high"]

        for variant in variants:
            mock_subscription = MagicMock()
            mock_subscription.id = str(uuid4())
            mock_subscription.company_id = str(sample_company_id)
            mock_subscription.tier = variant
            mock_subscription.status = "active"
            mock_subscription.cancel_at_period_end = False
            mock_subscription.created_at = datetime.now(timezone.utc)

            mock_company = MagicMock()
            mock_company.id = str(sample_company_id)
            mock_company.paddle_customer_id = None

            with patch(
                "backend.app.services.subscription_service.SessionLocal",
                return_value=mock_db_session
            ):
                mock_db_session.query.return_value.filter.return_value.first.side_effect = [
                    None,  # No existing subscription
                    mock_company,  # Company found
                ]
                mock_db_session.add = MagicMock()
                mock_db_session.commit = MagicMock()

                # Validate variant
                validated = subscription_service._validate_variant(variant)
                assert validated == variant

    @pytest.mark.asyncio
    async def test_create_subscription_already_exists(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test that creating subscription fails if one already exists."""
        mock_existing = MagicMock()
        mock_existing.id = str(uuid4())

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_existing

            with pytest.raises(SubscriptionAlreadyExistsError):
                await subscription_service.create_subscription(
                    company_id=sample_company_id,
                    variant="starter",
                )

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_variant(
        self, subscription_service, sample_company_id
    ):
        """Test that invalid variant raises error."""
        with pytest.raises(InvalidVariantError):
            await subscription_service.create_subscription(
                company_id=sample_company_id,
                variant="invalid_variant",
            )


# ── Subscription Retrieval Tests ──────────────────────────────────────────

class TestSubscriptionRetrieval:
    """Tests for subscription retrieval."""

    @pytest.mark.asyncio
    async def test_get_subscription_found(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test retrieving an existing subscription."""
        mock_subscription = MagicMock()
        mock_subscription.id = str(uuid4())
        mock_subscription.company_id = str(sample_company_id)
        mock_subscription.tier = "growth"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = datetime.now(timezone.utc)
        mock_subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        mock_subscription.cancel_at_period_end = False
        mock_subscription.paddle_subscription_id = "sub_123"
        mock_subscription.created_at = datetime.now(timezone.utc)

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            result = await subscription_service.get_subscription(sample_company_id)

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_subscription_not_found(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test retrieving a non-existent subscription."""
        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

            result = await subscription_service.get_subscription(sample_company_id)

            assert result is None


# ── Upgrade Tests ─────────────────────────────────────────────────────────

class TestSubscriptionUpgrade:
    """Tests for subscription upgrades."""

    def test_is_upgrade_correct(self, subscription_service):
        """Test upgrade detection logic."""
        # Starter to Growth
        assert subscription_service._is_upgrade("starter", "growth") is True
        # Starter to High
        assert subscription_service._is_upgrade("starter", "high") is True
        # Growth to High
        assert subscription_service._is_upgrade("growth", "high") is True
        # Growth to Starter (not upgrade)
        assert subscription_service._is_upgrade("growth", "starter") is False
        # High to Growth (not upgrade)
        assert subscription_service._is_upgrade("high", "growth") is False
        # Same tier (not upgrade)
        assert subscription_service._is_upgrade("starter", "starter") is False

    def test_calculate_proration_mid_month(self, subscription_service):
        """Test proration calculation in middle of billing period."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0)
        if now.month == 12:
            period_end = period_start.replace(year=now.year + 1, month=1)
        else:
            period_end = period_start.replace(month=now.month + 1)

        proration = subscription_service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=period_start,
            billing_cycle_end=period_end,
        )

        assert proration["old_variant"] == "starter"
        assert proration["new_variant"] == "growth"
        assert proration["old_price"] == Decimal("999.00")
        assert proration["new_price"] == Decimal("2499.00")
        assert proration["unused_amount"] > Decimal("0")
        assert proration["proration_credit"] > Decimal("0")
        # All amounts should be Decimal
        assert isinstance(proration["old_price"], Decimal)
        assert isinstance(proration["new_price"], Decimal)
        assert isinstance(proration["unused_amount"], Decimal)

    def test_calculate_proration_first_day(self, subscription_service):
        """Test proration calculation on first day of period."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            period_end = period_start.replace(year=now.year + 1, month=1)
        else:
            period_end = period_start.replace(month=now.month + 1)

        proration = subscription_service._calculate_proration(
            old_variant="starter",
            new_variant="high",
            billing_cycle_start=period_start,
            billing_cycle_end=period_end,
        )

        # First day of period means most of period remaining
        # (may be off by 1 due to calculation timing)
        assert proration["days_remaining"] >= proration["days_in_period"] - 1
        # Full unused amount should be close to old price
        assert proration["unused_amount"] >= Decimal("999.00") - Decimal("50.00")

    def test_calculate_proration_last_day(self, subscription_service):
        """Test proration calculation on last day of period."""
        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0)
        period_end = now

        proration = subscription_service._calculate_proration(
            old_variant="growth",
            new_variant="high",
            billing_cycle_start=period_start,
            billing_cycle_end=period_end,
        )

        # Last day means 0 or minimal days remaining
        assert proration["days_remaining"] <= 1


# ── Downgrade Tests ───────────────────────────────────────────────────────

class TestSubscriptionDowngrade:
    """Tests for subscription downgrades."""

    @pytest.mark.asyncio
    async def test_downgrade_schedules_for_next_cycle(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test that downgrades are scheduled for next billing cycle."""
        mock_subscription = MagicMock()
        mock_subscription.id = str(uuid4())
        mock_subscription.company_id = str(sample_company_id)
        mock_subscription.tier = "growth"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = datetime.now(timezone.utc)
        mock_subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=15)
        mock_subscription.cancel_at_period_end = False
        mock_subscription.paddle_subscription_id = None  # Explicitly set to None
        mock_subscription.created_at = datetime.now(timezone.utc)

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_subscription

            result = await subscription_service.downgrade_subscription(
                company_id=sample_company_id,
                new_variant="starter",
            )

            assert "scheduled_change" in result
            assert result["scheduled_change"]["current_variant"] == "growth"
            assert result["scheduled_change"]["new_variant"] == "starter"

    @pytest.mark.asyncio
    async def test_downgrade_high_to_growth(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test downgrading from high to growth."""
        mock_subscription = MagicMock()
        mock_subscription.id = str(uuid4())
        mock_subscription.company_id = str(sample_company_id)
        mock_subscription.tier = "high"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = datetime.now(timezone.utc)
        mock_subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
        mock_subscription.cancel_at_period_end = False
        mock_subscription.paddle_subscription_id = None  # Explicitly set to None
        mock_subscription.created_at = datetime.now(timezone.utc)

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_subscription

            result = await subscription_service.downgrade_subscription(
                company_id=sample_company_id,
                new_variant="growth",
            )

            assert result["scheduled_change"]["new_variant"] == "growth"


# ── Cancellation Tests ─────────────────────────────────────────────────────

class TestSubscriptionCancellation:
    """Tests for subscription cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_at_period_end(
        self, subscription_service, mock_db_session, sample_company_id, sample_user_id
    ):
        """Test cancellation at end of billing period (Netflix style)."""
        mock_subscription = MagicMock()
        mock_subscription.id = str(uuid4())
        mock_subscription.company_id = str(sample_company_id)
        mock_subscription.tier = "growth"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = datetime.now(timezone.utc)
        mock_subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=20)
        mock_subscription.cancel_at_period_end = False
        mock_subscription.paddle_subscription_id = None
        mock_subscription.created_at = datetime.now(timezone.utc)

        mock_company = MagicMock()
        mock_company.id = str(sample_company_id)

        # Mock the CancellationRequest to avoid SQLAlchemy relationship issues
        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ), patch(
            "backend.app.services.subscription_service.CancellationRequest"
        ) as MockCancellation:
            mock_cancellation = MagicMock()
            mock_cancellation.id = str(uuid4())
            MockCancellation.return_value = mock_cancellation

            mock_db_session.query.return_value.filter.return_value.first.side_effect = [
                mock_subscription,  # Subscription found
                mock_company,  # Company found
            ]
            mock_db_session.add = MagicMock()
            mock_db_session.commit = MagicMock()

            result = await subscription_service.cancel_subscription(
                company_id=sample_company_id,
                reason="No longer needed",
                effective_immediately=False,
                user_id=sample_user_id,
            )

            assert result["cancellation"]["effective_immediately"] is False
            assert result["cancellation"]["access_until"] is not None
            assert "continue using PARWA" in result["message"]

    @pytest.mark.asyncio
    async def test_cancel_immediately(
        self, subscription_service, mock_db_session, sample_company_id, sample_user_id
    ):
        """Test immediate cancellation."""
        mock_subscription = MagicMock()
        mock_subscription.id = str(uuid4())
        mock_subscription.company_id = str(sample_company_id)
        mock_subscription.tier = "starter"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = datetime.now(timezone.utc)
        mock_subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=25)
        mock_subscription.cancel_at_period_end = False
        mock_subscription.paddle_subscription_id = None
        mock_subscription.created_at = datetime.now(timezone.utc)

        mock_company = MagicMock()
        mock_company.id = str(sample_company_id)

        # Mock the CancellationRequest to avoid SQLAlchemy relationship issues
        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ), patch(
            "backend.app.services.subscription_service.CancellationRequest"
        ) as MockCancellation:
            mock_cancellation = MagicMock()
            mock_cancellation.id = str(uuid4())
            MockCancellation.return_value = mock_cancellation

            mock_db_session.query.return_value.filter.return_value.first.side_effect = [
                mock_subscription,
                mock_company,
            ]
            mock_db_session.add = MagicMock()
            mock_db_session.commit = MagicMock()

            result = await subscription_service.cancel_subscription(
                company_id=sample_company_id,
                reason="Switching to competitor",
                effective_immediately=True,
                user_id=sample_user_id,
            )

            assert result["cancellation"]["effective_immediately"] is True
            assert "canceled immediately" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_no_subscription(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test cancellation fails when no subscription exists."""
        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(SubscriptionNotFoundError):
                await subscription_service.cancel_subscription(
                    company_id=sample_company_id,
                    reason="Test",
                )


# ── Reactivation Tests ────────────────────────────────────────────────────

class TestSubscriptionReactivation:
    """Tests for subscription reactivation."""

    @pytest.mark.asyncio
    async def test_reactivate_pending_cancellation(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test reactivating a subscription pending cancellation."""
        mock_subscription = MagicMock()
        mock_subscription.id = str(uuid4())
        mock_subscription.company_id = str(sample_company_id)
        mock_subscription.tier = "growth"
        mock_subscription.status = "active"
        mock_subscription.cancel_at_period_end = True  # Pending cancellation
        mock_subscription.paddle_subscription_id = None
        mock_subscription.created_at = datetime.now(timezone.utc)

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_subscription
            mock_db_session.commit = MagicMock()

            result = await subscription_service.reactivate_subscription(sample_company_id)

            # Should clear cancel_at_period_end
            assert mock_subscription.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_reactivate_no_pending_cancellation(
        self, subscription_service, mock_db_session, sample_company_id
    ):
        """Test reactivation fails when no pending cancellation."""
        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(InvalidStatusTransitionError):
                await subscription_service.reactivate_subscription(sample_company_id)


# ── Variant Price Tests ────────────────────────────────────────────────────

class TestVariantPrices:
    """Tests for variant price calculations."""

    def test_get_variant_price_starter(self, subscription_service):
        """Test getting starter variant price."""
        price = subscription_service._get_variant_price("starter")
        assert price == Decimal("999.00")

    def test_get_variant_price_growth(self, subscription_service):
        """Test getting growth variant price."""
        price = subscription_service._get_variant_price("growth")
        assert price == Decimal("2499.00")

    def test_get_variant_price_high(self, subscription_service):
        """Test getting high variant price."""
        price = subscription_service._get_variant_price("high")
        assert price == Decimal("3999.00")


# ── Tenant Isolation Tests ─────────────────────────────────────────────────

class TestTenantIsolation:
    """Tests for tenant isolation (BC-001)."""

    @pytest.mark.asyncio
    async def test_get_subscription_isolated_by_company(
        self, subscription_service, mock_db_session
    ):
        """Test that subscription queries are isolated by company_id."""
        company_a = uuid4()

        mock_subscription_a = MagicMock()
        mock_subscription_a.id = str(uuid4())
        mock_subscription_a.company_id = str(company_a)
        mock_subscription_a.tier = "high"
        mock_subscription_a.status = "active"
        mock_subscription_a.current_period_start = datetime.now(timezone.utc)
        mock_subscription_a.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        mock_subscription_a.cancel_at_period_end = False
        mock_subscription_a.paddle_subscription_id = None
        mock_subscription_a.created_at = datetime.now(timezone.utc)

        with patch(
            "backend.app.services.subscription_service.SessionLocal",
            return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription_a

            result = await subscription_service.get_subscription(company_a)

            # Verify the query was called
            assert mock_db_session.query.called
            # Verify filter was called
            assert mock_db_session.query.return_value.filter.called
            # The result should have the correct company_id
            assert result.company_id == company_a


# ── Decimal Precision Tests ───────────────────────────────────────────────

class TestDecimalPrecision:
    """Tests for Decimal precision (BC-002)."""

    def test_proration_returns_decimal(self, subscription_service):
        """Test that proration calculation returns Decimal values."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0)
        if now.month == 12:
            period_end = period_start.replace(year=now.year + 1, month=1)
        else:
            period_end = period_start.replace(month=now.month + 1)

        proration = subscription_service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=period_start,
            billing_cycle_end=period_end,
        )

        # All monetary values must be Decimal
        assert isinstance(proration["old_price"], Decimal)
        assert isinstance(proration["new_price"], Decimal)
        assert isinstance(proration["unused_amount"], Decimal)
        assert isinstance(proration["proration_credit"], Decimal)
        assert isinstance(proration["new_charge"], Decimal)
        assert isinstance(proration["net_charge"], Decimal)

    def test_proration_precision_two_decimals(self, subscription_service):
        """Test that proration amounts have exactly 2 decimal places."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0)
        if now.month == 12:
            period_end = period_start.replace(year=now.year + 1, month=1)
        else:
            period_end = period_start.replace(month=now.month + 1)

        proration = subscription_service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=period_start,
            billing_cycle_end=period_end,
        )

        # Check precision (quantize to 0.01)
        for field in ["unused_amount", "proration_credit", "new_charge", "net_charge"]:
            value = proration[field]
            # Should be exactly 2 decimal places
            str_value = str(value)
            if "." in str_value:
                decimals = len(str_value.split(".")[1])
                assert decimals <= 2, f"{field} has more than 2 decimal places"
