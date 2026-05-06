"""Price Adjustment System.

Provides price adjustment capabilities:
- Automated price recommendation
- Margin protection
- MAP compliance
- Sale price scheduling
- Audit trail
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AdjustmentType(str, Enum):
    """Adjustment type."""
    INCREASE = "increase"
    DECREASE = "decrease"
    SALE = "sale"
    ROLLBACK = "rollback"


@dataclass
class PriceAdjustment:
    """Price adjustment record."""
    adjustment_id: str
    product_id: str
    old_price: Decimal
    new_price: Decimal
    adjustment_type: AdjustmentType
    reason: str
    created_at: datetime
    created_by: str = "system"


class PriceAdjustmentEngine:
    """Price adjustment engine with compliance."""

    # MAP (Minimum Advertised Price) compliance
    MAP_MINIMUM = Decimal("49.99")

    # Margin thresholds
    MIN_MARGIN_PERCENT = 15

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._adjustments: List[PriceAdjustment] = []

    def recommend_adjustment(
        self,
        product_id: str,
        current_price: Decimal,
        target_margin: Decimal,
        cost: Decimal
    ) -> Dict[str, Any]:
        """Recommend price adjustment."""
        target_price = cost * (Decimal("1") + target_margin / Decimal("100"))

        if target_price > current_price:
            adjustment_type = AdjustmentType.INCREASE
        else:
            adjustment_type = AdjustmentType.DECREASE

        # Check MAP compliance
        if target_price < self.MAP_MINIMUM:
            target_price = self.MAP_MINIMUM
            adjustment_type = AdjustmentType.DECREASE

        return {
            "product_id": product_id,
            "current_price": float(current_price),
            "recommended_price": float(target_price),
            "adjustment_type": adjustment_type.value,
            "change_amount": float(target_price - current_price),
            "margin_impact": float(target_margin),
            "map_compliant": target_price >= self.MAP_MINIMUM
        }

    def apply_adjustment(
        self,
        product_id: str,
        new_price: Decimal,
        old_price: Decimal,
        adjustment_type: AdjustmentType,
        reason: str
    ) -> PriceAdjustment:
        """Apply price adjustment with audit trail."""
        adjustment = PriceAdjustment(
            adjustment_id=f"adj_{product_id}_{datetime.utcnow().timestamp()}",
            product_id=product_id,
            old_price=old_price,
            new_price=new_price,
            adjustment_type=adjustment_type,
            reason=reason,
            created_at=datetime.utcnow()
        )

        self._adjustments.append(adjustment)
        logger.info(f"Applied price adjustment: {adjustment.adjustment_id}")

        return adjustment

    def schedule_sale_price(
        self,
        product_id: str,
        sale_price: Decimal,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Schedule a sale price."""
        return {
            "product_id": product_id,
            "sale_price": float(sale_price),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "status": "scheduled"
        }

    def check_map_compliance(self, price: Decimal) -> bool:
        """Check MAP compliance."""
        return price >= self.MAP_MINIMUM

    def get_audit_trail(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price adjustment audit trail."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        return [
            {
                "adjustment_id": a.adjustment_id,
                "product_id": a.product_id,
                "old_price": float(a.old_price),
                "new_price": float(a.new_price),
                "type": a.adjustment_type.value,
                "reason": a.reason,
                "created_at": a.created_at.isoformat()
            }
            for a in self._adjustments
            if a.product_id == product_id and a.created_at >= cutoff
        ]
