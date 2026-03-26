"""
PARWA Logistics Industry Configuration.

Configuration for logistics and shipping companies.
Features tracking integration and delivery support.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class LogisticsConfig(BaseModel):
    """
    Logistics industry configuration.

    Designed for shipping, delivery, and logistics companies
    with tracking integration and supply chain support.

    Attributes:
        industry_type: Industry identifier
        supported_channels: Available support channels
        tracking_integration: Enable tracking integration
        sla_response_hours: Maximum response time in hours
    """

    model_config = ConfigDict()

    industry_type: str = Field(
        default="logistics",
        description="Industry type identifier"
    )
    supported_channels: List[str] = Field(
        default=["faq", "email", "chat", "sms", "voice"],
        description="Supported support channels"
    )
    tracking_integration: bool = Field(
        default=True,
        description="Enable tracking integration"
    )
    sla_response_hours: int = Field(
        default=6,
        description="SLA response time in hours"
    )
    delivery_notifications: bool = Field(
        default=True,
        description="Enable delivery notifications"
    )
    route_optimization_support: bool = Field(
        default=True,
        description="Enable route optimization support"
    )
    customs_support: bool = Field(
        default=True,
        description="Enable customs documentation support"
    )
    warehouse_support: bool = Field(
        default=True,
        description="Enable warehouse management support"
    )
    max_concurrent_chats: int = Field(
        default=20,
        description="Maximum concurrent chat sessions"
    )
    auto_escalation_threshold: float = Field(
        default=0.65,
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
            "tracking_integration": self.tracking_integration,
            "sla_response_hours": self.sla_response_hours,
            "delivery_notifications": self.delivery_notifications,
            "route_optimization_support": self.route_optimization_support,
            "customs_support": self.customs_support,
            "warehouse_support": self.warehouse_support,
            "max_concurrent_chats": self.max_concurrent_chats,
            "auto_escalation_threshold": self.auto_escalation_threshold,
            "features": self.get_features(),
            "integrations": self.get_integrations(),
        }

    def get_features(self) -> List[str]:
        """
        Get list of enabled features for logistics.

        Returns:
            List of feature names
        """
        return [
            "shipment_tracking",
            "delivery_status",
            "proof_of_delivery",
            "route_tracking",
            "exception_handling",
            "returns_management",
            "customs_documentation",
            "warehouse_management",
            "fleet_tracking",
            "driver_communication",
            "inventory_visibility",
            "multi_carrier_support",
        ]

    def get_integrations(self) -> List[str]:
        """
        Get list of supported integrations for logistics.

        Returns:
            List of integration names
        """
        return [
            "ups",
            "fedex",
            "usps",
            "dhl",
            "ontrac",
            "laserShip",
            "aftership",
            "shipstation",
            "shippo",
            "easypost",
            "woocommerce_shipment",
            "shopify_shipping",
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
                "max_questions_per_session": 25,
                "tracking_lookup": True,
            },
            "email": {
                "enabled": True,
                "response_time_hours": 6,
                "template_support": True,
                "attachment_support": True,
            },
            "chat": {
                "enabled": True,
                "response_time_seconds": 20,
                "typing_indicator": True,
                "file_sharing": True,
                "image_support": True,
            },
            "sms": {
                "enabled": True,
                "response_time_minutes": 10,
                "max_length": 160,
                "delivery_alerts": True,
            },
            "voice": {
                "enabled": True,
                "answer_time_seconds": 6,
                "ivr_enabled": True,
                "recording_disclosure": True,
                "tracking_by_phone": True,
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

    def get_tracking_providers(self) -> List[str]:
        """
        Get list of supported tracking providers.

        Returns:
            List of tracking provider names
        """
        return [
            "ups",
            "fedex",
            "usps",
            "dhl",
            "ontrac",
            "canada_post",
            "royal_mail",
            "deutsche_post",
        ]

    def get_shipment_status_codes(self) -> Dict[str, str]:
        """
        Get standard shipment status codes.

        Returns:
            Dict mapping status codes to descriptions
        """
        return {
            "PU": "Picked Up",
            "IT": "In Transit",
            "OF": "Out for Delivery",
            "DE": "Delivered",
            "EX": "Exception",
            "CA": "Cancelled",
            "RE": "Returned",
            "LD": "Loading",
            "UL": "Unloading",
            "WH": "At Warehouse",
        }

    def get_exception_types(self) -> List[str]:
        """
        Get list of recognized exception types.

        Returns:
            List of exception types
        """
        return [
            "delivery_attempt_failed",
            "address_incorrect",
            "recipient_unavailable",
            "signature_required",
            "customs_hold",
            "weather_delay",
            " damaged_package",
            "lost_package",
            "wrong_address",
            "refused_by_recipient",
        ]
