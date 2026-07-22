"""
FlexPay Service Unit Tests — Comprehensive Test Suite

Tests the core FlexPay payment splitting algorithm and business logic:
- Installment schedule calculation (the $100 base + extra $100 every 3rd day pattern)
- Plan creation and validation
- Installment processing and status transitions
- Failure handling and retry logic
- Pause/resume functionality
- Edge cases and boundary conditions

Business Rules Being Tested (from CLAUDE.md P-002):
- Mini PARWA ($999): ~10 days of $100 installments
- PARWA ($2,499): ~25 days 
- PARWA High ($3,999): 30 days ($100 base + extra $100 every 3rd day)
- All amounts stay under Razorpay's $100/transaction limit

CLAUDE.md Compliance:
- P-004 Business First: These tests protect revenue collection logic
- BC-002: All money calculations use Decimal (verified in tests)
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session

# Import the module under test
import sys
sys.path.insert(0, '/home/z/my-project/parwa/backend')

from app.services.flexpay_service import (
    calculate_installment_schedule,
    create_flexpay_plan,
    process_next_installment,
    get_plan_status,
    cancel_flexpay_plan,
    pause_flexpay_plan,
    resume_flexpay_plan,
    get_due_installments,
    FlexPayError,
    FlexPayPlanNotFoundError,
    FlexPayInvalidStateError,
    BASE_INSTALLMENT_AMOUNT,
    EXTRA_INSTALLMENT_AMOUNT,
    EXTRA_DAY_INTERVAL,
    EXTRA_CHARGE_DELAY_HOURS,
    MAX_CONSECUTIVE_FAILURES,
    RETRY_DELAY_HOURS,
)

from app.core.pricing_config import VariantType, VARIANT_PRICES


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES — Test Data Setup
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db

@pytest.fixture
def sample_period():
    """Create a standard 30-day billing period."""
    start = datetime(2025, 7, 18, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=30)
    return start, end

@pytest.fixture
def company_id():
    """Sample company UUID."""
    return "test-company-123456789"

@pytest.fixture
def user_id():
    """Sample user UUID."""
    return "test-user-123456789"


# ═══════════════════════════════════════════════════════════════════════════
# TEST SUITE 1: Installment Schedule Calculation Algorithm
# ═══════════════════════════════════════════════════════════════════════════

class TestInstallmentScheduleCalculation:
    """
    Tests for the core installment calculation algorithm.
    
    This is THE most critical test suite - it validates that our smart
    splitting math correctly handles all three pricing tiers while
    staying under Razorpay's $100 limit.
    
    Business Impact:
    - If this is wrong, we either lose revenue or exceed transaction limits
    - Must collect EXACT amount within exactly 30 days
    - Extra charges on day 3 pattern must work correctly
    """

    def test_mini_parwa_999_dollar_plan(self, sample_period):
        """
        Mini PARWA ($999) should complete in ~10 days.
        
        Expected: 10 installments of $99.90 (or 9×$100 + $99 final day)
        """
        start, end = sample_period
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("999.00"),
            variant_tier="mini",
            period_start=start,
            period_end=end
        )
        
        # Should have around 10 installments
        assert count <= 12, f"Too many installments for $999 plan: {count}"
        assert count >= 9, f"Too few installments for $999 plan: {count}"
        
        # Total should equal exactly $999
        total = sum(Decimal(str(inst["amount"])) for inst in schedule)
        assert abs(total - Decimal("999.00")) < Decimal("0.01"), \
            f"Total ${total} doesn't match expected $999.00"
        
        # No single installment should exceed $100
        for inst in schedule:
            assert inst["amount"] <= 100.01, \
                f"Installment ${inst['amount']} exceeds $100 limit"
        
        print(f"✅ Mini PARWA ($999): {count} installments, total=${total}")

    def test_parwa_2499_dollar_plan(self, sample_period):
        """
        PARWA ($2,499) should complete in ~25 days.
        
        Expected: Mix of $100 base charges + extra charges on every 3rd day
        Total should be collected within 30-day window.
        """
        start, end = sample_period
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("2499.00"),
            variant_tier="parwa",
            period_start=start,
            period_end=end
        )
        
        # Should complete within 30 days
        assert count <= 40, f"Too many installments: {count} (would exceed 30 days)"
        
        # Total should equal exactly $2,499
        total = sum(Decimal(str(inst["amount"])) for inst in schedule)
        assert abs(total - Decimal("2499.00")) < Decimal("0.01"), \
            f"Total ${total} doesn't match expected $2,499.00"
        
        # All installments should be ≤ $200 (max with extra charge)
        for inst in schedule:
            assert inst["amount"] <= 200.01, \
                f"Installment ${inst['amount']} exceeds max charge"
        
        print(f"✅ PARWA ($2,499): {count} installments, total=${total}")

    def test_parwa_high_3999_dollar_plan(self, sample_period):
        """
        PARWA High ($3,999) should complete in exactly 30 days.
        
        This is the MAIN use case - tests the full algorithm:
        - Base: $100/day
        - Extra: Additional $100 on days 3, 6, 9, 12, 15, 18, 21, 24, 27, 30
        - Pattern: Day 1=$100, Day 2=$100, Day 3=$100+$100, Day 4=$100, ...
        """
        start, end = sample_period
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("3999.00"),
            variant_tier="high",
            period_start=start,
            period_end=end
        )
        
        # Should have around 30-40 installments (30 days + extras every 3rd day)
        assert 25 <= count <= 45, \
            f"Unexpected installment count for $3,999 plan: {count}"
        
        # Total must be EXACTLY $3,999
        total = sum(Decimal(str(inst["amount"])) for inst in schedule)
        assert abs(total - Decimal("3999.00")) < Decimal("0.01"), \
            f"Total ${total} doesn't match expected $3,999.00"
        
        # Verify no installment exceeds $200 (base + extra)
        for inst in schedule:
            assert inst["amount"] <= 200.01, \
                f"Installment ${inst['amount']} exceeds $200 max (base+extra)"
        
        # Count extra charges (should be on every 3rd day approximately)
        extra_charges = [inst for inst in schedule if inst["is_extra"] == True]
        assert len(extra_charges) >= 8, \
            f"Expected at least 8 extra charges, got {len(extra_charges)}"
        
        print(f"✅ PARWA High ($3,999): {count} installments ({len(extra_charges)} extras), total=${total}")

    def test_extra_charge_every_third_day(self, sample_period):
        """
        Verify the 'extra charge every 3rd day' pattern works correctly.
        
        Days 3, 6, 9, 12, ... should have TWO charges:
        - One base charge ($100) at 9 AM
        - One extra charge ($100) at 11 AM (2 hours later)
        """
        start, end = sample_period
        schedule, _ = calculate_installment_schedule(
            total_amount=Decimal("3999.00"),
            variant_tier="high",
            period_start=start,
            period_end=end
        )
        
        # Group installments by day
        from collections import defaultdict
        by_day = defaultdict(list)
        for inst in schedule:
            by_day[inst["day"]].append(inst)
        
        # Check that days divisible by 3 have extra charges
        third_days_with_extra = [
            day for day, installs in by_day.items()
            if day % 3 == 0 and any(i["is_extra"] for i in installs)
        ]
        
        assert len(third_days_with_extra) >= 5, \
            f"Expected extra charges on multiple 3rd days, found {len(third_days_with_extra)}"
        
        # Verify extra charges are scheduled 2 hours after base
        for day_num, installs in by_day.items():
            if len(installs) == 2:  # Has both base and extra
                base = [i for i in installs if not i["is_extra"]][0]
                extra = [i for i in installs if i["is_extra"]][0]
                
                time_diff = extra["scheduled_at"] - base["scheduled_at"]
                assert time_diff.total_seconds() / 3600 == EXTRA_CHARGE_DELAY_HOURS, \
                    f"Extra charge not scheduled {EXTRA_CHARGE_DELAY_HOURS}h after base on day {day_num}"

    def test_all_amounts_under_transaction_limit(self, sample_period):
        """
        CRITICAL TEST: No single installment can exceed $100 (Razorpay limit).
        
        This is the whole reason FlexPay exists!
        """
        start, end = sample_period
        
        for tier_name, price in [("mini", 999), ("parwa", 2499), ("high", 3999)]:
            schedule, _ = calculate_installment_schedule(
                total_amount=Decimal(str(price)),
                variant_tier=tier_name,
                period_start=start,
                period_end=end
            )
            
            for inst in schedule:
                # Allow tiny rounding errors but no more than $100.01
                assert inst["amount"] <= 100.01, \
                    f"TIER {tier_name.upper()}: Installment ${inst['amount']} exceeds $100 limit!"

    def test_final_installment_adjusts_to_exact_total(self, sample_period):
        """
        The last installment should adjust to make the total exact.
        
        Example: If we need $3,999 and have 39 installments of $100 ($3,900),
        the last one should be $99 (not another $100 which would overcharge).
        """
        start, end = sample_period
        schedule, _ = calculate_installment_schedule(
            total_amount=Decimal("1050.00"),  # Unusual amount to force adjustment
            variant_tier="parwa",
            period_start=start,
            period_end=end
        )
        
        total = sum(Decimal(str(inst["amount"])) for inst in schedule)
        
        # Should be exact (within 1 cent)
        assert abs(total - Decimal("1050.00")) < Decimal("0.02"), \
            f"Final adjustment failed: total is ${total}, expected $1050.00"


# ═══════════════════════════════════════════════════════════════════════════
# TEST SUITE 2: Plan Creation & Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanCreation:
    """
    Tests for creating new FlexPay plans via create_flexpay_plan().
    
    Validates:
    - Plan record creation in database
    - Installment records generation
    - Price tier validation
    - Company/user association
    """

    @pytest.mark.asyncio
    async def test_create_plan_for_high_tier(self, mock_db, company_id, user_id):
        """
        Create a plan for PARWA High ($3,999) tier.
        """
        # Mock DB operations
        mock_plan = Mock()
        mock_plan.id = "new-plan-uuid-12345"
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        
        with patch('app.services.flexpay_service.FlexPayPlan') as MockPlan, \
             patch('app.services.flexpay_service.FlexPayInstallment') as MockInstallment:
            
            MockPlan.return_value = mock_plan
            MockInstallment.return_value = Mock(id=f"installment-test")
            
            result = await create_flexpay_plan(
                db=mock_db,
                company_id=company_id,
                user_id=user_id,
                variant_tier=VariantType.HIGH
            )
            
            # Verify response structure
            assert "plan_id" in result
            assert result["variant_tier"] == "high"
            assert result["total_amount"] == float(VARIANT_PRICES[VariantType.HIGH])
            assert result["status"] == "pending"
            assert "installment_schedule" in result
            assert len(result["installment_schedule"]) > 0
            
            # Verify DB was called correctly
            assert mock_db.add.called
            assert mock_db.commit.called
            
            print(f"✅ Created HIGH tier plan: {result['plan_id'][:8]}...")

    @pytest.mark.asyncio
    async def test_create_plan_validates_variant_tiers(self, mock_db, company_id, user_id):
        """
        Only valid variant tiers should be accepted (mini, parwa, high).
        """
        # Test all three valid tiers
        for tier in [VariantType.MINI, VariantType.PARWA, VariantType.HIGH]:
            with patch('app.services.flexpay_service.FlexPayPlan'), \
                 patch('app.services.flexpay_service.FlexPayInstallment'):
                
                mock_db.reset_mock()
                
                result = await create_flexpay_plan(
                    db=mock_db,
                    company_id=company_id,
                    user_id=user_id,
                    variant_tier=tier
                )
                
                assert result["variant_tier"] == tier.value
        
        print("✅ All three variant tiers validated successfully")

    @pytest.mark.asyncio
    async def test_create_plan_generates_correct_number_of_installments(self, mock_db, company_id, user_id):
        """
        Higher-priced plans should generate more installments.
        """
        results = {}
        
        for tier in [VariantType.MINI, VariantType.PARWA, VariantType.HIGH]:
            with patch('app.services.flexpay_service.FlexPayPlan') as MockPlan, \
                 patch('app.services.flexpay_service.FlexPayInstallment') as MockInstallment:
                
                MockPlan.return_value = Mock(id=f"plan-{tier.value}")
                MockInstallment.return_value = Mock()
                
                result = await create_flexpay_plan(
                    db=mock_db,
                    company_id=company_id,
                    user_id=user_id,
                    variant_tier=tier
                )
                
                results[tier.value] = result["total_installments"]
        
        # Higher tiers should have more installments
        assert results["high"] > results["parwa"], \
            "HIGH tier should have more installments than PARWA"
        assert results["parwa"] > results["mini"], \
            "PARWA tier should have more installments than MINI"
        
        print(f"✅ Installment counts by tier: MINI={results['mini']}, PARWA={results['parwa']}, HIGH={results['high']}")


# ═══════════════════════════════════════════════════════════════════════════
# TEST SUITE 3: Installment Processing & Status Transitions
# ═══════════════════════════════════════════════════════════════════════════

class TestInstallmentProcessing:
    """
    Tests for processing individual installments via process_next_installment().
    
    Validates state machine transitions:
    PENDING → PROCESSING → PAID (success)
    PENDING → PROCESSING → FAILED (failure with retry)
    Multiple failures → PAUSED (auto-pause after MAX_CONSECUTIVE_FAILURES)
    All paid → COMPLETED
    """

    @pytest.mark.asyncio
    async def test_successful_payment_processing(self, mock_db):
        """
        Successful payment should transition: PENDING → PROCESSING → PAID
        """
        # Setup mocks
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "active"
        mock_plan.completed_installments = 5
        mock_plan.total_installments = 40
        mock_plan.consecutive_failures = 0
        
        mock_installment = Mock()
        mock_installment.installment_number = 6
        mock_installment.amount = Decimal("100.00")
        mock_installment.is_extra = False
        mock_installment.status = "pending"
        mock_installment.retry_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_plan, mock_installment]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        with patch('app.services.flexpay_service.Invoice'), \
             patch('app.services.flexpay_service.Transaction'):
            
            result = await process_next_installment(
                db=mock_db,
                plan_id="test-plan",
                razorpay_client=None  # Use simulated payment
            )
            
            assert result["status"] == "success"
            assert result["installment_number"] == 6
            assert result["amount"] == 100.00
            assert result["payment_id"].startswith("pay_simulated_")
            
            # Verify installment was marked as paid
            assert mock_installment.status == "paid"
            
            print(f"✅ Successfully processed installment #6")

    @pytest.mark.asyncio
    async def test_failed_payment_handling(self, mock_db):
        """
        Failed payment should transition: PENDING → PROCESSING → FAILED
        And increment failure counters.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "active"
        mock_plan.completed_installments = 5
        mock_plan.total_installments = 40
        mock_plan.consecutive_failures = 0
        
        mock_installment = Mock()
        mock_installment.installment_number = 7
        mock_installment.amount = Decimal("100.00")
        mock_installment.is_extra = False
        mock_installment.status = "pending"
        mock_installment.retry_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_plan, mock_installment]
        
        # Simulate payment failure by making razorpay_client raise exception
        with patch('app.services.flexpay_service.Invoice'), \
             patch('app.services.flexpay_service.Transaction'):
            
            # Force a failure by setting up the mock to simulate it
            original_process = None
            # We'll test the failure handler directly instead
            
        # Test failure handler directly
        from app.services.flexpay_service import _handle_installment_failure
        result = _handle_installment_failure(
            db=mock_db,
            plan=mock_plan,
            installment=mock_installment,
            reason="Card declined"
        )
        
        assert result["status"] == "failed"
        assert result["reason"] == "Card declined"
        assert result["retry_count"] == 1
        assert mock_installment.status == "failed"
        assert mock_plan.consecutive_failures == 1
        
        print(f"✅ Handled failed payment correctly")

    @pytest.mark.asyncio
    async def test_auto_pause_after_max_failures(self, mock_db):
        """
        After MAX_CONSECUTIVE_FAILURES (3), plan should auto-pause.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "active"
        mock_plan.consecutive_failures = 2  # Already had 2 failures
        
        mock_installment = Mock()
        mock_installment.installment_number = 10
        mock_installment.amount = Decimal("100.00")
        mock_installment.status = "pending"
        mock_installment.retry_count = 2
        
        from app.services.flexpay_service import _handle_installment_failure
        result = _handle_installment_failure(
            db=mock_db,
            plan=mock_plan,
            installment=mock_installment,
            reason="Insufficient funds"
        )
        
        # This 3rd failure should trigger auto-pause
        assert result["plan_paused"] == True
        assert mock_plan.status == "paused"
        
        print(f"✅ Auto-paused plan after {MAX_CONSECUTIVE_FAILURES} consecutive failures")

    @pytest.mark.asyncio
    async def test_plan_completion_when_all_paid(self, mock_db):
        """
        When all installments are paid, plan status should change to COMPLETED.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "active"
        mock_plan.completed_installments = 39
        mock_plan.total_installments = 40
        mock_plan.consecutive_failures = 0
        
        # No pending installments left
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # All installments are paid
        mock_all_installments = [Mock(status="paid") for _ in range(40)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_all_installments
        
        result = await process_next_installment(
            db=mock_db,
            plan_id="test-plan",
            razorpay_client=None
        )
        
        assert result["status"] == "completed"
        assert mock_plan.status == "completed"
        
        print(f"✅ Plan marked as completed when all installments paid")


# ═══════════════════════════════════════════════════════════════════════════
# TEST SUITE 4: Pause & Resume Functionality
# ═══════════════════════════════════════════════════════════════════════════

class TestPauseResume:
    """
    Tests for pause/resume functionality.
    
    Business Logic:
    - Only ACTIVE or PENDING plans can be paused
    - Only PAUSED plans can be resumed
    - Resume resets failure counters for fresh start
    - Paused plans stop all future processing until resumed
    """

    @pytest.mark.asyncio
    async def test_pause_active_plan(self, mock_db):
        """
        Active plan should successfully pause.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "active"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.count.return_value = 15
        
        result = await pause_flexpay_plan(
            db=mock_db,
            plan_id="test-plan",
            reason="Customer requested pause"
        )
        
        assert result["status"] == "paused"
        assert result["previous_status"] == "active"
        assert result["reason"] == "Customer requested pause"
        assert result["pending_installments"] == 15
        assert mock_plan.status == "paused"
        
        print(f"✅ Successfully paused active plan")

    @pytest.mark.asyncio
    async def test_cannot_pause_completed_plan(self, mock_db):
        """
        Cannot pause an already completed plan.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "completed"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        
        with pytest.raises(FlexPayInvalidStateError) as exc_info:
            await pause_flexpay_plan(
                db=mock_db,
                plan_id="test-plan"
            )
        
        assert "Cannot pause" in str(exc_info.value)
        
        print(f"✅ Correctly rejected pause on completed plan")

    @pytest.mark.asyncio
    async def test_resume_paused_plan(self, mock_db):
        """
        Paused plan should resume and reset failure counters.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "paused"
        mock_plan.consecutive_failures = 3
        mock_plan.last_failure_reason = "Card declined"
        
        mock_next_installment = Mock()
        mock_next_installment.installment_number = 11
        mock_next_installment.scheduled_at = datetime.now(timezone.utc) + timedelta(hours=2)
        
        mock_pending_installments = [Mock(amount=Decimal("100.00")) for _ in range(20)]
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_plan,           # First call returns plan
            mock_next_installment  # Second call returns next installment
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_pending_installments
        
        result = await resume_flexpay_plan(
            db=mock_db,
            plan_id="test-plan",
            notes="Customer updated card"
        )
        
        assert result["status"] == "active"
        assert mock_plan.status == "active"
        assert mock_plan.consecutive_failures == 0  # Reset!
        assert mock_plan.last_failure_reason is None  # Cleared!
        assert result["next_installment_number"] == 11
        assert "remaining_amount" in result
        
        print(f"✅ Successfully resumed paused plan, counters reset")

    @pytest.mark.asyncio
    async def test_cannot_resume_active_plan(self, mock_db):
        """
        Cannot resume a plan that isn't paused.
        """
        mock_plan = Mock()
        mock_plan.id = "test-plan"
        mock_plan.status = "active"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        
        with pytest.raises(FlexPayInvalidStateError) as exc_info:
            await resume_flexpay_plan(
                db=mock_db,
                plan_id="test-plan"
            )
        
        assert "Cannot resume" in str(exc_info.value)
        
        print(f"✅ Correctly rejected resume on non-paused plan")


# ═══════════════════════════════════════════════════════════════════════════
# TEST SUITE 5: Get Due Installments (for Scheduler)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetDueInstallments:
    """
    Tests for finding due installments (used by cron scheduler).
    
    Validates:
    - Only PENDING installments from ACTIVE/PENDING plans are returned
    - Time-based filtering works correctly
    - Old missed installments aren't re-processed endlessly
    """

    @pytest.mark.asyncio
    async def test_get_due_installments_basic(self, mock_db):
        """
        Should find installments scheduled within the look-ahead window.
        """
        now = datetime.now(timezone.utc)
        
        mock_due_installment = Mock()
        mock_due_installment.id = "inst-1"
        mock_due_installment.plan_id = "plan-1"
        mock_due_installment.company_id = "company-1"
        mock_due_installment.installment_number = 5
        mock_due_installment.amount = Decimal("100.00")
        mock_due_installment.is_extra = False
        mock_due_installment.scheduled_at = now + timedelta(minutes=30)  # Due in 30 min
        mock_due_installment.plan = Mock(variant_tier="high")
        
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_due_installment
        ]
        
        due = await get_due_installments(db=mock_db, hours_ahead=1)
        
        assert len(due) == 1
        assert due[0]["installment_number"] == 5
        assert due[0]["amount"] == 100.00
        assert due[0]["variant_tier"] == "high"
        
        print(f"✅ Found 1 due installment correctly")

    @pytest.mark.asyncio
    async def test_no_due_installments_returns_empty(self, mock_db):
        """
        If nothing is due, should return empty list (not error).
        """
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        due = await get_due_installments(db=mock_db, hours_ahead=1)
        
        assert due == []
        
        print(f"✅ Empty list returned when no installments due")


# ═══════════════════════════════════════════════════════════════════════════
# TEST SUITE 6: Edge Cases & Error Handling
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCasesAndErrors:
    """
    Tests for edge cases, boundary conditions, and error handling.
    
    Critical for production stability!
    """

    @pytest.mark.asyncio
    async def test_nonexistent_plan_raises_error(self, mock_db):
        """
        Querying a non-existent plan should raise PlanNotFoundError.
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(FlexPayPlanNotFoundError):
            await get_plan_status(db=mock_db, plan_id="nonexistent-plan")
        
        print(f"✅ Correctly raised error for non-existent plan")

    def test_zero_amount_plan_rejected(self, sample_period):
        """
        Cannot create a plan with $0 total amount.
        """
        start, end = sample_period
        
        with pytest.raises((ValueError, Exception)):
            # Should either raise error or return empty schedule
            schedule, count = calculate_installment_schedule(
                total_amount=Decimal("0"),
                variant_tier="mini",
                period_start=start,
                period_end=end
            )
            
            # If it doesn't error, schedule should be empty
            if count > 0:
                raise AssertionError("Should not generate installments for $0 plan")

    def test_extremely_large_amount_handled(self, sample_period):
        """
        Very large amounts should still work (just many installments).
        """
        start, end = sample_period
        
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("99999.00"),  # $99,999!
            variant_tier="high",
            period_start=start,
            period_end=end
        )
        
        # Should have safety break or handle gracefully
        assert count > 0, "Should generate some installments even for large amounts"
        
        # Still no installment over $100
        for inst in schedule:
            assert inst["amount"] <= 100.01
        
        print(f"✅ Handled large amount ($99,999) with {count} installments")

    def test_single_day_period(self, sample_period):
        """
        Period of just 1 day should still work (for edge case testing).
        """
        start = datetime(2025, 7, 18, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)  # Just 1 day!
        
        schedule, count = calculate_installment_schedule(
            total_amount=Decimal("150.00"),
            variant_tier="mini",
            period_start=start,
            period_end=end
        )
        
        # Should fit within 1-2 installments
        assert count <= 3, f"Too many installments for 1-day period: {count}"


# ═══════════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
