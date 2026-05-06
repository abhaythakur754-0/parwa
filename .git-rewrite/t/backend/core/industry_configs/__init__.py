"""
PARWA Industry Configurations Module.

Provides industry-specific configuration for different business types.
Each industry has unique settings for channels, SLA, and compliance.

Available Industries:
- ecommerce: E-commerce/retail businesses
- saas: Software-as-a-Service companies
- healthcare: Healthcare providers (BAA required)
- logistics: Logistics and shipping companies

Usage:
    from backend.core.industry_configs import get_industry_config

    config = get_industry_config("ecommerce")
    print(config.get_config())
"""
from typing import Dict, Any, Optional, Type
from enum import Enum

from backend.core.industry_configs.ecommerce import EcommerceConfig
from backend.core.industry_configs.saas import SaaSConfig
from backend.core.industry_configs.healthcare import HealthcareConfig
from backend.core.industry_configs.logistics import LogisticsConfig


class IndustryType(str, Enum):
    """Supported industry types."""
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    LOGISTICS = "logistics"


# Registry of industry configurations
INDUSTRY_CONFIGS: Dict[str, Type] = {
    IndustryType.ECOMMERCE: EcommerceConfig,
    IndustryType.SAAS: SaaSConfig,
    IndustryType.HEALTHCARE: HealthcareConfig,
    IndustryType.LOGISTICS: LogisticsConfig,
}


def get_industry_config(industry_type: str) -> Any:
    """
    Get industry configuration by type.

    Args:
        industry_type: Type of industry (ecommerce, saas, healthcare, logistics)

    Returns:
        Industry configuration instance

    Raises:
        ValueError: If industry type is not supported
    """
    industry_type = industry_type.lower()

    if industry_type not in INDUSTRY_CONFIGS:
        raise ValueError(
            f"Unknown industry type: {industry_type}. "
            f"Supported types: {list(INDUSTRY_CONFIGS.keys())}"
        )

    return INDUSTRY_CONFIGS[industry_type]()


def get_all_industry_configs() -> Dict[str, Dict[str, Any]]:
    """
    Get all industry configurations.

    Returns:
        Dict mapping industry type to config dict
    """
    return {
        industry: config().get_config()
        for industry, config in INDUSTRY_CONFIGS.items()
    }


def validate_industry(industry_type: str) -> bool:
    """
    Validate if industry type is supported.

    Args:
        industry_type: Industry type to validate

    Returns:
        True if supported
    """
    return industry_type.lower() in INDUSTRY_CONFIGS


__all__ = [
    "IndustryType",
    "INDUSTRY_CONFIGS",
    "get_industry_config",
    "get_all_industry_configs",
    "validate_industry",
    "EcommerceConfig",
    "SaaSConfig",
    "HealthcareConfig",
    "LogisticsConfig",
]
