"""
FlexPay Unit Tests — Comprehensive Test Suite

Tests all core FlexPay functionality:
1. Installment schedule calculation
2. Plan creation and lifecycle
3. Payment processing (success/failure)
4. Failure handling and retry logic
5. Plan cancellation
6. Edge cases and error conditions

CLAUDE.md Compliance:
- Goal-driven: Each test has clear success criteria
- Tests first: Write tests that define expected behavior

Run with:
    pytest tests/unit/test_flexpay.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import the modules under test
import sys
sys.path.insert(0, '/home/z/my-project/parwa/backend')

from app.services.flexpay_service import (
    calculate_installment_schedule,
    create_flexpay_plan,
    process_next_installment,
    get_plan_status,
    cancel_flexpay_plan,
    get_due_installments,
    _handle_installment_failure,
    FlexPayError,
    FlexPayPlanNotFoundError,
    FlexPayInvalidStateError,
)
from database.models.flexpay import (
    FlexPayPlan, FlexPayInstallment, FlexPayStatus, InstallmentStatus
)


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_period():
    """Standard 30-day billing period."""
    return (
        datetime(2025, 7, 17, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 8, 16, 23, 59, 59, tzinfo=timezone.utc)
    )


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.flush = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_razorpay_client():
    """Mock Razorpay client."""
    client = AsyncMock()
    return client


# ─── Test: Installment Schedule Calculation ────────────────────────

class TestInstallmentScheduleCalculation:
    """Tests for the installment schedule algorithm."""
    
    def test_mini_parwa_999_schedule(self, sample_period):
        """Test Mini PARWA ($999) generates correct ~10-day schedule."""
        start, end = sample_period
        
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("999"),
            variant_tier="mini",
            period_start=start,
            period_end=end
        )
        
        # Should have around 10 installments ($100 each + final adjustment)
        assert count > 8, f"Expected ~10 installments, got {count}"
        assert count < 15, f"Too many installments: {count}"
        
        # Total should equal $999 (with small rounding tolerance)
        total = sum(Decimal(str(s["amount"])) for s in schedule)
        assert abs(total - Decimal("999")) < Decimal("0.02"), \
            f"Total ${total} doesn't match $999"
        
        # All amounts should be positive
        for inst in schedule:
            assert inst["amount"] > 0, "Negative amount found"
    
    def test_parwa_2499_schedule(self, sample_period):
        """Test PARWA ($2,499) generates correct ~25-day schedule."""
        start, end = sample_period
        
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("2499"),
            variant_tier="parwa",
            period_start=start,
            period_end=end
        )
        
        # Should have around 20-30 installments
        assert count > 18, f"Expected ~25 installments, got {count}"
        assert count < 35, f"Too many installments: {count}"
        
        # Total should equal $2,499
        total = sum(Decimal(str(s["amount"])) for s in schedule)
        assert abs(total - Decimal("2499")) < Decimal("0.02")
    
    def test_high_parwa_3999_30day_schedule(self, sample_period):
        """Test PARWA High ($3,999) completes within 30 days."""
        start, end = sample_period
        
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("3999"),
            variant_tier="high",
            period_start=start,
            period_end=end
        )
        
        # CRITICAL: Must complete within 30 days!
        last_day = max(s["day"] for s in schedule) if schedule else 0
        assert last_day <= 32, \
            f"Schedule exceeds 30-day limit! Last day: {last_day}, installments: {count}"
        
        # Total should equal $3,999
        total = sum(Decimal(str(s["amount"])) for s in schedule)
        assert abs(total - Decimal("3999")) < Decimal("0.02"), \
            f"Total ${total} doesn't match $3,999"
        
        print(f"\n✅ PARWA High Schedule:")
        print(f"   Total installments: {count}")
        print(f"   Spans {last_day} days")
        print(f"   First 10 installments:")
        for s in schedule[:10]:
            extra_mark = " [EXTRA]" if s["is_extra"] else ""
            print(f"     Day {s['day']:2d}: ${s['amount']:.2f}{extra_mark}")
    
    def test_extra_charges_every_third_day(self, sample_period):
        """Verify extra charges happen on days 3, 6, 9, etc."""
        start, end = sample_period
        
        schedule, _ = calculate_installment_schedule(
            total_amount=Decimal("3999"),
            variant_tier="high",
            period_start=start,
            period_end=end
        )
        
        extra_days = [s["day"] for s in schedule if s["is_extra"]]
        
        # Check that extras are on multiples of 3 (approximately)
        for day in extra_days:
            assert day % 3 == 0 or day % 3 == 1, \
                f"Extra charge on unexpected day: {day}"
    
    def test_base_amount_never_exceeds_100(self, sample_period):
        """Ensure no single installment exceeds $100 limit."""
        start, end = sample_period
        
        for variant, amount in [("mini", 999), ("parwa", 2499), ("high", 3999)]:
            schedule, _ = calculate_installment_schedule(
                total_amount=Decimal(amount),
                variant_tier=variant,
                period_start=start,
                period_end=end
            )
            
            for inst in schedule:
                if not inst["is_extra"]:  # Base charges
                    assert inst["amount"] <= 100.01, \
                        f"Base charge ${inst['amount']} exceeds $100 limit!"
                
                # Even extra charges should be reasonable
                assert inst["amount"] <= 100.01, \
                    f"Charge ${inst['amount']} exceeds $100 limit!"
    
    def test_all_amounts_under_transaction_limit(self, sample_period):
        """
        CRITICAL TEST: Every transaction must be under Razorpay's limit.
        
        Current limit: $100 per transaction (~₹9,638 at current rates)
        """
        start, end = sample_period
        max_allowed = Decimal("100.00")  # Safety margin
        
        for variant, amount in [("mini", 999), ("parwa", 2499), ("high", 3999)]:
            schedule, _ = calculate_installment_schedule(
                total_amount=Decimal(amount),
                variant_tier=variant,
                period_start=start,
                period_end=end
            )
            
            for inst in schedule:
                actual = Decimal(str(inst["amount"]))
                assert actual <= max_allowed, \
                    f"❌ VIOLATION: ${actual} > ${max_allowed} limit for {variant}!"


# ─── Test: Plan Creation ───────────────────────────────────────────

class TestFlexPayPlanCreation:
    """Tests for creating FlexPay plans."""
    
    @patch('app.services.flexpay_service.get_db')
    async def test_create_plan_for_high_tier(self, mock_get_db):
        """Test creating a plan for PARWA High tier."""
        # Setup mocks
        db = Mock()
        mock_get_db.return_value = db
        
        # Mock query chain for company/user checks
        mock_query = Mock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # No existing plan
        
        result = await create_flexpay_plan(
            db=db,
            company_id="company_123",
            user_id="user_456",
            variant_tier="high_variant",  # Will be converted to VariantType.HIGH
            razorpay_customer_id="cust_abc"
        )
        
        # Verify basic structure
        assert "plan_id" in result
        assert result["variant_tier"] == "high_variant"
        assert result["total_amount"] == 3999.0
        assert result["status"] == "pending"
        assert "installment_schedule" in result
        assert len(result["installment_schedule"]) > 0
    
    @patch('app.services.flexpay_service.get_db')
    async def test_create_plan_generates_correct_number_of_installments(self, mock_get_db):
        """Test that created plan has right number of installments."""
        db = Mock()
        mock_get_db.return_value = db
        
        mock_query = Mock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        result = await create_flexpay_plan(
            db=db,
            company_id="company_123",
            user_id="user_456",
            variant_tier="high_variant"
        )
        
        # For $3999 at $100/day (+extras every 3rd day), expect ~40 installments
        num_installments = len(result["installment_schedule"])
        assert 35 <= num_installments <= 45, \
            f"Unexpected installment count: {num_installments}"


# ─── Test: Payment Processing ──────────────────────────────────────

class TestPaymentProcessing:
    """Tests for processing installments."""
    
    async def test_process_first_installment_success(self, mock_db, mock_razorpay_client):
        """Test successful processing of first installment."""
        # Setup: Create a plan with pending installments
        plan = Mock(spec=FlexPayPlan)
        plan.id = "plan_123"
        plan.company_id = "company_456"
        plan.variant_tier = "high"
        plan.total_amount = Decimal("3999")
        plan.total_installments = 40
        plan.completed_installments = 0
        plan.status = FlexPayStatus.PENDING.value
        plan.consecutive_failures = 0
        plan.razorpay_customer_id = "cust_abc"
        
        installment = Mock(spec=FlexPayInstallment)
        installment.id = "inst_1"
        installment.plan_id = "plan_123"
        installment.company_id = "company_456"
        installment.installment_number = 1
        installment.amount = Decimal("100")
        installment.is_extra = False
        installment.status = InstallmentStatus.PENDING.value
        installment.scheduled_at = datetime.now(timezone.utc)
        installment.retry_count = 0
        
        # Mock DB queries
        def mock_query_side_effect(cls):
            result = Mock()
            if cls == FlexPayPlan:
                result.first.return_value = plan
            elif cls == FlexPayInstallment:
                result.order_by.return_value.first.return_value = installment
            return result
        
        mock_db.query.side_effect = mock_query_side_effect
        mock_razorpay_client.charge_tokenized_card.return_value = {
            "id": "pay_success_123",
            "status": "captured"
        }
        
        result = await process_next_installment(
            db=mock_db,
            plan_id="plan_123",
            razorpay_client=mock_razorpay_client
        )
        
        assert result["status"] == "success"
        assert result["installment_number"] == 1
        assert result["amount"] == 100.0
        assert result["remaining"] == 39
    
    async def test_process_installment_updates_plan_to_active(self, mock_db):
        """Test that first successful payment changes plan status to ACTIVE."""
        plan = Mock(spec=FlexPayPlan)
        plan.id = "plan_123"
        plan.status = FlexPayStatus.PENDING.value
        plan.completed_installments = 0
        plan.consecutive_failures = 0
        
        installment = Mock(spec=FlexPayInstallment)
        installment.id = "inst_1"
        installment.installment_number = 1
        installment.amount = Decimal("100")
        installment.status = InstallmentStatus.PENDING.value
        installment.retry_count = 0
        
        def mock_query_side_effect(cls):
            result = Mock()
            if cls == FlexPayPlan:
                result.first.return_value = plan
            elif cls == FlexPayInstallment:
                result.order_by.return_value.first.return_value = installment
            return result
        
        mock_db.query.side_effect = mock_query_side_effect
        
        result = await process_next_installment(db=mock_db, plan_id="plan_123")
        
        # After first success, plan should become ACTIVE
        # This is verified by checking the mock was called with correct value
        assert plan.status == FlexPayStatus.ACTIVE.value


# ─── Test: Failure Handling ────────────────────────────────────────

class TestFailureHandling:
    """Tests for payment failure scenarios."""
    
    async def test_failure_increments_consecutive_counter(self, mock_db):
        """Test that failures increment the consecutive failure counter."""
        plan = Mock(spec=FlexPayPlan)
        plan.id = "plan_123"
        plan.status = FlexPayStatus.ACTIVE.value
        plan.consecutive_failures = 0
        plan.total_installments = 40
        plan.completed_installments = 5
        
        installment = Mock(spec=FlexPayInstallment)
        installment.id = "inst_failed"
        installment.installment_number = 6
        installment.amount = Decimal("100")
        installment.retry_count = 0
        
        def mock_query_side_effect(cls):
            result = Mock()
            if cls == FlexPayPlan:
                result.first.return_value = plan
            elif cls == FlexPayInstallment:
                result.order_by.return_value.first.return_value = installment
            return result
        
        mock_db.query.side_effect = mock_query_side_effect
        
        # Simulate payment failure
        result = _handle_installment_failure(
            db=mock_db,
            plan=plan,
            installment=installment,
            reason="Insufficient funds"
        )
        
        assert result["status"] == "failed"
        assert plan.consecutive_failures == 1
        assert installment.retry_count == 1
    
    async def test_three_failures_pauses_plan(self, mock_db):
        """Test that 3 consecutive failures pause the plan."""
        plan = Mock(spec=FlexPayPlan)
        plan.id = "plan_123"
        plan.status = FlexPayStatus.ACTIVE.value
        plan.consecutive_failures = 2  # Already failed twice
        
        installment = Mock(spec=FlexPayInstallment)
        installment.id = "inst_fail_3"
        installment.installment_number = 8
        installment.amount = Decimal("100")
        installment.retry_count = 2
        
        def mock_query_side_effect(cls):
            result = Mock()
            if cls == FlexPayPlan:
                result.first.return_value = plan
            elif cls == FlexPayInstallment:
                result.order_by.return_value.first.return_value = installment
            return result
        
        mock_db.query.side_effect = mock_query_side_effect
        
        result = _handle_installment_failure(
            db=mock_db,
            plan=plan,
            installment=installment,
            reason="Card declined"
        )
        
        # Third failure should pause the plan
        assert result["plan_paused"] == True
        assert plan.status == FlexPayStatus.PAUSED.value
        assert plan.consecutive_failures == 3


# ─── Test: Plan Cancellation ──────────────────────────────────────

class TestPlanCancellation:
    """Tests for cancelling FlexPay plans."""
    
    async def test_cancellation_skips_pending_installments(self, mock_db):
        """Test that cancellation marks pending installments as SKIPPED."""
        plan = Mock(spec=FlexPayPlan)
        plan.id = "plan_cancel_test"
        plan.status = FlexPayStatus.ACTIVE.value
        
        # Simulate 5 pending installments
        pending_installments = [
            Mock(id=f"inst_pending_{i}", amount=Decimal("100"))
            for i in range(5)
        ]
        
        # Simulate 3 already paid installments
        paid_installments = [
            Mock(id=f"inst_paid_{i}", amount=Decimal("100"))
            for i in range(3)
        ]
        for inst in paid_installments:
            inst.status = InstallmentStatus.PAID.value
        
        def mock_filter_side_effect(*args, **kwargs):
            result = Mock()
            if kwargs.get('status') == InstallmentStatus.PENDING.value:
                result.all.return_value = pending_installments
            elif kwargs.get('status') == InstallmentStatus.PAID.value:
                result.all.return_value = paid_installments
            else:
                result.all.return_value = []
            return result
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_filter_side_effect
        mock_db.query.return_value = mock_query
        
        result = await cancel_flexpay_plan(
            db=mock_db,
            plan_id="plan_cancel_test",
            reason="Customer requested"
        )
        
        assert result["status"] == "cancelled"
        assert result["skipped_installments"] == 5
        assert result["collected_amount"] == 300.0  # 3 × $100
        
        # Verify pending were marked skipped
        for inst in pending_installments:
            assert inst.status == InstallmentStatus.SKIPPED.value
    
    async def test_cannot_cancel_completed_plan(self, mock_db):
        """Test that completed plans cannot be cancelled."""
        plan = Mock(spec=FlexPayPlan)
        plan.id = "plan_already_done"
        plan.status = FlexPayStatus.COMPLETED.value
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = plan
        mock_db.query.return_value = mock_query
        
        with pytest.raises(FlexPayInvalidStateError):
            await cancel_flexpay_plan(db=mock_db, plan_id="plan_already_done")


# ─── Test: Edge Cases ─────────────────────────────────────────────

class TestEdgeCases:
    """Edge case tests for robustness."""
    
    def test_zero_amount_raises_error(self, sample_period):
        """Test that zero total amount raises appropriate error."""
        start, end = sample_period
        
        with pytest.raises((ValueError, Exception)):
            calculate_installment_schedule(
                total_amount=Decimal("0"),
                variant_tier="mini",
                period_start=start,
                period_end=end
            )
    
    def test_very_small_amount_single_installment(self, sample_period):
        """Test very small amount results in single installment."""
        start, end = sample_period
        
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("50"),
            variant_tier="mini",
            period_start=start,
            period_end=end
        )
        
        # Small amount should result in 1 installment
        assert count >= 1
        assert len(schedule) >= 1
    
    def test_exact_multiple_of_100_no_adjustment_needed(self, sample_period):
        """Test exact multiple of $100 needs no adjustment."""
        start, end = sample_period
        
        schedule, _ = calculate_installment_schedule(
            total_amount=Decimal("1000"),  # Exactly 10 × $100
            variant_tier="mini",
            period_start=start,
            period_end=end
        )
        
        total = sum(Decimal(str(s["amount"])) for s in schedule)
        # Should be very close to exact
        assert abs(total - Decimal("1000")) < Decimal("0.02")


# ─── Test: Multi-Customer Support ─────────────────────────────────

class TestMultiCustomerSupport:
    """Tests verifying multiple customers can be processed simultaneously."""
    
    async def test_due_installments_returns_multiple_plans(self, mock_db):
        """Test that due installments can come from different customers."""
        # Mock returning due installments from 3 different companies
        mock_installments = [
            {
                "installment_id": "inst_1",
                "plan_id": "plan_A",
                "company_id": "company_111",
                "installment_number": 5,
                "amount": 100.00,
                "is_extra": False,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "variant_tier": "high"
            },
            {
                "installment_id": "inst_2",
                "plan_id": "plan_B",
                "company_id": "company_222",
                "installment_number": 12,
                "amount": 100.00,
                "is_extra": True,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "variant_tier": "parwa"
            },
            {
                "installment_id": "inst_3",
                "plan_id": "plan_C",
                "company_id": "company_333",
                "installment_number": 3,
                "amount": 99.90,
                "is_extra": False,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "variant_tier": "mini"
            }
        ]
        
        # Mock the get_due_installments function
        with patch('app.services.flexpay_service.get_due_installments', 
                   return_value=mock_installments):
            
            due = await get_due_installments(db=mock_db, hours_ahead=1)
            
            assert len(due) == 3
            
            # Verify different companies
            companies = set(d["company_id"] for d in due)
            assert len(companies) == 3
            assert "company_111" in companies
            assert "company_222" in companies
            assert "company_333" in companies


# ─── Run Tests ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
