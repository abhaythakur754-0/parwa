"""
PARWA Mini Anti-Arbitrage Configuration.

Ensures pricing is structured so customers cannot arbitrage
between Mini PARWA and hiring human managers directly.

Anti-arbitrage principle:
- Mini PARWA cost proportional to value delivered
- ROI calculation shows time saved vs human manager cost
- Pricing validated to prevent arbitrage opportunities
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class AntiArbitrageConfig(BaseModel):
    """
    Anti-arbitrage pricing configuration for Mini PARWA.

    Ensures Mini PARWA pricing delivers value while preventing
    customers from saving money by bypassing the system.

    Attributes:
        mini_hourly_rate: Cost per hour for Mini PARWA
        manager_hourly_rate: Cost per hour for human manager
        starter_monthly: Starter tier monthly price
        growth_monthly: Growth tier monthly price
        scale_monthly: Scale tier monthly price
    """

    model_config = ConfigDict()

    # Hourly rates
    mini_hourly_rate: float = Field(
        default=15.0,
        ge=5.0,
        description="Cost per hour for Mini PARWA"
    )
    manager_hourly_rate: float = Field(
        default=75.0,
        ge=20.0,
        description="Cost per hour for human manager"
    )

    # Subscription pricing
    starter_monthly: float = Field(
        default=99.0,
        ge=29.0,
        description="Starter tier monthly price"
    )
    growth_monthly: float = Field(
        default=299.0,
        ge=99.0,
        description="Growth tier monthly price"
    )
    scale_monthly: float = Field(
        default=599.0,
        ge=299.0,
        description="Scale tier monthly price"
    )

    # Time estimates
    avg_query_time_saved_minutes: float = Field(
        default=5.0,
        ge=1.0,
        description="Average minutes saved per query"
    )

    @field_validator('manager_hourly_rate')
    @classmethod
    def manager_rate_must_exceed_mini(cls, v: float, info) -> float:
        """Ensure manager rate is higher than mini rate."""
        mini_rate = info.data.get('mini_hourly_rate', 15.0)
        if v <= mini_rate:
            raise ValueError(
                f"manager_hourly_rate ({v}) must be higher than "
                f"mini_hourly_rate ({mini_rate})"
            )
        return v

    def calculate_manager_time(
        self,
        complexity: float = 1.0
    ) -> float:
        """
        Calculate time saved by using Mini vs human manager.

        Args:
            complexity: Complexity multiplier (1.0 = average)

        Returns:
            Time saved in minutes
        """
        base_time = self.avg_query_time_saved_minutes
        return base_time * complexity

    def calculate_roi(
        self,
        queries_handled: int,
        manager_time_saved: float,
        subscription_cost: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate ROI for using Mini PARWA.

        Args:
            queries_handled: Number of queries handled by Mini
            manager_time_saved: Total manager time saved in minutes
            subscription_cost: Monthly subscription cost (default: starter)

        Returns:
            Dict with ROI calculation details
        """
        if subscription_cost is None:
            subscription_cost = self.starter_monthly

        # Convert time to hours
        hours_saved = manager_time_saved / 60.0

        # Calculate cost savings
        manager_cost = hours_saved * self.manager_hourly_rate
        mini_cost = subscription_cost

        # Net savings
        net_savings = manager_cost - mini_cost

        # ROI percentage
        roi_percent = (net_savings / mini_cost * 100) if mini_cost > 0 else 0.0

        # Cost per query
        cost_per_query = mini_cost / queries_handled if queries_handled > 0 else 0

        return {
            "queries_handled": queries_handled,
            "hours_saved": round(hours_saved, 2),
            "manager_cost": round(manager_cost, 2),
            "mini_cost": round(mini_cost, 2),
            "net_savings": round(net_savings, 2),
            "roi_percent": round(roi_percent, 2),
            "cost_per_query": round(cost_per_query, 4),
            "is_positive_roi": net_savings > 0,
        }

    def validate_pricing(
        self,
        subscription_tier: str
    ) -> Dict[str, Any]:
        """
        Validate that pricing is anti-arbitrage compliant.

        Args:
            subscription_tier: Tier name (starter, growth, scale)

        Returns:
            Dict with validation result
        """
        tier_prices = {
            "starter": self.starter_monthly,
            "growth": self.growth_monthly,
            "scale": self.scale_monthly,
        }

        price = tier_prices.get(subscription_tier.lower())

        if price is None:
            return {
                "valid": False,
                "error": f"Unknown tier: {subscription_tier}",
            }

        errors = []
        warnings = []

        # Calculate break-even point
        hours_needed = price / self.manager_hourly_rate
        queries_needed = hours_needed * 60 / self.avg_query_time_saved_minutes

        # Check for reasonable break-even
        if queries_needed > 100:
            warnings.append(
                f"Requires {int(queries_needed)} queries to break even"
            )

        # Check cost per query at reasonable usage
        reasonable_queries = 500
        cost_per_query = price / reasonable_queries

        if cost_per_query > 0.50:
            warnings.append(
                f"Cost per query (${cost_per_query:.2f}) may be high"
            )

        return {
            "valid": True,
            "tier": subscription_tier,
            "price": price,
            "hours_needed_to_break_even": round(hours_needed, 2),
            "queries_needed_to_break_even": int(queries_needed),
            "cost_per_query_at_500_queries": round(cost_per_query, 2),
            "errors": errors,
            "warnings": warnings,
        }

    def get_tier_pricing(self) -> Dict[str, Dict[str, float]]:
        """Get pricing for all tiers."""
        return {
            "starter": {
                "monthly": self.starter_monthly,
                "hourly_equivalent": round(self.starter_monthly / 30 / 24, 4),
            },
            "growth": {
                "monthly": self.growth_monthly,
                "hourly_equivalent": round(self.growth_monthly / 30 / 24, 4),
            },
            "scale": {
                "monthly": self.scale_monthly,
                "hourly_equivalent": round(self.scale_monthly / 30 / 24, 4),
            },
        }

    def get_savings_ratio(self) -> float:
        """
        Get the ratio of manager cost to Mini cost.

        Returns:
            Ratio (e.g., 5.0 means manager costs 5x more than Mini)
        """
        return self.manager_hourly_rate / self.mini_hourly_rate

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "mini_hourly_rate": self.mini_hourly_rate,
            "manager_hourly_rate": self.manager_hourly_rate,
            "savings_ratio": self.get_savings_ratio(),
            "starter_monthly": self.starter_monthly,
            "growth_monthly": self.growth_monthly,
            "scale_monthly": self.scale_monthly,
            "avg_query_time_saved_minutes": self.avg_query_time_saved_minutes,
            "tier_pricing": self.get_tier_pricing(),
        }


# Default configuration instance
DEFAULT_ANTI_ARBITRAGE_CONFIG = AntiArbitrageConfig()


def get_anti_arbitrage_config() -> AntiArbitrageConfig:
    """Get the default anti-arbitrage configuration."""
    return DEFAULT_ANTI_ARBITRAGE_CONFIG


def calculate_mini_roi(
    queries_handled: int,
    subscription_tier: str = "starter"
) -> Dict[str, Any]:
    """
    Convenience function to calculate Mini PARWA ROI.

    Args:
        queries_handled: Number of queries handled
        subscription_tier: Subscription tier name

    Returns:
        ROI calculation dict
    """
    config = get_anti_arbitrage_config()
    tier_prices = {
        "starter": config.starter_monthly,
        "growth": config.growth_monthly,
        "scale": config.scale_monthly,
    }

    subscription_cost = tier_prices.get(subscription_tier, config.starter_monthly)
    time_saved = queries_handled * config.avg_query_time_saved_minutes

    return config.calculate_roi(queries_handled, time_saved, subscription_cost)
