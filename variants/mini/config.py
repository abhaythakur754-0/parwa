"""
PARWA Mini Configuration.

Configuration settings specific to the Mini PARWA variant.
Defines capabilities, limits, and thresholds for the entry-level variant.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class MiniConfig(BaseModel):
    """
    Configuration for Mini PARWA variant.

    Mini PARWA is the entry-level variant with the following characteristics:
    - Maximum 2 concurrent calls
    - Basic channels: FAQ, Email, Chat, SMS
    - Escalation threshold: 70%
    - Maximum refund recommendation: $50
    """

    model_config = ConfigDict()

    # Concurrency limits
    max_concurrent_calls: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum concurrent voice calls Mini can handle"
    )

    # Supported communication channels
    supported_channels: List[str] = Field(
        default=["faq", "email", "chat", "sms"],
        description="List of channels Mini PARWA supports"
    )

    # Confidence thresholds
    escalation_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Escalate when confidence falls below this threshold"
    )

    # Financial limits
    refund_limit: float = Field(
        default=50.0,
        ge=0.0,
        description="Maximum refund amount Mini can recommend (in USD)"
    )

    # Auto-approve threshold for refunds
    auto_approve_threshold: float = Field(
        default=25.0,
        ge=0.0,
        description="Refunds under this amount can be auto-approved for review"
    )

    # Review threshold
    review_threshold: float = Field(
        default=50.0,
        ge=0.0,
        description="Refunds over this amount require manual review"
    )

    # Tier settings
    default_tier: str = Field(
        default="light",
        description="Default AI tier for Mini (always 'light')"
    )

    # Response settings
    max_response_time_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Maximum time to generate a response"
    )

    def get_variant_name(self) -> str:
        """Get the display name for this variant."""
        return "Mini PARWA"

    def get_variant_id(self) -> str:
        """Get the identifier for this variant."""
        return "mini"

    def is_channel_supported(self, channel: str) -> bool:
        """Check if a channel is supported by Mini."""
        return channel.lower() in self.supported_channels

    def can_handle_refund_amount(self, amount: float) -> bool:
        """Check if Mini can handle a refund of the given amount."""
        return amount <= self.refund_limit

    def should_escalate_refund(self, amount: float) -> bool:
        """Check if a refund should be escalated to a higher variant."""
        return amount > self.refund_limit


# Default configuration instance
DEFAULT_MINI_CONFIG = MiniConfig()


def get_mini_config() -> MiniConfig:
    """Get the default Mini configuration."""
    return DEFAULT_MINI_CONFIG
