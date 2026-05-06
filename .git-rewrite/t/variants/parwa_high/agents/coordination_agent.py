"""
PARWA High Team Coordination Agent.

Manages team coordination and task assignment for PARWA High.
Supports multi-team coordination, workload balancing, and progress monitoring.

PARWA High coordination features:
- Coordinate up to 5 concurrent teams
- Assign tasks to teams
- Monitor task progress
- Escalate to managers when needed
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task status types."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    FAILED = "failed"


class TeamStatus(Enum):
    """Team status types."""
    AVAILABLE = "available"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    OFFLINE = "offline"


@dataclass
class TeamInfo:
    """Team information."""
    team_id: str
    name: str
    status: TeamStatus = TeamStatus.AVAILABLE
    current_tasks: int = 0
    max_concurrent_tasks: int = 5
    specializations: List[str] = field(default_factory=list)


@dataclass
class TaskInfo:
    """Task information."""
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_team: Optional[str] = None
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ParwaHighCoordinationAgent(BaseAgent):
    """
    Team coordination agent for PARWA High variant.

    Provides team coordination capabilities including:
    - Coordinating multiple teams (up to 5 concurrent)
    - Assigning tasks to appropriate teams
    - Monitoring task progress
    - Escalating issues to managers

    Example:
        agent = ParwaHighCoordinationAgent()
        result = await agent.coordinate_teams({"task": "Handle VIP customer complaint"})
    """

    # CRITICAL: Max 5 concurrent teams for PARWA High
    MAX_CONCURRENT_TEAMS = 5

    def __init__(
        self,
        agent_id: str = "parwa_high_coordination",
        parwa_high_config: Optional[ParwaHighConfig] = None
    ) -> None:
        """
        Initialize PARWA High coordination agent.

        Args:
            agent_id: Unique agent identifier
            parwa_high_config: PARWA High configuration
        """
        super().__init__(agent_id=agent_id)
        self._config = parwa_high_config or get_parwa_high_config()
        self._teams: Dict[str, TeamInfo] = {}
        self._tasks: Dict[str, TaskInfo] = {}
        self._active_teams: int = 0

    async def coordinate_teams(
        self,
        task: Dict[str, Any]
    ) -> AgentResponse:
        """
        Coordinate teams for a given task.

        Args:
            task: Task data containing:
                - description: Task description
                - priority: Task priority (1-5)
                - required_skills: Required team skills
                - deadline: Optional deadline

        Returns:
            AgentResponse with coordination result
        """
        description = task.get("description", "")
        priority = task.get("priority", 1)
        required_skills = task.get("required_skills", [])

        logger.info({
            "event": "coordinating_teams",
            "task_description": description[:100],
            "priority": priority,
            "required_skills": required_skills,
            "variant": "parwa_high",
        })

        # Check team capacity
        if self._active_teams >= self.MAX_CONCURRENT_TEAMS:
            logger.warning({
                "event": "team_capacity_reached",
                "active_teams": self._active_teams,
                "max_teams": self.MAX_CONCURRENT_TEAMS,
            })
            return AgentResponse(
                success=False,
                message=f"Maximum concurrent teams ({self.MAX_CONCURRENT_TEAMS}) reached",
                data={
                    "active_teams": self._active_teams,
                    "max_teams": self.MAX_CONCURRENT_TEAMS,
                    "task_queued": True,
                },
            )

        # Find best team for task
        best_team = self._find_best_team(required_skills)

        # Always create a task_id for tracking
        task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if best_team is None:
            # Create a new team assignment
            team_id = f"team_{self._active_teams + 1}"

            team = TeamInfo(
                team_id=team_id,
                name=f"Support Team {self._active_teams + 1}",
                status=TeamStatus.BUSY,
                current_tasks=1,
                specializations=required_skills if required_skills else ["general"],
            )

            task_info = TaskInfo(
                task_id=task_id,
                description=description,
                status=TaskStatus.ASSIGNED,
                assigned_team=team_id,
                priority=priority,
            )

            self._teams[team_id] = team
            self._tasks[task_id] = task_info
            self._active_teams += 1
            best_team = team
        else:
            # Create task for existing team
            task_info = TaskInfo(
                task_id=task_id,
                description=description,
                status=TaskStatus.ASSIGNED,
                assigned_team=best_team.team_id,
                priority=priority,
            )
            self._tasks[task_id] = task_info
            best_team.current_tasks += 1

        logger.info({
            "event": "teams_coordinated",
            "assigned_team": best_team.team_id,
            "task_id": task_id,
            "active_teams": self._active_teams,
        })

        return AgentResponse(
            success=True,
            message=f"Task assigned to {best_team.name}",
            confidence=0.85,
            data={
                "task_id": task_id,
                "team_id": best_team.team_id,
                "team_name": best_team.name,
                "task_description": description,
                "priority": priority,
                "active_teams": self._active_teams,
                "max_teams": self.MAX_CONCURRENT_TEAMS,
            },
        )

    async def assign_task(
        self,
        task: Dict[str, Any],
        team_id: str
    ) -> AgentResponse:
        """
        Assign a specific task to a specific team.

        Args:
            task: Task data
            team_id: Target team identifier

        Returns:
            AgentResponse with assignment result
        """
        description = task.get("description", "")
        priority = task.get("priority", 1)

        logger.info({
            "event": "assigning_task",
            "team_id": team_id,
            "task_description": description[:100],
            "variant": "parwa_high",
        })

        # Check if team exists
        team = self._teams.get(team_id)
        if team is None:
            # Create team if doesn't exist
            if self._active_teams >= self.MAX_CONCURRENT_TEAMS:
                return AgentResponse(
                    success=False,
                    message=f"Cannot create new team: max ({self.MAX_CONCURRENT_TEAMS}) reached",
                    data={"active_teams": self._active_teams},
                )

            team = TeamInfo(
                team_id=team_id,
                name=f"Team {team_id}",
                status=TeamStatus.BUSY,
                current_tasks=1,
            )
            self._teams[team_id] = team
            self._active_teams += 1

        # Check team capacity
        if team.current_tasks >= team.max_concurrent_tasks:
            return AgentResponse(
                success=False,
                message=f"Team {team_id} is at capacity ({team.max_concurrent_tasks} tasks)",
                data={"team_id": team_id, "current_tasks": team.current_tasks},
            )

        # Create and assign task
        task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        task_info = TaskInfo(
            task_id=task_id,
            description=description,
            status=TaskStatus.ASSIGNED,
            assigned_team=team_id,
            priority=priority,
        )

        self._tasks[task_id] = task_info
        team.current_tasks += 1
        if team.current_tasks >= team.max_concurrent_tasks:
            team.status = TeamStatus.OVERLOADED
        else:
            team.status = TeamStatus.BUSY

        logger.info({
            "event": "task_assigned",
            "task_id": task_id,
            "team_id": team_id,
            "team_tasks": team.current_tasks,
        })

        return AgentResponse(
            success=True,
            message=f"Task assigned to team {team_id}",
            confidence=0.90,
            data={
                "task_id": task_id,
                "team_id": team_id,
                "status": TaskStatus.ASSIGNED.value,
                "team_current_tasks": team.current_tasks,
                "team_max_tasks": team.max_concurrent_tasks,
            },
        )

    async def monitor_progress(
        self,
        task_id: str
    ) -> AgentResponse:
        """
        Monitor progress of a specific task.

        Args:
            task_id: Task identifier

        Returns:
            AgentResponse with task progress
        """
        task = self._tasks.get(task_id)

        if task is None:
            return AgentResponse(
                success=False,
                message=f"Task {task_id} not found",
                data={"task_id": task_id, "error": "not_found"},
            )

        team = self._teams.get(task.assigned_team) if task.assigned_team else None

        # Update timestamp
        task.updated_at = datetime.now(timezone.utc)

        progress_data = {
            "task_id": task_id,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority,
            "assigned_team": task.assigned_team,
            "team_status": team.status.value if team else None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }

        logger.info({
            "event": "progress_monitored",
            "task_id": task_id,
            "status": task.status.value,
        })

        return AgentResponse(
            success=True,
            message=f"Task {task_id} status: {task.status.value}",
            confidence=0.95,
            data=progress_data,
        )

    def _find_best_team(
        self,
        required_skills: List[str]
    ) -> Optional[TeamInfo]:
        """
        Find the best team for the required skills.

        Args:
            required_skills: List of required skills

        Returns:
            Best matching team or None
        """
        best_team = None
        best_score = -1

        for team in self._teams.values():
            if team.status == TeamStatus.OFFLINE:
                continue
            if team.current_tasks >= team.max_concurrent_tasks:
                continue

            # Calculate skill match score
            if required_skills:
                matching_skills = set(required_skills) & set(team.specializations)
                score = len(matching_skills) / len(required_skills)
            else:
                score = 1.0 if team.status == TeamStatus.AVAILABLE else 0.5

            if score > best_score:
                best_score = score
                best_team = team

        return best_team

    def get_active_team_count(self) -> int:
        """Get count of active teams."""
        return self._active_teams

    def get_max_teams(self) -> int:
        """Get maximum concurrent teams."""
        return self.MAX_CONCURRENT_TEAMS

    def get_tier(self) -> str:
        """Get the tier for this agent."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process coordination-related request.

        Args:
            input_data: Must contain 'action' key with value:
                - 'coordinate': Coordinate teams for task
                - 'assign': Assign task to specific team
                - 'monitor': Monitor task progress

        Returns:
            AgentResponse with result
        """
        action = input_data.get("action", "")

        if action == "coordinate":
            return await self.coordinate_teams(
                task=input_data.get("task", {}),
            )
        elif action == "assign":
            return await self.assign_task(
                task=input_data.get("task", {}),
                team_id=input_data.get("team_id", ""),
            )
        elif action == "monitor":
            return await self.monitor_progress(
                task_id=input_data.get("task_id", ""),
            )
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown coordination action: {action}",
                data={"action": action, "valid_actions": ["coordinate", "assign", "monitor"]},
            )
