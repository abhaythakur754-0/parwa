"""
MF3: Promo Code Service

Manages discount/promo codes:
- Create promo codes (admin)
- Validate codes
- Apply to invoices
- Track usage per company
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import CompanyPromoUse, PromoCode

logger = logging.getLogger(__name__)


class PromoError(Exception):
    """Base error for promo operations."""


class PromoNotFoundError(PromoError):
    pass


class PromoExpiredError(PromoError):
    pass


class PromoUsesExhaustedError(PromoError):
    pass


class PromoAlreadyUsedError(PromoError):
    pass


class PromoTierMismatchError(PromoError):
    pass


class _PromoService:
    """Singleton promo service."""

    def create_promo_code(
        self,
        code: str,
        discount_type: str,
        discount_value: Decimal,
        max_uses: Optional[int] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        applies_to_tiers: Optional[List[str]] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new promo code. Admin-only.

        Args:
            code: Unique promo code string
            discount_type: 'percentage' or 'fixed'
            discount_value: Discount amount (e.g., 20.00 for 20% or $20)
            max_uses: Maximum total uses (None = unlimited)
            valid_from: Start of validity period
            valid_until: End of validity period
            applies_to_tiers: List of tier codes this applies to (None = all)
            created_by: Admin user ID
        """
        if discount_type not in ("percentage", "fixed"):
            raise PromoError(
                f"Invalid discount_type '{discount_type}'. "
                "Must be 'percentage' or 'fixed' (PROMO-001)"
            )

        if discount_type == "percentage" and discount_value > Decimal("100"):
            raise PromoError("Percentage discount cannot exceed 100% (PROMO-002)")

        if discount_value <= 0:
            raise PromoError("Discount value must be positive (PROMO-003)")

        with SessionLocal() as db:
            # Check for existing code
            existing = (
                db.query(PromoCode)
                .filter(PromoCode.code == code.upper().strip())
                .first()
            )

            if existing:
                raise PromoError(f"Promo code '{code}' already exists (PROMO-004)")

            promo = PromoCode(
                code=code.upper().strip(),
                discount_type=discount_type,
                discount_value=discount_value,
                max_uses=max_uses,
                valid_from=valid_from,
                valid_until=valid_until,
                applies_to_tiers=applies_to_tiers,
                created_by=created_by,
            )
            db.add(promo)
            db.flush()

            logger.info(
                "promo_code_created code=%s type=%s value=%s by=%s",
                promo.code,
                discount_type,
                discount_value,
                created_by,
            )

            return {
                "id": promo.id,
                "code": promo.code,
                "discount_type": discount_type,
                "discount_value": str(discount_value),
                "max_uses": max_uses,
                "valid_from": valid_from.isoformat() if valid_from else None,
                "valid_until": valid_until.isoformat() if valid_until else None,
                "applies_to_tiers": applies_to_tiers,
                "status": "active",
            }

    def validate_promo_code(
        self,
        code: str,
        company_id: str,
        tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate a promo code for use.

        Checks: exists, active, not expired, uses remaining, tier match,
        company hasn't used before.
        """
        with SessionLocal() as db:
            promo = (
                db.query(PromoCode)
                .filter(
                    PromoCode.code == code.upper().strip(),
                    PromoCode.is_active,
                )
                .first()
            )

            if not promo:
                raise PromoNotFoundError(
                    f"Promo code '{code}' not found or inactive (PROMO-005)"
                )

            now = datetime.now(timezone.utc)

            # Check validity period
            if promo.valid_from and promo.valid_from > now:
                raise PromoError(
                    f"Promo code '{code}' is not yet valid. "
                    f"Starts at {promo.valid_from.isoformat()} (PROMO-006)"
                )

            if promo.valid_until and promo.valid_until < now:
                raise PromoExpiredError(
                    f"Promo code '{code}' expired at "
                    f"{promo.valid_until.isoformat()} (PROMO-007)"
                )

            # Check uses
            if promo.max_uses is not None and promo.used_count >= promo.max_uses:
                raise PromoUsesExhaustedError(
                    f"Promo code '{code}' has been fully used "
                    f"({promo.used_count}/{promo.max_uses}) (PROMO-008)"
                )

            # Check tier restriction
            if promo.applies_to_tiers and tier:
                if tier not in promo.applies_to_tiers:
                    raise PromoTierMismatchError(
                        f"Promo code '{code}' does not apply to tier '{tier}'. "
                        f"Valid tiers: {
                            promo.applies_to_tiers} (PROMO-009)"
                    )

            # Check company hasn't used before
            prev_use = (
                db.query(CompanyPromoUse)
                .filter(
                    CompanyPromoUse.company_id == str(company_id),
                    CompanyPromoUse.promo_code_id == promo.id,
                )
                .first()
            )

            if prev_use:
                raise PromoAlreadyUsedError(
                    f"Company has already used promo code '{code}' " "(PROMO-010)"
                )

            return {
                "valid": True,
                "code": promo.code,
                "discount_type": promo.discount_type,
                "discount_value": str(promo.discount_value),
                "remaining_uses": (
                    promo.max_uses - promo.used_count if promo.max_uses else None
                ),
            }

    def apply_promo_code(
        self,
        code: str,
        company_id: str,
        invoice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply a validated promo code to a company's account.

        Records the usage and increments the counter.
        Returns the discount details for the next invoice.
        """
        # First validate
        validation = self.validate_promo_code(code, company_id)

        with SessionLocal() as db:
            promo = (
                db.query(PromoCode)
                .filter(PromoCode.code == code.upper().strip())
                .first()
            )

            if not promo:
                raise PromoNotFoundError("Promo code not found (PROMO-011)")

            # Get company's subscription to calculate discount
            subscription = (
                db.query(Subscription)
                .filter(Subscription.company_id == str(company_id))
                .order_by(Subscription.created_at.desc())
                .first()
            )

            base_amount = Decimal("0.00")
            if subscription:
                tier = subscription.tier
                try:
                    from database.models.billing_extended import get_variant_limits

                    limits = get_variant_limits(tier)
                    if limits:
                        base_amount = limits.get("price_monthly", Decimal("0.00"))
                except Exception:
                    pass

            # Calculate discount
            if promo.discount_type == "percentage":
                discount_amount = base_amount * (promo.discount_value / Decimal("100"))
            else:
                discount_amount = promo.discount_value

            # Record usage
            usage = CompanyPromoUse(
                company_id=str(company_id),
                promo_code_id=promo.id,
                invoice_id=invoice_id,
                discount_amount=discount_amount,
            )
            db.add(usage)

            # Increment counter
            promo.used_count += 1
            db.flush()

            logger.info(
                "promo_code_applied code=%s company_id=%s discount=%s",
                code,
                company_id,
                discount_amount,
            )

            return {
                "code": promo.code,
                "discount_type": promo.discount_type,
                "discount_value": str(promo.discount_value),
                "discount_amount": str(discount_amount),
                "base_amount": str(base_amount),
                "final_amount": str(base_amount - discount_amount),
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }

    def list_promo_codes(self) -> List[Dict[str, Any]]:
        """Admin: List all promo codes with usage stats."""
        with SessionLocal() as db:
            promos = db.query(PromoCode).order_by(PromoCode.created_at.desc()).all()

            return [
                {
                    "id": p.id,
                    "code": p.code,
                    "discount_type": p.discount_type,
                    "discount_value": str(p.discount_value),
                    "max_uses": p.max_uses,
                    "used_count": p.used_count,
                    "valid_from": p.valid_from.isoformat() if p.valid_from else None,
                    "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                    "is_active": p.is_active,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in promos
            ]

    def deactivate_promo_code(self, promo_code_id: str) -> Dict[str, Any]:
        """Admin: Deactivate a promo code."""
        with SessionLocal() as db:
            promo = (
                db.query(PromoCode).filter(PromoCode.id == str(promo_code_id)).first()
            )

            if not promo:
                raise PromoNotFoundError(
                    f"Promo code not found: {promo_code_id} (PROMO-012)"
                )

            promo.is_active = False
            db.flush()

            logger.info(
                "promo_code_deactivated code=%s by_deactivation",
                promo.code,
            )

            return {
                "id": promo.id,
                "code": promo.code,
                "status": "deactivated",
            }


_promo_service_instance: Optional[_PromoService] = None


def get_promo_service() -> _PromoService:
    """Factory for promo service singleton."""
    global _promo_service_instance
    if _promo_service_instance is None:
        _promo_service_instance = _PromoService()
    return _promo_service_instance
