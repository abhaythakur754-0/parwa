"""
PARWA Backend Configuration Module.

Contains configuration files for variants, features, and system settings.
"""

from app.config.variant_features import (
    VARIANT_FEATURES,
    BLOCKED_FEATURES,
    VARIANT_LIMITS,
    get_variant_features,
    is_feature_available,
    is_feature_blocked,
    get_blocked_features,
    get_upgrade_required_for_feature,
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
