"""
PARWA E-commerce Industry Configuration.

Configuration for e-commerce and retail businesses.
Supports full omnichannel customer support.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class EcommerceConfig(BaseModel):
    """
    E-commerce industry configuration.

    Designed for online retail and e-commerce businesses with
    full omnichannel support including voice calls.

    Attributes:
        industry_type: Industry identifier
        supported_channels: Available support channels
        refund_policy_days: Days allowed for refund requests
        sla_response_hours: Maximum response time in hours
    """

    model_config = ConfigDict()

    industry_type: str = Field(
        default="ecommerce",
        description="Industry type identifier"
    )
    supported_channels: List[str] = Field(
        default=["faq", "email", "chat", "sms", "voice"],
        description="Supported support channels"
    )
    refund_policy_days: int = Field(
        default=30,
        description="Number of days for refund policy"
    )
    sla_response_hours: int = Field(
        default=4,
        description="SLA response time in hours"
    )
    order_lookup_enabled: bool = Field(
        default=True,
        description="Enable order lookup functionality"
    )
    inventory_check_enabled: bool = Field(
        default=True,
        description="Enable inventory check"
    )
    shipping_tracking_enabled: bool = Field(
        default=True,
        description="Enable shipping tracking"
    )
    max_concurrent_chats: int = Field(
        default=10,
        description="Maximum concurrent chat sessions"
    )
    auto_escalation_threshold: float = Field(
        default=0.7,
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
            "order_lookup_enabled": self.order_lookup_enabled,
            "inventory_check_enabled": self.inventory_check_enabled,
            "shipping_tracking_enabled": self.shipping_tracking_enabled,
            "max_concurrent_chats": self.max_concurrent_chats,
            "auto_escalation_threshold": self.auto_escalation_threshold,
            "features": self.get_features(),
            "integrations": self.get_integrations(),
        }

    def get_features(self) -> List[str]:
        """
        Get list of enabled features for e-commerce.

        Returns:
            List of feature names
        """
        return [
            "order_tracking",
            "refund_processing",
            "product_inquiry",
            "shipping_updates",
            "inventory_check",
            "coupon_application",
            "cart_abandonment",
            "review_management",
        ]

    def get_integrations(self) -> List[str]:
        """
        Get list of supported integrations for e-commerce.

        Returns:
            List of integration names
        """
        return [
            "shopify",
            "woocommerce",
            "magento",
            "bigcommerce",
            "stripe",
            "paypal",
            "ups",
            "fedex",
            "usps",
            "aftership",
        ]

    def get_channel_config(self, channel: str) -> Dict[str, Any]:
        """
        Get configuration for a specific channel.

        Args:
            channel: Channel name (faq, email, chat, sms, voice)

        Returns:
            Channel-specific configuration
        """
        channel_configs = {
            "faq": {
                "enabled": True,
                "response_time_seconds": 2,
                "max_questions_per_session": 20,
            },
            "email": {
                "enabled": True,
                "response_time_hours": 4,
                "template_support": True,
            },
            "chat": {
                "enabled": True,
                "response_time_seconds": 30,
                "typing_indicator": True,
                "file_sharing": True,
            },
            "sms": {
                "enabled": True,
                "response_time_minutes": 15,
                "max_length": 160,
            },
            "voice": {
                "enabled": True,
                "answer_time_seconds": 6,
                "ivr_enabled": False,
                "recording_disclosure": True,
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
