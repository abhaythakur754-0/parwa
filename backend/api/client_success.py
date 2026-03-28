"""
Client Success API Endpoints

API endpoints for client success features including:
- Health monitoring
- Onboarding analytics
- Milestone tracking
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.dependencies import get_db, get_current_user
from backend.services.client_success.health_monitor import (
    HealthMonitor,
    HealthStatus,
    ClientHealthSnapshot,
)
from backend.services.client_success.health_scorer import (
    HealthScorer,
    TrendDirection,
)
from backend.services.client_success.alert_manager import (
    AlertManager,
    AlertSeverity,
    AlertType,
)


router = APIRouter(prefix="/client-success", tags=["Client Success"])


# ============ Schemas ============

class HealthScoreResponse(BaseModel):
    """Response schema for health score."""
    client_id: str
    overall_score: float
    status: str
    grade: str
    trend: str
    activity_level: float
    accuracy_rate: float
    avg_response_time: float
    resolution_rate: float
    engagement_score: float
    timestamp: datetime


class ClientHealthListResponse(BaseModel):
    """Response for list of client health scores."""
    clients: List[HealthScoreResponse]
    average_score: float
    total_clients: int
    status_distribution: dict


class OnboardingProgressResponse(BaseModel):
    """Response schema for onboarding progress."""
    client_id: str
    status: str
    completion_percentage: float
    current_step: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_time_minutes: float


class MilestoneResponse(BaseModel):
    """Response schema for milestone."""
    milestone_id: str
    name: str
    description: str
    status: str
    progress_percentage: float
    due_at: Optional[datetime]
    achieved_at: Optional[datetime]


class AlertResponse(BaseModel):
    """Response schema for alert."""
    alert_id: str
    client_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    timestamp: datetime
    acknowledged: bool


class OnboardingAnalyticsResponse(BaseModel):
    """Response for onboarding analytics."""
    average_time_minutes: float
    completion_rate: float
    by_industry: dict
    by_variant: dict
    bottlenecks: List[dict]


# ============ Health Endpoints ============

@router.get("/health", response_model=ClientHealthListResponse)
async def get_all_client_health(
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get health scores for all clients.

    Returns health metrics for all tracked clients.
    """
    monitor = HealthMonitor(db)
    snapshots = await monitor.monitor_all_clients()

    clients = []
    total_score = 0

    for client_id, snapshot in snapshots.items():
        total_score += snapshot.overall_health
        clients.append(HealthScoreResponse(
            client_id=client_id,
            overall_score=snapshot.overall_health,
            status=snapshot.status.value,
            grade=_score_to_grade(snapshot.overall_health),
            trend=_determine_trend(snapshot),
            activity_level=snapshot.activity_level,
            accuracy_rate=snapshot.accuracy_rate,
            avg_response_time=snapshot.avg_response_time,
            resolution_rate=snapshot.resolution_rate,
            engagement_score=snapshot.engagement_score,
            timestamp=snapshot.timestamp,
        ))

    return ClientHealthListResponse(
        clients=clients,
        average_score=round(total_score / len(clients), 1) if clients else 0,
        total_clients=len(clients),
        status_distribution=_calculate_status_distribution(clients),
    )


@router.get("/health/{client_id}", response_model=HealthScoreResponse)
async def get_client_health(
    client_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get health score for a specific client.

    Args:
        client_id: Client identifier (e.g., "client_001")
    """
    monitor = HealthMonitor(db)

    try:
        snapshot = await monitor.monitor_client(client_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    return HealthScoreResponse(
        client_id=client_id,
        overall_score=snapshot.overall_health,
        status=snapshot.status.value,
        grade=_score_to_grade(snapshot.overall_health),
        trend=_determine_trend(snapshot),
        activity_level=snapshot.activity_level,
        accuracy_rate=snapshot.accuracy_rate,
        avg_response_time=snapshot.avg_response_time,
        resolution_rate=snapshot.resolution_rate,
        engagement_score=snapshot.engagement_score,
        timestamp=snapshot.timestamp,
    )


@router.get("/health/{client_id}/history")
async def get_client_health_history(
    client_id: str,
    days: int = Query(7, ge=1, le=30),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get health score history for a client.

    Args:
        client_id: Client identifier
        days: Number of days of history (1-30)
    """
    monitor = HealthMonitor(db)
    history = monitor.get_client_history(client_id, days=days)

    return {
        "client_id": client_id,
        "days": days,
        "history": [
            {
                "timestamp": s.timestamp.isoformat(),
                "overall_health": s.overall_health,
                "status": s.status.value,
            }
            for s in history
        ]
    }


# ============ Onboarding Endpoints ============

@router.get("/onboarding/{client_id}", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    client_id: str,
    current_user = Depends(get_current_user)
):
    """
    Get onboarding progress for a client.

    Args:
        client_id: Client identifier
    """
    from backend.services.client_success.onboarding_tracker import OnboardingTracker

    tracker = OnboardingTracker()

    try:
        progress = tracker.get_client_progress(client_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    return OnboardingProgressResponse(
        client_id=client_id,
        status=progress.status.value,
        completion_percentage=progress.completion_percentage,
        current_step=progress.current_step.value if progress.current_step else None,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        total_time_minutes=progress.total_time_minutes,
    )


@router.get("/analytics", response_model=OnboardingAnalyticsResponse)
async def get_onboarding_analytics(
    current_user = Depends(get_current_user)
):
    """
    Get onboarding analytics.

    Returns average time, completion rates, and bottlenecks.
    """
    from backend.services.client_success.onboarding_tracker import OnboardingTracker
    from backend.services.client_success.onboarding_analytics import OnboardingAnalytics

    tracker = OnboardingTracker()
    analytics = OnboardingAnalytics(tracker)

    summary = analytics.get_analytics_summary()

    return OnboardingAnalyticsResponse(
        average_time_minutes=summary["average_time"].get("average_time_minutes", 0),
        completion_rate=summary["average_time"].get("completion_rate", 0),
        by_industry=summary["completion_by_industry"],
        by_variant=summary["completion_by_variant"],
        bottlenecks=summary["bottlenecks"],
    )


# ============ Milestone Endpoints ============

@router.get("/milestones/{client_id}", response_model=List[MilestoneResponse])
async def get_client_milestones(
    client_id: str,
    current_user = Depends(get_current_user)
):
    """
    Get milestones for a client.

    Args:
        client_id: Client identifier
    """
    from backend.services.client_success.milestone_manager import MilestoneManager

    manager = MilestoneManager()

    try:
        milestones = manager.get_client_milestones(client_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    return [
        MilestoneResponse(
            milestone_id=m.milestone_id,
            name=manager._definitions.get(m.milestone_id, type('', (), {'name': m.milestone_id})()).name,
            description=manager._definitions.get(m.milestone_id, type('', (), {'description': ''})()).description,
            status=m.status.value,
            progress_percentage=m.progress_percentage,
            due_at=m.due_at,
            achieved_at=m.achieved_at,
        )
        for m in milestones.values()
    ]


@router.post("/milestones/{client_id}/{milestone_id}/achieve")
async def achieve_milestone(
    client_id: str,
    milestone_id: str,
    current_user = Depends(get_current_user)
):
    """
    Mark a milestone as achieved.

    Args:
        client_id: Client identifier
        milestone_id: Milestone identifier
    """
    from backend.services.client_success.milestone_manager import MilestoneManager

    manager = MilestoneManager()
    progress = manager.mark_achieved(client_id, milestone_id)

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found"
        )

    return {"status": "achieved", "milestone_id": milestone_id}


# ============ Alert Endpoints ============

@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    client_id: Optional[str] = None,
    severity: Optional[str] = None,
    active_only: bool = True,
    current_user = Depends(get_current_user)
):
    """
    Get health alerts.

    Args:
        client_id: Optional filter by client
        severity: Optional filter by severity
        active_only: Only return active (unacknowledged) alerts
    """
    alert_manager = AlertManager()

    if active_only:
        severity_enum = AlertSeverity(severity) if severity else None
        alerts = alert_manager.get_active_alerts(client_id, severity_enum)
    else:
        alerts = alert_manager.get_alert_history(client_id)

    return [
        AlertResponse(
            alert_id=a.alert_id,
            client_id=a.client_id,
            alert_type=a.alert_type.value,
            severity=a.severity.value,
            title=a.title,
            message=a.message,
            timestamp=a.timestamp,
            acknowledged=a.acknowledged,
        )
        for a in alerts[:50]  # Limit to 50
    ]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user = Depends(get_current_user)
):
    """
    Acknowledge an alert.

    Args:
        alert_id: Alert identifier
    """
    alert_manager = AlertManager()
    alert = alert_manager.acknowledge_alert(alert_id, str(current_user.id))

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return {"status": "acknowledged", "alert_id": alert_id}


# ============ Summary Endpoints ============

@router.get("/summary")
async def get_client_success_summary(
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get comprehensive client success summary.

    Returns health, onboarding, and milestone summaries.
    """
    monitor = HealthMonitor(db)
    alert_manager = AlertManager()

    # Get health summary
    await monitor.monitor_all_clients()
    health_summary = monitor.get_health_summary()

    # Get alert summary
    alert_summary = alert_manager.get_alert_summary()

    return {
        "health": health_summary,
        "alerts": alert_summary,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============ Helper Functions ============

def _score_to_grade(score: float) -> str:
    """Convert score to grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _determine_trend(snapshot) -> str:
    """Determine trend from snapshot metrics."""
    # Simple trend based on metric directions
    up_count = sum(1 for m in snapshot.metrics if m.trend == "up")
    down_count = sum(1 for m in snapshot.metrics if m.trend == "down")

    if up_count > down_count:
        return "improving"
    elif down_count > up_count:
        return "declining"
    else:
        return "stable"


def _calculate_status_distribution(clients: List[HealthScoreResponse]) -> dict:
    """Calculate distribution of health statuses."""
    distribution = {}
    for client in clients:
        status = client.status
        distribution[status] = distribution.get(status, 0) + 1
    return distribution
