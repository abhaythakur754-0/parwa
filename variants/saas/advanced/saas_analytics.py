"""
SaaS Analytics for SaaS Advanced Module.

Provides SaaS analytics including:
- MRR/ARR calculation
- Customer acquisition metrics
- Churn rate tracking
- LTV (Lifetime Value) calculation
- CAC (Customer Acquisition Cost)
- ARPU (Average Revenue Per User)
- Cohort analysis
- Revenue attribution
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MetricPeriod(str, Enum):
    """Metric aggregation periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class CustomerSegment(str, Enum):
    """Customer segments."""
    ENTERPRISE = "enterprise"
    MID_MARKET = "mid_market"
    SMB = "smb"
    STARTUP = "startup"
    FREE_TRIAL = "free_trial"


@dataclass
class RevenueMetrics:
    """Revenue metrics for a period."""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    mrr: float = 0.0
    arr: float = 0.0
    new_mrr: float = 0.0
    expansion_mrr: float = 0.0
    contraction_mrr: float = 0.0
    churned_mrr: float = 0.0
    net_new_mrr: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "mrr": round(self.mrr, 2),
            "arr": round(self.arr, 2),
            "new_mrr": round(self.new_mrr, 2),
            "expansion_mrr": round(self.expansion_mrr, 2),
            "contraction_mrr": round(self.contraction_mrr, 2),
            "churned_mrr": round(self.churned_mrr, 2),
            "net_new_mrr": round(self.net_new_mrr, 2),
        }


@dataclass
class CustomerMetrics:
    """Customer metrics for a period."""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_customers: int = 0
    new_customers: int = 0
    churned_customers: int = 0
    net_new_customers: int = 0
    active_customers: int = 0
    trial_customers: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_customers": self.total_customers,
            "new_customers": self.new_customers,
            "churned_customers": self.churned_customers,
            "net_new_customers": self.net_new_customers,
            "active_customers": self.active_customers,
            "trial_customers": self.trial_customers,
        }


@dataclass
class CohortData:
    """Cohort analysis data."""
    cohort_month: str = ""
    cohort_size: int = 0
    retention_by_month: Dict[int, float] = field(default_factory=dict)
    revenue_by_month: Dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "cohort_month": self.cohort_month,
            "cohort_size": self.cohort_size,
            "retention_by_month": self.retention_by_month,
            "revenue_by_month": {k: round(v, 2) for k, v in self.revenue_by_month.items()},
        }


class SaaSAnalytics:
    """
    Provides SaaS-specific analytics.

    Features:
    - MRR/ARR calculation
    - Customer acquisition
    - Churn tracking
    - LTV/CAC
    - ARPU
    - Cohort analysis
    - Revenue attribution
    """

    def __init__(
        self,
        client_id: str = "",
        currency: str = "USD"
    ):
        """
        Initialize SaaS analytics.

        Args:
            client_id: Client identifier
            currency: Currency for metrics
        """
        self.client_id = client_id
        self.currency = currency

        self._revenue_history: List[RevenueMetrics] = []
        self._customer_history: List[CustomerMetrics] = []
        self._cohorts: Dict[str, CohortData] = {}

    async def calculate_mrr(
        self,
        subscriptions: List[Dict[str, Any]]
    ) -> RevenueMetrics:
        """
        Calculate Monthly Recurring Revenue.

        Args:
            subscriptions: List of subscription data

        Returns:
            RevenueMetrics with MRR details
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        active_mrr = 0.0
        new_mrr = 0.0
        expansion_mrr = 0.0
        contraction_mrr = 0.0
        churned_mrr = 0.0

        for sub in subscriptions:
            status = sub.get("status", "active")
            amount = sub.get("amount", 0)
            billing_cycle = sub.get("billing_cycle", "monthly")

            # Convert to monthly
            if billing_cycle == "annual":
                monthly = amount / 12
            elif billing_cycle == "quarterly":
                monthly = amount / 3
            else:
                monthly = amount

            if status == "active":
                active_mrr += monthly

                # Check if new this period
                created = sub.get("created_at")
                if created:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created_dt >= period_start:
                        new_mrr += monthly

            elif status == "churned":
                churned_mrr += monthly

            # Check for upgrades/downgrades
            previous_amount = sub.get("previous_amount", 0)
            if previous_amount > 0:
                change = monthly - (previous_amount / 12 if billing_cycle == "annual" else previous_amount)
                if change > 0:
                    expansion_mrr += change
                elif change < 0:
                    contraction_mrr += abs(change)

        net_new_mrr = new_mrr + expansion_mrr - contraction_mrr - churned_mrr

        metrics = RevenueMetrics(
            period_start=period_start,
            period_end=now,
            mrr=active_mrr,
            arr=active_mrr * 12,
            new_mrr=new_mrr,
            expansion_mrr=expansion_mrr,
            contraction_mrr=contraction_mrr,
            churned_mrr=churned_mrr,
            net_new_mrr=net_new_mrr,
        )

        self._revenue_history.append(metrics)

        logger.info(
            "MRR calculated",
            extra={
                "client_id": self.client_id,
                "mrr": active_mrr,
                "net_new_mrr": net_new_mrr,
            }
        )

        return metrics

    async def calculate_arr(
        self,
        subscriptions: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate Annual Recurring Revenue.

        Args:
            subscriptions: List of subscription data

        Returns:
            ARR value
        """
        mrr = await self.calculate_mrr(subscriptions)
        return mrr.arr

    async def calculate_churn_rate(
        self,
        period_start: datetime,
        period_end: datetime,
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate churn rate.

        Args:
            period_start: Period start
            period_end: Period end
            customer_data: Customer movement data

        Returns:
            Dict with churn metrics
        """
        starting_customers = customer_data.get("starting_customers", 0)
        churned_customers = customer_data.get("churned_customers", 0)
        new_customers = customer_data.get("new_customers", 0)

        # Customer churn rate
        customer_churn = (churned_customers / starting_customers * 100) if starting_customers > 0 else 0

        # Revenue churn
        starting_mrr = customer_data.get("starting_mrr", 0)
        churned_mrr = customer_data.get("churned_mrr", 0)
        revenue_churn = (churned_mrr / starting_mrr * 100) if starting_mrr > 0 else 0

        # Net churn (including expansion)
        expansion_mrr = customer_data.get("expansion_mrr", 0)
        net_revenue_churn = ((churned_mrr - expansion_mrr) / starting_mrr * 100) if starting_mrr > 0 else 0

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "customer_churn_rate": round(customer_churn, 2),
            "revenue_churn_rate": round(revenue_churn, 2),
            "net_revenue_churn_rate": round(net_revenue_churn, 2),
            "starting_customers": starting_customers,
            "churned_customers": churned_customers,
            "new_customers": new_customers,
            "ending_customers": starting_customers - churned_customers + new_customers,
        }

    async def calculate_ltv(
        self,
        arpu: float,
        churn_rate: float,
        gross_margin: float = 0.8
    ) -> Dict[str, Any]:
        """
        Calculate Customer Lifetime Value.

        Args:
            arpu: Average Revenue Per User
            churn_rate: Monthly churn rate (decimal)
            gross_margin: Gross margin percentage

        Returns:
            Dict with LTV details
        """
        if churn_rate <= 0:
            churn_rate = 0.01  # Minimum 1% churn

        # LTV = ARPU * Gross Margin / Churn Rate
        ltv = (arpu * gross_margin) / churn_rate

        # Calculate customer lifespan
        lifespan_months = 1 / churn_rate

        return {
            "ltv": round(ltv, 2),
            "arpu": round(arpu, 2),
            "churn_rate": round(churn_rate * 100, 2),
            "gross_margin": gross_margin,
            "customer_lifespan_months": round(lifespan_months, 1),
            "currency": self.currency,
        }

    async def calculate_cac(
        self,
        marketing_spend: float,
        sales_spend: float,
        new_customers: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate Customer Acquisition Cost.

        Args:
            marketing_spend: Marketing expenditure
            sales_spend: Sales expenditure
            new_customers: New customers acquired
            period_days: Period length in days

        Returns:
            Dict with CAC details
        """
        total_spend = marketing_spend + sales_spend

        cac = total_spend / new_customers if new_customers > 0 else 0

        return {
            "cac": round(cac, 2),
            "total_spend": round(total_spend, 2),
            "marketing_spend": round(marketing_spend, 2),
            "sales_spend": round(sales_spend, 2),
            "new_customers": new_customers,
            "period_days": period_days,
            "currency": self.currency,
        }

    async def calculate_arpu(
        self,
        total_revenue: float,
        total_customers: int,
        period: MetricPeriod = MetricPeriod.MONTHLY
    ) -> Dict[str, Any]:
        """
        Calculate Average Revenue Per User.

        Args:
            total_revenue: Total revenue for period
            total_customers: Total customers
            period: Metric period

        Returns:
            Dict with ARPU details
        """
        arpu = total_revenue / total_customers if total_customers > 0 else 0

        return {
            "arpu": round(arpu, 2),
            "total_revenue": round(total_revenue, 2),
            "total_customers": total_customers,
            "period": period.value,
            "currency": self.currency,
        }

    async def calculate_ltv_cac_ratio(
        self,
        ltv: float,
        cac: float
    ) -> Dict[str, Any]:
        """
        Calculate LTV:CAC ratio.

        Args:
            ltv: Lifetime Value
            cac: Customer Acquisition Cost

        Returns:
            Dict with ratio analysis
        """
        ratio = ltv / cac if cac > 0 else 0

        if ratio >= 3:
            health = "excellent"
            recommendation = "Strong unit economics, scale acquisition"
        elif ratio >= 2:
            health = "good"
            recommendation = "Healthy ratio, optimize for efficiency"
        elif ratio >= 1:
            health = "concerning"
            recommendation = "Review acquisition efficiency"
        else:
            health = "critical"
            recommendation = "Urgent: Reduce CAC or increase LTV"

        return {
            "ratio": round(ratio, 2),
            "ltv": round(ltv, 2),
            "cac": round(cac, 2),
            "health": health,
            "recommendation": recommendation,
            "payback_months": round(cac / (ltv / 12), 1) if ltv > 0 else None,
        }

    async def analyze_cohorts(
        self,
        customer_data: List[Dict[str, Any]],
        months: int = 12
    ) -> List[CohortData]:
        """
        Perform cohort analysis.

        Args:
            customer_data: Customer data with signup and activity
            months: Number of months to analyze

        Returns:
            List of CohortData
        """
        cohorts: Dict[str, CohortData] = {}

        for customer in customer_data:
            signup_date = customer.get("signup_date")
            if not signup_date:
                continue

            signup_dt = datetime.fromisoformat(signup_date.replace("Z", "+00:00"))
            cohort_month = signup_dt.strftime("%Y-%m")

            if cohort_month not in cohorts:
                cohorts[cohort_month] = CohortData(
                    cohort_month=cohort_month,
                    cohort_size=0,
                    retention_by_month={},
                    revenue_by_month={},
                )

            cohorts[cohort_month].cohort_size += 1

            # Track activity
            activity_months = customer.get("active_months", [])
            revenue_history = customer.get("revenue_history", [])

            for i, month in enumerate(activity_months):
                if i + 1 not in cohorts[cohort_month].retention_by_month:
                    cohorts[cohort_month].retention_by_month[i + 1] = 0
                cohorts[cohort_month].retention_by_month[i + 1] += 1

            for i, revenue in enumerate(revenue_history):
                if i + 1 not in cohorts[cohort_month].revenue_by_month:
                    cohorts[cohort_month].revenue_by_month[i + 1] = 0
                cohorts[cohort_month].revenue_by_month[i + 1] += revenue

        # Convert retention counts to percentages
        for cohort in cohorts.values():
            for month in cohort.retention_by_month:
                cohort.retention_by_month[month] = round(
                    cohort.retention_by_month[month] / cohort.cohort_size * 100, 2
                )

        self._cohorts = cohorts

        return list(cohorts.values())

    async def attribute_revenue(
        self,
        revenue_data: List[Dict[str, Any]],
        attribution_model: str = "last_touch"
    ) -> Dict[str, Any]:
        """
        Attribute revenue to channels.

        Args:
            revenue_data: Revenue with channel attribution
            attribution_model: Attribution model (first_touch, last_touch, linear)

        Returns:
            Dict with revenue attribution
        """
        channel_revenue: Dict[str, float] = defaultdict(float)
        channel_customers: Dict[str, int] = defaultdict(int)

        for record in revenue_data:
            amount = record.get("amount", 0)
            channels = record.get("channels", [])

            if not channels:
                channels = ["direct"]

            if attribution_model == "last_touch":
                channel = channels[-1] if channels else "direct"
                channel_revenue[channel] += amount
                channel_customers[channel] += 1
            elif attribution_model == "first_touch":
                channel = channels[0] if channels else "direct"
                channel_revenue[channel] += amount
                channel_customers[channel] += 1
            else:  # linear
                if channels:
                    share = amount / len(channels)
                    for channel in channels:
                        channel_revenue[channel] += share
                        channel_customers[channel] += 1 / len(channels)
                else:
                    channel_revenue["direct"] += amount
                    channel_customers["direct"] += 1

        total = sum(channel_revenue.values())

        return {
            "attribution_model": attribution_model,
            "channels": {
                channel: {
                    "revenue": round(rev, 2),
                    "customers": round(customers),
                    "percentage": round(rev / total * 100, 2) if total > 0 else 0,
                }
                for channel, rev, customers in zip(
                    channel_revenue.keys(),
                    channel_revenue.values(),
                    channel_customers.values()
                )
            },
            "total_revenue": round(total, 2),
            "currency": self.currency,
        }

    async def get_saas_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive SaaS dashboard metrics.

        Returns:
            Dict with all dashboard metrics
        """
        # Get latest metrics
        latest_revenue = self._revenue_history[-1] if self._revenue_history else RevenueMetrics()

        return {
            "revenue": latest_revenue.to_dict(),
            "cohorts": len(self._cohorts),
            "currency": self.currency,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def project_growth(
        self,
        current_mrr: float,
        growth_rate: float,
        churn_rate: float,
        months: int = 12
    ) -> Dict[str, Any]:
        """
        Project MRR growth.

        Args:
            current_mrr: Current MRR
            growth_rate: Monthly growth rate (decimal)
            churn_rate: Monthly churn rate (decimal)
            months: Months to project

        Returns:
            Dict with projection
        """
        projections = []
        mrr = current_mrr

        for month in range(1, months + 1):
            new_mrr = mrr * growth_rate
            lost_mrr = mrr * churn_rate
            mrr = mrr + new_mrr - lost_mrr

            projections.append({
                "month": month,
                "projected_mrr": round(mrr, 2),
                "projected_arr": round(mrr * 12, 2),
                "new_mrr": round(new_mrr, 2),
                "churned_mrr": round(lost_mrr, 2),
            })

        return {
            "starting_mrr": current_mrr,
            "growth_rate": round(growth_rate * 100, 2),
            "churn_rate": round(churn_rate * 100, 2),
            "ending_mrr": round(mrr, 2),
            "ending_arr": round(mrr * 12, 2),
            "projections": projections,
        }

    async def segment_analysis(
        self,
        customer_segments: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Analyze metrics by customer segment.

        Args:
            customer_segments: Customers grouped by segment

        Returns:
            Dict with segment analysis
        """
        analysis = {}

        for segment, customers in customer_segments.items():
            if not customers:
                continue

            mrr = sum(c.get("mrr", 0) for c in customers)
            count = len(customers)
            arpu = mrr / count if count > 0 else 0

            analysis[segment] = {
                "customer_count": count,
                "mrr": round(mrr, 2),
                "arpu": round(arpu, 2),
                "percentage_of_total": None,  # Filled later
            }

        # Calculate percentages
        total_mrr = sum(s["mrr"] for s in analysis.values())
        for segment in analysis:
            analysis[segment]["percentage_of_total"] = round(
                analysis[segment]["mrr"] / total_mrr * 100, 2
            ) if total_mrr > 0 else 0

        return {
            "segments": analysis,
            "total_mrr": round(total_mrr, 2),
            "total_customers": sum(s["customer_count"] for s in analysis.values()),
        }


# Export for testing
__all__ = [
    "SaaSAnalytics",
    "RevenueMetrics",
    "CustomerMetrics",
    "CohortData",
    "MetricPeriod",
    "CustomerSegment",
]
