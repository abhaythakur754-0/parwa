"""
PARWA Backend Configuration Module.

Contains configuration files for variants, features, and system settings.
"""

from app.config.variant_features import (
    BLOCKED_FEATURES,
    VARIANT_FEATURES,
    VARIANT_LIMITS,
    get_blocked_features,
    get_upgrade_required_for_feature,
    get_variant_features,
    is_feature_available,
    is_feature_blocked,
)

__all__ = [
    "VARIANT_FEATURES",
    "BLOCKED_FEATURES",
    "VARIANT_LIMITS",
    "get_variant_features",
    "is_feature_available",
    "is_feature_blocked",
    "get_blocked_features",
    "get_upgrade_required_for_feature",
]
