"""
Proactive Outreach Worker.

Handles proactive customer outreach and follow-ups.

Features:
- Send proactive messages
- Schedule follow-ups
- Track outreach status
- Respect opt-out preferences
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class OutreachStatus(str, Enum):
    """Status of outreach."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    OPTED_OUT = "opted_out"


class OutreachType(str, Enum):
    """Types of outreach."""
    FOLLOW_UP = "follow_up"
    CHECK_IN = "check_in"
    SATISFACTION_SURVEY = "satisfaction_survey"
    PRODUCT_UPDATE = "product_update"
    RENEWAL_REMINDER = "renewal_reminder"


@dataclass
class OutreachRecord:
    """Record of an outreach attempt."""
    outreach_id: str
    customer_id: str
    company_id: str
    message: str
    outreach_type: OutreachType
    status: OutreachStatus
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProactiveOutreachWorker:
    """
    Worker for proactive customer outreach.

    Features:
    - Send proactive messages
    - Schedule follow-ups
    - Track outreach status
    - Respect opt-out preferences

    Example:
        worker = ProactiveOutreachWorker()
        result = await worker.send_outreach("cust_123", "Checking in!")
    """

    # Default follow-up delay in hours
    DEFAULT_FOLLOWUP_DELAY_HOURS = 24

    def __init__(self) -> None:
        """Initialize Proactive Outreach Worker."""
        self._outreach: Dict[str, OutreachRecord] = {}
        self._scheduled: Dict[str, OutreachRecord] = {}
        self._opted_out: set = set()

        logger.info({
            "event": "proactive_outreach_worker_initialized"
        })

    async def send_outreach(
        self,
        customer_id: str,
        message: str,
        company_id: str = "default",
        outreach_type: str = "check_in",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a proactive message to customer.

        Args:
            customer_id: Customer identifier
            message: Message to send
            company_id: Company identifier
            outreach_type: Type of outreach
            metadata: Additional metadata

        Returns:
            Dict with outreach result
        """
        outreach_id = f"outreach_{uuid.uuid4().hex[:8]}"

        logger.info({
            "event": "outreach_started",
            "outreach_id": outreach_id,
            "customer_id": customer_id,
            "outreach_type": outreach_type
        })

        # Check opt-out
        if customer_id in self._opted_out:
            logger.info({
                "event": "outreach_opted_out",
                "outreach_id": outreach_id,
                "customer_id": customer_id
            })

            return {
                "success": False,
                "status": OutreachStatus.OPTED_OUT.value,
                "error": "Customer has opted out",
                "outreach_id": outreach_id
            }

        try:
            out_type = OutreachType(outreach_type)
        except ValueError:
            out_type = OutreachType.CHECK_IN

        record = OutreachRecord(
            outreach_id=outreach_id,
            customer_id=customer_id,
            company_id=company_id,
            message=message,
            outreach_type=out_type,
            status=OutreachStatus.PENDING,
            metadata=metadata or {}
        )

        try:
            # Simulate sending message
            await asyncio.sleep(0.01)

            record.status = OutreachStatus.SENT
            record.sent_at = datetime.now(timezone.utc)

            self._outreach[outreach_id] = record

            logger.info({
                "event": "outreach_sent",
                "outreach_id": outreach_id,
                "customer_id": customer_id,
                "outreach_type": out_type.value
            })

            return {
                "success": True,
                "status": OutreachStatus.SENT.value,
                "outreach_id": outreach_id,
                "customer_id": customer_id,
                "outreach_type": out_type.value,
                "sent_at": record.sent_at.isoformat()
            }

        except Exception as e:
            record.status = OutreachStatus.FAILED
            self._outreach[outreach_id] = record

            logger.error({
                "event": "outreach_failed",
                "outreach_id": outreach_id,
                "error": str(e)
            })

            return {
                "success": False,
                "status": OutreachStatus.FAILED.value,
                "error": str(e),
                "outreach_id": outreach_id
            }

    async def schedule_followup(
        self,
        customer_id: str,
        delay_hours: int = 24,
        message: Optional[str] = None,
        company_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Schedule a follow-up outreach.

        Args:
            customer_id: Customer identifier
            delay_hours: Hours until follow-up
            message: Optional custom message
            company_id: Company identifier

        Returns:
            Dict with scheduling result
        """
        outreach_id = f"followup_{uuid.uuid4().hex[:8]}"
        scheduled_for = datetime.now(timezone.utc) + timedelta(hours=delay_hours)

        logger.info({
            "event": "followup_scheduled",
            "outreach_id": outreach_id,
            "customer_id": customer_id,
            "delay_hours": delay_hours,
            "scheduled_for": scheduled_for.isoformat()
        })

        record = OutreachRecord(
            outreach_id=outreach_id,
            customer_id=customer_id,
            company_id=company_id,
            message=message or "Following up on your recent interaction",
            outreach_type=OutreachType.FOLLOW_UP,
            status=OutreachStatus.PENDING,
            scheduled_for=scheduled_for
        )

        self._scheduled[outreach_id] = record

        return {
            "success": True,
            "outreach_id": outreach_id,
            "customer_id": customer_id,
            "scheduled_for": scheduled_for.isoformat(),
            "delay_hours": delay_hours
        }

    async def get_due_outreach(self) -> List[Dict[str, Any]]:
        """
        Get outreach that is due to be sent.

        Returns:
            List of due outreach records
        """
        now = datetime.now(timezone.utc)
        due = []

        for record in self._scheduled.values():
            if record.scheduled_for and record.scheduled_for <= now:
                if record.status == OutreachStatus.PENDING:
                    due.append({
                        "outreach_id": record.outreach_id,
                        "customer_id": record.customer_id,
                        "company_id": record.company_id,
                        "message": record.message,
                        "outreach_type": record.outreach_type.value,
                        "scheduled_for": record.scheduled_for.isoformat()
                    })

        logger.info({
            "event": "due_outreach_retrieved",
            "count": len(due)
        })

        return due

    async def process_scheduled_outreach(self) -> Dict[str, Any]:
        """
        Process all scheduled outreach that is due.

        Returns:
            Dict with processing results
        """
        due = await self.get_due_outreach()
        results = []

        for outreach in due:
            result = await self.send_outreach(
                customer_id=outreach["customer_id"],
                message=outreach["message"],
                company_id=outreach["company_id"],
                outreach_type=outreach["outreach_type"]
            )

            # Remove from scheduled
            if result["success"]:
                if outreach["outreach_id"] in self._scheduled:
                    del self._scheduled[outreach["outreach_id"]]

            results.append(result)

        logger.info({
            "event": "scheduled_outreach_processed",
            "total": len(due),
            "successful": sum(1 for r in results if r.get("success"))
        })

        return {
            "processed": len(results),
            "successful": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "results": results
        }

    def add_opt_out(self, customer_id: str) -> None:
        """
        Add customer to opt-out list.

        Args:
            customer_id: Customer to opt out
        """
        self._opted_out.add(customer_id)

        logger.info({
            "event": "opt_out_added",
            "customer_id": customer_id
        })

    def remove_opt_out(self, customer_id: str) -> None:
        """
        Remove customer from opt-out list.

        Args:
            customer_id: Customer to remove opt-out
        """
        self._opted_out.discard(customer_id)

        logger.info({
            "event": "opt_out_removed",
            "customer_id": customer_id
        })

    def get_outreach_history(
        self,
        customer_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get outreach history.

        Args:
            customer_id: Optional filter by customer
            limit: Maximum records

        Returns:
            List of outreach records
        """
        records = list(self._outreach.values())

        if customer_id:
            records = [r for r in records if r.customer_id == customer_id]

        records = sorted(records, key=lambda r: r.created_at, reverse=True)

        return [
            {
                "outreach_id": r.outreach_id,
                "customer_id": r.customer_id,
                "company_id": r.company_id,
                "outreach_type": r.outreach_type.value,
                "status": r.status.value,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "created_at": r.created_at.isoformat()
            }
            for r in records[:limit]
        ]

    def get_status(self) -> Dict[str, Any]:
        """
        Get worker status.

        Returns:
            Dict with status information
        """
        return {
            "worker_type": "proactive_outreach",
            "total_outreach": len(self._outreach),
            "scheduled_outreach": len(self._scheduled),
            "opted_out_count": len(self._opted_out)
        }


# ARQ worker function
async def send_outreach(
    ctx: Dict[str, Any],
    customer_id: str,
    message: str,
    company_id: str = "default"
) -> Dict[str, Any]:
    """
    ARQ worker function for sending outreach.

    Args:
        ctx: ARQ context
        customer_id: Customer to reach
        message: Message to send
        company_id: Company identifier

    Returns:
        Outreach result
    """
    worker = ProactiveOutreachWorker()
    return await worker.send_outreach(customer_id, message, company_id)


def get_proactive_outreach_worker() -> ProactiveOutreachWorker:
    """
    Get a ProactiveOutreachWorker instance.

    Returns:
        ProactiveOutreachWorker instance
    """
    return ProactiveOutreachWorker()
