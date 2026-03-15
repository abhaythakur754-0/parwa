"""
PARWA Backend Services Layer

Service modules contain business logic for API operations.
All services enforce company-scoped data access (RLS).
"""
from backend.services.analytics_service import AnalyticsService

__all__ = ["AnalyticsService"]
