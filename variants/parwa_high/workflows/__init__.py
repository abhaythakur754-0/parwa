"""
PARWA High Workflows Module.

Workflows for PARWA High variant providing end-to-end processes:
- Video support workflow for screen sharing sessions
- Analytics workflow for insights generation
- Coordination workflow for team management
- Customer success workflow with churn prediction

PARWA High is the enterprise-grade variant with:
- Heavy AI tier for complex processing
- Video support capabilities
- Advanced analytics
- Customer success with churn prediction
- Multi-team coordination (up to 5 teams)
"""
from variants.parwa_high.workflows.video_support import VideoSupportWorkflow
from variants.parwa_high.workflows.analytics import AnalyticsWorkflow
from variants.parwa_high.workflows.coordination import CoordinationWorkflow
from variants.parwa_high.workflows.customer_success import CustomerSuccessWorkflow

__all__ = [
    "VideoSupportWorkflow",
    "AnalyticsWorkflow",
    "CoordinationWorkflow",
    "CustomerSuccessWorkflow",
]
