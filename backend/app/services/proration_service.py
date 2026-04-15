"""
Proration Service (BG-04)

Handles proration calculations for subscription variant changes:
- Calculate prorated amounts for upgrades
- Apply proration credits
- Maintain audit trail of all proration calculations

Proration Rules (Netflix Style):
- Upgrade: Immediate, prorated credit from old variant applied to new variant
- Downgrade: Effective at NEXT billing cycle (no proration needed)
- Cancel: Access until end of current billing period

Formula (Upgrade only):
- unused_amount = (old_price / days_in_period) * days_remaining
- proration_credit = unused_amount
- new_charge = (new_price / days_in_period) * days_remaining
- net_charge = new_charge - proration_credit

BC-002: All money calculations use Decimal (never float)
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.billing import (
    ProrationResult,
    ProrationAudit as ProrationAuditSchema,
    VariantType,
    VARIANT_LIMITS,
)
from database.base import SessionLocal
from database.models.billing_extended import ProrationAudit

logger = logging.getLogger("parwa.services.proration")


class ProrationError(Exception):
    """Base exception for proration errors."""
    pass


class InvalidProrationPeriodError(ProrationError):
    """Invalid billing period for proration."""
    pass


class ProrationService:
    """
    Proration calculation service for subscription changes.

    Usage:
        service = ProrationService()

        # Calculate upgrade proration
        result = await service.calculate_upgrade_proration(
            company_id=uuid,
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=date(2024, 1, 1),
            billing_cycle_end=date(2024, 2, 1),
        )

        # Apply the proration credit
        await service.apply_proration_credit(company_id, result)
    """

    # Minimum proration amount to charge (avoid tiny charges)
    MINIMUM_CHARGE_AMOUNT = Decimal("0.50")

    # Proration precision (2 decimal places for currency)
    PRECISION = Decimal("0.01")

    def __init__(self):
        pass

    # P3: Always use 30-day divisor for monthly proration
    BILLING_PERIOD_DAYS = 30

    async def calculate_upgrade_proration(
        self,
        company_id: UUID,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: date,
        billing_cycle_end: date,
        reference_date: Optional[date] = None,
        billing_frequency: str = "monthly",
    ) -> ProrationResult:
        """
        Calculate proration for upgrading subscription.

        P3: daily_rate = price / 30 always (30-day divisor) for monthly.
        For yearly, use the actual period days (365/366).

        Args:
            company_id: Company UUID
            old_variant: Current variant
            new_variant: Target variant (must be higher tier)
            billing_cycle_start: Start of current billing period
            billing_cycle_end: End of current billing period
            reference_date: Date to calculate from (default: today)
            billing_frequency: 'monthly' or 'yearly'

        Returns:
            ProrationResult with all calculation details

        Raises:
            InvalidProrationPeriodError: Invalid billing period
        """
        # Validate variants
        old_variant = self._validate_variant(old_variant)
        new_variant = self._validate_variant(new_variant)

        # Validate upgrade direction
        if not self._is_upgrade(old_variant, new_variant):
            raise ProrationError(
                f"calculate_upgrade_proration called for non-upgrade: "
                f"{old_variant} -> {new_variant}"
            )

        # Validate billing period
        self._validate_billing_period(billing_cycle_start, billing_cycle_end)

        # Use provided reference date or today
        if reference_date is None:
            reference_date = datetime.now(timezone.utc).date()

        # Get prices (frequency-aware)
        old_price = self._get_variant_price(old_variant, billing_frequency)
        new_price = self._get_variant_price(new_variant, billing_frequency)

        # P3: For monthly, ALWAYS use 30-day divisor
        if billing_frequency == "monthly":
            days_in_period = self.BILLING_PERIOD_DAYS
        else:
            days_in_period = (billing_cycle_end - billing_cycle_start).days

        days_elapsed = (reference_date - billing_cycle_start).days
        days_remaining = max(days_in_period - days_elapsed, 0)

        # Calculate proration (BC-002: all Decimal)
        daily_rate_old = old_price / Decimal(days_in_period)
        daily_rate_new = new_price / Decimal(days_in_period)

        unused_amount = daily_rate_old * Decimal(days_remaining)
        new_charge = daily_rate_new * Decimal(days_remaining)
        proration_credit = unused_amount
        net_charge = new_charge - proration_credit

        # Round to precision
        unused_amount = self._round(unused_amount)
        new_charge = self._round(new_charge)
        proration_credit = self._round(proration_credit)
        net_charge = self._round(net_charge)

        result = ProrationResult(
            old_variant=VariantType(old_variant),
            new_variant=VariantType(new_variant),
            old_price=old_price,
            new_price=new_price,
            days_remaining=days_remaining,
            days_in_period=days_in_period,
            unused_amount=unused_amount,
            proration_credit=proration_credit,
            new_charge=new_charge,
            net_charge=net_charge,
            billing_cycle_start=billing_cycle_start,
            billing_cycle_end=billing_cycle_end,
        )

        logger.info(
            "proration_calculated company_id=%s old=%s new=%s credit=%s net_charge=%s",
            company_id,
            old_variant,
            new_variant,
            proration_credit,
            net_charge,
        )

        return result

    async def apply_proration_credit(
        self,
        company_id: UUID,
        proration_result: ProrationResult,
    ) -> ProrationAudit:
        """
        Apply proration credit and create audit record.

        This records the proration in the database for audit trail.
        Actual charge/credit to Paddle happens separately.

        Args:
            company_id: Company UUID
            proration_result: ProrationResult from calculate_upgrade_proration

        Returns:
            ProrationAudit record
        """
        with SessionLocal() as db:
            audit = ProrationAudit(
                company_id=str(company_id),
                old_variant=proration_result.old_variant.value,
                new_variant=proration_result.new_variant.value,
                old_price=proration_result.old_price,
                new_price=proration_result.new_price,
                days_remaining=proration_result.days_remaining,
                days_in_period=proration_result.days_in_period,
                unused_amount=proration_result.unused_amount,
                proration_amount=proration_result.proration_credit,
                credit_applied=proration_result.proration_credit,
                charge_applied=proration_result.net_charge,
                billing_cycle_start=proration_result.billing_cycle_start,
                billing_cycle_end=proration_result.billing_cycle_end,
            )

            db.add(audit)
            db.commit()
            db.refresh(audit)

            logger.info(
                "proration_applied company_id=%s audit_id=%s credit=%s charge=%s",
                company_id,
                audit.id,
                proration_result.proration_credit,
                proration_result.net_charge,
            )

            return audit

    async def get_proration_audit_log(
        self,
        company_id: UUID,
        limit: int = 12,
    ) -> List[ProrationAuditSchema]:
        """
        Get proration audit history for a company.

        Args:
            company_id: Company UUID
            limit: Maximum number of records to return

        Returns:
            List of ProrationAudit records (most recent first)
        """
        with SessionLocal() as db:
            audits = db.query(ProrationAudit).filter(
                ProrationAudit.company_id == str(company_id)
            ).order_by(
                ProrationAudit.calculated_at.desc()
            ).limit(limit).all()

            return [
                ProrationAuditSchema(
                    id=UUID(audit.id),
                    company_id=UUID(audit.company_id),
                    old_variant=VariantType(audit.old_variant),
                    new_variant=VariantType(audit.new_variant),
                    old_price=audit.old_price,
                    new_price=audit.new_price,
                    days_remaining=audit.days_remaining,
                    days_in_period=audit.days_in_period,
                    unused_amount=audit.unused_amount,
                    proration_amount=audit.proration_amount,
                    credit_applied=audit.credit_applied,
                    charge_applied=audit.charge_applied,
                    calculated_at=audit.calculated_at,
                )
                for audit in audits
            ]

    async def calculate_downgrade_effective_date(
        self,
        billing_cycle_end: date,
    ) -> date:
        """
        Calculate effective date for downgrade.

        Downgrades are always effective at the next billing cycle.

        Args:
            billing_cycle_end: End of current billing period

        Returns:
            Effective date (same as billing_cycle_end)
        """
        return billing_cycle_end

    async def estimate_upgrade_cost(
        self,
        old_variant: str,
        new_variant: str,
        days_remaining: int,
        days_in_period: int,
    ) -> Dict[str, Decimal]:
        """
        Quick estimate of upgrade cost without full proration.

        Useful for showing preview before user confirms.

        Args:
            old_variant: Current variant
            new_variant: Target variant
            days_remaining: Days left in billing period
            days_in_period: Total days in billing period

        Returns:
            Dict with estimated amounts
        """
        old_variant = self._validate_variant(old_variant)
        new_variant = self._validate_variant(new_variant)

        old_price = self._get_variant_price(old_variant)
        new_price = self._get_variant_price(new_variant)

        # Calculate daily rates
        daily_old = old_price / Decimal(days_in_period)
        daily_new = new_price / Decimal(days_in_period)

        # Calculate amounts
        unused = self._round(daily_old * Decimal(days_remaining))
        new_charge = self._round(daily_new * Decimal(days_remaining))
        net = self._round(new_charge - unused)

        return {
            "old_price": old_price,
            "new_price": new_price,
            "unused_credit": unused,
            "new_charge": new_charge,
            "net_cost": net,
            "per_day_difference": self._round(daily_new - daily_old),
        }

    # ── Edge Case Handlers ───────────────────────────────────────────────

    async def calculate_first_day_proration(
        self,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: date,
        billing_cycle_end: date,
    ) -> ProrationResult:
        """
        Special case: Upgrade on first day of billing period.

        Full credit for old variant, full charge for new variant.
        """
        return await self.calculate_upgrade_proration(
            company_id=UUID("00000000-0000-0000-0000-000000000000"),
            old_variant=old_variant,
            new_variant=new_variant,
            billing_cycle_start=billing_cycle_start,
            billing_cycle_end=billing_cycle_end,
            reference_date=billing_cycle_start,
        )

    async def calculate_last_day_proration(
        self,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: date,
        billing_cycle_end: date,
    ) -> ProrationResult:
        """
        Special case: Upgrade on last day of billing period.

        No proration needed - upgrade effective next cycle.
        """
        # Last day means 0 days remaining
        result = await self.calculate_upgrade_proration(
            company_id=UUID("00000000-0000-0000-0000-000000000000"),
            old_variant=old_variant,
            new_variant=new_variant,
            billing_cycle_start=billing_cycle_start,
            billing_cycle_end=billing_cycle_end,
            reference_date=billing_cycle_end,
        )

        # Should have 0 net charge
        return result

    async def calculate_mid_month_proration(
        self,
        company_id: UUID,
        old_variant: str,
        new_variant: str,
        days_into_period: int,
    ) -> Dict[str, Any]:
        """
        Calculate proration given days into a 30-day period.

        Convenience method for standard monthly periods.

        Args:
            company_id: Company UUID
            old_variant: Current variant
            new_variant: Target variant
            days_into_period: How many days into the billing period

        Returns:
            Full proration details
        """
        today = datetime.now(timezone.utc).date()
        billing_start = today - timedelta(days=days_into_period)
        billing_end = billing_start + timedelta(days=30)

        result = await self.calculate_upgrade_proration(
            company_id=company_id,
            old_variant=old_variant,
            new_variant=new_variant,
            billing_cycle_start=billing_start,
            billing_cycle_end=billing_end,
        )

        return {
            "proration": result,
            "billing_start": billing_start,
            "billing_end": billing_end,
            "days_elapsed": days_into_period,
        }

    # ── Validation Helpers ───────────────────────────────────────────────

    def _validate_variant(self, variant: str) -> str:
        """Validate and normalize variant name."""
        variant_lower = variant.lower().strip()
        valid_variants = {"starter", "growth", "high"}
        if variant_lower not in valid_variants:
            raise ProrationError(
                f"Invalid variant: {variant}. "
                f"Must be one of: {', '.join(sorted(valid_variants))}"
            )
        return variant_lower

    def _validate_billing_period(
        self,
        billing_cycle_start: date,
        billing_cycle_end: date,
    ) -> None:
        """Validate billing period dates.

        P1: Allows 1-400 days to accommodate yearly plans.
        """
        if billing_cycle_end <= billing_cycle_start:
            raise InvalidProrationPeriodError(
                f"billing_cycle_end ({billing_cycle_end}) must be after "
                f"billing_cycle_start ({billing_cycle_start})"
            )

        # Check for reasonable period length (1-400 days for yearly)
        period_days = (billing_cycle_end - billing_cycle_start).days
        if period_days < 1 or period_days > 400:
            raise InvalidProrationPeriodError(
                f"Unusual billing period length: {period_days} days. "
                "Expected 1-400 days."
            )

    def _is_upgrade(self, old_variant: str, new_variant: str) -> bool:
        """Check if new_variant is an upgrade from old_variant."""
        tier_order = {"starter": 1, "growth": 2, "high": 3}
        return tier_order.get(new_variant, 0) > tier_order.get(old_variant, 0)

    def _get_variant_price(
        self, variant: str, billing_frequency: str = "monthly"
    ) -> Decimal:
        """Get price for a variant based on billing frequency."""
        variant_type = VariantType(variant)
        limits = VARIANT_LIMITS[variant_type]
        if billing_frequency == "yearly":
            return limits.get("yearly_price", limits["price"] * 12)
        return limits["price"]

    def _round(self, amount: Decimal) -> Decimal:
        """Round to currency precision (2 decimal places)."""
        return amount.quantize(self.PRECISION, rounding=ROUND_HALF_UP)


# ── Singleton Service ────────────────────────────────────────────────────

_proration_service: Optional[ProrationService] = None


def get_proration_service() -> ProrationService:
    """Get the proration service singleton."""
    global _proration_service
    if _proration_service is None:
        _proration_service = ProrationService()
    return _proration_service
