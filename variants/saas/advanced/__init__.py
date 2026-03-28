"""SaaS Advanced Module.

This module provides advanced SaaS features including:
- Subscription Lifecycle Management
- Usage-Based Billing & Metering
- Churn Prediction & Retention
- Feature Request & Feedback Intelligence
- SaaS Analytics Dashboard
"""

from variants.saas.advanced.subscription_manager import SubscriptionManager
from variants.saas.advanced.plan_manager import PlanManager
from variants.saas.advanced.upgrade_downgrade import UpgradeDowngradeHandler
from variants.saas.advanced.trial_handler import TrialHandler

__version__ = "1.0.0"
__all__ = [
    "SubscriptionManager",
    "PlanManager",
    "UpgradeDowngradeHandler",
    "TrialHandler",
]
