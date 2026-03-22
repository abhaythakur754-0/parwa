"""
PARWA High Configuration.

Configuration settings specific to the PARWA High variant.
Defines capabilities, limits, and thresholds for the heavy-tier variant.

PARWA High is the premium tier offering:
- 10 concurrent voice calls (vs 5 for PARWA Junior)
- All channels including video support
- Higher refund limit: $2000 (vs $500 for PARWA Junior)
- Can execute refunds with approval
- Lower escalation threshold: 50% (vs 60% for PARWA Junior)
- Heavy AI tier support
- Customer success with churn prediction
- Team coordination (5 teams)
- HIPAA compliance support
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ParwaHighConfig(BaseModel):
    """
    Configuration for PARWA High variant.

    PARWA High is the heavy-tier variant with the following characteristics:
    - Maximum 10 concurrent calls
    - Channels: FAQ, Email, Chat, SMS, Voice, Video
    - Escalation threshold: 50%
    - Maximum refund: $2000 (can execute with approval)
    - AI Tier: Heavy
    - Can execute refunds (with pending_approval)
    - Video support
    - Customer success with churn prediction
    - Team coordination (5 teams)
    """

    model_config = ConfigDict()

    # Concurrency limits - CRITICAL: 10 for PARWA High
    max_concurrent_calls: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum concurrent voice calls PARWA High can handle"
    )

    # Supported communication channels - all channels
    supported_channels: List[str] = Field(
        default=["faq", "email", "chat", "sms", "voice", "video"],
        description="List of channels PARWA High supports"
    )

    # Confidence thresholds - CRITICAL: 50% for PARWA High
    escalation_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Escalate when confidence falls below this threshold"
    )

    # Financial limits - CRITICAL: $2000 for PARWA High
    refund_limit: float = Field(
        default=2000.0,
        ge=0.0,
        description="Maximum refund amount PARWA High can execute (in USD)"
    )

    # CRITICAL: PARWA High can execute refunds (with approval)
    can_execute_refunds: bool = Field(
        default=True,
        description="Whether PARWA High can execute refunds (requires approval)"
    )

    # Auto-approve threshold for refunds
    auto_approve_threshold: float = Field(
        default=500.0,
        ge=0.0,
        description="Refunds under this amount can be auto-approved for review"
    )

    # Review threshold
    review_threshold: float = Field(
        default=1000.0,
        ge=0.0,
        description="Refunds over this amount require manual review"
    )

    # Tier settings - CRITICAL: heavy tier
    default_tier: str = Field(
        default="heavy",
        description="Default AI tier for PARWA High"
    )

    # Response settings
    max_response_time_seconds: int = Field(
        default=60,
        ge=5,
        le=300,
        description="Maximum time to generate a response"
    )

    # Learning settings
    enable_learning: bool = Field(
        default=True,
        description="Whether PARWA High learns from feedback"
    )

    # Safety settings
    enable_safety_checks: bool = Field(
        default=True,
        description="Whether to run safety checks on responses"
    )

    # Video support settings
    enable_video_support: bool = Field(
        default=True,
        description="Whether video support is enabled"
    )

    max_video_duration_minutes: int = Field(
        default=60,
        ge=5,
        le=180,
        description="Maximum duration for video support sessions"
    )

    # Team coordination settings - CRITICAL: 5 teams
    max_concurrent_teams: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum concurrent teams PARWA High can coordinate"
    )

    # Customer success settings
    enable_churn_prediction: bool = Field(
        default=True,
        description="Whether churn prediction is enabled"
    )

    # HIPAA compliance settings
    enable_hipaa_compliance: bool = Field(
        default=True,
        description="Whether HIPAA compliance features are enabled"
    )

    def get_variant_name(self) -> str:
        """Get the display name for this variant."""
        return "PARWA High"

    def get_variant_id(self) -> str:
        """Get the identifier for this variant."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get the tier for this variant."""
        return "heavy"

    def is_channel_supported(self, channel: str) -> bool:
        """Check if a channel is supported by PARWA High."""
        return channel.lower() in self.supported_channels

    def can_handle_refund_amount(self, amount: float) -> bool:
        """Check if PARWA High can handle a refund of the given amount."""
        return amount <= self.refund_limit

    def should_escalate_refund(self, amount: float) -> bool:
        """Check if a refund should be escalated (never for PARWA High)."""
        # PARWA High handles all refunds within limit
        return amount > self.refund_limit

    def get_refund_recommendation_thresholds(self) -> dict:
        """Get the thresholds for refund recommendations."""
        return {
            "auto_approve": self.auto_approve_threshold,
            "review": self.review_threshold,
            "limit": self.refund_limit,
            "can_execute": self.can_execute_refunds,
        }

    def can_execute_refund(self, amount: float, has_approval: bool) -> bool:
        """
        Check if PARWA High can execute a refund.

        CRITICAL: Refunds can only be executed with pending_approval.

        Args:
            amount: Refund amount
            has_approval: Whether approval exists

        Returns:
            True if refund can be executed
        """
        if not self.can_execute_refunds:
            return False
        if amount > self.refund_limit:
            return False
        if not has_approval:
            return False
        return True


# Default configuration instance
DEFAULT_PARWA_HIGH_CONFIG = ParwaHighConfig()


def get_parwa_high_config() -> ParwaHighConfig:
    """Get the default PARWA High configuration."""
    return DEFAULT_PARWA_HIGH_CONFIG
