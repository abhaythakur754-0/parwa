"""
PARWA Public Schemas

Pydantic models for public API responses (no authentication required).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FeatureItem(BaseModel):
    """Feature highlight for landing page carousel."""

    id: int
    icon: str
    title: str
    description: str
    psychological_trigger: str
    gradient: str


class PublicStatsResponse(BaseModel):
    """Public statistics for landing page."""

    automation_rate: str
    hours_saved_per_week: str
    availability: str
    response_time: str
    starting_price: str


class IndustryItem(BaseModel):
    """Industry option for onboarding."""

    id: str
    name: str
    description: str
    variants: List[str]
