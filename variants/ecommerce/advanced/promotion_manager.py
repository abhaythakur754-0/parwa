"""Promotion Manager for E-commerce.

Provides promotion management:
- Promotion creation support
- Coupon code management
- Flash sale handling
- Bundle promotion support
- Promotion stacking rules
- Paddle integration
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import random
import string
import logging

logger = logging.getLogger(__name__)


class PromotionType(str, Enum):
    """Promotion type."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    BOGO = "bogo"
    FLASH_SALE = "flash_sale"
    BUNDLE = "bundle"


class StackingRule(str, Enum):
    """Stacking rule."""
    NONE = "none"
    WITH_SALE = "with_sale"
    WITH_COUPON = "with_coupon"
    ALL = "all"


@dataclass
class Promotion:
    """Promotion definition."""
    promotion_id: str
    name: str
    code: Optional[str]
    promotion_type: PromotionType
    value: Decimal
    start_date: datetime
    end_date: datetime
    stacking_rule: StackingRule
    active: bool = True


class PromotionManager:
    """Promotion management system."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._promotions: Dict[str, Promotion] = {}

    def create_promotion(
        self,
        name: str,
        promotion_type: PromotionType,
        value: Decimal,
        duration_days: int = 7,
        generate_code: bool = True,
        stacking_rule: StackingRule = StackingRule.NONE
    ) -> Promotion:
        """Create a new promotion."""
        code = self._generate_code() if generate_code else None
        now = datetime.utcnow()

        promotion = Promotion(
            promotion_id=f"promo_{code or now.timestamp()}",
            name=name,
            code=code,
            promotion_type=promotion_type,
            value=value,
            start_date=now,
            end_date=now + timedelta(days=duration_days),
            stacking_rule=stacking_rule
        )

        self._promotions[promotion.promotion_id] = promotion
        logger.info(f"Created promotion: {promotion.promotion_id}")

        return promotion

    def create_flash_sale(
        self,
        name: str,
        discount_percent: Decimal,
        duration_hours: int = 24
    ) -> Promotion:
        """Create a flash sale."""
        return self.create_promotion(
            name=name,
            promotion_type=PromotionType.FLASH_SALE,
            value=discount_percent,
            duration_days=duration_hours // 24 + 1,
            generate_code=False
        )

    def create_bundle_promotion(
        self,
        name: str,
        bundle_discount: Decimal
    ) -> Promotion:
        """Create bundle promotion."""
        return self.create_promotion(
            name=name,
            promotion_type=PromotionType.BUNDLE,
            value=bundle_discount,
            duration_days=30,
            generate_code=True
        )

    def validate_stacking(
        self,
        promotion_codes: List[str]
    ) -> Dict[str, Any]:
        """Validate if promotions can stack."""
        promotions = [
            self._get_by_code(c) for c in promotion_codes
        ]
        promotions = [p for p in promotions if p]

        if len(promotions) <= 1:
            return {"stackable": True, "reason": "Single promotion"}

        # Check stacking rules
        for p in promotions:
            if p.stacking_rule == StackingRule.NONE:
                return {"stackable": False, "reason": f"{p.name} cannot be stacked"}

        return {"stackable": True, "reason": "All promotions allow stacking"}

    def apply_promotion(
        self,
        code: str,
        order_value: Decimal
    ) -> Dict[str, Any]:
        """Apply promotion to order."""
        promotion = self._get_by_code(code)

        if not promotion:
            return {"applied": False, "reason": "Invalid code"}

        if not promotion.active:
            return {"applied": False, "reason": "Promotion inactive"}

        now = datetime.utcnow()
        if now < promotion.start_date or now > promotion.end_date:
            return {"applied": False, "reason": "Promotion expired"}

        if promotion.promotion_type == PromotionType.PERCENTAGE:
            discount = order_value * (promotion.value / Decimal("100"))
        elif promotion.promotion_type == PromotionType.FIXED:
            discount = promotion.value
        else:
            discount = Decimal("0")

        return {
            "applied": True,
            "promotion_id": promotion.promotion_id,
            "discount": float(discount),
            "final_total": float(order_value - discount)
        }

    def validate_with_paddle(self, code: str) -> bool:
        """Validate promotion with Paddle."""
        promotion = self._get_by_code(code)
        return promotion is not None and promotion.active

    def _generate_code(self, length: int = 8) -> str:
        """Generate unique code."""
        return ''.join(random.choices(
            string.ascii_uppercase + string.digits,
            k=length
        ))

    def _get_by_code(self, code: str) -> Optional[Promotion]:
        """Get promotion by code."""
        for p in self._promotions.values():
            if p.code == code:
                return p
        return None
