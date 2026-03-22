"""
PARWA Backend Services Layer

Service modules contain business logic for API operations.
All services enforce company-scoped data access (RLS).
"""

# Lazy import to avoid sqlalchemy dependency during testing
# Import services directly when needed
__all__ = [
    "AnalyticsService",
    "BillingService",
    "SubscriptionTier",
    "SubscriptionStatus",
    "TIER_PRICING",
    "TIER_LIMITS",
    "OnboardingService",
    "OnboardingStep",
    "ONBOARDING_STEPS",
    "NonFinancialUndoService",
]


def __getattr__(name):
    """Lazy import services when accessed."""
    if name == "AnalyticsService":
        from backend.services.analytics_service import AnalyticsService
        return AnalyticsService
    elif name == "BillingService":
        from backend.services.billing_service import BillingService
        return BillingService
    elif name == "SubscriptionTier":
        from backend.services.billing_service import SubscriptionTier
        return SubscriptionTier
    elif name == "SubscriptionStatus":
        from backend.services.billing_service import SubscriptionStatus
        return SubscriptionStatus
    elif name == "TIER_PRICING":
        from backend.services.billing_service import TIER_PRICING
        return TIER_PRICING
    elif name == "TIER_LIMITS":
        from backend.services.billing_service import TIER_LIMITS
        return TIER_LIMITS
    elif name == "OnboardingService":
        from backend.services.onboarding_service import OnboardingService
        return OnboardingService
    elif name == "OnboardingStep":
        from backend.services.onboarding_service import OnboardingStep
        return OnboardingStep
    elif name == "ONBOARDING_STEPS":
        from backend.services.onboarding_service import ONBOARDING_STEPS
        return ONBOARDING_STEPS
    elif name == "NonFinancialUndoService":
        from backend.services.non_financial_undo import NonFinancialUndoService
        return NonFinancialUndoService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
