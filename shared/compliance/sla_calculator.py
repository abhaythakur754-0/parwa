"""
PARWA SLA (Service Level Agreement) Calculator.

Provides SLA breach detection, calculation, and tracking for customer
support tickets and response time compliance.

Key Features:
- SLA policy definitions
- Breach detection and calculation
- Response time tracking
- Escalation triggers
- Multi-tier SLA support
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SLATier(str, Enum):
    """SLA tier levels."""
    CRITICAL = "critical"  # VIP/Enterprise - fastest response
    HIGH = "high"  # Premium customers
    STANDARD = "standard"  # Regular customers
    LOW = "low"  # Free tier


class SLAType(str, Enum):
    """Types of SLA metrics."""
    FIRST_RESPONSE = "first_response"  # Time to first response
    RESOLUTION = "resolution"  # Time to full resolution
    UPDATE = "update"  # Time between updates


class SLABreachStatus(str, Enum):
    """SLA breach status."""
    OK = "ok"  # Within SLA
    WARNING = "warning"  # Approaching breach
    BREACHED = "breached"  # SLA breached
    CRITICAL_BREACH = "critical_breach"  # Significantly breached


class SLAPolicy(BaseModel):
    """SLA policy definition."""
    tier: SLATier
    first_response_hours: float = Field(ge=0)
    resolution_hours: float = Field(ge=0)
    update_hours: float = Field(ge=0)
    warning_threshold: float = Field(default=0.8, ge=0, le=1)  # 80% of SLA
    business_hours_only: bool = Field(default=True)
    business_start_hour: int = Field(default=9, ge=0, le=23)
    business_end_hour: int = Field(default=18, ge=0, le=23)
    include_weekends: bool = Field(default=False)

    model_config = ConfigDict(use_enum_values=True)


class SLAResult(BaseModel):
    """Result from SLA calculation."""
    ticket_id: str
    sla_type: SLAType
    tier: SLATier
    status: SLABreachStatus
    is_breached: bool = False
    is_warning: bool = False
    time_elapsed_hours: float = Field(ge=0)
    time_remaining_hours: float = Field(default=0)
    sla_deadline: Optional[datetime] = None
    breach_duration_hours: float = Field(default=0)
    percentage_used: float = Field(ge=0, le=100)
    should_escalate: bool = False
    processing_time_ms: float = Field(default=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class SLASummary(BaseModel):
    """SLA summary statistics."""
    total_tickets: int = Field(default=0)
    within_sla: int = Field(default=0)
    warnings: int = Field(default=0)
    breached: int = Field(default=0)
    critical_breaches: int = Field(default=0)
    breach_rate: float = Field(default=0)
    average_response_hours: float = Field(default=0)
    average_resolution_hours: float = Field(default=0)

    model_config = ConfigDict()


# Default SLA policies by tier
DEFAULT_SLA_POLICIES: Dict[SLATier, SLAPolicy] = {
    SLATier.CRITICAL: SLAPolicy(
        tier=SLATier.CRITICAL,
        first_response_hours=1,  # 1 hour
        resolution_hours=8,  # 8 hours
        update_hours=2,  # 2 hours
        warning_threshold=0.75,
        business_hours_only=False,  # 24/7
        include_weekends=True,
    ),
    SLATier.HIGH: SLAPolicy(
        tier=SLATier.HIGH,
        first_response_hours=2,  # 2 hours
        resolution_hours=24,  # 24 hours
        update_hours=4,  # 4 hours
        warning_threshold=0.8,
        business_hours_only=True,
        include_weekends=False,
    ),
    SLATier.STANDARD: SLAPolicy(
        tier=SLATier.STANDARD,
        first_response_hours=4,  # 4 hours
        resolution_hours=48,  # 48 hours
        update_hours=8,  # 8 hours
        warning_threshold=0.8,
        business_hours_only=True,
        include_weekends=False,
    ),
    SLATier.LOW: SLAPolicy(
        tier=SLATier.LOW,
        first_response_hours=24,  # 24 hours
        resolution_hours=72,  # 72 hours
        update_hours=24,  # 24 hours
        warning_threshold=0.85,
        business_hours_only=True,
        include_weekends=False,
    ),
}


class SLACalculator:
    """
    SLA Calculator for PARWA.

    Calculates SLA metrics, detects breaches, and manages escalation
    triggers for customer support tickets.

    Features:
    - Multi-tier SLA policies
    - Business hours calculation
    - Breach detection and tracking
    - Escalation recommendations
    """

    def __init__(
        self,
        custom_policies: Optional[Dict[SLATier, SLAPolicy]] = None
    ) -> None:
        """
        Initialize SLA Calculator.

        Args:
            custom_policies: Optional custom policies to override defaults
        """
        self._policies = DEFAULT_SLA_POLICIES.copy()
        if custom_policies:
            self._policies.update(custom_policies)

        # Tracking
        self._calculations_performed = 0
        self._breaches_detected = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "sla_calculator_initialized",
            "tiers_configured": len(self._policies),
        })

    def get_policy(self, tier: SLATier) -> SLAPolicy:
        """
        Get SLA policy for a tier.

        Args:
            tier: SLA tier

        Returns:
            SLAPolicy for the tier
        """
        return self._policies.get(tier, self._policies[SLATier.STANDARD])

    def calculate_sla(
        self,
        ticket_id: str,
        tier: SLATier,
        sla_type: SLAType,
        created_at: datetime,
        current_time: Optional[datetime] = None,
        is_vip: bool = False
    ) -> SLAResult:
        """
        Calculate SLA status for a ticket.

        Args:
            ticket_id: Ticket identifier
            tier: SLA tier
            sla_type: Type of SLA metric
            created_at: When the ticket was created
            current_time: Current time (defaults to now)
            is_vip: Whether customer is VIP

        Returns:
            SLAResult with status and timing information
        """
        start_time = datetime.now()
        policy = self.get_policy(tier)

        if current_time is None:
            current_time = datetime.now()

        # Get SLA limit based on type
        sla_limit_hours = self._get_sla_limit(policy, sla_type)

        # Calculate elapsed time
        if policy.business_hours_only:
            elapsed_hours = self._calculate_business_hours(
                created_at, current_time, policy
            )
        else:
            elapsed = current_time - created_at
            elapsed_hours = elapsed.total_seconds() / 3600

        # Calculate remaining time
        remaining_hours = max(0, sla_limit_hours - elapsed_hours)

        # Calculate percentage used
        percentage_used = min(100, (elapsed_hours / sla_limit_hours) * 100)

        # Determine status
        status = self._determine_status(
            elapsed_hours, sla_limit_hours, policy.warning_threshold
        )

        # Check if should escalate
        should_escalate = (
            status == SLABreachStatus.BREACHED or
            status == SLABreachStatus.CRITICAL_BREACH or
            (is_vip and status == SLABreachStatus.WARNING)
        )

        # Calculate breach duration if applicable
        breach_duration = max(0, elapsed_hours - sla_limit_hours)

        # Calculate deadline
        if policy.business_hours_only:
            deadline = self._add_business_hours(
                created_at, sla_limit_hours, policy
            )
        else:
            deadline = created_at + timedelta(hours=sla_limit_hours)

        result = SLAResult(
            ticket_id=ticket_id,
            sla_type=sla_type,
            tier=tier,
            status=status,
            is_breached=status in [SLABreachStatus.BREACHED, SLABreachStatus.CRITICAL_BREACH],
            is_warning=status == SLABreachStatus.WARNING,
            time_elapsed_hours=round(elapsed_hours, 2),
            time_remaining_hours=round(remaining_hours, 2),
            sla_deadline=deadline,
            breach_duration_hours=round(breach_duration, 2),
            percentage_used=round(percentage_used, 2),
            should_escalate=should_escalate,
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._calculations_performed += 1
        if result.is_breached:
            self._breaches_detected += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "sla_calculated",
            "ticket_id": ticket_id,
            "tier": tier.value,
            "sla_type": sla_type.value,
            "status": status.value,
            "percentage_used": percentage_used,
        })

        return result

    def check_breach(
        self,
        ticket_id: str,
        tier: SLATier,
        created_at: datetime,
        current_time: Optional[datetime] = None
    ) -> Dict[str, SLAResult]:
        """
        Check all SLA types for a ticket.

        Args:
            ticket_id: Ticket identifier
            tier: SLA tier
            created_at: When ticket was created
            current_time: Current time (defaults to now)

        Returns:
            Dict mapping SLAType to SLAResult
        """
        results = {}

        for sla_type in SLAType:
            results[sla_type] = self.calculate_sla(
                ticket_id=ticket_id,
                tier=tier,
                sla_type=sla_type,
                created_at=created_at,
                current_time=current_time,
            )

        return results

    def get_summary(self, results: List[SLAResult]) -> SLASummary:
        """
        Generate summary from SLA results.

        Args:
            results: List of SLA results

        Returns:
            SLASummary with statistics
        """
        if not results:
            return SLASummary()

        total = len(results)
        within_sla = sum(1 for r in results if r.status == SLABreachStatus.OK)
        warnings = sum(1 for r in results if r.status == SLABreachStatus.WARNING)
        breached = sum(1 for r in results if r.status == SLABreachStatus.BREACHED)
        critical = sum(1 for r in results if r.status == SLABreachStatus.CRITICAL_BREACH)

        # Calculate averages
        response_times = [
            r.time_elapsed_hours for r in results
            if r.sla_type == SLAType.FIRST_RESPONSE
        ]
        resolution_times = [
            r.time_elapsed_hours for r in results
            if r.sla_type == SLAType.RESOLUTION
        ]

        return SLASummary(
            total_tickets=total,
            within_sla=within_sla,
            warnings=warnings,
            breached=breached,
            critical_breaches=critical,
            breach_rate=(breached + critical) / total if total > 0 else 0,
            average_response_hours=(
                sum(response_times) / len(response_times)
                if response_times else 0
            ),
            average_resolution_hours=(
                sum(resolution_times) / len(resolution_times)
                if resolution_times else 0
            ),
        )

    def estimate_deadline(
        self,
        tier: SLATier,
        sla_type: SLAType,
        start_time: Optional[datetime] = None
    ) -> datetime:
        """
        Estimate SLA deadline from a start time.

        Args:
            tier: SLA tier
            sla_type: Type of SLA metric
            start_time: Start time (defaults to now)

        Returns:
            Estimated deadline datetime
        """
        if start_time is None:
            start_time = datetime.now()

        policy = self.get_policy(tier)
        sla_limit_hours = self._get_sla_limit(policy, sla_type)

        if policy.business_hours_only:
            return self._add_business_hours(start_time, sla_limit_hours, policy)
        else:
            return start_time + timedelta(hours=sla_limit_hours)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get SLA calculator statistics.

        Returns:
            Dict with stats
        """
        return {
            "calculations_performed": self._calculations_performed,
            "breaches_detected": self._breaches_detected,
            "breach_rate": (
                self._breaches_detected / self._calculations_performed
                if self._calculations_performed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._calculations_performed
                if self._calculations_performed > 0 else 0
            ),
        }

    def _get_sla_limit(self, policy: SLAPolicy, sla_type: SLAType) -> float:
        """Get SLA limit hours for a type."""
        limits = {
            SLAType.FIRST_RESPONSE: policy.first_response_hours,
            SLAType.RESOLUTION: policy.resolution_hours,
            SLAType.UPDATE: policy.update_hours,
        }
        return limits.get(sla_type, policy.resolution_hours)

    def _determine_status(
        self,
        elapsed_hours: float,
        sla_limit: float,
        warning_threshold: float
    ) -> SLABreachStatus:
        """Determine SLA status from elapsed time."""
        if elapsed_hours >= sla_limit * 1.5:
            return SLABreachStatus.CRITICAL_BREACH
        elif elapsed_hours >= sla_limit:
            return SLABreachStatus.BREACHED
        elif elapsed_hours >= sla_limit * warning_threshold:
            return SLABreachStatus.WARNING
        else:
            return SLABreachStatus.OK

    def _calculate_business_hours(
        self,
        start: datetime,
        end: datetime,
        policy: SLAPolicy
    ) -> float:
        """
        Calculate business hours between two timestamps.

        Args:
            start: Start datetime
            end: End datetime
            policy: SLA policy with business hours settings

        Returns:
            Hours in business time
        """
        if start >= end:
            return 0

        total_hours = 0
        current = start

        while current < end:
            # Check if working day
            is_weekday = current.weekday() < 5  # Mon=0, Fri=4

            if policy.include_weekends or is_weekday:
                # Calculate hours for this day
                day_start = current.replace(
                    hour=policy.business_start_hour,
                    minute=0, second=0, microsecond=0
                )
                day_end = current.replace(
                    hour=policy.business_end_hour,
                    minute=0, second=0, microsecond=0
                )

                # Adjust for current position
                if current < day_start:
                    period_start = day_start
                else:
                    period_start = current

                if end < day_end:
                    period_end = end
                else:
                    period_end = day_end

                # Add hours if within business hours
                if period_start < period_end:
                    delta = period_end - period_start
                    total_hours += delta.total_seconds() / 3600

            # Move to next day
            current = current.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)

        return max(0, total_hours)

    def _add_business_hours(
        self,
        start: datetime,
        hours_to_add: float,
        policy: SLAPolicy
    ) -> datetime:
        """
        Add business hours to a datetime.

        Args:
            start: Start datetime
            hours_to_add: Hours to add
            policy: SLA policy with business hours settings

        Returns:
            Resulting datetime
        """
        current = start
        remaining = hours_to_add

        while remaining > 0:
            # Check if working day
            is_weekday = current.weekday() < 5

            if policy.include_weekends or is_weekday:
                day_start = current.replace(
                    hour=policy.business_start_hour,
                    minute=0, second=0, microsecond=0
                )
                day_end = current.replace(
                    hour=policy.business_end_hour,
                    minute=0, second=0, microsecond=0
                )

                # If before business hours, start at opening
                if current < day_start:
                    current = day_start

                # Calculate available hours today
                available = (
                    day_end - current
                ).total_seconds() / 3600

                if available > 0:
                    if remaining <= available:
                        return current + timedelta(hours=remaining)
                    else:
                        remaining -= available

            # Move to next business day
            current = current.replace(
                hour=policy.business_start_hour,
                minute=0, second=0, microsecond=0
            ) + timedelta(days=1)

        return current


def get_sla_calculator() -> SLACalculator:
    """
    Get a default SLACalculator instance.

    Returns:
        SLACalculator instance
    """
    return SLACalculator()
