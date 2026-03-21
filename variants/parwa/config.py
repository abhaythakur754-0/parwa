"""
PARWA Junior Configuration.

Configuration settings specific to the PARWA Junior variant.
Defines capabilities, limits, and thresholds for the medium-tier variant.

PARWA Junior is a step up from Mini PARWA, offering:
- 5 concurrent voice calls (vs 2 for Mini)
- Additional channels: Voice and Video
- Higher refund limit: $500 (vs $50 for Mini)
- Lower escalation threshold: 60% (vs 70% for Mini)
- Medium AI tier support (vs Light only for Mini)
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ParwaConfig(BaseModel):
    """
    Configuration for PARWA Junior variant.

    PARWA Junior is the medium-tier variant with the following characteristics:
    - Maximum 5 concurrent calls
    - Channels: FAQ, Email, Chat, SMS, Voice, Video
    - Escalation threshold: 60%
    - Maximum refund recommendation: $500
    - AI Tier: Medium
    - Returns APPROVE/REVIEW/DENY with reasoning for refunds
    """

    model_config = ConfigDict()

    # Concurrency limits
    max_concurrent_calls: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum concurrent voice calls PARWA Junior can handle"
    )

    # Supported communication channels
    supported_channels: List[str] = Field(
        default=["faq", "email", "chat", "sms", "voice", "video"],
        description="List of channels PARWA Junior supports"
    )

    # Confidence thresholds
    escalation_threshold: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Escalate when confidence falls below this threshold"
    )

    # Financial limits
    refund_limit: float = Field(
        default=500.0,
        ge=0.0,
        description="Maximum refund amount PARWA Junior can recommend (in USD)"
    )

    # Auto-approve threshold for refunds
    auto_approve_threshold: float = Field(
        default=100.0,
        ge=0.0,
        description="Refunds under this amount can be auto-approved for review"
    )

    # Review threshold
    review_threshold: float = Field(
        default=250.0,
        ge=0.0,
        description="Refunds over this amount require manual review"
    )

    # Tier settings
    default_tier: str = Field(
        default="medium",
        description="Default AI tier for PARWA Junior (can use light or medium)"
    )

    # Response settings
    max_response_time_seconds: int = Field(
        default=45,
        ge=5,
        le=180,
        description="Maximum time to generate a response"
    )

    # Learning settings
    enable_learning: bool = Field(
        default=True,
        description="Whether PARWA Junior learns from feedback"
    )

    # Safety settings
    enable_safety_checks: bool = Field(
        default=True,
        description="Whether to run safety checks on responses"
    )

    def get_variant_name(self) -> str:
        """Get the display name for this variant."""
        return "PARWA Junior"

    def get_variant_id(self) -> str:
        """Get the identifier for this variant."""
        return "parwa"

    def get_tier(self) -> str:
        """Get the tier for this variant."""
        return "medium"

    def is_channel_supported(self, channel: str) -> bool:
        """Check if a channel is supported by PARWA Junior."""
        return channel.lower() in self.supported_channels

    def can_handle_refund_amount(self, amount: float) -> bool:
        """Check if PARWA Junior can handle a refund of the given amount."""
        return amount <= self.refund_limit

    def should_escalate_refund(self, amount: float) -> bool:
        """Check if a refund should be escalated to a higher variant."""
        return amount > self.refund_limit

    def get_refund_recommendation_thresholds(self) -> dict:
        """Get the thresholds for refund recommendations."""
        return {
            "auto_approve": self.auto_approve_threshold,
            "review": self.review_threshold,
            "limit": self.refund_limit,
        }


# Default configuration instance
DEFAULT_PARWA_CONFIG = ParwaConfig()


def get_parwa_config() -> ParwaConfig:
    """Get the default PARWA Junior configuration."""
    return DEFAULT_PARWA_CONFIG
