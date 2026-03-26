"""
PARWA High Coordinate Teams Task.

Task for coordinating multiple teams in PARWA High.
Provides team assignment, workload balancing, and progress monitoring.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

from variants.parwa_high.agents.coordination_agent import ParwaHighCoordinationAgent
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CoordinateTeamsResult:
    """Result from coordinate teams task."""
    success: bool
    task_id: Optional[str] = None
    assigned_teams: List[str] = field(default_factory=list)
    status: str = "pending"
    active_teams: int = 0
    max_teams: int = 5
    message: str = ""
    created_at: str = ""


class CoordinateTeamsTask:
    """
    Task for coordinating multiple teams.

    Uses ParwaHighCoordinationAgent to:
    - Coordinate up to 5 concurrent teams
    - Assign tasks to appropriate teams
    - Monitor task progress

    Example:
        task = CoordinateTeamsTask()
        result = await task.execute({
            "description": "Handle VIP customer complaint",
            "priority": 1,
            "required_skills": ["vip_support"]
        })
    """

    def __init__(
        self,
        parwa_high_config: Optional[ParwaHighConfig] = None,
        agent_id: str = "coordinate_teams_task"
    ) -> None:
        """
        Initialize coordinate teams task.

        Args:
            parwa_high_config: PARWA High configuration
            agent_id: Agent identifier
        """
        self._config = parwa_high_config or get_parwa_high_config()
        self._agent = ParwaHighCoordinationAgent(agent_id=agent_id)

    async def execute(self, task: Dict[str, Any]) -> CoordinateTeamsResult:
        """
        Execute team coordination.

        Args:
            task: Task data containing:
                - description: Task description
                - priority: Task priority (1-5)
                - required_skills: Required team skills
                - team_id: Optional specific team to assign

        Returns:
            CoordinateTeamsResult with coordination status
        """
        description = task.get("description", "")
        priority = task.get("priority", 3)
        team_id = task.get("team_id")

        logger.info({
            "event": "coordinate_teams_task_started",
            "description": description[:100],
            "priority": priority,
            "team_id": team_id,
            "variant": "parwa_high",
        })

        if team_id:
            # Assign to specific team
            response = await self._agent.assign_task(
                task=task,
                team_id=team_id,
            )
        else:
            # Coordinate teams automatically
            response = await self._agent.coordinate_teams(task=task)

        if not response.success:
            return CoordinateTeamsResult(
                success=False,
                status="failed",
                message=response.message,
                active_teams=self._agent.get_active_team_count(),
                max_teams=self._agent.get_max_teams(),
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        data = response.data or {}
        assigned_team = data.get("team_id")
        task_id = data.get("task_id", f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")

        assigned_teams = [assigned_team] if assigned_team else []

        logger.info({
            "event": "coordinate_teams_task_completed",
            "task_id": task_id,
            "assigned_teams": assigned_teams,
            "active_teams": self._agent.get_active_team_count(),
        })

        return CoordinateTeamsResult(
            success=True,
            task_id=task_id,
            assigned_teams=assigned_teams,
            status="assigned",
            active_teams=self._agent.get_active_team_count(),
            max_teams=self._agent.get_max_teams(),
            message=response.message,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    async def monitor_progress(self, task_id: str) -> CoordinateTeamsResult:
        """
        Monitor progress of a coordinated task.

        Args:
            task_id: Task identifier

        Returns:
            CoordinateTeamsResult with progress status
        """
        response = await self._agent.monitor_progress(task_id=task_id)

        if not response.success:
            return CoordinateTeamsResult(
                success=False,
                task_id=task_id,
                status="not_found",
                message=response.message,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        data = response.data or {}
        assigned_team = data.get("assigned_team")
        assigned_teams = [assigned_team] if assigned_team else []

        return CoordinateTeamsResult(
            success=True,
            task_id=task_id,
            assigned_teams=assigned_teams,
            status=data.get("status", "unknown"),
            active_teams=self._agent.get_active_team_count(),
            max_teams=self._agent.get_max_teams(),
            message=f"Task status: {data.get('status', 'unknown')}",
            created_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )

    def get_task_name(self) -> str:
        """Get task name."""
        return "coordinate_teams"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get tier used."""
        return "heavy"
