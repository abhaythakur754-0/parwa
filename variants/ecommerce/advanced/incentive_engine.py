"""Incentive Engine for Cart Recovery.

Provides discount and incentive management:
- Discount code generation
- Incentive eligibility rules
- Margin protection logic
- Customer segment targeting
- Expiration management
- Fraud prevention
- Paddle integration
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import random
import string
import logging

logger = logging.getLogger(__name__)


class IncentiveType(str, Enum):
    """Type of incentive."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    FREE_SHIPPING = "free_shipping"
    BOGO = "bogo"  # Buy one get one


class IncentiveStatus(str, Enum):
    """Incentive status."""
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Incentive:
    """Incentive/discount representation."""
    incentive_id: str
    code: str
    incentive_type: IncentiveType
    value: Decimal
    min_cart_value: Decimal
    max_discount: Optional[Decimal]
    customer_id: Optional[str]
    created_at: datetime
    expires_at: datetime
    status: IncentiveStatus = IncentiveStatus.ACTIVE
    used_at: Optional[datetime] = None
    usage_count: int = 0
    max_uses: int = 1


@dataclass
class EligibilityResult:
    """Eligibility check result."""
    eligible: bool
    reason: str
    max_allowed_discount: Decimal
    recommended_value: Optional[Decimal] = None


class IncentiveEngine:
    """Incentive and discount management engine."""

    # Margin protection thresholds
    MAX_DISCOUNT_PERCENT = 25  # Maximum 25% discount
    MIN_MARGIN_THRESHOLD = 15  # Minimum margin after discount

    # Customer segment discount caps
    SEGMENT_CAPS = {
        "new": 15,
        "regular": 20,
        "vip": 25,
        "at_risk": 25
    }

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize incentive engine.

        Args:
            client_id: Client identifier
            config: Optional configuration
        """
        self.client_id = client_id
        self.config = config or {}
        self.default_expiry_hours = self.config.get("default_expiry_hours", 72)
        self._incentives: Dict[str, Incentive] = {}
        self._used_codes: set = set()

    def generate_incentive(
        self,
        incentive_type: IncentiveType,
        value: Decimal,
        customer_id: Optional[str] = None,
        min_cart_value: Optional[Decimal] = None,
        expiry_hours: Optional[int] = None,
        customer_segment: Optional[str] = None
    ) -> Incentive:
        """Generate a new incentive code.

        Args:
            incentive_type: Type of incentive
            value: Discount value (percentage or fixed amount)
            customer_id: Optional customer ID for personalization
            min_cart_value: Minimum cart value for eligibility
            expiry_hours: Hours until expiration
            customer_segment: Customer segment for margin protection

        Returns:
            Generated incentive
        """
        # Apply margin protection
        capped_value = self._apply_margin_protection(value, customer_segment)

        # Generate unique code
        code = self._generate_code()

        expiry = datetime.utcnow() + timedelta(
            hours=expiry_hours or self.default_expiry_hours
        )

        incentive = Incentive(
            incentive_id=f"inc_{code}",
            code=code,
            incentive_type=incentive_type,
            value=capped_value,
            min_cart_value=min_cart_value or Decimal("0"),
            max_discount=self._calculate_max_discount(capped_value, incentive_type),
            customer_id=customer_id,
            created_at=datetime.utcnow(),
            expires_at=expiry
        )

        self._incentives[incentive.incentive_id] = incentive

        logger.info(
            "Generated incentive",
            extra={
                "client_id": self.client_id,
                "incentive_id": incentive.incentive_id,
                "type": incentive_type.value,
                "value": float(capped_value)
            }
        )

        return incentive

    def check_eligibility(
        self,
        code: str,
        customer_id: str,
        cart_value: Decimal,
        customer_segment: Optional[str] = None
    ) -> EligibilityResult:
        """Check if customer is eligible for incentive.

        Args:
            code: Discount code
            customer_id: Customer identifier
            cart_value: Current cart value
            customer_segment: Customer segment

        Returns:
            Eligibility result
        """
        incentive = self._get_incentive_by_code(code)

        if not incentive:
            return EligibilityResult(
                eligible=False,
                reason="Invalid code",
                max_allowed_discount=Decimal("0")
            )

        if incentive.status != IncentiveStatus.ACTIVE:
            return EligibilityResult(
                eligible=False,
                reason=f"Code is {incentive.status.value}",
                max_allowed_discount=Decimal("0")
            )

        if datetime.utcnow() > incentive.expires_at:
            incentive.status = IncentiveStatus.EXPIRED
            return EligibilityResult(
                eligible=False,
                reason="Code has expired",
                max_allowed_discount=Decimal("0")
            )

        if incentive.customer_id and incentive.customer_id != customer_id:
            return EligibilityResult(
                eligible=False,
                reason="Code is not valid for this customer",
                max_allowed_discount=Decimal("0")
            )

        if cart_value < incentive.min_cart_value:
            return EligibilityResult(
                eligible=False,
                reason=f"Minimum cart value is ${incentive.min_cart_value}",
                max_allowed_discount=Decimal("0")
            )

        if incentive.usage_count >= incentive.max_uses:
            return EligibilityResult(
                eligible=False,
                reason="Code has reached maximum uses",
                max_allowed_discount=Decimal("0")
            )

        # Check fraud
        if self._check_fraud(code, customer_id):
            return EligibilityResult(
                eligible=False,
                reason="Code flagged for review",
                max_allowed_discount=Decimal("0")
            )

        return EligibilityResult(
            eligible=True,
            reason="Eligible",
            max_allowed_discount=incentive.max_discount or Decimal("9999"),
            recommended_value=incentive.value
        )

    def apply_incentive(
        self,
        code: str,
        order_value: Decimal
    ) -> Tuple[Decimal, bool]:
        """Apply incentive to order.

        Args:
            code: Discount code
            order_value: Order value before discount

        Returns:
            Tuple of (discount_amount, success)
        """
        incentive = self._get_incentive_by_code(code)

        if not incentive:
            return Decimal("0"), False

        if incentive.incentive_type == IncentiveType.PERCENTAGE:
            discount = order_value * (incentive.value / Decimal("100"))
        elif incentive.incentive_type == IncentiveType.FIXED:
            discount = incentive.value
        else:
            discount = Decimal("0")

        # Apply max discount cap
        if incentive.max_discount and discount > incentive.max_discount:
            discount = incentive.max_discount

        # Update incentive
        incentive.usage_count += 1
        if incentive.usage_count >= incentive.max_uses:
            incentive.status = IncentiveStatus.USED
            incentive.used_at = datetime.utcnow()

        self._used_codes.add(code)

        logger.info(
            "Applied incentive",
            extra={
                "client_id": self.client_id,
                "code": code,
                "discount": float(discount)
            }
        )

        return discount, True

    def validate_with_paddle(
        self,
        code: str,
        paddle_transaction_id: Optional[str] = None
    ) -> bool:
        """Validate discount code with Paddle.

        Args:
            code: Discount code
            paddle_transaction_id: Optional transaction ID

        Returns:
            True if valid
        """
        # In production, call Paddle API to validate
        # Paddle integration point for discount validation
        incentive = self._get_incentive_by_code(code)
        return incentive is not None and incentive.status == IncentiveStatus.ACTIVE

    def cancel_incentive(self, code: str) -> bool:
        """Cancel an incentive.

        Args:
            code: Discount code

        Returns:
            True if cancelled
        """
        incentive = self._get_incentive_by_code(code)
        if incentive:
            incentive.status = IncentiveStatus.CANCELLED
            return True
        return False

    def get_incentive_stats(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get incentive statistics.

        Args:
            days: Days to analyze

        Returns:
            Statistics dictionary
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        total = 0
        used = 0
        expired = 0
        total_discount_given = Decimal("0")

        for incentive in self._incentives.values():
            if incentive.created_at >= cutoff:
                total += 1
                if incentive.status == IncentiveStatus.USED:
                    used += 1
                    total_discount_given += incentive.max_discount or Decimal("0")
                elif incentive.status == IncentiveStatus.EXPIRED:
                    expired += 1

        redemption_rate = used / total if total > 0 else 0

        return {
            "period_days": days,
            "total_generated": total,
            "total_used": used,
            "total_expired": expired,
            "redemption_rate": redemption_rate,
            "total_discount_given": float(total_discount_given)
        }

    def _generate_code(self, length: int = 8) -> str:
        """Generate unique discount code."""
        while True:
            code = ''.join(random.choices(
                string.ascii_uppercase + string.digits,
                k=length
            ))
            if code not in self._used_codes:
                return code

    def _get_incentive_by_code(self, code: str) -> Optional[Incentive]:
        """Get incentive by code."""
        for incentive in self._incentives.values():
            if incentive.code == code:
                return incentive
        return None

    def _apply_margin_protection(
        self,
        value: Decimal,
        segment: Optional[str]
    ) -> Decimal:
        """Apply margin protection caps."""
        # Get segment cap
        if segment and segment in self.SEGMENT_CAPS:
            max_allowed = Decimal(str(self.SEGMENT_CAPS[segment]))
        else:
            max_allowed = Decimal(str(self.MAX_DISCOUNT_PERCENT))

        # Cap the value
        return min(value, max_allowed)

    def _calculate_max_discount(
        self,
        value: Decimal,
        incentive_type: IncentiveType
    ) -> Optional[Decimal]:
        """Calculate maximum discount amount."""
        if incentive_type == IncentiveType.PERCENTAGE:
            # For percentage, max is relative to a $500 cart
            return Decimal("500") * (value / Decimal("100"))
        return None

    def _check_fraud(
        self,
        code: str,
        customer_id: str
    ) -> bool:
        """Check for fraud indicators."""
        # In production, implement fraud detection logic
        # - Multiple attempts from same IP
        # - Rapid code generation
        # - Pattern detection
        return False
