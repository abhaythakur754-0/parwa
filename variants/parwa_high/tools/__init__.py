"""
PARWA High Tools Module.

Tools for PARWA High variant providing advanced capabilities:
- Analytics engine for insights generation
- Team coordination for multi-team management
- Customer success tools with churn prediction

PARWA High is the enterprise-grade variant with:
- Heavy AI tier for complex queries
- Video support capabilities
- Customer success with churn prediction
- Analytics and insights generation
- Team coordination for 5 concurrent teams
"""
from variants.parwa_high.tools.analytics_engine import AnalyticsEngine
from variants.parwa_high.tools.team_coordination import TeamCoordinationTool
from variants.parwa_high.tools.customer_success_tools import CustomerSuccessTools

__all__ = [
    "AnalyticsEngine",
    "TeamCoordinationTool",
    "CustomerSuccessTools",
]
