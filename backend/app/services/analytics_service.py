"""Billing Analytics Service (MF8-MF11) — Spending analytics, budget alerts, usage."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import UsageRecord

logger = logging.getLogger("parwa.services.billing_analytics")


class BillingAnalyticsService:
    """MF8-MF11: Billing analytics, spending trends, budget alerts, usage."""

    def get_spending_summary(self, company_id: str) -> Dict[str, Any]:
        """Monthly spend, overage costs, variant costs, projected next month."""
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            current_month = now.strftime("%Y-%m")

            # Get subscription
            sub = (
                db.query(Subscription)
                .filter(Subscription.company_id == company_id)
                .order_by(Subscription.created_at.desc())
                .first()
            )

            base_price = Decimal("0.00")
            if sub:
                from database.models.billing_extended import get_variant_limits

                limits = get_variant_limits(sub.tier) if sub.tier else None
                if limits:
                    base_price = limits.get("price_monthly", Decimal("0.00"))

            # Get current month usage
            usage = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id,
                    UsageRecord.record_month == current_month,
                )
                .first()
            )

            overage_cost = usage.overage_charges if usage else Decimal("0.00")

            total = base_price + (overage_cost or Decimal("0.00"))

            return {
                "month": current_month,
                "base_plan": str(base_price),
                "overage_cost": str(overage_cost or Decimal("0.00")),
                "variant_costs": "0.00",
                "total_spend": str(total),
                "projected_next_month": str(base_price),
            }

    def get_channel_breakdown(self, company_id: str) -> Dict[str, Any]:
        """Per-channel spend (email, chat, voice, SMS)."""
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            current_month = now.strftime("%Y-%m")

            usage = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id,
                    UsageRecord.record_month == current_month,
                )
                .first()
            )

            return {
                "month": current_month,
                "channels": {
                    "email": {
                        "tickets": usage.tickets_used if usage else 0,
                        "cost": "included",
                    },
                    "chat": {"tickets": 0, "cost": "included"},
                    "voice": {
                        "minutes": (
                            float(usage.voice_minutes_used)
                            if usage and usage.voice_minutes_used
                            else 0.0
                        ),
                        "cost": "0.00",
                    },
                    "sms": {"count": 0, "cost": "0.00"},
                },
            }

    def get_spending_trend(
        self, company_id: str, months: int = 6
    ) -> List[Dict[str, Any]]:
        """6 month trend data."""
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            months_data = []

            for i in range(months - 1, -1, -1):
                dt = now - timedelta(days=30 * i)
                month_str = dt.strftime("%Y-%m")

                usage = (
                    db.query(UsageRecord)
                    .filter(
                        UsageRecord.company_id == company_id,
                        UsageRecord.record_month == month_str,
                    )
                    .first()
                )

                months_data.append(
                    {
                        "month": month_str,
                        "tickets_used": usage.tickets_used if usage else 0,
                        "overage_cost": (
                            str(usage.overage_charges)
                            if usage and usage.overage_charges
                            else "0.00"
                        ),
                    }
                )

            return months_data

    def get_budget_alert(self, company_id: str) -> Dict[str, Any]:
        """Check if near budget thresholds (50%, 75%, 90%, 100%)."""
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            current_month = now.strftime("%Y-%m")

            sub = (
                db.query(Subscription)
                .filter(Subscription.company_id == company_id)
                .order_by(Subscription.created_at.desc())
                .first()
            )

            ticket_limit = 2000
            if sub:
                from database.models.billing_extended import get_variant_limits

                limits = get_variant_limits(sub.tier) if sub.tier else None
                if limits:
                    ticket_limit = limits.get("monthly_tickets", 2000)

            usage = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id,
                    UsageRecord.record_month == current_month,
                )
                .first()
            )

            tickets_used = usage.tickets_used if usage else 0
            percentage = (tickets_used / ticket_limit * 100) if ticket_limit > 0 else 0

            thresholds = [50, 75, 90, 100]
            alerts = []
            for t in thresholds:
                if percentage >= t:
                    alerts.append(t)

            return {
                "usage_percentage": round(percentage, 1),
                "tickets_used": tickets_used,
                "ticket_limit": ticket_limit,
                "thresholds_triggered": alerts,
                "is_over_limit": percentage >= 100,
            }

    def get_voice_usage(self, company_id: str) -> Dict[str, Any]:
        """Voice minutes used this period (Phase 1: track only)."""
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            current_month = now.strftime("%Y-%m")

            usage = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id,
                    UsageRecord.record_month == current_month,
                )
                .first()
            )

            minutes = 0.0
            if usage and usage.voice_minutes_used:
                minutes = float(usage.voice_minutes_used)

            return {
                "period": current_month,
                "voice_minutes_used": minutes,
                "status": "tracked",
            }

    def get_sms_usage(self, company_id: str) -> Dict[str, Any]:
        """SMS count this period (Phase 1: track only)."""
        return {
            "period": datetime.now(timezone.utc).strftime("%Y-%m"),
            "sms_count": 0,
            "status": "tracked",
        }


_analytics_service_instance: Optional[BillingAnalyticsService] = None


def get_billing_analytics_service() -> BillingAnalyticsService:
    """Get singleton BillingAnalyticsService instance."""
    global _analytics_service_instance
    if _analytics_service_instance is None:
        _analytics_service_instance = BillingAnalyticsService()
    return _analytics_service_instance
