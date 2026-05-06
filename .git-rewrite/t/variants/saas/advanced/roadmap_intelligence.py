"""
Roadmap Intelligence for SaaS Advanced Module.

Provides roadmap intelligence including:
- Feature popularity ranking
- Impact estimation
- Effort estimation
- ROI calculation for features
- Customer segment demand
- Competitive gap analysis
- Roadmap recommendation engine
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FeatureStatus(str, Enum):
    """Feature status on roadmap."""
    BACKLOG = "backlog"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RELEASED = "released"


class ImpactLevel(str, Enum):
    """Impact level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EffortLevel(str, Enum):
    """Effort level enumeration."""
    TRIVIAL = "trivial"  # < 1 week
    SMALL = "small"     # 1-2 weeks
    MEDIUM = "medium"   # 2-4 weeks
    LARGE = "large"     # 1-2 months
    HUGE = "huge"       # > 2 months


@dataclass
class RoadmapFeature:
    """Represents a feature on the roadmap."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    category: str = ""
    status: FeatureStatus = FeatureStatus.BACKLOG
    impact: ImpactLevel = ImpactLevel.MEDIUM
    effort: EffortLevel = EffortLevel.MEDIUM
    votes: int = 0
    requests: int = 0
    customer_demand: int = 0
    revenue_impact: float = 0.0
    strategic_value: float = 0.0
    segments: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    target_quarter: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "status": self.status.value,
            "impact": self.impact.value,
            "effort": self.effort.value,
            "votes": self.votes,
            "requests": self.requests,
            "customer_demand": self.customer_demand,
            "revenue_impact": self.revenue_impact,
            "strategic_value": self.strategic_value,
            "segments": self.segments,
            "tags": self.tags,
            "target_quarter": self.target_quarter,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RoadmapRecommendation:
    """Represents a roadmap recommendation."""
    id: UUID = field(default_factory=uuid4)
    feature_id: UUID = field(default_factory=uuid4)
    feature_name: str = ""
    priority_score: float = 0.0
    roi_score: float = 0.0
    rationale: str = ""
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "feature_id": str(self.feature_id),
            "feature_name": self.feature_name,
            "priority_score": round(self.priority_score, 2),
            "roi_score": round(self.roi_score, 2),
            "rationale": self.rationale,
            "supporting_data": self.supporting_data,
            "created_at": self.created_at.isoformat(),
        }


# Impact scoring weights
IMPACT_WEIGHTS = {
    ImpactLevel.LOW: 1,
    ImpactLevel.MEDIUM: 2,
    ImpactLevel.HIGH: 3,
    ImpactLevel.CRITICAL: 4,
}

# Effort scoring weights (inverted for ROI)
EFFORT_WEIGHTS = {
    EffortLevel.TRIVIAL: 5,
    EffortLevel.SMALL: 4,
    EffortLevel.MEDIUM: 3,
    EffortLevel.LARGE: 2,
    EffortLevel.HUGE: 1,
}

# Category importance
CATEGORY_IMPORTANCE = {
    "core": 3,
    "integration": 2,
    "reporting": 2,
    "security": 4,
    "performance": 3,
    "ux": 2,
    "other": 1,
}


class RoadmapIntelligence:
    """
    Provides intelligence for roadmap planning.

    Features:
    - Feature popularity ranking
    - Impact/effort estimation
    - ROI calculation
    - Segment demand analysis
    - Competitive gap analysis
    - Recommendation engine
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize roadmap intelligence.

        Args:
            client_id: Client identifier
        """
        self.client_id = client_id
        self._features: Dict[str, RoadmapFeature] = {}
        self._recommendations: Dict[str, RoadmapRecommendation] = {}

    async def add_feature(
        self,
        name: str,
        description: str,
        category: str = "other",
        impact: ImpactLevel = ImpactLevel.MEDIUM,
        effort: EffortLevel = EffortLevel.MEDIUM,
        segments: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        votes: int = 0,
        requests: int = 0,
        revenue_impact: float = 0.0,
        strategic_value: float = 0.0
    ) -> RoadmapFeature:
        """
        Add a feature to roadmap analysis.

        Args:
            name: Feature name
            description: Feature description
            category: Feature category
            impact: Expected impact
            effort: Estimated effort
            segments: Target customer segments
            tags: Feature tags
            votes: Initial vote count
            requests: Initial request count
            revenue_impact: Estimated revenue impact
            strategic_value: Strategic value score

        Returns:
            Created RoadmapFeature
        """
        feature = RoadmapFeature(
            name=name,
            description=description,
            category=category,
            impact=impact,
            effort=effort,
            segments=segments or [],
            tags=tags or [],
            votes=votes,
            requests=requests,
            revenue_impact=revenue_impact,
            strategic_value=strategic_value,
        )

        self._features[str(feature.id)] = feature

        logger.info(
            "Feature added to roadmap",
            extra={
                "feature_id": str(feature.id),
                "name": name,
                "category": category,
            }
        )

        return feature

    async def rank_by_popularity(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Rank features by popularity.

        Args:
            limit: Maximum features to return

        Returns:
            List of ranked features
        """
        features = list(self._features.values())

        # Calculate popularity score
        ranked = []
        for feature in features:
            popularity_score = (
                feature.votes * 1.0 +
                feature.requests * 2.0 +
                feature.customer_demand * 1.5
            )

            ranked.append({
                "feature": feature.to_dict(),
                "popularity_score": round(popularity_score, 2),
                "votes": feature.votes,
                "requests": feature.requests,
                "customer_demand": feature.customer_demand,
            })

        # Sort by popularity
        ranked.sort(key=lambda x: x["popularity_score"], reverse=True)

        return ranked[:limit]

    async def estimate_impact(
        self,
        feature_id: UUID,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Estimate feature impact.

        Args:
            feature_id: Feature to estimate
            customer_data: Optional customer impact data

        Returns:
            Dict with impact estimation
        """
        feature = self._features.get(str(feature_id))
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        base_impact = IMPACT_WEIGHTS.get(feature.impact, 2)

        # Adjust based on customer demand
        demand_multiplier = 1 + (feature.customer_demand / 100)
        adjusted_impact = base_impact * demand_multiplier

        # Calculate segment reach
        segment_count = len(feature.segments)

        # Estimate affected users
        if customer_data:
            affected_users = customer_data.get("affected_users", feature.customer_demand)
        else:
            affected_users = feature.customer_demand

        return {
            "feature_id": str(feature_id),
            "feature_name": feature.name,
            "base_impact": base_impact,
            "adjusted_impact": round(adjusted_impact, 2),
            "impact_level": feature.impact.value,
            "segment_reach": segment_count,
            "estimated_affected_users": affected_users,
            "revenue_impact": feature.revenue_impact,
        }

    async def estimate_effort(
        self,
        feature_id: UUID,
        team_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Estimate feature effort.

        Args:
            feature_id: Feature to estimate
            team_data: Optional team capacity data

        Returns:
            Dict with effort estimation
        """
        feature = self._features.get(str(feature_id))
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        effort_map = {
            EffortLevel.TRIVIAL: {"weeks": 0.5, "story_points": 3},
            EffortLevel.SMALL: {"weeks": 1.5, "story_points": 8},
            EffortLevel.MEDIUM: {"weeks": 3, "story_points": 13},
            EffortLevel.LARGE: {"weeks": 6, "story_points": 21},
            EffortLevel.HUGE: {"weeks": 12, "story_points": 40},
        }

        base_effort = effort_map.get(feature.effort, effort_map[EffortLevel.MEDIUM])

        # Adjust for complexity
        complexity_factor = 1.0
        if team_data and team_data.get("team_size", 1) < 3:
            complexity_factor = 1.25

        adjusted_weeks = base_effort["weeks"] * complexity_factor

        return {
            "feature_id": str(feature_id),
            "feature_name": feature.name,
            "effort_level": feature.effort.value,
            "estimated_weeks": round(adjusted_weeks, 1),
            "story_points": base_effort["story_points"],
            "complexity_factor": complexity_factor,
        }

    async def calculate_roi(
        self,
        feature_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate ROI for a feature.

        Args:
            feature_id: Feature to analyze

        Returns:
            Dict with ROI calculation
        """
        feature = self._features.get(str(feature_id))
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        # Get impact and effort scores
        impact_score = IMPACT_WEIGHTS.get(feature.impact, 2)
        effort_score = EFFORT_WEIGHTS.get(feature.effort, 3)

        # Calculate base ROI
        base_roi = (impact_score * effort_score) / 5

        # Adjust for votes and requests
        demand_multiplier = 1 + (feature.votes / 50) + (feature.requests / 20)

        # Adjust for revenue impact
        revenue_multiplier = 1 + (feature.revenue_impact / 10000)

        # Adjust for strategic value
        strategic_multiplier = 1 + feature.strategic_value

        # Calculate final ROI
        final_roi = base_roi * demand_multiplier * revenue_multiplier * strategic_multiplier

        # Determine ROI level
        if final_roi >= 4:
            roi_level = "excellent"
        elif final_roi >= 3:
            roi_level = "high"
        elif final_roi >= 2:
            roi_level = "medium"
        else:
            roi_level = "low"

        return {
            "feature_id": str(feature_id),
            "feature_name": feature.name,
            "roi_score": round(final_roi, 2),
            "roi_level": roi_level,
            "components": {
                "impact_score": impact_score,
                "effort_score": effort_score,
                "demand_multiplier": round(demand_multiplier, 2),
                "revenue_multiplier": round(revenue_multiplier, 2),
                "strategic_multiplier": round(strategic_multiplier, 2),
            },
            "break_even_estimate": "2-3 months" if final_roi >= 3 else "6+ months",
        }

    async def analyze_segment_demand(
        self,
        feature_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Analyze demand by customer segment.

        Args:
            feature_id: Optional specific feature

        Returns:
            Dict with segment demand analysis
        """
        segment_demand = {}

        features = [self._features[str(feature_id)]] if feature_id else list(self._features.values())

        for feature in features:
            for segment in feature.segments:
                if segment not in segment_demand:
                    segment_demand[segment] = {
                        "features": [],
                        "total_votes": 0,
                        "total_requests": 0,
                    }

                segment_demand[segment]["features"].append({
                    "id": str(feature.id),
                    "name": feature.name,
                    "votes": feature.votes,
                    "requests": feature.requests,
                })
                segment_demand[segment]["total_votes"] += feature.votes
                segment_demand[segment]["total_requests"] += feature.requests

        # Sort segments by total demand
        sorted_segments = sorted(
            segment_demand.items(),
            key=lambda x: x[1]["total_votes"] + x[1]["total_requests"],
            reverse=True
        )

        return {
            "feature_id": str(feature_id) if feature_id else None,
            "segments": dict(sorted_segments),
            "segment_count": len(segment_demand),
            "top_segment": sorted_segments[0][0] if sorted_segments else None,
        }

    async def identify_competitive_gaps(
        self,
        competitor_features: List[str]
    ) -> Dict[str, Any]:
        """
        Identify competitive gaps.

        Args:
            competitor_features: List of competitor feature names

        Returns:
            Dict with gap analysis
        """
        our_features = {f.name.lower() for f in self._features.values()}
        competitor_set = {f.lower() for f in competitor_features}

        # Find gaps
        gaps = competitor_set - our_features
        covered = competitor_set & our_features
        unique = our_features - competitor_set

        # Score gaps by estimated importance
        gap_priority = []
        for gap in gaps:
            # Estimate priority based on category
            priority = "medium"
            if any(kw in gap for kw in ["security", "api", "integration"]):
                priority = "high"
            elif any(kw in gap for kw in ["analytics", "reporting"]):
                priority = "medium"

            gap_priority.append({
                "feature": gap,
                "priority": priority,
            })

        return {
            "gap_count": len(gaps),
            "coverage_percent": round(len(covered) / len(competitor_set) * 100, 2) if competitor_set else 100,
            "gaps": gap_priority,
            "covered_features": list(covered),
            "unique_advantages": list(unique),
        }

    async def generate_recommendations(
        self,
        count: int = 10
    ) -> List[RoadmapRecommendation]:
        """
        Generate roadmap recommendations.

        Args:
            count: Number of recommendations

        Returns:
            List of RoadmapRecommendation
        """
        features = [f for f in self._features.values() if f.status == FeatureStatus.BACKLOG]

        recommendations = []

        for feature in features:
            # Calculate priority score
            roi_result = await self.calculate_roi(feature.id)
            roi_score = roi_result["roi_score"]

            # Calculate priority components
            popularity_score = feature.votes + feature.requests * 2
            category_score = CATEGORY_IMPORTANCE.get(feature.category, 1)

            # Combined priority score
            priority_score = (
                roi_score * 0.4 +
                (popularity_score / 100) * 0.3 +
                feature.strategic_value * 0.2 +
                category_score * 0.1
            )

            # Generate rationale
            rationale_parts = []
            if roi_score >= 3:
                rationale_parts.append("High ROI potential")
            if popularity_score > 50:
                rationale_parts.append("Strong customer demand")
            if feature.strategic_value > 0.5:
                rationale_parts.append("Strategic importance")
            if not rationale_parts:
                rationale_parts.append("Balanced priority")

            recommendation = RoadmapRecommendation(
                feature_id=feature.id,
                feature_name=feature.name,
                priority_score=priority_score,
                roi_score=roi_score,
                rationale=". ".join(rationale_parts),
                supporting_data={
                    "votes": feature.votes,
                    "requests": feature.requests,
                    "impact": feature.impact.value,
                    "effort": feature.effort.value,
                    "category": feature.category,
                },
            )

            recommendations.append(recommendation)

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)

        # Store top recommendations
        for rec in recommendations[:count]:
            self._recommendations[str(rec.id)] = rec

        logger.info(
            "Roadmap recommendations generated",
            extra={
                "recommendation_count": len(recommendations[:count]),
            }
        )

        return recommendations[:count]

    async def get_feature(self, feature_id: UUID) -> Optional[RoadmapFeature]:
        """Get feature by ID."""
        return self._features.get(str(feature_id))

    async def update_feature_status(
        self,
        feature_id: UUID,
        status: FeatureStatus
    ) -> RoadmapFeature:
        """Update feature status."""
        feature = self._features.get(str(feature_id))
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        feature.status = status

        return feature

    async def get_roadmap_summary(self) -> Dict[str, Any]:
        """Get roadmap summary."""
        features = list(self._features.values())

        by_status = {}
        for feature in features:
            status = feature.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_features": len(features),
            "by_status": by_status,
            "recommendation_count": len(self._recommendations),
        }


# Export for testing
__all__ = [
    "RoadmapIntelligence",
    "RoadmapFeature",
    "RoadmapRecommendation",
    "FeatureStatus",
    "ImpactLevel",
    "EffortLevel",
    "IMPACT_WEIGHTS",
    "EFFORT_WEIGHTS",
]
