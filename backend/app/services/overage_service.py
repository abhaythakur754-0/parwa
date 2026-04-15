"""
Overage Service (F-024, BC-002, BC-004, BC-006)

Handles daily overage detection and charging:
- Calculate ticket usage vs plan limits
- Calculate overage charges at $0.10/ticket
- Submit charges to Paddle
- Send email and Socket.io notifications
- Maintain audit trail

Overage Rules:
- Overage rate: $0.10 per ticket over plan limit
- Charged daily for previous day's usage
- Notification sent via email (Brevo) + Socket.io
- Overage tracked per company per day

BC-002: All money calculations use Decimal (never float)
BC-004: Celery task integration
BC-006: Email notification via Brevo
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.schemas.billing import (
    OverageChargeInfo,
    UsageInfo,
    VariantType,
    VARIANT_LIMITS,
)
from app.clients.paddle_client import (
    PaddleClient,
    PaddleError,
    get_paddle_client,
)
from database.base import SessionLocal
from database.models.billing import Subscription, OverageCharge
from database.models.billing_extended import UsageRecord, get_variant_limits
from database.models.core import Company

import os
OVERAGE_PRICE_ID = os.getenv("PADDLE_OVERAGE_PRICE_ID", "pri_overage")

logger = logging.getLogger("parwa.services.overage")

# Overage rate: $0.10 per ticket
OVERAGE_RATE_PER_TICKET = Decimal("0.10")

# Minimum overage charge to process (avoid tiny charges)
MINIMUM_OVERAGE_CHARGE = Decimal("1.00")


class OverageError(Exception):
    """Base exception for overage errors."""
    pass


class OverageService:
    """
    Overage detection and charging service.

    Usage:
        service = OverageService()

        # Calculate daily overage for a company
        result = await service.process_daily_overage(
            company_id=uuid,
            target_date=date(2024, 1, 15),
        )

        # Get usage info for dashboard
        usage = await service.get_usage_info(company_id)
    """

    def __init__(self, paddle_client: Optional[PaddleClient] = None):
        self._paddle_client = paddle_client

    async def _get_paddle(self) -> PaddleClient:
        """Get Paddle client (lazy initialization)."""
        if self._paddle_client is None:
            self._paddle_client = get_paddle_client()
        return self._paddle_client

    async def process_daily_overage(
        self,
        company_id: UUID,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Process daily overage for a company.

        This is the main entry point for the daily cron job.

        Steps:
        1. Get company's subscription and plan limits
        2. Get ticket usage for the target date
        3. Calculate overage (if any)
        4. Create overage charge record
        5. Submit charge to Paddle (if above minimum)
        6. Send notifications
        7. Return result

        Args:
            company_id: Company UUID
            target_date: Date to process (default: yesterday)

        Returns:
            Dict with overage details and charge status
        """
        if target_date is None:
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        with SessionLocal() as db:
            # Get company with subscription
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()

            if not company:
                raise OverageError(f"Company {company_id} not found")

            # Get active subscription
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.status == "active",
            ).first()

            if not subscription:
                logger.info(
                    "overage_skip_no_subscription company_id=%s",
                    company_id,
                )
                return {
                    "status": "skipped",
                    "reason": "no_active_subscription",
                    "company_id": str(company_id),
                    "date": target_date.isoformat(),
                }

            # Get plan limits
            variant = subscription.tier
            limits = get_variant_limits(variant)
            if not limits:
                limits = VARIANT_LIMITS.get(VariantType(variant), {})

            ticket_limit = limits.get("monthly_tickets", 2000)

            # Get or create usage record for the date
            usage_record = db.query(UsageRecord).filter(
                UsageRecord.company_id == str(company_id),
                UsageRecord.record_date == target_date,
            ).first()

            if not usage_record:
                # Create usage record (ticket count would come from ticket system)
                usage_record = UsageRecord(
                    company_id=str(company_id),
                    record_date=target_date,
                    record_month=target_date.strftime("%Y-%m"),
                    tickets_used=0,  # Will be updated by ticket system
                )
                db.add(usage_record)
                db.commit()
                db.refresh(usage_record)

            # Get month-to-date usage (current day's record is already included
            # because it was committed before this query and has same record_month)
            month_usage = db.query(
                func.sum(UsageRecord.tickets_used).label("total_tickets")
            ).filter(
                UsageRecord.company_id == str(company_id),
                UsageRecord.record_month == target_date.strftime("%Y-%m"),
            ).scalar() or 0

            total_tickets = int(month_usage)

            # Calculate overage
            overage_result = self._calculate_overage(total_tickets, ticket_limit)

            # Check if there's actual overage
            if overage_result["overage_tickets"] <= 0:
                logger.info(
                    "overage_none company_id=%s tickets=%s limit=%s",
                    company_id,
                    total_tickets,
                    ticket_limit,
                )
                return {
                    "status": "no_overage",
                    "company_id": str(company_id),
                    "date": target_date.isoformat(),
                    "tickets_used": total_tickets,
                    "ticket_limit": ticket_limit,
                    "overage_tickets": 0,
                    "overage_charges": "0.00",
                }

            # Create overage charge record
            overage_charge = OverageCharge(
                company_id=str(company_id),
                date=target_date,
                tickets_over_limit=overage_result["overage_tickets"],
                charge_amount=overage_result["overage_charges"],
                status="pending",
            )
            db.add(overage_charge)

            # Update usage record
            usage_record.overage_tickets = overage_result["overage_tickets"]
            usage_record.overage_charges = overage_result["overage_charges"]

            db.commit()
            db.refresh(overage_charge)

            # Check if charge is above minimum
            if overage_result["overage_charges"] < MINIMUM_OVERAGE_CHARGE:
                logger.info(
                    "overage_below_minimum company_id=%s charge=%s",
                    company_id,
                    overage_result["overage_charges"],
                )
                overage_charge.status = "skipped_below_minimum"
                db.commit()

                return {
                    "status": "below_minimum",
                    "company_id": str(company_id),
                    "date": target_date.isoformat(),
                    "overage_tickets": overage_result["overage_tickets"],
                    "overage_charges": str(overage_result["overage_charges"]),
                    "minimum_charge": str(MINIMUM_OVERAGE_CHARGE),
                }

            # Submit charge to Paddle
            try:
                paddle = await self._get_paddle()
                charge_result = await self._submit_paddle_charge(
                    paddle=paddle,
                    company=company,
                    subscription=subscription,
                    overage_charge=overage_charge,
                )

                overage_charge.status = "charged"
                overage_charge.paddle_charge_id = charge_result.get("charge_id")
                db.commit()

                logger.info(
                    "overage_charged company_id=%s amount=%s paddle_id=%s",
                    company_id,
                    overage_result["overage_charges"],
                    charge_result.get("charge_id"),
                )

                # Send notifications
                await self._send_notifications(
                    company=company,
                    overage_charge=overage_charge,
                    usage_info={
                        "tickets_used": total_tickets,
                        "ticket_limit": ticket_limit,
                        "overage_tickets": overage_result["overage_tickets"],
                        "overage_charges": overage_result["overage_charges"],
                    },
                )

                return {
                    "status": "charged",
                    "company_id": str(company_id),
                    "date": target_date.isoformat(),
                    "overage_tickets": overage_result["overage_tickets"],
                    "overage_charges": str(overage_result["overage_charges"]),
                    "paddle_charge_id": charge_result.get("charge_id"),
                    "overage_charge_id": overage_charge.id,
                }

            except PaddleError as e:
                logger.error(
                    "overage_paddle_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                overage_charge.status = "failed"
                db.commit()

                return {
                    "status": "failed",
                    "company_id": str(company_id),
                    "date": target_date.isoformat(),
                    "overage_tickets": overage_result["overage_tickets"],
                    "overage_charges": str(overage_result["overage_charges"]),
                    "error": str(e),
                }

    def _calculate_overage(
        self,
        tickets_used: int,
        ticket_limit: int,
    ) -> Dict[str, Any]:
        """
        Calculate overage tickets and charges.

        BC-002: All money calculations use Decimal.

        Args:
            tickets_used: Total tickets used
            ticket_limit: Plan ticket limit

        Returns:
            Dict with overage_tickets, overage_charges, overage_rate
        """
        overage_tickets = max(0, tickets_used - ticket_limit)
        overage_charges = Decimal(str(overage_tickets)) * OVERAGE_RATE_PER_TICKET

        # Round to 2 decimal places
        overage_charges = overage_charges.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return {
            "overage_tickets": overage_tickets,
            "overage_charges": overage_charges,
            "overage_rate": OVERAGE_RATE_PER_TICKET,
            "tickets_used": tickets_used,
            "ticket_limit": ticket_limit,
        }

    async def _submit_paddle_charge(
        self,
        paddle: PaddleClient,
        company: Company,
        subscription: Subscription,
        overage_charge: OverageCharge,
    ) -> Dict[str, Any]:
        """
        Submit overage charge to Paddle.

        Uses Paddle's transaction API to create a one-time charge.

        Args:
            paddle: Paddle client
            company: Company model
            subscription: Subscription model
            overage_charge: OverageCharge model

        Returns:
            Dict with charge_id and status
        """
        try:
            # Create one-time charge in Paddle
            result = await paddle.create_transaction(
                customer_id=company.paddle_customer_id,
                items=[{
                    "price_id": OVERAGE_PRICE_ID,
                    "quantity": overage_charge.tickets_over_limit,
                }],
                custom_data={
                    "company_id": str(company.id),
                    "charge_type": "overage",
                    "overage_date": overage_charge.date.isoformat(),
                },
            )

            return {
                "charge_id": result.get("data", {}).get("id"),
                "status": "submitted",
            }

        except Exception as e:
            logger.error(
                "paddle_charge_failed company_id=%s error=%s",
                company.id,
                str(e),
            )
            raise

    async def _send_notifications(
        self,
        company: Company,
        overage_charge: OverageCharge,
        usage_info: Dict[str, Any],
    ) -> None:
        """
        Send overage notifications via email and Socket.io.

        BC-006: Email notification via Brevo.

        Args:
            company: Company model
            overage_charge: OverageCharge model
            usage_info: Dict with usage details
        """
        # Prepare notification data
        notification_data = {
            "company_id": str(company.id),
            "overage_date": overage_charge.date.isoformat(),
            "tickets_used": usage_info["tickets_used"],
            "ticket_limit": usage_info["ticket_limit"],
            "overage_tickets": usage_info["overage_tickets"],
            "overage_charges": str(usage_info["overage_charges"]),
            "charge_id": overage_charge.id,
        }

        # Send Socket.io notification
        try:
            from app.core.event_emitter import emit_billing_event

            await emit_billing_event(
                company_id=str(company.id),
                event_type="overage_charged",
                data=notification_data,
            )

            logger.info(
                "overage_socket_notification_sent company_id=%s",
                company.id,
            )

        except Exception as e:
            logger.warning(
                "overage_socket_notification_failed company_id=%s error=%s",
                company.id,
                str(e),
            )

        # Send email notification
        try:
            from app.services.email_service import send_overage_notification

            await send_overage_notification(
                company_id=str(company.id),
                usage_info=notification_data,
            )

            logger.info(
                "overage_email_notification_sent company_id=%s",
                company.id,
            )

        except Exception as e:
            logger.warning(
                "overage_email_notification_failed company_id=%s error=%s",
                company.id,
                str(e),
            )

    async def get_usage_info(
        self,
        company_id: UUID,
        record_month: Optional[str] = None,
    ) -> UsageInfo:
        """
        Get usage information for a company.

        Args:
            company_id: Company UUID
            record_month: Month in YYYY-MM format (default: current month)

        Returns:
            UsageInfo with current usage details
        """
        if record_month is None:
            record_month = datetime.now(timezone.utc).strftime("%Y-%m")

        with SessionLocal() as db:
            # Get subscription
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                return UsageInfo(
                    company_id=company_id,
                    record_month=record_month,
                    tickets_used=0,
                    ticket_limit=0,
                    overage_tickets=0,
                    overage_charges=Decimal("0.00"),
                    usage_percentage=0.0,
                    approaching_limit=False,
                    limit_exceeded=False,
                )

            # Get plan limits
            limits = get_variant_limits(subscription.tier)
            if not limits:
                limits = VARIANT_LIMITS.get(
                    VariantType(subscription.tier), {}
                )

            ticket_limit = limits.get("monthly_tickets", 2000)

            # Get month usage
            month_usage = db.query(
                func.sum(UsageRecord.tickets_used).label("total_tickets"),
                func.sum(UsageRecord.overage_tickets).label("total_overage"),
                func.sum(UsageRecord.overage_charges).label("total_charges"),
            ).filter(
                UsageRecord.company_id == str(company_id),
                UsageRecord.record_month == record_month,
            ).first()

            tickets_used = int(month_usage.total_tickets or 0)
            overage_tickets = int(month_usage.total_overage or 0)
            overage_charges = month_usage.total_charges or Decimal("0.00")

            # Calculate percentage
            usage_percentage = (tickets_used / ticket_limit * 100) if ticket_limit > 0 else 0.0

            return UsageInfo(
                company_id=company_id,
                record_month=record_month,
                tickets_used=tickets_used,
                ticket_limit=ticket_limit,
                overage_tickets=overage_tickets,
                overage_charges=overage_charges,
                usage_percentage=round(usage_percentage, 2),
                approaching_limit=usage_percentage >= 80,
                limit_exceeded=tickets_used > ticket_limit,
            )

    async def get_overage_history(
        self,
        company_id: UUID,
        limit: int = 30,
    ) -> List[OverageChargeInfo]:
        """
        Get overage charge history for a company.

        Args:
            company_id: Company UUID
            limit: Maximum records to return

        Returns:
            List of OverageChargeInfo records
        """
        with SessionLocal() as db:
            charges = db.query(OverageCharge).filter(
                OverageCharge.company_id == str(company_id),
            ).order_by(
                OverageCharge.date.desc()
            ).limit(limit).all()

            return [
                OverageChargeInfo(
                    id=UUID(charge.id),
                    company_id=UUID(charge.company_id),
                    date=charge.date,
                    tickets_over_limit=charge.tickets_over_limit,
                    charge_amount=charge.charge_amount,
                    status=charge.status,
                    created_at=charge.created_at,
                )
                for charge in charges
            ]

    async def record_ticket_usage(
        self,
        company_id: UUID,
        ticket_count: int,
        record_date: Optional[date] = None,
    ) -> UsageRecord:
        """
        Record ticket usage for a company on a specific date.

        This would typically be called by the ticket system.

        Args:
            company_id: Company UUID
            ticket_count: Number of tickets to record
            record_date: Date to record (default: today)

        Returns:
            UsageRecord
        """
        if record_date is None:
            record_date = datetime.now(timezone.utc).date()

        with SessionLocal() as db:
            # Get or create usage record
            usage_record = db.query(UsageRecord).filter(
                UsageRecord.company_id == str(company_id),
                UsageRecord.record_date == record_date,
            ).first()

            if usage_record:
                # Increment existing record (not replace)
                usage_record.tickets_used = (usage_record.tickets_used or 0) + ticket_count
            else:
                # Create new record
                usage_record = UsageRecord(
                    company_id=str(company_id),
                    record_date=record_date,
                    record_month=record_date.strftime("%Y-%m"),
                    tickets_used=ticket_count,
                )
                db.add(usage_record)

            db.commit()
            db.refresh(usage_record)

            return usage_record

    async def check_approaching_limit(
        self,
        company_id: UUID,
        threshold: float = 80.0,
    ) -> Dict[str, Any]:
        """
        Check if company is approaching their plan limit.

        Args:
            company_id: Company UUID
            threshold: Percentage threshold (default: 80%)

        Returns:
            Dict with approaching status and usage details
        """
        usage = await self.get_usage_info(company_id)

        return {
            "approaching_limit": usage.usage_percentage >= threshold,
            "limit_exceeded": usage.limit_exceeded,
            "usage_percentage": usage.usage_percentage,
            "tickets_used": usage.tickets_used,
            "ticket_limit": usage.ticket_limit,
            "tickets_remaining": max(0, usage.ticket_limit - usage.tickets_used),
            "threshold": threshold,
        }


# ── Singleton Service ────────────────────────────────────────────────────

_overage_service: Optional[OverageService] = None


def get_overage_service() -> OverageService:
    """Get the overage service singleton."""
    global _overage_service
    if _overage_service is None:
        _overage_service = OverageService()
    return _overage_service
