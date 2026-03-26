"""
PARWA High Tasks Package.

This package contains task modules for PARWA High variant:
- video_call: Task to manage video call sessions
- generate_insights: Task to generate analytics insights
- coordinate_teams: Task to coordinate multiple teams
- customer_success: Task for customer success operations

All PARWA High tasks:
- Use 'heavy' tier for processing
- Support advanced features (video, analytics, coordination)
- Return structured results with metadata
"""
from variants.parwa_high.tasks.video_call import VideoCallTask
from variants.parwa_high.tasks.generate_insights import GenerateInsightsTask
from variants.parwa_high.tasks.coordinate_teams import CoordinateTeamsTask
from variants.parwa_high.tasks.customer_success import CustomerSuccessTask

__all__ = [
    "VideoCallTask",
    "GenerateInsightsTask",
    "CoordinateTeamsTask",
    "CustomerSuccessTask",
]
