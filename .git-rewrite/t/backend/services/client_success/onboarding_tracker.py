"""
Onboarding Tracker Service

Tracks onboarding progress for clients including step completion,
time-to-complete metrics, stuck step detection, and completion rates.
"""
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OnboardingStep(str, Enum):
    """Standard onboarding steps."""
    COMPANY_INFO = "company_info"
    BRANDING_SETUP = "branding_setup"
    VARIANT_SELECTION = "variant_selection"
    INTEGRATIONS = "integrations"
    KNOWLEDGE_BASE = "knowledge_base"
    TEAM_SETUP = "team_setup"
    TRAINING = "training"
    GO_LIVE = "go_live"


class OnboardingStatus(str, Enum):
    """Onboarding status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STUCK = "stuck"
    ABANDONED = "abandoned"


@dataclass
class StepProgress:
    """Progress for a single onboarding step."""
    step: OnboardingStep
    status: OnboardingStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    time_spent_minutes: float = 0.0
    attempts: int = 0
    stuck_since: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        return self.status == OnboardingStatus.COMPLETED

    @property
    def is_stuck(self) -> bool:
        return self.status == OnboardingStatus.STUCK


@dataclass
class ClientOnboardingProgress:
    """Complete onboarding progress for a client."""
    client_id: str
    company_id: Optional[UUID] = None
    status: OnboardingStatus = OnboardingStatus.NOT_STARTED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: Optional[OnboardingStep] = None
    steps: Dict[OnboardingStep, StepProgress] = field(default_factory=dict)
    total_time_minutes: float = 0.0
    completion_percentage: float = 0.0
    variant: Optional[str] = None
    industry: Optional[str] = None

    def calculate_completion(self) -> float:
        """Calculate completion percentage."""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps.values() if s.is_completed)
        return round((completed / len(self.steps)) * 100, 1)


class OnboardingTracker:
    """
    Track onboarding progress for clients.

    Provides step completion tracking, time-to-complete metrics,
    stuck step detection, and onboarding completion rate.
    """

    # Expected time to complete each step (in minutes)
    STEP_EXPECTED_TIMES = {
        OnboardingStep.COMPANY_INFO: 10,
        OnboardingStep.BRANDING_SETUP: 15,
        OnboardingStep.VARIANT_SELECTION: 5,
        OnboardingStep.INTEGRATIONS: 30,
        OnboardingStep.KNOWLEDGE_BASE: 45,
        OnboardingStep.TEAM_SETUP: 15,
        OnboardingStep.TRAINING: 60,
        OnboardingStep.GO_LIVE: 10,
    }

    # Threshold for stuck detection (minutes over expected time)
    STUCK_THRESHOLD_MULTIPLIER = 3.0

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize onboarding tracker."""
        self._progress: Dict[str, ClientOnboardingProgress] = {}
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize tracking for all supported clients."""
        for client_id in self.SUPPORTED_CLIENTS:
            self._progress[client_id] = ClientOnboardingProgress(
                client_id=client_id,
                steps={
                    step: StepProgress(step=step, status=OnboardingStatus.NOT_STARTED)
                    for step in OnboardingStep
                }
            )

    def start_onboarding(
        self,
        client_id: str,
        variant: Optional[str] = None,
        industry: Optional[str] = None
    ) -> ClientOnboardingProgress:
        """
        Start onboarding for a client.

        Args:
            client_id: Client identifier
            variant: Selected variant (mini, parwa, parwa_high)
            industry: Client industry

        Returns:
            Updated ClientOnboardingProgress
        """
        if client_id not in self._progress:
            raise ValueError(f"Unsupported client: {client_id}")

        progress = self._progress[client_id]
        progress.status = OnboardingStatus.IN_PROGRESS
        progress.started_at = datetime.utcnow()
        progress.variant = variant
        progress.industry = industry

        # Start first step
        first_step = OnboardingStep.COMPANY_INFO
        progress.current_step = first_step
        progress.steps[first_step].status = OnboardingStatus.IN_PROGRESS
        progress.steps[first_step].started_at = datetime.utcnow()

        logger.info(f"Started onboarding for {client_id} (variant: {variant})")
        return progress

    def start_step(
        self,
        client_id: str,
        step: OnboardingStep
    ) -> StepProgress:
        """
        Start a specific onboarding step.

        Args:
            client_id: Client identifier
            step: Step to start

        Returns:
            Updated StepProgress
        """
        progress = self._get_progress(client_id)
        step_progress = progress.steps[step]

        step_progress.status = OnboardingStatus.IN_PROGRESS
        step_progress.started_at = datetime.utcnow()
        step_progress.attempts += 1
        progress.current_step = step

        logger.info(f"Started step {step.value} for {client_id}")
        return step_progress

    def complete_step(
        self,
        client_id: str,
        step: OnboardingStep,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StepProgress:
        """
        Complete an onboarding step.

        Args:
            client_id: Client identifier
            step: Step to complete
            metadata: Optional metadata for the step

        Returns:
            Updated StepProgress
        """
        progress = self._get_progress(client_id)
        step_progress = progress.steps[step]

        step_progress.status = OnboardingStatus.COMPLETED
        step_progress.completed_at = datetime.utcnow()

        if step_progress.started_at:
            step_progress.time_spent_minutes = (
                step_progress.completed_at - step_progress.started_at
            ).total_seconds() / 60

        if metadata:
            step_progress.metadata.update(metadata)

        # Update overall progress
        progress.completion_percentage = progress.calculate_completion()

        # Check if all steps completed
        if progress.completion_percentage == 100:
            progress.status = OnboardingStatus.COMPLETED
            progress.completed_at = datetime.utcnow()
            if progress.started_at:
                progress.total_time_minutes = (
                    progress.completed_at - progress.started_at
                ).total_seconds() / 60
            logger.info(f"Onboarding completed for {client_id}")

        # Move to next step
        self._advance_to_next_step(client_id, step)

        logger.info(f"Completed step {step.value} for {client_id}")
        return step_progress

    def _advance_to_next_step(
        self,
        client_id: str,
        completed_step: OnboardingStep
    ) -> None:
        """Move to the next step after completion."""
        progress = self._get_progress(client_id)
        steps_order = list(OnboardingStep)

        try:
            current_index = steps_order.index(completed_step)
            if current_index < len(steps_order) - 1:
                next_step = steps_order[current_index + 1]
                if progress.steps[next_step].status == OnboardingStatus.NOT_STARTED:
                    progress.current_step = next_step
        except ValueError:
            pass

    def detect_stuck_steps(
        self,
        client_id: Optional[str] = None
    ) -> Dict[str, List[OnboardingStep]]:
        """
        Detect stuck onboarding steps.

        A step is considered stuck if it's been in progress for
        longer than expected_time * STUCK_THRESHOLD_MULTIPLIER.

        Args:
            client_id: Optional specific client to check

        Returns:
            Dict mapping client_id to list of stuck steps
        """
        stuck = {}
        clients_to_check = [client_id] if client_id else self.SUPPORTED_CLIENTS

        for cid in clients_to_check:
            progress = self._get_progress(cid)
            stuck_steps = []

            for step, step_progress in progress.steps.items():
                if step_progress.status == OnboardingStatus.IN_PROGRESS:
                    if step_progress.started_at:
                        elapsed = (
                            datetime.utcnow() - step_progress.started_at
                        ).total_seconds() / 60
                        expected = self.STEP_EXPECTED_TIMES.get(step, 30)
                        threshold = expected * self.STUCK_THRESHOLD_MULTIPLIER

                        if elapsed > threshold:
                            step_progress.status = OnboardingStatus.STUCK
                            step_progress.stuck_since = datetime.utcnow()
                            stuck_steps.append(step)

            if stuck_steps:
                stuck[cid] = stuck_steps
                progress.status = OnboardingStatus.STUCK

        return stuck

    def get_time_to_complete(
        self,
        client_id: str,
        step: Optional[OnboardingStep] = None
    ) -> Dict[str, Any]:
        """
        Get time-to-complete metrics.

        Args:
            client_id: Client identifier
            step: Optional specific step

        Returns:
            Dict with time metrics
        """
        progress = self._get_progress(client_id)

        if step:
            step_progress = progress.steps[step]
            return {
                "client_id": client_id,
                "step": step.value,
                "time_spent_minutes": step_progress.time_spent_minutes,
                "expected_minutes": self.STEP_EXPECTED_TIMES.get(step, 30),
                "status": step_progress.status.value,
            }

        return {
            "client_id": client_id,
            "total_time_minutes": progress.total_time_minutes,
            "completion_percentage": progress.completion_percentage,
            "steps": {
                step.value: {
                    "time_spent": sp.time_spent_minutes,
                    "expected": self.STEP_EXPECTED_TIMES.get(step, 30),
                    "status": sp.status.value,
                }
                for step, sp in progress.steps.items()
            }
        }

    def get_completion_rate(
        self,
        industry: Optional[str] = None,
        variant: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate onboarding completion rate.

        Args:
            industry: Optional filter by industry
            variant: Optional filter by variant

        Returns:
            Dict with completion rate metrics
        """
        total = 0
        completed = 0
        in_progress = 0
        stuck = 0

        for progress in self._progress.values():
            # Apply filters
            if industry and progress.industry != industry:
                continue
            if variant and progress.variant != variant:
                continue

            total += 1
            if progress.status == OnboardingStatus.COMPLETED:
                completed += 1
            elif progress.status == OnboardingStatus.IN_PROGRESS:
                in_progress += 1
            elif progress.status == OnboardingStatus.STUCK:
                stuck += 1

        rate = (completed / total * 100) if total > 0 else 0

        return {
            "total_clients": total,
            "completed": completed,
            "in_progress": in_progress,
            "stuck": stuck,
            "completion_rate": round(rate, 1),
        }

    def get_client_progress(
        self,
        client_id: str
    ) -> ClientOnboardingProgress:
        """
        Get onboarding progress for a client.

        Args:
            client_id: Client identifier

        Returns:
            ClientOnboardingProgress
        """
        return self._get_progress(client_id)

    def get_all_progress(self) -> Dict[str, ClientOnboardingProgress]:
        """
        Get onboarding progress for all clients.

        Returns:
            Dict mapping client_id to progress
        """
        return self._progress.copy()

    def _get_progress(self, client_id: str) -> ClientOnboardingProgress:
        """Get progress, raising error if client not supported."""
        if client_id not in self._progress:
            raise ValueError(f"Unsupported client: {client_id}")
        return self._progress[client_id]

    def get_onboarding_summary(self) -> Dict[str, Any]:
        """
        Get overall onboarding summary.
        """
        total = len(self._progress)
        by_status = {}
        by_variant = {}
        avg_completion = 0

        total_completion = 0
        for progress in self._progress.values():
            status = progress.status.value
            by_status[status] = by_status.get(status, 0) + 1

            if progress.variant:
                by_variant[progress.variant] = by_variant.get(progress.variant, 0) + 1

            total_completion += progress.completion_percentage

        avg_completion = total_completion / total if total > 0 else 0

        stuck = self.detect_stuck_steps()

        return {
            "total_clients": total,
            "by_status": by_status,
            "by_variant": by_variant,
            "average_completion": round(avg_completion, 1),
            "stuck_clients": len(stuck),
        }
