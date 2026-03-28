"""
Milestone Manager Service

Manages onboarding milestones including definition, tracking,
notifications, and custom milestone support.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class MilestoneType(str, Enum):
    """Types of onboarding milestones."""
    ONBOARDING_COMPLETE = "onboarding_complete"
    FIRST_TICKET = "first_ticket"
    FIRST_RESOLUTION = "first_resolution"
    INTEGRATION_CONNECTED = "integration_connected"
    KNOWLEDGE_BASE_POPULATED = "knowledge_base_populated"
    TEAM_MEMBERS_ADDED = "team_members_added"
    TRAINING_COMPLETE = "training_complete"
    ACCURACY_THRESHOLD = "accuracy_threshold"
    RESPONSE_TIME_TARGET = "response_time_target"
    CUSTOM = "custom"


class MilestoneStatus(str, Enum):
    """Status of a milestone."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    MISSED = "missed"


@dataclass
class MilestoneDefinition:
    """Definition of a milestone."""
    milestone_id: str
    name: str
    description: str
    milestone_type: MilestoneType
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    due_days_from_start: Optional[int] = None
    is_required: bool = True
    notification_templates: Dict[str, str] = field(default_factory=dict)


@dataclass
class MilestoneProgress:
    """Progress tracking for a milestone."""
    milestone_id: str
    client_id: str
    status: MilestoneStatus
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    started_at: Optional[datetime] = None
    achieved_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    progress_percentage: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MilestoneNotification:
    """Notification for a milestone event."""
    notification_id: str
    client_id: str
    milestone_id: str
    notification_type: str  # achieved, due_soon, overdue, missed
    message: str
    created_at: datetime
    sent: bool = False
    sent_at: Optional[datetime] = None


class MilestoneManager:
    """
    Manage onboarding milestones.

    Provides:
    - Define onboarding milestones
    - Track milestone completion
    - Milestone notifications
    - Custom milestone support
    """

    # Default milestone templates
    DEFAULT_MILESTONES = [
        MilestoneDefinition(
            milestone_id="first_week_complete",
            name="First Week Complete",
            description="Complete first week of onboarding",
            milestone_type=MilestoneType.ONBOARDING_COMPLETE,
            due_days_from_start=7,
            is_required=True,
        ),
        MilestoneDefinition(
            milestone_id="first_ticket_handled",
            name="First Ticket Handled",
            description="Successfully handle first support ticket",
            milestone_type=MilestoneType.FIRST_TICKET,
            due_days_from_start=14,
            is_required=True,
        ),
        MilestoneDefinition(
            milestone_id="first_resolution",
            name="First Resolution",
            description="Achieve first successful ticket resolution",
            milestone_type=MilestoneType.FIRST_RESOLUTION,
            due_days_from_start=14,
            is_required=True,
        ),
        MilestoneDefinition(
            milestone_id="accuracy_80",
            name="80% Accuracy Achieved",
            description="Reach 80% accuracy rate",
            milestone_type=MilestoneType.ACCURACY_THRESHOLD,
            target_value=80.0,
            target_unit="percentage",
            due_days_from_start=30,
            is_required=True,
        ),
        MilestoneDefinition(
            milestone_id="integrations_complete",
            name="Integrations Complete",
            description="All selected integrations connected",
            milestone_type=MilestoneType.INTEGRATION_CONNECTED,
            due_days_from_start=7,
            is_required=False,
        ),
        MilestoneDefinition(
            milestone_id="team_setup",
            name="Team Setup Complete",
            description="Add at least 2 team members",
            milestone_type=MilestoneType.TEAM_MEMBERS_ADDED,
            target_value=2,
            target_unit="members",
            due_days_from_start=7,
            is_required=False,
        ),
        MilestoneDefinition(
            milestone_id="knowledge_base_ready",
            name="Knowledge Base Ready",
            description="Knowledge base populated with 10+ entries",
            milestone_type=MilestoneType.KNOWLEDGE_BASE_POPULATED,
            target_value=10,
            target_unit="entries",
            due_days_from_start=14,
            is_required=True,
        ),
    ]

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize milestone manager."""
        self._definitions: Dict[str, MilestoneDefinition] = {
            m.milestone_id: m for m in self.DEFAULT_MILESTONES
        }
        self._progress: Dict[str, Dict[str, MilestoneProgress]] = {
            client: {} for client in self.SUPPORTED_CLIENTS
        }
        self._notifications: List[MilestoneNotification] = []
        self._notification_counter = 0

    def define_milestone(
        self,
        name: str,
        description: str,
        milestone_type: MilestoneType,
        target_value: Optional[float] = None,
        target_unit: Optional[str] = None,
        due_days_from_start: Optional[int] = None,
        is_required: bool = True
    ) -> MilestoneDefinition:
        """
        Define a new milestone.

        Args:
            name: Milestone name
            description: Milestone description
            milestone_type: Type of milestone
            target_value: Optional target value
            target_unit: Optional unit for target value
            due_days_from_start: Days from onboarding start
            is_required: Whether milestone is required

        Returns:
            Created MilestoneDefinition
        """
        milestone_id = f"{milestone_type.value}_{uuid.uuid4().hex[:8]}"

        milestone = MilestoneDefinition(
            milestone_id=milestone_id,
            name=name,
            description=description,
            milestone_type=milestone_type,
            target_value=target_value,
            target_unit=target_unit,
            due_days_from_start=due_days_from_start,
            is_required=is_required,
        )

        self._definitions[milestone_id] = milestone
        logger.info(f"Defined milestone: {name} ({milestone_id})")

        return milestone

    def start_tracking(
        self,
        client_id: str,
        onboarding_start: datetime
    ) -> Dict[str, MilestoneProgress]:
        """
        Start tracking milestones for a client.

        Args:
            client_id: Client identifier
            onboarding_start: Onboarding start date

        Returns:
            Dict of milestone progress for the client
        """
        if client_id not in self._progress:
            raise ValueError(f"Unsupported client: {client_id}")

        progress_dict = {}

        for milestone_id, definition in self._definitions.items():
            due_at = None
            if definition.due_days_from_start:
                due_at = onboarding_start + timedelta(days=definition.due_days_from_start)

            progress = MilestoneProgress(
                milestone_id=milestone_id,
                client_id=client_id,
                status=MilestoneStatus.PENDING,
                target_value=definition.target_value,
                due_at=due_at,
                started_at=onboarding_start,
            )

            progress_dict[milestone_id] = progress
            self._progress[client_id][milestone_id] = progress

        logger.info(f"Started tracking {len(progress_dict)} milestones for {client_id}")
        return progress_dict

    def update_progress(
        self,
        client_id: str,
        milestone_type: MilestoneType,
        current_value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[MilestoneProgress]:
        """
        Update progress for a milestone type.

        Args:
            client_id: Client identifier
            milestone_type: Type of milestone
            current_value: Current value
            metadata: Optional metadata

        Returns:
            Updated MilestoneProgress if found
        """
        # Find milestone by type
        milestone_id = None
        definition = None
        for mid, mdef in self._definitions.items():
            if mdef.milestone_type == milestone_type:
                milestone_id = mid
                definition = mdef
                break

        if not milestone_id or milestone_id not in self._progress.get(client_id, {}):
            return None

        progress = self._progress[client_id][milestone_id]
        progress.current_value = current_value

        if metadata:
            progress.metadata.update(metadata)

        # Check if achieved
        if definition and definition.target_value:
            progress.progress_percentage = min(100, (current_value / definition.target_value) * 100)

            if current_value >= definition.target_value:
                self._achieve_milestone(client_id, milestone_id)
        else:
            # No target value means just mark as in progress
            progress.status = MilestoneStatus.IN_PROGRESS

        return progress

    def mark_achieved(
        self,
        client_id: str,
        milestone_id: str
    ) -> Optional[MilestoneProgress]:
        """
        Manually mark a milestone as achieved.

        Args:
            client_id: Client identifier
            milestone_id: Milestone identifier

        Returns:
            Updated MilestoneProgress
        """
        return self._achieve_milestone(client_id, milestone_id)

    def _achieve_milestone(
        self,
        client_id: str,
        milestone_id: str
    ) -> Optional[MilestoneProgress]:
        """Internal method to mark milestone as achieved."""
        if milestone_id not in self._progress.get(client_id, {}):
            return None

        progress = self._progress[client_id][milestone_id]
        progress.status = MilestoneStatus.ACHIEVED
        progress.achieved_at = datetime.utcnow()
        progress.progress_percentage = 100.0

        definition = self._definitions.get(milestone_id)
        milestone_name = definition.name if definition else milestone_id

        logger.info(f"Milestone achieved: {milestone_name} for {client_id}")

        # Create notification
        self._create_notification(
            client_id=client_id,
            milestone_id=milestone_id,
            notification_type="achieved",
            message=f"Congratulations! '{milestone_name}' milestone achieved!"
        )

        return progress

    def check_overdue_milestones(self) -> Dict[str, List[str]]:
        """
        Check for overdue milestones.

        Returns:
            Dict mapping client_id to list of overdue milestone IDs
        """
        overdue = {}
        now = datetime.utcnow()

        for client_id, milestones in self._progress.items():
            client_overdue = []

            for milestone_id, progress in milestones.items():
                if progress.status in [MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS]:
                    if progress.due_at and progress.due_at < now:
                        progress.status = MilestoneStatus.MISSED
                        client_overdue.append(milestone_id)

                        # Create notification
                        definition = self._definitions.get(milestone_id)
                        name = definition.name if definition else milestone_id
                        self._create_notification(
                            client_id=client_id,
                            milestone_id=milestone_id,
                            notification_type="overdue",
                            message=f"Milestone '{name}' is overdue. Please take action."
                        )

            if client_overdue:
                overdue[client_id] = client_overdue

        return overdue

    def get_upcoming_milestones(
        self,
        client_id: str,
        days_ahead: int = 7
    ) -> List[MilestoneProgress]:
        """
        Get upcoming milestones due within specified days.

        Args:
            client_id: Client identifier
            days_ahead: Days to look ahead

        Returns:
            List of upcoming MilestoneProgress
        """
        if client_id not in self._progress:
            return []

        now = datetime.utcnow()
        cutoff = now + timedelta(days=days_ahead)

        upcoming = []
        for progress in self._progress[client_id].values():
            if progress.status in [MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS]:
                if progress.due_at and now <= progress.due_at <= cutoff:
                    upcoming.append(progress)

        # Sort by due date
        upcoming.sort(key=lambda p: p.due_at or datetime.max)
        return upcoming

    def get_client_milestones(
        self,
        client_id: str
    ) -> Dict[str, MilestoneProgress]:
        """
        Get all milestones for a client.

        Args:
            client_id: Client identifier

        Returns:
            Dict of milestone progress
        """
        return self._progress.get(client_id, {}).copy()

    def get_milestone_summary(
        self,
        client_id: str
    ) -> Dict[str, Any]:
        """
        Get milestone summary for a client.

        Args:
            client_id: Client identifier

        Returns:
            Summary dict with counts and progress
        """
        milestones = self._progress.get(client_id, {})

        total = len(milestones)
        achieved = sum(1 for m in milestones.values() if m.status == MilestoneStatus.ACHIEVED)
        pending = sum(1 for m in milestones.values() if m.status == MilestoneStatus.PENDING)
        in_progress = sum(1 for m in milestones.values() if m.status == MilestoneStatus.IN_PROGRESS)
        missed = sum(1 for m in milestones.values() if m.status == MilestoneStatus.MISSED)

        required_achieved = sum(
            1 for mid, m in milestones.items()
            if m.status == MilestoneStatus.ACHIEVED and
            self._definitions.get(mid, MilestoneDefinition("", "", "", MilestoneType.CUSTOM)).is_required
        )

        return {
            "client_id": client_id,
            "total_milestones": total,
            "achieved": achieved,
            "pending": pending,
            "in_progress": in_progress,
            "missed": missed,
            "completion_rate": round((achieved / total * 100) if total > 0 else 0, 1),
            "required_achieved": required_achieved,
        }

    def _create_notification(
        self,
        client_id: str,
        milestone_id: str,
        notification_type: str,
        message: str
    ) -> MilestoneNotification:
        """Create a milestone notification."""
        self._notification_counter += 1

        notification = MilestoneNotification(
            notification_id=f"notif_{self._notification_counter:06d}",
            client_id=client_id,
            milestone_id=milestone_id,
            notification_type=notification_type,
            message=message,
            created_at=datetime.utcnow(),
        )

        self._notifications.append(notification)
        return notification

    def get_pending_notifications(
        self,
        client_id: Optional[str] = None
    ) -> List[MilestoneNotification]:
        """
        Get pending notifications.

        Args:
            client_id: Optional filter by client

        Returns:
            List of pending notifications
        """
        notifications = [n for n in self._notifications if not n.sent]

        if client_id:
            notifications = [n for n in notifications if n.client_id == client_id]

        return notifications

    def mark_notification_sent(
        self,
        notification_id: str
    ) -> Optional[MilestoneNotification]:
        """Mark a notification as sent."""
        for notification in self._notifications:
            if notification.notification_id == notification_id:
                notification.sent = True
                notification.sent_at = datetime.utcnow()
                return notification
        return None

    def get_overall_summary(self) -> Dict[str, Any]:
        """Get overall milestone summary across all clients."""
        total_milestones = 0
        total_achieved = 0

        for client_id in self.SUPPORTED_CLIENTS:
            summary = self.get_milestone_summary(client_id)
            total_milestones += summary["total_milestones"]
            total_achieved += summary["achieved"]

        overdue = self.check_overdue_milestones()

        return {
            "clients_tracked": len(self._progress),
            "total_milestones": total_milestones,
            "total_achieved": total_achieved,
            "overall_completion_rate": round(
                (total_achieved / total_milestones * 100) if total_milestones > 0 else 0, 1
            ),
            "clients_with_overdue": len(overdue),
            "pending_notifications": len(self.get_pending_notifications()),
        }
