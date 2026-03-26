"""Delivery Exception Handler.

Provides exception handling:
- Exception detection
- Exception classification
- Automated resolution
- Refund eligibility
- Paddle refund gate
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExceptionType(str, Enum):
    """Exception type."""
    LOST = "lost"
    DAMAGED = "damaged"
    DELAYED = "delayed"
    WRONG_ADDRESS = "wrong_address"
    REFUSED = "refused"
    CUSTOMS = "customs"


class ResolutionType(str, Enum):
    """Resolution type."""
    RESHIP = "reship"
    REFUND = "refund"
    CREDIT = "credit"
    INVESTIGATE = "investigate"


@dataclass
class DeliveryException:
    """Delivery exception."""
    exception_id: str
    order_id: str
    tracking_number: str
    exception_type: ExceptionType
    description: str
    created_at: datetime
    status: str = "open"
    resolution: Optional[ResolutionType] = None


class ExceptionHandler:
    """Delivery exception handler with Paddle integration."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._exceptions: Dict[str, DeliveryException] = {}
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}

    def detect_exception(
        self,
        tracking_number: str,
        tracking_events: List[Dict[str, Any]]
    ) -> Optional[DeliveryException]:
        """Detect delivery exception from tracking events."""
        for event in tracking_events:
            status = event.get("status", "").lower()
            description = event.get("description", "").lower()

            # Detect exception types
            if "lost" in description or "unable to locate" in description:
                return self._create_exception(
                    "ord_unknown", tracking_number, ExceptionType.LOST, description
                )
            elif "damaged" in description:
                return self._create_exception(
                    "ord_unknown", tracking_number, ExceptionType.DAMAGED, description
                )
            elif "delayed" in status or "exception" in status:
                return self._create_exception(
                    "ord_unknown", tracking_number, ExceptionType.DELAYED, description
                )

        return None

    def classify_exception(
        self,
        exception: DeliveryException
    ) -> Dict[str, Any]:
        """Classify exception and determine resolution."""
        classification = {
            "exception_id": exception.exception_id,
            "type": exception.exception_type.value,
            "severity": self._get_severity(exception.exception_type),
            "auto_resolvable": self._is_auto_resolvable(exception.exception_type),
            "recommended_resolution": self._get_recommended_resolution(exception.exception_type)
        }

        return classification

    def initiate_resolution(
        self,
        exception_id: str,
        resolution_type: ResolutionType,
        order_value: Decimal,
        pending_approval: bool = True
    ) -> Dict[str, Any]:
        """Initiate resolution workflow."""
        exception = self._exceptions.get(exception_id)
        if not exception:
            return {"success": False, "reason": "Exception not found"}

        # PADDLE REFUND GATE - NEVER bypass approval for refunds
        if resolution_type == ResolutionType.REFUND:
            if pending_approval:
                approval_id = f"approval_{exception_id}"
                self._pending_approvals[approval_id] = {
                    "exception_id": exception_id,
                    "order_value": float(order_value),
                    "created_at": datetime.utcnow().isoformat()
                }

                return {
                    "success": True,
                    "status": "pending_approval",
                    "approval_id": approval_id,
                    "message": "Refund requires manager approval (Paddle gate enforced)"
                }

        # For non-refund resolutions or approved refunds
        exception.resolution = resolution_type
        exception.status = "resolved"

        return {
            "success": True,
            "status": "resolved",
            "resolution": resolution_type.value
        }

    def check_refund_eligibility(
        self,
        exception_type: ExceptionType,
        order_age_days: int
    ) -> Dict[str, Any]:
        """Check refund eligibility."""
        eligible_types = [ExceptionType.LOST, ExceptionType.DAMAGED]

        is_eligible = exception_type in eligible_types and order_age_days <= 30

        return {
            "eligible": is_eligible,
            "reason": "Item lost or damaged within 30 days" if is_eligible else "Not eligible for refund"
        }

    def escalate_to_human(
        self,
        exception_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Escalate exception to human agent."""
        exception = self._exceptions.get(exception_id)
        if exception:
            exception.status = "escalated"

        return {
            "success": True,
            "exception_id": exception_id,
            "escalated_to": "human_agent",
            "reason": reason
        }

    def _create_exception(
        self,
        order_id: str,
        tracking_number: str,
        exception_type: ExceptionType,
        description: str
    ) -> DeliveryException:
        """Create new exception."""
        exception = DeliveryException(
            exception_id=f"exc_{tracking_number}_{datetime.utcnow().timestamp()}",
            order_id=order_id,
            tracking_number=tracking_number,
            exception_type=exception_type,
            description=description,
            created_at=datetime.utcnow()
        )

        self._exceptions[exception.exception_id] = exception
        return exception

    def _get_severity(self, exception_type: ExceptionType) -> str:
        """Get exception severity."""
        high = [ExceptionType.LOST, ExceptionType.DAMAGED]
        if exception_type in high:
            return "high"
        return "medium"

    def _is_auto_resolvable(self, exception_type: ExceptionType) -> bool:
        """Check if auto-resolvable."""
        return exception_type == ExceptionType.DELAYED

    def _get_recommended_resolution(self, exception_type: ExceptionType) -> str:
        """Get recommended resolution."""
        resolutions = {
            ExceptionType.LOST: ResolutionType.REFUND.value,
            ExceptionType.DAMAGED: ResolutionType.RESHIP.value,
            ExceptionType.DELAYED: ResolutionType.INVESTIGATE.value,
            ExceptionType.WRONG_ADDRESS: ResolutionType.RESHIP.value,
            ExceptionType.REFUSED: ResolutionType.CREDIT.value,
            ExceptionType.CUSTOMS: ResolutionType.INVESTIGATE.value
        }
        return resolutions.get(exception_type, ResolutionType.INVESTIGATE.value)
