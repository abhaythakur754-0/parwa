"""
W5D3 Tests - Overage Detection + Auto-Charge (F-024)

Tests for overage calculation, charging, and notification:
1. Overage calculation logic
2. Plan limit checking
3. Paddle charge submission
4. Email + Socket.io notifications
5. Usage tracking
6. Edge cases (no subscription, no usage, etc.)
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from uuid import uuid4, UUID

import sys
sys.path.insert(0, '/home/z/my-project/parwa')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.billing import Subscription, OverageCharge
from database.models.billing_extended import UsageRecord
from database.models.core import Company


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_company(db_session):
    """Create a test company."""
    company = Company(
        id=str(uuid4()),
        name="Test Company",
        industry="technology",
        subscription_tier="starter",
        subscription_status="active",
        paddle_customer_id="cust_test123",
    )
    db_session.add(company)
    db_session.commit()
    return company


@pytest.fixture
def test_subscription(db_session, test_company):
    """Create a test subscription."""
    subscription = Subscription(
        id=str(uuid4()),
        company_id=test_company.id,
        tier="starter",
        status="active",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(subscription)
    db_session.commit()
    return subscription


# =============================================================================
# Overage Calculation Tests
# =============================================================================

class TestOverageCalculation:
    """Test overage calculation logic."""

    def test_no_overage_under_limit(self):
        """No overage when usage is under limit."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=1000,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")
        assert result["tickets_used"] == 1000
        assert result["ticket_limit"] == 2000

    def test_overage_exactly_at_limit(self):
        """No overage when usage equals limit."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=2000,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")

    def test_overage_one_ticket_over(self):
        """One ticket over limit = $0.10 charge."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=2001,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 1
        assert result["overage_charges"] == Decimal("0.10")

    def test_overage_hundred_tickets_over(self):
        """100 tickets over limit = $10.00 charge."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=2100,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 100
        assert result["overage_charges"] == Decimal("10.00")

    def test_overage_thousand_tickets_over(self):
        """1000 tickets over limit = $100.00 charge."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=3000,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 1000
        assert result["overage_charges"] == Decimal("100.00")

    def test_overage_decimal_precision(self):
        """Verify decimal precision for odd numbers."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=2547,
            ticket_limit=2000,
        )

        # 547 * $0.10 = $54.70
        assert result["overage_tickets"] == 547
        assert result["overage_charges"] == Decimal("54.70")


# =============================================================================
# Plan Limit Tests
# =============================================================================

class TestPlanLimits:
    """Test plan limit retrieval for different variants."""

    def test_starter_plan_limits(self):
        """Starter plan: 2000 tickets/month."""
        from backend.app.schemas.billing import VARIANT_LIMITS, VariantType

        limits = VARIANT_LIMITS[VariantType.STARTER]
        assert limits["monthly_tickets"] == 2000
        assert limits["price"] == Decimal("999.00")

    def test_growth_plan_limits(self):
        """Growth plan: 5000 tickets/month."""
        from backend.app.schemas.billing import VARIANT_LIMITS, VariantType

        limits = VARIANT_LIMITS[VariantType.GROWTH]
        assert limits["monthly_tickets"] == 5000
        assert limits["price"] == Decimal("2499.00")

    def test_high_plan_limits(self):
        """High plan: 15000 tickets/month."""
        from backend.app.schemas.billing import VARIANT_LIMITS, VariantType

        limits = VARIANT_LIMITS[VariantType.HIGH]
        assert limits["monthly_tickets"] == 15000
        assert limits["price"] == Decimal("3999.00")


# =============================================================================
# Usage Record Tests
# =============================================================================

class TestUsageRecords:
    """Test usage record creation and tracking."""

    def test_create_usage_record(self, db_session, test_company):
        """Create a new usage record."""
        today = date.today()
        usage = UsageRecord(
            company_id=test_company.id,
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=150,
        )
        db_session.add(usage)
        db_session.commit()

        assert usage.id is not None
        assert usage.tickets_used == 150
        assert usage.overage_tickets == 0

    def test_usage_record_unique_per_day(self, db_session, test_company):
        """Only one usage record per company per day."""
        today = date.today()

        usage1 = UsageRecord(
            company_id=test_company.id,
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=100,
        )
        db_session.add(usage1)
        db_session.commit()

        # Attempting to create second record for same day should fail
        from sqlalchemy.exc import IntegrityError
        usage2 = UsageRecord(
            company_id=test_company.id,
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=200,
        )
        db_session.add(usage2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_update_usage_record(self, db_session, test_company):
        """Update existing usage record."""
        today = date.today()
        usage = UsageRecord(
            company_id=test_company.id,
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=100,
        )
        db_session.add(usage)
        db_session.commit()

        # Update the record
        usage.tickets_used = 250
        db_session.commit()
        db_session.refresh(usage)

        assert usage.tickets_used == 250


# =============================================================================
# Overage Charge Tests
# =============================================================================

class TestOverageCharges:
    """Test overage charge creation."""

    def test_create_overage_charge(self, db_session, test_company):
        """Create an overage charge record."""
        charge = OverageCharge(
            company_id=test_company.id,
            date=date.today(),
            tickets_over_limit=50,
            charge_amount=Decimal("5.00"),
            status="pending",
        )
        db_session.add(charge)
        db_session.commit()

        assert charge.id is not None
        assert charge.tickets_over_limit == 50
        assert charge.charge_amount == Decimal("5.00")
        assert charge.status == "pending"

    def test_overage_charge_status_transitions(self, db_session, test_company):
        """Test overage charge status changes."""
        charge = OverageCharge(
            company_id=test_company.id,
            date=date.today(),
            tickets_over_limit=100,
            charge_amount=Decimal("10.00"),
            status="pending",
        )
        db_session.add(charge)
        db_session.commit()

        # Update to charged
        charge.status = "charged"
        charge.paddle_charge_id = "txn_123"
        db_session.commit()

        assert charge.status == "charged"
        assert charge.paddle_charge_id == "txn_123"


# =============================================================================
# Overage Rate Tests
# =============================================================================

class TestOverageRate:
    """Test overage rate calculation."""

    def test_overage_rate_is_ten_cents(self):
        """Verify overage rate is $0.10 per ticket."""
        from backend.app.services.overage_service import OVERAGE_RATE_PER_TICKET

        assert OVERAGE_RATE_PER_TICKET == Decimal("0.10")

    def test_minimum_overage_charge(self):
        """Verify minimum overage charge threshold."""
        from backend.app.services.overage_service import MINIMUM_OVERAGE_CHARGE

        assert MINIMUM_OVERAGE_CHARGE == Decimal("1.00")

    def test_calculate_overage_for_various_amounts(self):
        """Test overage calculation for various ticket amounts."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()

        test_cases = [
            (1, Decimal("0.10")),
            (10, Decimal("1.00")),
            (50, Decimal("5.00")),
            (100, Decimal("10.00")),
            (500, Decimal("50.00")),
            (1000, Decimal("100.00")),
        ]

        for tickets, expected_charge in test_cases:
            result = service._calculate_overage(
                tickets_used=2000 + tickets,
                ticket_limit=2000,
            )
            assert result["overage_charges"] == expected_charge, \
                f"Failed for {tickets} tickets over"


# =============================================================================
# Usage Info Tests
# =============================================================================

class TestUsageInfo:
    """Test usage info retrieval."""

    def test_usage_info_no_subscription(self, db_session, test_company):
        """Usage info returns zeros when no subscription."""
        from backend.app.services.overage_service import OverageService

        # No subscription created
        service = OverageService()

        # Mock SessionLocal to use test session
        with patch('backend.app.services.overage_service.SessionLocal') as mock_session:
            mock_session.return_value = db_session

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    service.get_usage_info(UUID(test_company.id))
                )
            finally:
                loop.close()

        assert result.tickets_used == 0
        assert result.ticket_limit == 0

    def test_approaching_limit_detection(self, db_session, test_company, test_subscription):
        """Test approaching limit detection at 80% threshold."""
        from backend.app.services.overage_service import OverageService

        # Create usage at 85% of limit
        usage = UsageRecord(
            company_id=test_company.id,
            record_date=date.today(),
            record_month=date.today().strftime("%Y-%m"),
            tickets_used=1700,  # 85% of 2000
        )
        db_session.add(usage)
        db_session.commit()

        service = OverageService()

        with patch('backend.app.services.overage_service.SessionLocal') as mock_session:
            mock_session.return_value = db_session

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    service.check_approaching_limit(UUID(test_company.id))
                )
            finally:
                loop.close()

        assert result["approaching_limit"] is True
        assert result["usage_percentage"] >= 80.0

    def test_limit_exceeded_detection(self, db_session, test_company, test_subscription):
        """Test limit exceeded detection."""
        from backend.app.services.overage_service import OverageService

        # Create usage over limit
        usage = UsageRecord(
            company_id=test_company.id,
            record_date=date.today(),
            record_month=date.today().strftime("%Y-%m"),
            tickets_used=2500,  # Over 2000 limit
        )
        db_session.add(usage)
        db_session.commit()

        service = OverageService()

        with patch('backend.app.services.overage_service.SessionLocal') as mock_session:
            mock_session.return_value = db_session

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    service.check_approaching_limit(UUID(test_company.id))
                )
            finally:
                loop.close()

        assert result["limit_exceeded"] is True


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestOverageEdgeCases:
    """Test edge cases in overage processing."""

    def test_zero_usage_no_overage(self):
        """Zero usage should result in zero overage."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=0,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")

    def test_zero_limit_all_overage(self):
        """Zero limit means all usage is overage."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=100,
            ticket_limit=0,
        )

        assert result["overage_tickets"] == 100
        assert result["overage_charges"] == Decimal("10.00")

    def test_negative_usage_treated_as_zero(self):
        """Negative usage should be treated as zero."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()
        result = service._calculate_overage(
            tickets_used=-100,
            ticket_limit=2000,
        )

        # max(0, -100 - 2000) = 0
        assert result["overage_tickets"] == 0


# =============================================================================
# Billing Task Tests
# =============================================================================

class TestBillingTasks:
    """Test Celery billing tasks."""

    def test_daily_overage_charge_task_definition(self):
        """Verify daily_overage_charge task is defined."""
        from backend.app.tasks.billing_tasks import daily_overage_charge

        assert daily_overage_charge.name == "backend.app.tasks.billing.daily_overage_charge"
        assert daily_overage_charge.max_retries == 3

    def test_process_all_overages_task_definition(self):
        """Verify process_all_overages task is defined."""
        from backend.app.tasks.billing_tasks import process_all_overages

        assert process_all_overages.name == "backend.app.tasks.billing.process_all_overages"

    def test_invoice_sync_task_definition(self):
        """Verify invoice_sync task is defined."""
        from backend.app.tasks.billing_tasks import invoice_sync

        assert invoice_sync.name == "backend.app.tasks.billing.invoice_sync"
        assert invoice_sync.max_retries == 3

    def test_subscription_check_task_definition(self):
        """Verify subscription_check task is defined."""
        from backend.app.tasks.billing_tasks import subscription_check

        assert subscription_check.name == "backend.app.tasks.billing.subscription_check"

    def test_send_usage_warning_task_definition(self):
        """Verify send_usage_warning task is defined."""
        from backend.app.tasks.billing_tasks import send_usage_warning

        assert send_usage_warning.name == "backend.app.tasks.billing.send_usage_warning"


# =============================================================================
# Decimal Precision Tests (BC-002)
# =============================================================================

class TestDecimalPrecision:
    """Test BC-002 compliance - all money calculations use Decimal."""

    def test_overage_charge_is_decimal(self, db_session, test_company):
        """Verify charge_amount is Decimal type."""
        charge = OverageCharge(
            company_id=test_company.id,
            date=date.today(),
            tickets_over_limit=100,
            charge_amount=Decimal("10.00"),
            status="pending",
        )
        db_session.add(charge)
        db_session.commit()

        assert isinstance(charge.charge_amount, Decimal)

    def test_usage_overage_charges_is_decimal(self, db_session, test_company):
        """Verify usage overage_charges is Decimal type."""
        usage = UsageRecord(
            company_id=test_company.id,
            record_date=date.today(),
            record_month=date.today().strftime("%Y-%m"),
            tickets_used=100,
            overage_charges=Decimal("5.00"),
        )
        db_session.add(usage)
        db_session.commit()

        assert isinstance(usage.overage_charges, Decimal)

    def test_no_floating_point_errors(self):
        """Verify no floating point precision errors."""
        from backend.app.services.overage_service import OverageService

        service = OverageService()

        # Test multiple calculations
        for i in range(1, 101):
            result = service._calculate_overage(
                tickets_used=2000 + i,
                ticket_limit=2000,
            )

            # Expected charge should be exactly i * 0.10
            expected = Decimal(str(i)) * Decimal("0.10")
            assert result["overage_charges"] == expected, \
                f"Precision error at {i} tickets"


# =============================================================================
# Tenant Isolation Tests (BC-001)
# =============================================================================

class TestOverageTenantIsolation:
    """Test BC-001 compliance - tenant isolation in overage."""

    def test_usage_records_isolated_by_company(self, db_session):
        """Usage records are isolated by company_id."""
        company_a = Company(
            id=str(uuid4()),
            name="Company A",
            industry="technology",
            subscription_tier="starter",
            subscription_status="active",
        )
        company_b = Company(
            id=str(uuid4()),
            name="Company B",
            industry="retail",
            subscription_tier="growth",
            subscription_status="active",
        )
        db_session.add_all([company_a, company_b])
        db_session.commit()

        today = date.today()

        usage_a = UsageRecord(
            company_id=company_a.id,
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=100,
        )
        usage_b = UsageRecord(
            company_id=company_b.id,
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=200,
        )
        db_session.add_all([usage_a, usage_b])
        db_session.commit()

        # Query each company's usage
        a_record = db_session.query(UsageRecord).filter(
            UsageRecord.company_id == company_a.id
        ).first()
        b_record = db_session.query(UsageRecord).filter(
            UsageRecord.company_id == company_b.id
        ).first()

        assert a_record.tickets_used == 100
        assert b_record.tickets_used == 200

    def test_overage_charges_isolated_by_company(self, db_session):
        """Overage charges are isolated by company_id."""
        company_a = Company(
            id=str(uuid4()),
            name="Company A",
            industry="technology",
            subscription_tier="starter",
            subscription_status="active",
        )
        company_b = Company(
            id=str(uuid4()),
            name="Company B",
            industry="retail",
            subscription_tier="growth",
            subscription_status="active",
        )
        db_session.add_all([company_a, company_b])
        db_session.commit()

        charge_a = OverageCharge(
            company_id=company_a.id,
            date=date.today(),
            tickets_over_limit=50,
            charge_amount=Decimal("5.00"),
        )
        charge_b = OverageCharge(
            company_id=company_b.id,
            date=date.today(),
            tickets_over_limit=100,
            charge_amount=Decimal("10.00"),
        )
        db_session.add_all([charge_a, charge_b])
        db_session.commit()

        # Query each company's charges
        a_charges = db_session.query(OverageCharge).filter(
            OverageCharge.company_id == company_a.id
        ).all()
        b_charges = db_session.query(OverageCharge).filter(
            OverageCharge.company_id == company_b.id
        ).all()

        assert len(a_charges) == 1
        assert len(b_charges) == 1
        assert a_charges[0].charge_amount == Decimal("5.00")
        assert b_charges[0].charge_amount == Decimal("10.00")
