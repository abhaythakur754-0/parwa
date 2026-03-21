"""
Manager Time Calculator Service.

Calculates estimated manager time savings based on PARWA variant usage.
This service is used for anti-arbitrage value demonstration and ROI calculations.

Manager Time Formula:
- Mini PARWA: 0.25 hrs/day saved per unit
- PARWA Junior: 0.5 hrs/day saved per unit
- PARWA High: 1.0 hrs/day saved per unit

The formula accounts for:
- Number of agents deployed
- Active channels
- Ticket volume handled
- Refund processing complexity
- Escalation rate reduction
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ManagerTimeEstimate(BaseModel):
    """Model for manager time estimate response."""

    variant: str
    units: int
    daily_hours_saved: float
    weekly_hours_saved: float
    monthly_hours_saved: float
    annual_hours_saved: float
    hourly_rate: float
    daily_savings_usd: float
    monthly_savings_usd: float
    annual_savings_usd: float
    breakdown: Dict[str, Any] = Field(default_factory=dict)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


# Manager time coefficients per variant (hours saved per day per unit)
VARIANT_TIME_COEFFICIENTS = {
    "mini": {
        "base_hours_per_unit": 0.25,
        "max_channels": 4,  # faq, email, chat, sms
        "refund_time_saved": 0.02,  # per refund
        "escalation_reduction": 0.05,  # hours saved per escalation avoided
        "description": "Mini PARWA handles simple FAQ and routing tasks"
    },
    "parwa": {
        "base_hours_per_unit": 0.5,
        "max_channels": 6,  # faq, email, chat, sms, voice, video
        "refund_time_saved": 0.05,  # more complex refund handling
        "escalation_reduction": 0.10,
        "description": "PARWA Junior handles medium complexity with recommendations"
    },
    "parwa_high": {
        "base_hours_per_unit": 1.0,
        "max_channels": 8,  # all channels including advanced
        "refund_time_saved": 0.10,  # complex refund analysis
        "escalation_reduction": 0.20,
        "description": "PARWA High handles complex queries with full analysis"
    }
}


# Default hourly rates by region (USD)
DEFAULT_HOURLY_RATES = {
    "us": 75.0,
    "eu": 65.0,
    "asia": 45.0,
    "default": 60.0
}


class ManagerTimeCalculator:
    """
    Manager Time Calculator Service.

    Calculates estimated manager time savings based on PARWA variant deployment.

    Usage:
        calculator = ManagerTimeCalculator()
        estimate = calculator.calculate(
            variant="parwa",
            units=1,
            hourly_rate=75.0
        )
        print(f"Daily hours saved: {estimate.daily_hours_saved}")
    """

    def __init__(
        self,
        default_hourly_rate: float = 60.0,
        region: str = "default"
    ):
        """
        Initialize Manager Time Calculator.

        Args:
            default_hourly_rate: Default hourly rate for manager time (USD)
            region: Region code for default hourly rate lookup
        """
        self.default_hourly_rate = default_hourly_rate or DEFAULT_HOURLY_RATES.get(region, 60.0)
        self.region = region

    def get_coefficient(self, variant: str) -> Dict[str, Any]:
        """
        Get time coefficient for a variant.

        Args:
            variant: Variant name (mini, parwa, parwa_high)

        Returns:
            Dict with coefficient data
        """
        variant_lower = variant.lower().replace("-", "_").replace(" ", "_")

        # Handle variant name variations
        if variant_lower in ["parwa_junior", "parwa"]:
            variant_lower = "parwa"
        elif variant_lower in ["parwa_high", "high"]:
            variant_lower = "parwa_high"
        elif variant_lower in ["mini", "mini_parwa"]:
            variant_lower = "mini"

        return VARIANT_TIME_COEFFICIENTS.get(variant_lower, VARIANT_TIME_COEFFICIENTS["mini"])

    def calculate(
        self,
        variant: str,
        units: int = 1,
        active_channels: Optional[List[str]] = None,
        monthly_tickets: int = 0,
        monthly_refunds: int = 0,
        hourly_rate: Optional[float] = None,
        custom_factors: Optional[Dict[str, float]] = None
    ) -> ManagerTimeEstimate:
        """
        Calculate manager time savings estimate.

        Args:
            variant: PARWA variant (mini, parwa, parwa_high)
            units: Number of agent units deployed
            active_channels: List of active channels
            monthly_tickets: Average monthly ticket volume
            monthly_refunds: Average monthly refund requests
            hourly_rate: Manager hourly rate (USD)
            custom_factors: Custom adjustment factors

        Returns:
            ManagerTimeEstimate with detailed breakdown
        """
        # Get variant coefficients
        coeff = self.get_coefficient(variant)
        variant_key = self._normalize_variant_name(variant)

        # Calculate base time saved
        base_hours = coeff["base_hours_per_unit"] * units

        # Channel multiplier
        channel_multiplier = 1.0
        if active_channels:
            max_channels = coeff["max_channels"]
            active_count = len(active_channels)
            channel_multiplier = min(active_count / max_channels, 1.5)

        # Ticket volume adjustment
        ticket_factor = 1.0
        if monthly_tickets > 0:
            # More tickets = more time saved, with diminishing returns
            ticket_factor = 1.0 + min(monthly_tickets / 1000, 0.5)

        # Refund time saved
        refund_time = 0.0
        if monthly_refunds > 0:
            refund_time = monthly_refunds * coeff["refund_time_saved"] / 30  # Daily average

        # Apply custom factors
        if custom_factors:
            for factor_name, factor_value in custom_factors.items():
                if factor_name == "volume_multiplier":
                    base_hours *= factor_value
                elif factor_name == "complexity_adjustment":
                    base_hours += factor_value

        # Calculate daily hours saved
        daily_hours = (base_hours * channel_multiplier * ticket_factor) + refund_time

        # Calculate time periods
        weekly_hours = daily_hours * 7
        monthly_hours = daily_hours * 30
        annual_hours = daily_hours * 365

        # Calculate USD savings
        rate = hourly_rate or self.default_hourly_rate
        daily_savings = daily_hours * rate
        monthly_savings = monthly_hours * rate
        annual_savings = annual_hours * rate

        # Create breakdown
        breakdown = {
            "base_hours_per_unit": coeff["base_hours_per_unit"],
            "units": units,
            "channel_multiplier": round(channel_multiplier, 2),
            "ticket_factor": round(ticket_factor, 2),
            "refund_time_daily": round(refund_time, 4),
            "variant_description": coeff["description"]
        }

        estimate = ManagerTimeEstimate(
            variant=variant_key,
            units=units,
            daily_hours_saved=round(daily_hours, 4),
            weekly_hours_saved=round(weekly_hours, 4),
            monthly_hours_saved=round(monthly_hours, 4),
            annual_hours_saved=round(annual_hours, 4),
            hourly_rate=rate,
            daily_savings_usd=round(daily_savings, 2),
            monthly_savings_usd=round(monthly_savings, 2),
            annual_savings_usd=round(annual_savings, 2),
            breakdown=breakdown
        )

        logger.info("manager_time_calculated", extra={
            "variant": variant_key,
            "units": units,
            "daily_hours": daily_hours,
            "annual_savings": annual_savings
        })

        return estimate

    def calculate_batch(
        self,
        deployments: List[Dict[str, Any]],
        hourly_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate manager time savings for multiple deployments.

        Args:
            deployments: List of deployment dicts with variant, units, etc.
            hourly_rate: Manager hourly rate (USD)

        Returns:
            Dict with total savings and individual estimates
        """
        total_daily_hours = 0.0
        total_annual_savings = 0.0
        estimates = []

        for deployment in deployments:
            estimate = self.calculate(
                variant=deployment.get("variant", "mini"),
                units=deployment.get("units", 1),
                active_channels=deployment.get("active_channels"),
                monthly_tickets=deployment.get("monthly_tickets", 0),
                monthly_refunds=deployment.get("monthly_refunds", 0),
                hourly_rate=hourly_rate or deployment.get("hourly_rate")
            )

            estimates.append(estimate)
            total_daily_hours += estimate.daily_hours_saved
            total_annual_savings += estimate.annual_savings_usd

        return {
            "total_daily_hours_saved": round(total_daily_hours, 4),
            "total_annual_savings_usd": round(total_annual_savings, 2),
            "estimates": estimates,
            "deployment_count": len(deployments)
        }

    def compare_variants(
        self,
        units: int = 1,
        hourly_rate: Optional[float] = None
    ) -> Dict[str, ManagerTimeEstimate]:
        """
        Compare manager time savings across all variants.

        Args:
            units: Number of units to compare
            hourly_rate: Manager hourly rate (USD)

        Returns:
            Dict mapping variant name to estimate
        """
        return {
            "mini": self.calculate("mini", units, hourly_rate=hourly_rate),
            "parwa": self.calculate("parwa", units, hourly_rate=hourly_rate),
            "parwa_high": self.calculate("parwa_high", units, hourly_rate=hourly_rate)
        }

    def get_roi_projection(
        self,
        variant: str,
        units: int,
        monthly_cost: float,
        hourly_rate: Optional[float] = None,
        months: int = 12
    ) -> Dict[str, Any]:
        """
        Calculate ROI projection for a deployment.

        Args:
            variant: PARWA variant
            units: Number of units
            monthly_cost: Monthly cost of the deployment
            hourly_rate: Manager hourly rate (USD)
            months: Number of months to project

        Returns:
            Dict with ROI analysis
        """
        estimate = self.calculate(variant, units, hourly_rate=hourly_rate)

        total_investment = monthly_cost * months
        total_savings = estimate.monthly_savings_usd * months
        net_savings = total_savings - total_investment
        roi_percentage = (net_savings / total_investment * 100) if total_investment > 0 else 0

        return {
            "variant": estimate.variant,
            "units": units,
            "projection_months": months,
            "total_investment_usd": round(total_investment, 2),
            "total_savings_usd": round(total_savings, 2),
            "net_savings_usd": round(net_savings, 2),
            "roi_percentage": round(roi_percentage, 2),
            "payback_days": round(total_investment / estimate.daily_savings_usd, 1) if estimate.daily_savings_usd > 0 else None,
            "monthly_cost": monthly_cost,
            "monthly_savings": round(estimate.monthly_savings_usd, 2)
        }

    def _normalize_variant_name(self, variant: str) -> str:
        """Normalize variant name for consistent output."""
        variant_lower = variant.lower().replace("-", "_").replace(" ", "_")

        if variant_lower in ["parwa_junior", "parwa"]:
            return "parwa"
        elif variant_lower in ["parwa_high", "high"]:
            return "parwa_high"
        elif variant_lower in ["mini", "mini_parwa"]:
            return "mini"

        return variant_lower


# Module-level convenience functions
def calculate_manager_time(
    variant: str,
    units: int = 1,
    hourly_rate: Optional[float] = None
) -> ManagerTimeEstimate:
    """
    Convenience function to calculate manager time savings.

    Args:
        variant: PARWA variant (mini, parwa, parwa_high)
        units: Number of agent units
        hourly_rate: Manager hourly rate (USD)

    Returns:
        ManagerTimeEstimate
    """
    calculator = ManagerTimeCalculator()
    return calculator.calculate(variant, units, hourly_rate=hourly_rate)


def get_default_calculator() -> ManagerTimeCalculator:
    """Get a default ManagerTimeCalculator instance."""
    return ManagerTimeCalculator()
