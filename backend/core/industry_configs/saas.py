"""
PARWA SaaS Industry Configuration.

Configuration for Software-as-a-Service companies.
Focuses on technical support and account management.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class SaaSConfig(BaseModel):
    """
    SaaS industry configuration.

    Designed for software companies with focus on
    technical support and account management.

    Attributes:
        industry_type: Industry identifier
        supported_channels: Available support channels
        refund_policy_days: Days allowed for refund requests
        sla_response_hours: Maximum response time in hours
    """

    model_config = ConfigDict()

    industry_type: str = Field(
        default="saas",
        description="Industry type identifier"
    )
    supported_channels: List[str] = Field(
        default=["faq", "email", "chat"],
        description="Supported support channels"
    )
    refund_policy_days: int = Field(
        default=14,
        description="Number of days for refund policy"
    )
    sla_response_hours: int = Field(
        default=2,
        description="SLA response time in hours"
    )
    technical_support_enabled: bool = Field(
        default=True,
        description="Enable technical support"
    )
    api_support_enabled: bool = Field(
        default=True,
        description="Enable API support"
    )
    account_management_enabled: bool = Field(
        default=True,
        description="Enable account management"
    )
    onboarding_support_enabled: bool = Field(
        default=True,
        description="Enable onboarding support"
    )
    max_concurrent_chats: int = Field(
        default=15,
        description="Maximum concurrent chat sessions"
    )
    auto_escalation_threshold: float = Field(
        default=0.6,
        description="Threshold for auto-escalation"
    )

    def get_config(self) -> Dict[str, Any]:
        """
        Get full configuration as dictionary.

        Returns:
            Dict containing all configuration values
        """
        return {
            "industry_type": self.industry_type,
            "supported_channels": self.supported_channels,
            "refund_policy_days": self.refund_policy_days,
            "sla_response_hours": self.sla_response_hours,
            "technical_support_enabled": self.technical_support_enabled,
            "api_support_enabled": self.api_support_enabled,
            "account_management_enabled": self.account_management_enabled,
            "onboarding_support_enabled": self.onboarding_support_enabled,
            "max_concurrent_chats": self.max_concurrent_chats,
            "auto_escalation_threshold": self.auto_escalation_threshold,
            "features": self.get_features(),
            "integrations": self.get_integrations(),
        }

    def get_features(self) -> List[str]:
        """
        Get list of enabled features for SaaS.

        Returns:
            List of feature names
        """
        return [
            "technical_support",
            "api_documentation",
            "account_management",
            "subscription_management",
            "billing_support",
            "feature_requests",
            "bug_reporting",
            "onboarding_assistance",
            "user_management",
            "integration_support",
        ]

    def get_integrations(self) -> List[str]:
        """
        Get list of supported integrations for SaaS.

        Returns:
            List of integration names
        """
        return [
            "stripe",
            "paddle",
            "chargebee",
            "recurly",
            "zendesk",
            "intercom",
            "freshdesk",
            "jira",
            "github",
            "slack",
            "webhooks",
        ]

    def get_channel_config(self, channel: str) -> Dict[str, Any]:
        """
        Get configuration for a specific channel.

        Args:
            channel: Channel name (faq, email, chat)

        Returns:
            Channel-specific configuration
        """
        channel_configs = {
            "faq": {
                "enabled": True,
                "response_time_seconds": 1,
                "max_questions_per_session": 30,
                "technical_docs_search": True,
            },
            "email": {
                "enabled": True,
                "response_time_hours": 2,
                "template_support": True,
                "priority_levels": ["low", "medium", "high", "critical"],
            },
            "chat": {
                "enabled": True,
                "response_time_seconds": 15,
                "typing_indicator": True,
                "file_sharing": True,
                "code_snippet_support": True,
                "screen_share_available": True,
            },
        }
        return channel_configs.get(channel, {"enabled": False})

    def validate_channel(self, channel: str) -> bool:
        """
        Validate if a channel is supported.

        Args:
            channel: Channel name to validate

        Returns:
            True if channel is supported
        """
        return channel.lower() in [c.lower() for c in self.supported_channels]

    def get_tier_limits(self) -> Dict[str, Any]:
        """
        Get SaaS-specific tier limits.

        Returns:
            Dict with tier limit information
        """
        return {
            "free_tier": {
                "max_users": 5,
                "api_calls_per_month": 1000,
                "support_level": "community",
            },
            "starter": {
                "max_users": 25,
                "api_calls_per_month": 10000,
                "support_level": "email",
            },
            "professional": {
                "max_users": 100,
                "api_calls_per_month": 100000,
                "support_level": "priority",
            },
            "enterprise": {
                "max_users": "unlimited",
                "api_calls_per_month": "unlimited",
                "support_level": "dedicated",
            },
        }
