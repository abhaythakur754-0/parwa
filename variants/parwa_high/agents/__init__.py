"""
PARWA High Agents Package.

This package contains agent modules for PARWA High variant:
- video_agent: Video support agent for video calls
- analytics_agent: Analytics agent for insights and trends
- coordination_agent: Team coordination agent

All PARWA High agents:
- Use 'heavy' tier for processing
- Support video channel
- Can coordinate multiple teams (up to 5)
- Provide advanced analytics and predictions
"""
from variants.parwa_high.agents.video_agent import ParwaHighVideoAgent
from variants.parwa_high.agents.analytics_agent import ParwaHighAnalyticsAgent
from variants.parwa_high.agents.coordination_agent import ParwaHighCoordinationAgent

__all__ = [
    "ParwaHighVideoAgent",
    "ParwaHighAnalyticsAgent",
    "ParwaHighCoordinationAgent",
]
