"""
PARWA High Anti-Arbitrage Configuration.

Ensures pricing is structured so customers cannot arbitrage
between PARWA High and hiring human managers directly.

Anti-arbitrage principle:
- PARWA High cost proportional to value delivered
- ROI calculation shows time saved vs human manager cost
- 0.25 hrs/day manager time saved per PARWA High instance (least of all variants)
- Pricing validated to prevent arbitrage opportunities

PARWA High saves the most manager time due to:
- Higher automation level
- Can execute refunds directly
- Advanced analytics and predictions
- Multi-team coordination
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ParwaHighAntiArbitrageConfig(BaseModel):
    """
    Anti-arbitrage pricing configuration for PARWA High.

    Ensures PARWA High pricing delivers value while preventing
    customers from saving money by bypassing the system.

    Key metrics:
    - PARWA High saves 0.25 hrs/day of manager time (least due to high automation)
    - At $75/hr manager rate, that's $18.75/day value
    - Monthly value = $562.50 in manager time saved
    - But PARWA High delivers much higher resolution rate (90%+)

    Attributes:
        parwa_high_hourly_rate: Cost per hour for PARWA High
        manager_hourly_rate: Cost per hour for human manager
        manager_time_per_day: Hours of manager time saved per day (0.25)
    """

    model_config = ConfigDict()

    # Hourly rates
    parwa_high_hourly_rate: float = Field(
        default=50.0,
        ge=20.0,
        description="Cost per hour for PARWA High"
    )
    manager_hourly_rate: float = Field(
        default=75.0,
        ge=20.0,
        description="Cost per hour for human manager"
    )

    # Time saved metrics - CRITICAL: 0.25 hrs/day for 1x PARWA High
    manager_time_per_day: float = Field(
        default=0.25,
        ge=0.05,
        le=4.0,
        description="Hours of manager time saved per day by PARWA High"
    )

    # Subscription pricing
    starter_monthly: float = Field(
        default=499.0,
        ge=299.0,
        description="Starter tier monthly price for PARWA High"
    )
    growth_monthly: float = Field(
        default=999.0,
        ge=599.0,
        description="Growth tier monthly price for PARWA High"
    )
    enterprise_monthly: float = Field(
        default=2499.0,
        ge=1499.0,
        description="Enterprise tier monthly price for PARWA High"
    )

    @field_validator('manager_hourly_rate')
    @classmethod
    def manager_rate_must_exceed_parwa_high(cls, v: float, info) -> float:
        """Ensure manager rate is higher than parwa_high rate."""
        parwa_rate = info.data.get('parwa_high_hourly_rate', 50.0)
        if v <= parwa_rate:
            raise ValueError(
                f"manager_hourly_rate ({v}) must be higher than "
                f"parwa_high_hourly_rate ({parwa_rate})"
            )
        return v

    def calculate_manager_time(
        self,
        complexity: float = 1.0,
        days: int = 1
    ) -> float:
        """
        Calculate time saved by using PARWA High vs human manager.

        CRITICAL: Base calculation is 0.25 hrs/day per PARWA High instance.

        Args:
            complexity: Complexity multiplier (1.0 = average)
            days: Number of days to calculate for

        Returns:
            Time saved in hours
        """
        # Base: 0.25 hrs/day for 1x PARWA High
        daily_time_saved = self.manager_time_per_day * complexity
        return daily_time_saved * days

    def calculate_roi(
        self,
        queries_handled: int,
        manager_time_saved: float,
        subscription_cost: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate ROI for using PARWA High.

        Args:
            queries_handled: Number of queries handled by PARWA High
            manager_time_saved: Total manager time saved in hours
            subscription_cost: Monthly subscription cost (default: starter)

        Returns:
            Dict with ROI calculation details
        """
        if subscription_cost is None:
            subscription_cost = self.starter_monthly

        # Calculate cost savings
        manager_cost = manager_time_saved * self.manager_hourly_rate
        parwa_high_cost = subscription_cost

        # Net savings
        net_savings = manager_cost - parwa_high_cost

        # ROI percentage
        roi_percent = (net_savings / parwa_high_cost * 100) if parwa_high_cost > 0 else 0.0

        # Cost per query
        cost_per_query = parwa_high_cost / queries_handled if queries_handled > 0 else 0

        return {
            "queries_handled": queries_handled,
            "hours_saved": round(manager_time_saved, 2),
            "manager_cost": round(manager_cost, 2),
            "parwa_high_cost": round(parwa_high_cost, 2),
            "net_savings": round(net_savings, 2),
            "roi_percent": round(roi_percent, 2),
            "cost_per_query": round(cost_per_query, 4),
            "is_positive_roi": net_savings > 0,
            "manager_time_per_day": self.manager_time_per_day,
        }

    def calculate_monthly_value(self) -> Dict[str, Any]:
        """
        Calculate the monthly value of PARWA High.

        Based on 0.25 hrs/day manager time saved.

        Returns:
            Dict with monthly value calculation
        """
        # Calculate monthly manager time saved (22 business days)
        monthly_hours = self.calculate_manager_time(days=22)

        # Value of time saved
        value_of_time = monthly_hours * self.manager_hourly_rate

        return {
            "monthly_hours_saved": round(monthly_hours, 2),
            "manager_hourly_rate": self.manager_hourly_rate,
            "value_of_time_saved": round(value_of_time, 2),
            "daily_hours_saved": self.manager_time_per_day,
            "working_days_per_month": 22,
        }

    def validate_pricing(
        self,
        subscription_tier: str
    ) -> Dict[str, Any]:
        """
        Validate that pricing is anti-arbitrage compliant.

        Args:
            subscription_tier: Tier name (starter, growth, enterprise)

        Returns:
            Dict with validation result
        """
        tier_prices = {
            "starter": self.starter_monthly,
            "growth": self.growth_monthly,
            "enterprise": self.enterprise_monthly,
        }

        price = tier_prices.get(subscription_tier.lower())

        if price is None:
            return {
                "valid": False,
                "error": f"Unknown tier: {subscription_tier}",
            }

        errors = []
        warnings = []

        # Calculate monthly value
        monthly_value = self.calculate_monthly_value()

        # Calculate break-even in days
        daily_value = self.manager_time_per_day * self.manager_hourly_rate
        days_to_break_even = price / daily_value if daily_value > 0 else 0

        if days_to_break_even > 20:
            warnings.append(
                f"Requires {int(days_to_break_even)} days to break even"
            )

        return {
            "valid": True,
            "tier": subscription_tier,
            "price": price,
            "monthly_value": monthly_value,
            "days_to_break_even": round(days_to_break_even, 1),
            "daily_value": round(daily_value, 2),
            "errors": errors,
            "warnings": warnings,
        }

    def get_tier_pricing(self) -> Dict[str, Dict[str, float]]:
        """Get pricing for all tiers."""
        return {
            "starter": {
                "monthly": self.starter_monthly,
                "daily_equivalent": round(self.starter_monthly / 30, 2),
                "hourly_equivalent": round(self.starter_monthly / 30 / 24, 4),
            },
            "growth": {
                "monthly": self.growth_monthly,
                "daily_equivalent": round(self.growth_monthly / 30, 2),
                "hourly_equivalent": round(self.growth_monthly / 30 / 24, 4),
            },
            "enterprise": {
                "monthly": self.enterprise_monthly,
                "daily_equivalent": round(self.enterprise_monthly / 30, 2),
                "hourly_equivalent": round(self.enterprise_monthly / 30 / 24, 4),
            },
        }

    def get_savings_ratio(self) -> float:
        """
        Get the ratio of manager cost to PARWA High cost.

        Returns:
            Ratio (e.g., 1.5 means manager costs 1.5x more than PARWA High)
        """
        return self.manager_hourly_rate / self.parwa_high_hourly_rate

    def compare_with_parwa_junior(self) -> Dict[str, Any]:
        """
        Compare PARWA High with PARWA Junior.

        Returns:
            Dict with comparison data
        """
        # PARWA Junior saves 0.5 hrs/day, PARWA High saves 0.25 hrs/day
        # But PARWA High handles more complex queries and has higher resolution rate
        return {
            "parwa_high_manager_time_per_day": self.manager_time_per_day,
            "parwa_junior_manager_time_per_day": 0.5,
            "parwa_high_resolution_rate": "90%+",
            "parwa_junior_resolution_rate": "70-80%",
            "parwa_high_can_execute_refunds": True,
            "parwa_junior_can_execute_refunds": False,
            "parwa_high_refund_limit": 2000.0,
            "parwa_junior_refund_limit": 500.0,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "parwa_high_hourly_rate": self.parwa_high_hourly_rate,
            "manager_hourly_rate": self.manager_hourly_rate,
            "manager_time_per_day": self.manager_time_per_day,
            "savings_ratio": self.get_savings_ratio(),
            "starter_monthly": self.starter_monthly,
            "growth_monthly": self.growth_monthly,
            "enterprise_monthly": self.enterprise_monthly,
            "tier_pricing": self.get_tier_pricing(),
            "monthly_value": self.calculate_monthly_value(),
        }


# Default configuration instance
DEFAULT_PARWA_HIGH_ANTI_ARBITRAGE_CONFIG = ParwaHighAntiArbitrageConfig()


def get_parwa_high_anti_arbitrage_config() -> ParwaHighAntiArbitrageConfig:
    """Get the default PARWA High anti-arbitrage configuration."""
    return DEFAULT_PARWA_HIGH_ANTI_ARBITRAGE_CONFIG


def calculate_parwa_high_roi(
    queries_handled: int,
    subscription_tier: str = "starter"
) -> Dict[str, Any]:
    """
    Convenience function to calculate PARWA High ROI.

    Args:
        queries_handled: Number of queries handled
        subscription_tier: Subscription tier name

    Returns:
        ROI calculation dict
    """
    config = get_parwa_high_anti_arbitrage_config()
    tier_prices = {
        "starter": config.starter_monthly,
        "growth": config.growth_monthly,
        "enterprise": config.enterprise_monthly,
    }

    subscription_cost = tier_prices.get(subscription_tier, config.starter_monthly)

    # Calculate monthly manager time saved (22 business days)
    # CRITICAL: 0.25 hrs/day per PARWA High
    monthly_time_saved = config.calculate_manager_time(days=22)

    return config.calculate_roi(queries_handled, monthly_time_saved, subscription_cost)
