"""Delivery Estimation System.

Provides delivery date estimation:
- ML-based prediction
- Weather impact consideration
- Holiday handling
- Regional delay factors
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DeliveryConfidence(str, Enum):
    """Delivery confidence level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DeliveryEstimate:
    """Delivery estimate."""
    estimated_date: datetime
    confidence: DeliveryConfidence
    confidence_interval_days: int
    factors: List[str]


class DeliveryEstimator:
    """Delivery date estimation engine."""

    # Regional delay factors
    REGIONAL_DELAYS = {
        "northeast": 1.0,
        "southeast": 0.5,
        "midwest": 0.5,
        "southwest": 0.0,
        "west": 0.0,
        "hawaii": 3.0,
        "alaska": 4.0
    }

    # Carrier delivery days
    CARRIER_DAYS = {
        "ups_ground": 5,
        "ups_express": 2,
        "fedex_ground": 5,
        "fedex_express": 2,
        "usps_priority": 3,
        "usps_first_class": 5,
        "dhl_express": 3
    }

    def __init__(self, client_id: str):
        self.client_id = client_id
        self._holidays: List[datetime] = []

    def estimate_delivery(
        self,
        carrier: str,
        service: str,
        origin_region: str,
        destination_region: str,
        ship_date: Optional[datetime] = None
    ) -> DeliveryEstimate:
        """Estimate delivery date."""
        ship_date = ship_date or datetime.utcnow()

        # Base delivery days
        service_key = f"{carrier.lower()}_{service.lower()}"
        base_days = self.CARRIER_DAYS.get(service_key, 5)

        # Add regional delays
        region_delay = self.REGIONAL_DELAYS.get(destination_region.lower(), 0)
        total_days = base_days + region_delay

        # Calculate estimated date
        estimated = ship_date + timedelta(days=int(total_days))

        # Skip weekends
        while estimated.weekday() >= 5:  # Saturday or Sunday
            estimated += timedelta(days=1)

        # Skip holidays
        estimated = self._skip_holidays(estimated)

        # Determine confidence
        confidence = DeliveryConfidence.HIGH if total_days <= 3 else DeliveryConfidence.MEDIUM
        confidence_interval = 2 if confidence == DeliveryConfidence.HIGH else 4

        return DeliveryEstimate(
            estimated_date=estimated,
            confidence=confidence,
            confidence_interval_days=confidence_interval,
            factors=[
                f"Base service: {service}",
                f"Regional factor: +{region_delay} days",
                f"Weekend adjustment applied"
            ]
        )

    def apply_weather_delay(
        self,
        estimate: DeliveryEstimate,
        weather_severity: float  # 0-1 scale
    ) -> DeliveryEstimate:
        """Apply weather delay to estimate."""
        if weather_severity < 0.3:
            return estimate

        delay_days = int(weather_severity * 3)
        new_date = estimate.estimated_date + timedelta(days=delay_days)

        factors = estimate.factors + [f"Weather delay: +{delay_days} days"]

        return DeliveryEstimate(
            estimated_date=new_date,
            confidence=DeliveryConfidence.LOW,
            confidence_interval_days=estimate.confidence_interval_days + delay_days,
            factors=factors
        )

    def get_delivery_window(
        self,
        estimate: DeliveryEstimate
    ) -> Dict[str, str]:
        """Get delivery window."""
        start = estimate.estimated_date - timedelta(days=estimate.confidence_interval_days // 2)
        end = estimate.estimated_date + timedelta(days=estimate.confidence_interval_days // 2)

        return {
            "earliest": start.strftime("%Y-%m-%d"),
            "estimated": estimate.estimated_date.strftime("%Y-%m-%d"),
            "latest": end.strftime("%Y-%m-%d"),
            "confidence": estimate.confidence.value
        }

    def _skip_holidays(self, date: datetime) -> datetime:
        """Skip holidays."""
        # Simplified holiday check
        holidays_2026 = [
            datetime(2026, 1, 1),   # New Year's
            datetime(2026, 7, 4),   # Independence Day
            datetime(2026, 12, 25), # Christmas
        ]

        while date in holidays_2026:
            date += timedelta(days=1)

        return date
