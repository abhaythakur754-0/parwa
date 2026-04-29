"""
Usage Tracking Service (BC-001, BC-002)

Handles real-time usage counting and monthly aggregation for the
PARWA SaaS billing system.

Responsibilities:
- Real-time usage counting (tickets, AI agents, voice minutes)
- Daily usage record upsert (find-or-create pattern)
- Monthly usage aggregation across daily records
- Overage calculation ($0.10/ticket over plan limit)
- Usage percentage and approaching-limit warnings (80% threshold)
- Historical usage reporting

Overage Rules:
- Rate: $0.10 per ticket over the monthly plan limit
- Tracked daily, aggregated monthly
- Notifications emitted when usage approaches or exceeds limits

BC-001: All methods validate company_id
BC-002: All money calculations use Decimal (never float)
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing_extended import UsageRecord, get_variant_limits
from database.models.billing import Subscription
from app.schemas.billing import VARIANT_LIMITS, VariantType

logger = logging.getLogger("parwa.services.usage_tracking")

# Overage rate: $0.10 per ticket over plan limit (BC-002: Decimal, never float)
OVERAGE_RATE_PER_TICKET = Decimal("0.10")

# Default approaching-limit warning threshold (80%)
DEFAULT_APPROACHING_THRESHOLD = Decimal("0.80")

# Default ticket limit when subscription/variant info is unavailable
DEFAULT_TICKET_LIMIT = 2000


# ── Exception Classes ─────────────────────────────────────────────────────


class UsageTrackingError(Exception):
    """Base exception for usage tracking errors."""


class UsageLimitExceededError(UsageTrackingError):
    """Raised when usage exceeds the plan ticket limit."""


# ── Service Implementation ───────────────────────────────────────────────


class UsageTrackingService:
    """
    Usage tracking service for PARWA SaaS billing.

    Tracks daily and monthly usage of tickets, AI agents, and voice minutes.
    Calculates overage charges and provides approaching-limit warnings.

    Usage:
        service = UsageTrackingService()

        # Increment ticket usage for today
        result = service.increment_ticket_usage(company_id=uuid, count=5)

        # Check if approaching limit
        status = service.check_approaching_limit(company_id=uuid)

        # Get monthly usage history
        history = service.get_usage_history(company_id=uuid, months=6)
    """

    def __init__(self) -> None:
        """Initialize the usage tracking service."""

    # ── Validation Helpers ───────────────────────────────────────────────

    @staticmethod
    def _validate_company_id(company_id: Any) -> str:
        """
        Validate and normalize company_id.

        BC-001: All operations validate company_id.
        Accepts UUID or str, returns string representation.

        Args:
            company_id: Company identifier (UUID or str)

        Returns:
            String representation of the company_id

        Raises:
            UsageTrackingError: If company_id is invalid
        """
        if company_id is None:
            raise UsageTrackingError("company_id is required")

        if isinstance(company_id, UUID):
            return str(company_id)

        if isinstance(company_id, str):
            company_id = company_id.strip()
            if not company_id:
                raise UsageTrackingError("company_id cannot be empty")
            return company_id

        raise UsageTrackingError(
            f"Invalid company_id type: {type(company_id).__name__}. "
            "Expected UUID or str."
        )

    @staticmethod
    def _round_money(amount: Decimal) -> Decimal:
        """
        Round a Decimal amount to 2 decimal places (currency precision).

        BC-002: All money calculations use Decimal.

        Args:
            amount: Decimal amount to round

        Returns:
            Rounded Decimal with 2 decimal places
        """
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _get_ticket_limit(self, db: Session, company_id: str) -> int:
        """
        Get the ticket limit for a company from its subscription.

        Looks up the active subscription tier and resolves the
        monthly ticket limit from VARIANT_LIMITS.

        Args:
            db: Database session
            company_id: Company ID string

        Returns:
            Monthly ticket limit (int)
        """
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id == company_id,
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )

        if not subscription:
            return DEFAULT_TICKET_LIMIT

        # Try extended model helper first, then schema fallback
        limits = None
        try:
            limits = get_variant_limits(subscription.tier)
        except Exception:
            pass

        if not limits:
            try:
                limits = VARIANT_LIMITS.get(VariantType(subscription.tier), {})
            except Exception:
                limits = {}

        return limits.get("monthly_tickets", DEFAULT_TICKET_LIMIT)

    def _get_or_create_daily_record(
        self,
        db: Session,
        company_id: str,
        target_date: date,
    ) -> UsageRecord:
        """
        Get or create a daily usage record for a company.

        Upsert pattern: queries first; if no record exists for the
        given date, creates a new one with zeroed counters.

        Args:
            db: Database session
            company_id: Company ID string
            target_date: Date to look up / create for

        Returns:
            UsageRecord instance (attached to session)
        """
        record = (
            db.query(UsageRecord)
            .filter(
                UsageRecord.company_id == company_id,
                UsageRecord.record_date == target_date,
            )
            .first()
        )

        if record is None:
            record = UsageRecord(
                id=str(uuid.uuid4()),
                company_id=company_id,
                record_date=target_date,
                record_month=target_date.strftime("%Y-%m"),
                tickets_used=0,
                ai_agents_used=0,
                voice_minutes_used=Decimal("0.00"),
                overage_tickets=0,
                overage_charges=Decimal("0.00"),
                created_at=datetime.now(timezone.utc),
            )
            db.add(record)
            db.flush()

        return record

    # ── Public API ───────────────────────────────────────────────────────

    def increment_ticket_usage(
        self,
        company_id: Any,
        count: int = 1,
    ) -> Dict[str, Any]:
        """
        Increment today's ticket usage for a company.

        Uses the upsert pattern: finds today's UsageRecord (or creates one),
        then increments ``tickets_used`` by ``count``.

        Args:
            company_id: Company UUID or str
            count: Number of tickets to add (default 1)

        Returns:
            Dict with updated usage stats:
                - company_id, record_date, tickets_used (daily),
                  record_month

        Raises:
            UsageTrackingError: If company_id is invalid or count is negative
        """
        company_id_str = self._validate_company_id(company_id)

        if count < 0:
            raise UsageTrackingError("count must be non-negative")

        today = datetime.now(timezone.utc).date()

        with SessionLocal() as db:
            record = self._get_or_create_daily_record(db, company_id_str, today)
            record.tickets_used = (record.tickets_used or 0) + count
            db.commit()
            db.refresh(record)

            logger.info(
                "ticket_usage_incremented " "company_id=%s date=%s count=%s total=%s",
                company_id_str,
                today.isoformat(),
                count,
                record.tickets_used,
            )

            return {
                "company_id": company_id_str,
                "record_date": today.isoformat(),
                "record_month": record.record_month,
                "tickets_used": record.tickets_used,
            }

    def increment_voice_usage(
        self,
        company_id: Any,
        minutes: Any,
    ) -> Dict[str, Any]:
        """
        Increment voice minutes for today for a company.

        Args:
            company_id: Company UUID or str
            minutes: Voice minutes to add (int, float, or Decimal)

        Returns:
            Dict with updated voice usage stats:
                - company_id, record_date, voice_minutes_used (daily),
                  record_month

        Raises:
            UsageTrackingError: If company_id is invalid or minutes are negative
        """
        company_id_str = self._validate_company_id(company_id)

        # BC-002: Convert to Decimal immediately
        voice_decimal = Decimal(str(minutes))
        if voice_decimal < 0:
            raise UsageTrackingError("minutes must be non-negative")

        today = datetime.now(timezone.utc).date()

        with SessionLocal() as db:
            record = self._get_or_create_daily_record(db, company_id_str, today)
            current = record.voice_minutes_used or Decimal("0.00")
            record.voice_minutes_used = self._round_money(current + voice_decimal)
            db.commit()
            db.refresh(record)

            logger.info(
                "voice_usage_incremented " "company_id=%s date=%s minutes=%s total=%s",
                company_id_str,
                today.isoformat(),
                voice_decimal,
                record.voice_minutes_used,
            )

            return {
                "company_id": company_id_str,
                "record_date": today.isoformat(),
                "record_month": record.record_month,
                "voice_minutes_used": str(record.voice_minutes_used),
            }

    def get_current_usage(
        self,
        company_id: Any,
        month: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get current month's aggregated usage for a company.

        Sums tickets_used and voice_minutes_used from all daily records
        for the specified month. Includes ticket_limit, usage_percentage,
        approaching_limit (80% threshold), limit_exceeded, and overage
        calculation.

        Args:
            company_id: Company UUID or str
            month: Month string in YYYY-MM format (default: current month)

        Returns:
            Dict with comprehensive usage information:
                - company_id, record_month, tickets_used, ticket_limit,
                  voice_minutes_used, ai_agents_used,
                  usage_percentage, approaching_limit, limit_exceeded,
                  overage_tickets, overage_charges, overage_rate,
                  tickets_remaining
        """
        company_id_str = self._validate_company_id(company_id)

        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")

        with SessionLocal() as db:
            # Aggregate all daily records for the month
            agg = (
                db.query(
                    func.coalesce(func.sum(UsageRecord.tickets_used), 0).label(
                        "total_tickets"
                    ),
                    func.coalesce(func.sum(UsageRecord.ai_agents_used), 0).label(
                        "total_ai_agents"
                    ),
                    func.coalesce(
                        func.sum(UsageRecord.voice_minutes_used), Decimal("0.00")
                    ).label("total_voice_minutes"),
                    func.coalesce(func.sum(UsageRecord.overage_tickets), 0).label(
                        "total_overage_tickets"
                    ),
                    func.coalesce(
                        func.sum(UsageRecord.overage_charges), Decimal("0.00")
                    ).label("total_overage_charges"),
                )
                .filter(
                    UsageRecord.company_id == company_id_str,
                    UsageRecord.record_month == month,
                )
                .first()
            )

            tickets_used = int(agg.total_tickets)
            ai_agents_used = int(agg.total_ai_agents)
            voice_minutes_used = agg.total_voice_minutes
            overage_tickets = int(agg.total_overage_tickets)
            overage_charges = agg.total_overage_charges

            ticket_limit = self._get_ticket_limit(db, company_id_str)

            # Calculate usage percentage (0.0 to 1.0+)
            if ticket_limit > 0:
                usage_percentage = round(tickets_used / ticket_limit, 4)
            else:
                usage_percentage = 0.0

            approaching_limit = usage_percentage >= float(DEFAULT_APPROACHING_THRESHOLD)
            limit_exceeded = tickets_used > ticket_limit
            tickets_remaining = max(0, ticket_limit - tickets_used)

            # Recalculate overage based on current totals
            overage_result = self.calculate_overage(
                company_id_str, tickets_used, ticket_limit
            )

            logger.info(
                "current_usage_retrieved "
                "company_id=%s month=%s tickets=%s limit=%s pct=%.2f%%",
                company_id_str,
                month,
                tickets_used,
                ticket_limit,
                usage_percentage * 100,
            )

            return {
                "company_id": company_id_str,
                "record_month": month,
                "tickets_used": tickets_used,
                "ticket_limit": ticket_limit,
                "ai_agents_used": ai_agents_used,
                "voice_minutes_used": str(voice_minutes_used),
                "usage_percentage": usage_percentage,
                "approaching_limit": approaching_limit,
                "limit_exceeded": limit_exceeded,
                "tickets_remaining": tickets_remaining,
                "overage_tickets": overage_result["overage_tickets"],
                "overage_charges": str(overage_result["overage_charges"]),
                "overage_rate": str(overage_result["overage_rate"]),
            }

    def get_usage_percentage(self, company_id: Any) -> float:
        """
        Get the current usage ratio (tickets_used / ticket_limit).

        Returns a float between 0.0 and 1.0 under normal usage.
        Values above 1.0 indicate the limit has been exceeded.

        Args:
            company_id: Company UUID or str

        Returns:
            Float ratio of tickets used to ticket limit (0.0+)
        """
        company_id_str = self._validate_company_id(company_id)
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        with SessionLocal() as db:
            total = (
                db.query(func.coalesce(func.sum(UsageRecord.tickets_used), 0))
                .filter(
                    UsageRecord.company_id == company_id_str,
                    UsageRecord.record_month == month,
                )
                .scalar()
            )

            tickets_used = int(total)
            ticket_limit = self._get_ticket_limit(db, company_id_str)

            if ticket_limit <= 0:
                return 0.0

            return round(tickets_used / ticket_limit, 4)

    def check_approaching_limit(
        self,
        company_id: Any,
        threshold: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Check if usage is approaching the plan ticket limit.

        Compares the current month's ticket usage against the configured
        ticket limit. Returns whether the threshold has been crossed
        and detailed breakdown.

        Args:
            company_id: Company UUID or str
            threshold: Warning threshold as a float (default 0.8 = 80%)

        Returns:
            Dict with:
                - approaching_limit (bool): True if usage >= threshold
                - usage_percentage (float): Current ratio (0.0 to 1.0+)
                - tickets_used (int): Total tickets this month
                - ticket_limit (int): Plan ticket limit
                - tickets_remaining (int): Tickets left before limit
                - threshold (float): The threshold used
        """
        company_id_str = self._validate_company_id(company_id)
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        with SessionLocal() as db:
            total = (
                db.query(func.coalesce(func.sum(UsageRecord.tickets_used), 0))
                .filter(
                    UsageRecord.company_id == company_id_str,
                    UsageRecord.record_month == month,
                )
                .scalar()
            )

            tickets_used = int(total)
            ticket_limit = self._get_ticket_limit(db, company_id_str)

            if ticket_limit > 0:
                usage_percentage = round(tickets_used / ticket_limit, 4)
            else:
                usage_percentage = 0.0

            approaching = usage_percentage >= threshold
            tickets_remaining = max(0, ticket_limit - tickets_used)

            logger.info(
                "approaching_limit_check "
                "company_id=%s month=%s pct=%.2f%% threshold=%.0f%% approaching=%s",
                company_id_str,
                month,
                usage_percentage * 100,
                threshold * 100,
                approaching,
            )

            return {
                "approaching_limit": approaching,
                "usage_percentage": usage_percentage,
                "tickets_used": tickets_used,
                "ticket_limit": ticket_limit,
                "tickets_remaining": tickets_remaining,
                "threshold": threshold,
            }

    def calculate_overage(
        self,
        company_id: Any,
        tickets_used: int,
        ticket_limit: int,
    ) -> Dict[str, Any]:
        """
        Calculate overage tickets and charges.

        Overage is charged at $0.10 per ticket over the plan limit.
        BC-002: All money calculations use Decimal (never float).

        Args:
            company_id: Company UUID or str
            tickets_used: Total tickets used in the period
            ticket_limit: Plan ticket limit for the period

        Returns:
            Dict with:
                - overage_tickets (int): Tickets over the limit
                - overage_charges (Decimal): Total overage charge
                - overage_rate (Decimal): Rate per overage ticket ($0.10)
                - tickets_used (int): Input tickets_used
                - ticket_limit (int): Input ticket_limit
        """
        # Validate but don't store (pure calculation)
        company_id_str = self._validate_company_id(company_id)

        overage_tickets = max(0, tickets_used - ticket_limit)

        # BC-002: Decimal arithmetic for all money
        overage_charges = Decimal(str(overage_tickets)) * OVERAGE_RATE_PER_TICKET
        overage_charges = self._round_money(overage_charges)

        logger.info(
            "overage_calculated "
            "company_id=%s tickets=%s limit=%s overage_tickets=%s charges=%s",
            company_id_str,
            tickets_used,
            ticket_limit,
            overage_tickets,
            overage_charges,
        )

        return {
            "overage_tickets": overage_tickets,
            "overage_charges": overage_charges,
            "overage_rate": OVERAGE_RATE_PER_TICKET,
            "tickets_used": tickets_used,
            "ticket_limit": ticket_limit,
        }

    def get_usage_history(
        self,
        company_id: Any,
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Get monthly usage history for a company.

        Groups daily UsageRecords by record_month and aggregates
        tickets_used, overage_tickets, and overage_charges.
        Returns the most recent ``months`` entries, ordered newest first.

        Args:
            company_id: Company UUID or str
            months: Number of months to retrieve (default 12)

        Returns:
            List of dicts, each with:
                - record_month (str): YYYY-MM
                - tickets_used (int)
                - overage_tickets (int)
                - overage_charges (str): Decimal string
        """
        company_id_str = self._validate_company_id(company_id)

        if months < 1:
            raise UsageTrackingError("months must be >= 1")

        with SessionLocal() as db:
            rows = (
                db.query(
                    UsageRecord.record_month,
                    func.coalesce(func.sum(UsageRecord.tickets_used), 0).label(
                        "total_tickets"
                    ),
                    func.coalesce(func.sum(UsageRecord.overage_tickets), 0).label(
                        "total_overage_tickets"
                    ),
                    func.coalesce(
                        func.sum(UsageRecord.overage_charges), Decimal("0.00")
                    ).label("total_overage_charges"),
                )
                .filter(UsageRecord.company_id == company_id_str)
                .group_by(UsageRecord.record_month)
                .order_by(UsageRecord.record_month.desc())
                .limit(months)
                .all()
            )

            history = [
                {
                    "record_month": row.record_month,
                    "tickets_used": int(row.total_tickets),
                    "overage_tickets": int(row.total_overage_tickets),
                    "overage_charges": str(row.total_overage_charges),
                }
                for row in rows
            ]

            logger.info(
                "usage_history_retrieved "
                "company_id=%s months_requested=%s months_returned=%s",
                company_id_str,
                months,
                len(history),
            )

            return history

    def record_overage(
        self,
        company_id: Any,
        overage_tickets: int,
        overage_charges: Any,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Record overage data on today's (or a specific date's) usage record.

        Updates the overage_tickets and overage_charges fields on the
        matching daily UsageRecord. Creates the record if it does not
        exist yet for the target date.

        Args:
            company_id: Company UUID or str
            overage_tickets: Number of tickets over the limit
            overage_charges: Total overage charge amount (int, float, Decimal, or str)
            target_date: Date to update (default: today)

        Returns:
            Dict with:
                - company_id, record_date, record_month,
                  overage_tickets, overage_charges

        Raises:
            UsageTrackingError: If company_id is invalid or amounts are negative
        """
        company_id_str = self._validate_company_id(company_id)

        if overage_tickets < 0:
            raise UsageTrackingError("overage_tickets must be non-negative")

        # BC-002: Convert to Decimal
        charges_decimal = Decimal(str(overage_charges))
        if charges_decimal < 0:
            raise UsageTrackingError("overage_charges must be non-negative")

        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        with SessionLocal() as db:
            record = self._get_or_create_daily_record(db, company_id_str, target_date)
            record.overage_tickets = overage_tickets
            record.overage_charges = self._round_money(charges_decimal)
            db.commit()
            db.refresh(record)

            logger.info(
                "overage_recorded "
                "company_id=%s date=%s overage_tickets=%s charges=%s",
                company_id_str,
                target_date.isoformat(),
                overage_tickets,
                record.overage_charges,
            )

            return {
                "company_id": company_id_str,
                "record_date": target_date.isoformat(),
                "record_month": record.record_month,
                "overage_tickets": record.overage_tickets,
                "overage_charges": str(record.overage_charges),
            }

    def get_daily_usage(
        self,
        company_id: Any,
        target_date: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Get usage for a company on a specific date.

        Args:
            company_id: Company UUID or str
            target_date: The date to query

        Returns:
            Dict with daily usage details, or None if no record exists:
                - company_id, record_date, record_month,
                  tickets_used, ai_agents_used, voice_minutes_used,
                  overage_tickets, overage_charges, created_at
        """
        company_id_str = self._validate_company_id(company_id)

        with SessionLocal() as db:
            record = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id_str,
                    UsageRecord.record_date == target_date,
                )
                .first()
            )

            if record is None:
                logger.info(
                    "daily_usage_not_found " "company_id=%s date=%s",
                    company_id_str,
                    target_date.isoformat(),
                )
                return None

            return {
                "company_id": record.company_id,
                "record_date": record.record_date.isoformat(),
                "record_month": record.record_month,
                "tickets_used": record.tickets_used or 0,
                "ai_agents_used": record.ai_agents_used or 0,
                "voice_minutes_used": str(record.voice_minutes_used or Decimal("0.00")),
                "overage_tickets": record.overage_tickets or 0,
                "overage_charges": str(record.overage_charges or Decimal("0.00")),
                "created_at": (
                    record.created_at.isoformat() if record.created_at else None
                ),
            }

    # ═════════════════════════════════════════════════════════════════════
    # Day 3.2: Redis-Based Real-Time Usage Tracking (BG-13)
    # ═════════════════════════════════════════════════════════════════════

    async def _get_redis(self):
        """Get Redis client for usage tracking."""
        from app.core.redis import get_redis

        return await get_redis()

    def _build_usage_redis_key(self, company_id: str, period_id: str) -> str:
        """
        Build Redis key for usage counter.

        Key format: parwa:{company_id}:usage:{period_id}:tickets
        Period ID is typically YYYY-MM format for monthly tracking.
        """
        return f"parwa:{company_id}:usage:{period_id}:tickets"

    async def increment_ticket_usage_redis(
        self,
        company_id: Any,
        count: int = 1,
    ) -> Dict[str, Any]:
        """
        Increment ticket usage in Redis with atomic INCR.

        BG-13: Real-time usage counting via Redis before PostgreSQL persistence.
        This method is called at ticket creation time for immediate tracking.

        Args:
            company_id: Company UUID or str
            count: Number of tickets to add (default 1)

        Returns:
            Dict with:
                - company_id, period_id, tickets_used (Redis count),
                  ticket_limit, remaining, is_over_limit

        Raises:
            UsageTrackingError: If company_id is invalid
        """
        company_id_str = self._validate_company_id(company_id)

        if count < 0:
            raise UsageTrackingError("count must be non-negative")

        period_id = datetime.now(timezone.utc).strftime("%Y-%m")
        redis_key = self._build_usage_redis_key(company_id_str, period_id)

        try:
            redis = await self._get_redis()

            # Atomic INCR
            new_count = await redis.incrby(redis_key, count)

            # Set TTL to 35 days (longer than a month for safety)
            await redis.expire(redis_key, 35 * 24 * 3600)

            # Get ticket limit for comparison
            with SessionLocal() as db:
                ticket_limit = self._get_ticket_limit(db, company_id_str)

            remaining = max(0, ticket_limit - new_count)
            is_over_limit = new_count > ticket_limit

            logger.info(
                "redis_usage_incremented "
                "company_id=%s period=%s count=%s total=%s limit=%s over=%s",
                company_id_str,
                period_id,
                count,
                new_count,
                ticket_limit,
                is_over_limit,
            )

            return {
                "company_id": company_id_str,
                "period_id": period_id,
                "tickets_used": new_count,
                "ticket_limit": ticket_limit,
                "tickets_remaining": remaining,
                "is_over_limit": is_over_limit,
            }

        except Exception as e:
            logger.error(
                "redis_usage_increment_failed company_id=%s error=%s",
                company_id_str,
                str(e),
            )
            # Fallback: still increment in PostgreSQL
            return self.increment_ticket_usage(company_id_str, count)

    async def get_realtime_usage(
        self,
        company_id: Any,
    ) -> Dict[str, Any]:
        """
        Get real-time ticket usage from Redis.

        Args:
            company_id: Company UUID or str

        Returns:
            Dict with:
                - company_id, period_id, tickets_used (Redis),
                  ticket_limit, usage_percentage, is_over_limit
        """
        company_id_str = self._validate_company_id(company_id)
        period_id = datetime.now(timezone.utc).strftime("%Y-%m")
        redis_key = self._build_usage_redis_key(company_id_str, period_id)

        try:
            redis = await self._get_redis()
            tickets_used = int(await redis.get(redis_key) or 0)

            with SessionLocal() as db:
                ticket_limit = self._get_ticket_limit(db, company_id_str)

            usage_percentage = round(tickets_used / max(ticket_limit, 1), 4)
            is_over_limit = tickets_used > ticket_limit

            return {
                "company_id": company_id_str,
                "period_id": period_id,
                "tickets_used": tickets_used,
                "ticket_limit": ticket_limit,
                "usage_percentage": usage_percentage,
                "is_over_limit": is_over_limit,
                "source": "redis",
            }

        except Exception as e:
            logger.warning(
                "redis_usage_get_failed company_id=%s error=%s",
                company_id_str,
                str(e),
            )
            # Fallback to PostgreSQL
            return self.get_current_usage(company_id_str)

    async def check_and_block_on_overage(
        self,
        company_id: Any,
    ) -> Dict[str, Any]:
        """
        BG-13: Check if company is over limit and should be blocked.

        Called before creating a new ticket. Returns blocking info.

        Args:
            company_id: Company UUID or str

        Returns:
            Dict with:
                - blocked: bool - whether to block ticket creation
                - tickets_used, ticket_limit, overage_count
                - message: human-readable status
                - overage_charge: Decimal if over limit
        """
        company_id_str = self._validate_company_id(company_id)

        # Get real-time usage from Redis
        usage = await self.get_realtime_usage(company_id_str)

        tickets_used = usage["tickets_used"]
        ticket_limit = usage["ticket_limit"]
        overage_count = max(0, tickets_used - ticket_limit)

        if tickets_used >= ticket_limit:
            # Calculate overage charge at $0.10/ticket
            overage_charge = Decimal(str(overage_count)) * OVERAGE_RATE_PER_TICKET

            return {
                "blocked": True,
                "company_id": company_id_str,
                "tickets_used": tickets_used,
                "ticket_limit": ticket_limit,
                "overage_count": overage_count,
                "overage_charge": str(self._round_money(overage_charge)),
                "overage_rate": str(OVERAGE_RATE_PER_TICKET),
                "message": (
                    f"Usage limit exceeded. You have used {tickets_used} of "
                    f"{ticket_limit} monthly tickets. Overage: "
                    f"${overage_charge} for {overage_count} extra tickets."
                ),
            }

        return {
            "blocked": False,
            "company_id": company_id_str,
            "tickets_used": tickets_used,
            "ticket_limit": ticket_limit,
            "overage_count": 0,
            "overage_charge": "0.00",
            "message": f"Within limit: {tickets_used}/{ticket_limit} tickets used.",
        }

    async def sync_redis_to_postgres(
        self,
        company_id: Any,
        period_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sync Redis usage counter to PostgreSQL for persistence.

        Called by Celery beat task for reconciliation.

        Args:
            company_id: Company UUID or str
            period_id: Period to sync (default: current month)

        Returns:
            Dict with sync status
        """
        company_id_str = self._validate_company_id(company_id)

        if period_id is None:
            period_id = datetime.now(timezone.utc).strftime("%Y-%m")

        redis_key = self._build_usage_redis_key(company_id_str, period_id)

        try:
            redis = await self._get_redis()
            redis_count = int(await redis.get(redis_key) or 0)

            # Get PostgreSQL count
            with SessionLocal() as db:
                pg_count = (
                    db.query(func.coalesce(func.sum(UsageRecord.tickets_used), 0))
                    .filter(
                        UsageRecord.company_id == company_id_str,
                        UsageRecord.record_month == period_id,
                    )
                    .scalar()
                )
                pg_count = int(pg_count)

                # If Redis count is higher, update PostgreSQL
                if redis_count > pg_count:
                    diff = redis_count - pg_count
                    today = datetime.now(timezone.utc).date()
                    record = self._get_or_create_daily_record(db, company_id_str, today)
                    record.tickets_used = redis_count
                    db.commit()

                    logger.info(
                        "usage_synced_to_postgres "
                        "company_id=%s period=%s redis=%s pg_before=%s diff=%s",
                        company_id_str,
                        period_id,
                        redis_count,
                        pg_count,
                        diff,
                    )

                return {
                    "status": "synced",
                    "company_id": company_id_str,
                    "period_id": period_id,
                    "redis_count": redis_count,
                    "postgres_count": pg_count,
                    "difference": redis_count - pg_count,
                }

        except Exception as e:
            logger.error(
                "usage_sync_failed company_id=%s error=%s",
                company_id_str,
                str(e),
            )
            return {
                "status": "error",
                "company_id": company_id_str,
                "error": str(e),
            }


# ── Singleton Service ────────────────────────────────────────────────────

_usage_tracking_service: Optional[UsageTrackingService] = None


def get_usage_tracking_service() -> UsageTrackingService:
    """
    Get the usage tracking service singleton.

    Returns:
        Shared UsageTrackingService instance
    """
    global _usage_tracking_service
    if _usage_tracking_service is None:
        _usage_tracking_service = UsageTrackingService()
    return _usage_tracking_service
