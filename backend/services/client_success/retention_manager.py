"""
Retention Manager Service

Manages retention actions including defining actions, priority queues,
tracking, success rate tracking, and recommendations.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of retention actions."""
    CHECK_IN = "check_in"
    TRAINING = "training"
    FEATURE_DEMO = "feature_demo"
    SUCCESS_REVIEW = "success_review"
    ESCALATION = "escalation"
    DISCOUNT = "discount"
    PLAN_UPGRADE = "plan_upgrade"
    PERSONALIZED_OUTREACH = "personalized_outreach"
    ONBOARDING_REVIEW = "onboarding_review"
    EXECUTIVE_SPONSOR = "executive_sponsor"


class ActionPriority(str, Enum):
    """Priority levels for actions."""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionStatus(str, Enum):
    """Status of retention actions."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RetentionAction:
    """A retention action to be taken."""
    action_id: str
    client_id: str
    action_type: ActionType
    priority: ActionPriority
    status: ActionStatus
    title: str
    description: str
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[str] = None
    success: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of a completed action."""
    action_id: str
    client_id: str
    action_type: ActionType
    success: bool
    outcome: str
    completed_at: datetime
    impact_score: float  # 0-100


class RetentionManager:
    """
    Manage retention actions for at-risk clients.

    Provides:
    - Define retention actions
    - Action priority queue
    - Action tracking
    - Success rate tracking
    - Recommended actions
    """

    # Recommended actions by risk level
    ACTIONS_BY_RISK = {
        "critical": [
            (ActionType.EXECUTIVE_SPONSOR, ActionPriority.URGENT),
            (ActionType.ESCALATION, ActionPriority.URGENT),
            (ActionType.PERSONALIZED_OUTREACH, ActionPriority.HIGH),
        ],
        "high": [
            (ActionType.SUCCESS_REVIEW, ActionPriority.HIGH),
            (ActionType.CHECK_IN, ActionPriority.HIGH),
            (ActionType.FEATURE_DEMO, ActionPriority.MEDIUM),
        ],
        "medium": [
            (ActionType.TRAINING, ActionPriority.MEDIUM),
            (ActionType.FEATURE_DEMO, ActionPriority.MEDIUM),
            (ActionType.CHECK_IN, ActionPriority.LOW),
        ],
        "low": [
            (ActionType.CHECK_IN, ActionPriority.LOW),
            (ActionType.ONBOARDING_REVIEW, ActionPriority.LOW),
        ],
    }

    # Priority weights for queue ordering
    PRIORITY_WEIGHTS = {
        ActionPriority.URGENT: 100,
        ActionPriority.HIGH: 75,
        ActionPriority.MEDIUM: 50,
        ActionPriority.LOW: 25,
    }

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize retention manager."""
        self._actions: Dict[str, List[RetentionAction]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }
        self._results: List[ActionResult] = []
        self._action_counter = 0

    def create_action(
        self,
        client_id: str,
        action_type: ActionType,
        priority: ActionPriority,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RetentionAction:
        """
        Create a new retention action.

        Args:
            client_id: Client identifier
            action_type: Type of action
            priority: Priority level
            title: Optional title
            description: Optional description
            scheduled_for: Optional scheduled date
            metadata: Optional metadata

        Returns:
            Created RetentionAction
        """
        if client_id not in self.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client: {client_id}")

        self._action_counter += 1
        action_id = f"action_{self._action_counter:06d}"

        if not title:
            title = self._generate_title(action_type)
        if not description:
            description = self._generate_description(action_type, client_id)

        action = RetentionAction(
            action_id=action_id,
            client_id=client_id,
            action_type=action_type,
            priority=priority,
            status=ActionStatus.PENDING,
            title=title,
            description=description,
            scheduled_for=scheduled_for,
            metadata=metadata or {},
        )

        self._actions[client_id].append(action)
        logger.info(f"Created retention action: {action_id} for {client_id}")

        return action

    def get_recommended_actions(
        self,
        client_id: str,
        risk_level: str
    ) -> List[Dict[str, Any]]:
        """
        Get recommended actions based on risk level.

        Args:
            client_id: Client identifier
            risk_level: Risk level (low, medium, high, critical)

        Returns:
            List of recommended actions with descriptions
        """
        risk_key = risk_level.lower()
        recommendations = self.ACTIONS_BY_RISK.get(risk_key, [])

        result = []
        for action_type, priority in recommendations:
            result.append({
                "action_type": action_type.value,
                "priority": priority.value,
                "title": self._generate_title(action_type),
                "description": self._generate_description(action_type, client_id),
                "recommended": True,
            })

        return result

    def get_priority_queue(self) -> List[RetentionAction]:
        """
        Get pending actions ordered by priority.

        Returns:
            List of pending actions sorted by priority
        """
        all_pending = []

        for client_id, actions in self._actions.items():
            for action in actions:
                if action.status == ActionStatus.PENDING:
                    all_pending.append(action)

        # Sort by priority weight (highest first), then by creation date
        all_pending.sort(
            key=lambda a: (
                -self.PRIORITY_WEIGHTS[a.priority],
                a.created_at
            )
        )

        return all_pending

    def assign_action(
        self,
        action_id: str,
        assigned_to: str
    ) -> Optional[RetentionAction]:
        """
        Assign an action to someone.

        Args:
            action_id: Action identifier
            assigned_to: User to assign to

        Returns:
            Updated RetentionAction
        """
        for client_id, actions in self._actions.items():
            for action in actions:
                if action.action_id == action_id:
                    action.assigned_to = assigned_to
                    action.status = ActionStatus.IN_PROGRESS
                    logger.info(f"Action {action_id} assigned to {assigned_to}")
                    return action

        return None

    def complete_action(
        self,
        action_id: str,
        outcome: str,
        success: bool
    ) -> Optional[RetentionAction]:
        """
        Mark an action as completed.

        Args:
            action_id: Action identifier
            outcome: Outcome description
            success: Whether action was successful

        Returns:
            Updated RetentionAction
        """
        for client_id, actions in self._actions.items():
            for action in actions:
                if action.action_id == action_id:
                    action.status = ActionStatus.COMPLETED
                    action.outcome = outcome
                    action.success = success
                    action.completed_at = datetime.utcnow()

                    # Record result
                    self._record_result(action)

                    logger.info(f"Action {action_id} completed: success={success}")
                    return action

        return None

    def _record_result(self, action: RetentionAction) -> None:
        """Record action result for tracking."""
        # Calculate impact score based on action type and success
        base_impact = {
            ActionType.EXECUTIVE_SPONSOR: 90,
            ActionType.ESCALATION: 85,
            ActionType.PERSONALIZED_OUTREACH: 75,
            ActionType.SUCCESS_REVIEW: 70,
            ActionType.FEATURE_DEMO: 60,
            ActionType.TRAINING: 55,
            ActionType.CHECK_IN: 45,
            ActionType.DISCOUNT: 40,
            ActionType.ONBOARDING_REVIEW: 50,
            ActionType.PLAN_UPGRADE: 65,
        }

        impact = base_impact.get(action.action_type, 50)
        if not action.success:
            impact *= 0.3  # Reduced impact for failed actions

        result = ActionResult(
            action_id=action.action_id,
            client_id=action.client_id,
            action_type=action.action_type,
            success=action.success,
            outcome=action.outcome or "",
            completed_at=action.completed_at or datetime.utcnow(),
            impact_score=round(impact, 1),
        )

        self._results.append(result)

    def get_success_rate(
        self,
        action_type: Optional[ActionType] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate success rate for actions.

        Args:
            action_type: Optional filter by action type
            days: Number of days to analyze

        Returns:
            Dict with success rate metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        relevant_results = [
            r for r in self._results
            if r.completed_at >= cutoff
        ]

        if action_type:
            relevant_results = [
                r for r in relevant_results
                if r.action_type == action_type
            ]

        if not relevant_results:
            return {
                "total_actions": 0,
                "success_rate": 0,
                "avg_impact_score": 0,
            }

        successful = sum(1 for r in relevant_results if r.success)
        avg_impact = sum(r.impact_score for r in relevant_results) / len(relevant_results)

        return {
            "total_actions": len(relevant_results),
            "successful": successful,
            "failed": len(relevant_results) - successful,
            "success_rate": round(successful / len(relevant_results) * 100, 1),
            "avg_impact_score": round(avg_impact, 1),
        }

    def get_client_actions(
        self,
        client_id: str,
        status: Optional[ActionStatus] = None
    ) -> List[RetentionAction]:
        """
        Get actions for a specific client.

        Args:
            client_id: Client identifier
            status: Optional filter by status

        Returns:
            List of actions
        """
        actions = self._actions.get(client_id, [])

        if status:
            actions = [a for a in actions if a.status == status]

        return sorted(actions, key=lambda a: a.created_at, reverse=True)

    def get_overdue_actions(self) -> List[RetentionAction]:
        """
        Get actions that are past their scheduled date.

        Returns:
            List of overdue actions
        """
        now = datetime.utcnow()
        overdue = []

        for client_id, actions in self._actions.items():
            for action in actions:
                if (action.status in [ActionStatus.PENDING, ActionStatus.IN_PROGRESS]
                    and action.scheduled_for
                    and action.scheduled_for < now):
                    overdue.append(action)

        overdue.sort(key=lambda a: a.scheduled_for or datetime.max)
        return overdue

    def get_action_summary(self) -> Dict[str, Any]:
        """Get summary of all retention actions."""
        total = 0
        by_status = {s.value: 0 for s in ActionStatus}
        by_priority = {p.value: 0 for p in ActionPriority}

        for client_id, actions in self._actions.items():
            for action in actions:
                total += 1
                by_status[action.status.value] += 1
                by_priority[action.priority.value] += 1

        success_rate = self.get_success_rate()

        return {
            "total_actions": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "pending_count": by_status["pending"],
            "success_rate": success_rate["success_rate"],
            "avg_impact_score": success_rate["avg_impact_score"],
        }

    def _generate_title(self, action_type: ActionType) -> str:
        """Generate title for an action type."""
        titles = {
            ActionType.CHECK_IN: "Proactive Check-in",
            ActionType.TRAINING: "Training Session",
            ActionType.FEATURE_DEMO: "Feature Demo",
            ActionType.SUCCESS_REVIEW: "Success Review Meeting",
            ActionType.ESCALATION: "Escalate to Leadership",
            ActionType.DISCOUNT: "Offer Discount/Renewal Terms",
            ActionType.PLAN_UPGRADE: "Plan Upgrade Discussion",
            ActionType.PERSONALIZED_OUTREACH: "Personalized Outreach",
            ActionType.ONBOARDING_REVIEW: "Onboarding Review",
            ActionType.EXECUTIVE_SPONSOR: "Executive Sponsor Engagement",
        }
        return titles.get(action_type, "Retention Action")

    def _generate_description(self, action_type: ActionType, client_id: str) -> str:
        """Generate description for an action."""
        descriptions = {
            ActionType.CHECK_IN: f"Schedule a check-in call with {client_id} to understand current needs",
            ActionType.TRAINING: f"Offer additional training session to improve feature adoption",
            ActionType.FEATURE_DEMO: f"Demonstrate underutilized features to increase value perception",
            ActionType.SUCCESS_REVIEW: f"Conduct quarterly success review to align on goals",
            ActionType.ESCALATION: f"Escalate to leadership for executive-level engagement",
            ActionType.DISCOUNT: f"Discuss renewal terms and potential discount options",
            ActionType.PLAN_UPGRADE: f"Explore plan upgrade opportunities for additional features",
            ActionType.PERSONALIZED_OUTREACH: f"Send personalized communication to re-engage",
            ActionType.ONBOARDING_REVIEW: f"Review onboarding progress and address gaps",
            ActionType.EXECUTIVE_SPONSOR: f"Engage executive sponsor for strategic partnership",
        }
        return descriptions.get(action_type, "Retention action to prevent churn")
