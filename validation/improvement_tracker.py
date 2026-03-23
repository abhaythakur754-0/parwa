"""
Improvement Tracker - Track accuracy improvements over time.

CRITICAL: Tracks aggregated improvement metrics only.
No client-specific data is exposed in tracking.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Direction of improvement trend"""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class MilestoneStatus(Enum):
    """Status of a milestone"""
    ACHIEVED = "achieved"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    MISSED = "missed"


@dataclass
class ImprovementRecord:
    """
    Record of accuracy improvement at a point in time.
    
    CRITICAL: Contains only aggregated metrics, no client data.
    """
    record_id: str
    timestamp: datetime
    week: int
    phase: int
    
    # Accuracy metrics
    baseline_accuracy: float
    current_accuracy: float
    improvement_percentage: float
    cumulative_improvement: float
    
    # Per-client aggregated (no client IDs exposed)
    clients_improved: int
    clients_total: int
    average_client_improvement: float
    
    # Trend information
    trend: TrendDirection
    velocity: float  # Rate of improvement per week
    
    # Milestone tracking
    milestone: str
    milestone_status: MilestoneStatus
    
    # Additional metadata
    training_runs: int
    collective_intelligence_active: bool
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "week": self.week,
            "phase": self.phase,
            "baseline_accuracy": self.baseline_accuracy,
            "current_accuracy": self.current_accuracy,
            "improvement_percentage": self.improvement_percentage,
            "cumulative_improvement": self.cumulative_improvement,
            "clients_improved": self.clients_improved,
            "clients_total": self.clients_total,
            "average_client_improvement": self.average_client_improvement,
            "trend": self.trend.value,
            "velocity": self.velocity,
            "milestone": self.milestone,
            "milestone_status": self.milestone_status.value,
            "training_runs": self.training_runs,
            "collective_intelligence_active": self.collective_intelligence_active,
            "notes": self.notes,
        }


@dataclass
class Milestone:
    """Represents an accuracy improvement milestone"""
    name: str
    target_accuracy: float
    required_improvement: float
    deadline_week: int
    achieved: bool = False
    achieved_week: Optional[int] = None
    achieved_date: Optional[datetime] = None

    def check_achievement(
        self,
        current_accuracy: float,
        current_week: int
    ) -> bool:
        """Check if milestone is achieved"""
        if current_accuracy >= self.target_accuracy:
            self.achieved = True
            self.achieved_week = current_week
            self.achieved_date = datetime.now()
            return True
        return False


class ImprovementTracker:
    """
    Tracks accuracy improvements over time.
    
    Tracks improvement from Week 19 baseline (72%) to Week 22 target (77%).
    All tracking uses aggregated metrics only - no client data exposed.
    """

    # Baseline accuracy (Week 19)
    BASELINE_ACCURACY = 0.72
    
    # Target accuracy (Week 22)
    TARGET_ACCURACY = 0.77
    
    # Required minimum improvement
    REQUIRED_IMPROVEMENT = 0.05  # 5%

    # Milestones for accuracy improvement journey
    MILESTONES = [
        Milestone("baseline", 0.72, 0.00, 19),
        Milestone("initial_improvement", 0.74, 0.02, 20),
        Milestone("training_boost", 0.76, 0.04, 21),
        Milestone("target_achieved", 0.77, 0.05, 22),
        Milestone("excellence", 0.80, 0.08, 24),
    ]

    def __init__(
        self,
        baseline_accuracy: float = BASELINE_ACCURACY,
        target_accuracy: float = TARGET_ACCURACY,
    ):
        """
        Initialize improvement tracker.

        Args:
            baseline_accuracy: Starting accuracy (default 72%)
            target_accuracy: Target accuracy (default 77%)
        """
        self.baseline_accuracy = baseline_accuracy
        self.target_accuracy = target_accuracy
        self._records: List[ImprovementRecord] = []
        self._milestones = list(self.MILESTONES)  # Copy milestones

    def record_improvement(
        self,
        current_accuracy: float,
        week: int,
        phase: int,
        clients_improved: int,
        clients_total: int,
        training_runs: int = 0,
        collective_intelligence_active: bool = False,
        notes: str = "",
    ) -> ImprovementRecord:
        """
        Record an accuracy improvement measurement.

        Args:
            current_accuracy: Current measured accuracy
            week: Current week number
            phase: Current phase number
            clients_improved: Number of clients showing improvement
            clients_total: Total number of clients
            training_runs: Number of training runs completed
            collective_intelligence_active: Whether CI is active
            notes: Additional notes

        Returns:
            ImprovementRecord
        """
        # Calculate improvements
        improvement_pct = ((current_accuracy - self.baseline_accuracy) / self.baseline_accuracy) * 100
        
        # Calculate cumulative improvement
        if self._records:
            cumulative = self._records[-1].cumulative_improvement + improvement_pct
        else:
            cumulative = improvement_pct

        # Determine trend
        trend = self._calculate_trend(current_accuracy)
        
        # Calculate velocity (improvement per week)
        velocity = self._calculate_velocity(current_accuracy, week)
        
        # Check milestone status
        milestone, milestone_status = self._check_milestone(current_accuracy, week)
        
        # Calculate average client improvement (aggregated only)
        avg_client_improvement = improvement_pct if clients_improved > 0 else 0.0

        # Create record
        record = ImprovementRecord(
            record_id=self._generate_record_id(),
            timestamp=datetime.now(),
            week=week,
            phase=phase,
            baseline_accuracy=self.baseline_accuracy,
            current_accuracy=current_accuracy,
            improvement_percentage=improvement_pct,
            cumulative_improvement=cumulative,
            clients_improved=clients_improved,
            clients_total=clients_total,
            average_client_improvement=avg_client_improvement,
            trend=trend,
            velocity=velocity,
            milestone=milestone,
            milestone_status=milestone_status,
            training_runs=training_runs,
            collective_intelligence_active=collective_intelligence_active,
            notes=notes,
        )

        self._records.append(record)

        logger.info(
            f"Recorded improvement for Week {week}: "
            f"accuracy={current_accuracy:.2%}, improvement={improvement_pct:.2f}%, "
            f"trend={trend.value}"
        )

        return record

    def get_improvement_history(self, limit: int = 20) -> List[ImprovementRecord]:
        """Get improvement history"""
        return self._records[-limit:]

    def get_latest_record(self) -> Optional[ImprovementRecord]:
        """Get most recent improvement record"""
        return self._records[-1] if self._records else None

    def get_milestone_progress(self) -> Dict[str, Any]:
        """Get progress towards milestones"""
        current_accuracy = (
            self._records[-1].current_accuracy
            if self._records else self.baseline_accuracy
        )

        progress = []
        for milestone in self._milestones:
            status = "achieved" if milestone.achieved else (
                "in_progress" if current_accuracy >= milestone.target_accuracy * 0.9
                else "not_started"
            )
            progress.append({
                "name": milestone.name,
                "target_accuracy": milestone.target_accuracy,
                "current_accuracy": current_accuracy,
                "gap": max(0, milestone.target_accuracy - current_accuracy),
                "status": status,
                "deadline_week": milestone.deadline_week,
                "achieved_week": milestone.achieved_week,
            })

        return {
            "milestones": progress,
            "current_milestone": self._get_current_milestone_name(),
            "overall_progress_pct": self._calculate_progress_percentage(current_accuracy),
        }

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive improvement report.

        Returns:
            Dict with complete improvement tracking report
        """
        latest = self.get_latest_record()
        if not latest:
            return {
                "status": "no_data",
                "message": "No improvement records available",
            }

        history = self.get_improvement_history()
        
        return {
            "summary": {
                "baseline_accuracy": self.baseline_accuracy,
                "current_accuracy": latest.current_accuracy,
                "target_accuracy": self.target_accuracy,
                "total_improvement": latest.improvement_percentage,
                "meets_target": latest.current_accuracy >= self.target_accuracy,
            },
            "trend_analysis": {
                "current_trend": latest.trend.value,
                "velocity": latest.velocity,
                "predicted_target_date": self._predict_target_date(latest),
            },
            "client_summary": {
                "clients_improved": latest.clients_improved,
                "clients_total": latest.clients_total,
                "improvement_rate": latest.clients_improved / latest.clients_total,
            },
            "milestone_progress": self.get_milestone_progress(),
            "history": [r.to_dict() for r in history],
            "recommendations": self._generate_recommendations(latest),
        }

    def _calculate_trend(self, current_accuracy: float) -> TrendDirection:
        """Calculate improvement trend"""
        if len(self._records) < 1:
            return TrendDirection.STABLE

        previous = self._records[-1].current_accuracy
        diff = current_accuracy - previous

        if diff > 0.001:  # 0.1% improvement
            return TrendDirection.UP
        elif diff < -0.001:  # 0.1% decline
            return TrendDirection.DOWN
        else:
            return TrendDirection.STABLE

    def _calculate_velocity(self, current_accuracy: float, week: int) -> float:
        """Calculate improvement velocity (per week)"""
        if week <= 19:
            return 0.0

        improvement = current_accuracy - self.baseline_accuracy
        weeks_elapsed = week - 19

        return improvement / weeks_elapsed if weeks_elapsed > 0 else 0.0

    def _check_milestone(
        self,
        current_accuracy: float,
        current_week: int
    ) -> tuple[str, MilestoneStatus]:
        """Check which milestone we're at"""
        for milestone in self._milestones:
            if not milestone.achieved:
                if milestone.check_achievement(current_accuracy, current_week):
                    logger.info(f"Milestone achieved: {milestone.name}")
                    return milestone.name, MilestoneStatus.ACHIEVED
                elif current_week <= milestone.deadline_week:
                    return milestone.name, MilestoneStatus.IN_PROGRESS
                else:
                    return milestone.name, MilestoneStatus.MISSED

        # All milestones achieved
        return "excellence", MilestoneStatus.ACHIEVED

    def _get_current_milestone_name(self) -> str:
        """Get name of current milestone being worked towards"""
        for milestone in self._milestones:
            if not milestone.achieved:
                return milestone.name
        return "excellence"

    def _calculate_progress_percentage(self, current_accuracy: float) -> float:
        """Calculate progress percentage towards target"""
        total_gap = self.target_accuracy - self.baseline_accuracy
        current_gap = self.target_accuracy - current_accuracy

        if total_gap <= 0:
            return 100.0

        progress = 1 - (current_gap / total_gap)
        return max(0, min(100, progress * 100))

    def _predict_target_date(self, latest: ImprovementRecord) -> Optional[str]:
        """Predict when target will be reached"""
        if latest.current_accuracy >= self.target_accuracy:
            return "already_achieved"

        if latest.velocity <= 0:
            return "insufficient_velocity"

        remaining_gap = self.target_accuracy - latest.current_accuracy
        weeks_to_target = remaining_gap / latest.velocity

        predicted_week = latest.week + int(weeks_to_target)

        return f"week_{predicted_week}"

    def _generate_recommendations(self, latest: ImprovementRecord) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []

        if latest.current_accuracy < self.target_accuracy:
            gap = self.target_accuracy - latest.current_accuracy
            recommendations.append(
                f"Increase training data to close {gap:.1%} accuracy gap"
            )

        if latest.velocity < 0.01:  # Less than 1% per week
            recommendations.append(
                "Consider additional training iterations or hyperparameter tuning"
            )

        if latest.clients_improved < latest.clients_total:
            recommendations.append(
                f"Focus on {latest.clients_total - latest.clients_improved} clients "
                f"not yet showing improvement"
            )

        if not latest.collective_intelligence_active:
            recommendations.append(
                "Activate collective intelligence for cross-client improvement"
            )

        if latest.trend == TrendDirection.DOWN:
            recommendations.append(
                "Investigate recent accuracy decline - consider rollback"
            )

        return recommendations

    def _generate_record_id(self) -> str:
        """Generate unique record ID"""
        import hashlib
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:8]


def track_improvement(
    current_accuracy: float,
    week: int,
    phase: int,
    clients_improved: int,
    clients_total: int,
    baseline_accuracy: float = 0.72,
    target_accuracy: float = 0.77,
) -> ImprovementRecord:
    """
    Convenience function to track improvement.

    Args:
        current_accuracy: Current measured accuracy
        week: Current week number
        phase: Current phase number
        clients_improved: Number of clients showing improvement
        clients_total: Total number of clients
        baseline_accuracy: Starting accuracy (default 72%)
        target_accuracy: Target accuracy (default 77%)

    Returns:
        ImprovementRecord
    """
    tracker = ImprovementTracker(
        baseline_accuracy=baseline_accuracy,
        target_accuracy=target_accuracy,
    )
    return tracker.record_improvement(
        current_accuracy=current_accuracy,
        week=week,
        phase=phase,
        clients_improved=clients_improved,
        clients_total=clients_total,
    )
