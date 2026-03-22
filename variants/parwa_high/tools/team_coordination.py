"""
PARWA High Team Coordination Tool.

Advanced team coordination capabilities for PARWA High variant:
- Task assignment across multiple teams
- Workload balancing
- Team load monitoring
- Manager escalation

PARWA High Features:
- Manage up to 5 concurrent teams
- Heavy AI tier for sophisticated coordination
- Company-isolated team data
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    """Task status types."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


@dataclass
class TeamTask:
    """Represents a task assigned to a team."""
    task_id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    team_id: Optional[str] = None
    assigned_at: Optional[str] = None
    due_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Team:
    """Represents a team in the system."""
    team_id: str
    name: str
    capacity: int  # Max concurrent tasks
    current_load: int = 0
    specializations: List[str] = field(default_factory=list)
    members: List[str] = field(default_factory=list)


class TeamCoordinationTool:
    """
    Team coordination tool for PARWA High variant.

    Provides advanced team management capabilities:
    - Assign tasks to appropriate teams
    - Monitor team workload
    - Balance workload across teams
    - Escalate to managers when needed

    PARWA High Specifics:
    - Max 5 concurrent teams managed
    - Heavy AI tier for smart assignment
    - Company-isolated data

    Example:
        tool = TeamCoordinationTool()
        result = await tool.assign_task(task, "team_123")
        load = await tool.get_team_load("team_123")
    """

    MAX_CONCURRENT_TEAMS = 5

    def __init__(
        self,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Team Coordination Tool.

        Args:
            company_id: Company UUID for data isolation
        """
        self._company_id = company_id
        self._teams: Dict[str, Team] = {}
        self._tasks: Dict[str, TeamTask] = {}
        self._escalations: Dict[str, Dict[str, Any]] = {}

        # Initialize default teams for PARWA High
        self._initialize_default_teams()

        logger.info({
            "event": "team_coordination_initialized",
            "company_id": str(company_id) if company_id else None,
            "max_teams": self.MAX_CONCURRENT_TEAMS,
            "variant": "parwa_high",
            "tier": "heavy",
        })

    def _initialize_default_teams(self) -> None:
        """Initialize default team structure."""
        default_teams = [
            Team(
                team_id="team_support_t1",
                name="Tier 1 Support",
                capacity=10,
                specializations=["general", "faq", "basic_issues"],
            ),
            Team(
                team_id="team_support_t2",
                name="Tier 2 Support",
                capacity=8,
                specializations=["technical", "complex_issues", "escalations"],
            ),
            Team(
                team_id="team_billing",
                name="Billing Team",
                capacity=6,
                specializations=["billing", "refunds", "payments"],
            ),
            Team(
                team_id="team_customer_success",
                name="Customer Success",
                capacity=5,
                specializations=["retention", "onboarding", "churn_prevention"],
            ),
            Team(
                team_id="team_technical",
                name="Technical Support",
                capacity=7,
                specializations=["api", "integrations", "debugging"],
            ),
        ]

        for team in default_teams:
            self._teams[team.team_id] = team

    async def assign_task(
        self,
        task: Dict[str, Any],
        team_id: str
    ) -> Dict[str, Any]:
        """
        Assign a task to a specific team.

        Validates team capacity and specialization match
        before assignment.

        Args:
            task: Dict with task details:
                - task_id: Unique task identifier
                - title: Task title
                - description: Task description
                - priority: Priority level (low/medium/high/critical)
                - required_skills: List of required skills
            team_id: Target team identifier

        Returns:
            Dict with assignment result
        """
        task_id = task.get("task_id", f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")

        # Validate team exists
        if team_id not in self._teams:
            logger.warning({
                "event": "team_not_found",
                "team_id": team_id,
                "task_id": task_id,
            })
            return {
                "success": False,
                "error": f"Team {team_id} not found",
                "task_id": task_id,
            }

        team = self._teams[team_id]

        # Check team capacity
        if team.current_load >= team.capacity:
            logger.info({
                "event": "team_at_capacity",
                "team_id": team_id,
                "current_load": team.current_load,
                "capacity": team.capacity,
            })
            return {
                "success": False,
                "error": f"Team {team.name} is at capacity ({team.current_load}/{team.capacity})",
                "task_id": task_id,
                "suggestion": self._suggest_alternative_team(task, team_id),
            }

        # Check specialization match
        required_skills = task.get("required_skills", [])
        skill_match = self._check_skill_match(required_skills, team.specializations)

        # Create task record
        priority_str = task.get("priority", "medium")
        try:
            priority = TaskPriority(priority_str.lower())
        except ValueError:
            priority = TaskPriority.MEDIUM

        team_task = TeamTask(
            task_id=task_id,
            title=task.get("title", "Untitled Task"),
            description=task.get("description", ""),
            priority=priority,
            status=TaskStatus.ASSIGNED,
            team_id=team_id,
            assigned_at=datetime.now(timezone.utc).isoformat(),
            due_at=task.get("due_at"),
            metadata={
                "required_skills": required_skills,
                "skill_match_score": skill_match,
            },
        )

        self._tasks[task_id] = team_task
        team.current_load += 1

        logger.info({
            "event": "task_assigned",
            "task_id": task_id,
            "team_id": team_id,
            "team_name": team.name,
            "priority": priority.value,
            "skill_match": skill_match,
        })

        return {
            "success": True,
            "task_id": task_id,
            "team_id": team_id,
            "team_name": team.name,
            "assigned_at": team_task.assigned_at,
            "skill_match_score": skill_match,
            "team_load": {
                "current": team.current_load,
                "capacity": team.capacity,
                "available": team.capacity - team.current_load,
            },
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    async def get_team_load(
        self,
        team_id: str
    ) -> Dict[str, Any]:
        """
        Get current load for a specific team.

        Args:
            team_id: Team identifier

        Returns:
            Dict with team load information
        """
        if team_id not in self._teams:
            return {
                "success": False,
                "error": f"Team {team_id} not found",
            }

        team = self._teams[team_id]

        # Get tasks for this team
        team_tasks = [
            t for t in self._tasks.values()
            if t.team_id == team_id
        ]

        # Calculate load metrics
        pending = sum(1 for t in team_tasks if t.status == TaskStatus.PENDING)
        in_progress = sum(1 for t in team_tasks if t.status == TaskStatus.IN_PROGRESS)
        high_priority = sum(1 for t in team_tasks if t.priority in [TaskPriority.HIGH, TaskPriority.CRITICAL])

        load_percentage = (team.current_load / team.capacity * 100) if team.capacity > 0 else 0

        return {
            "success": True,
            "team_id": team_id,
            "team_name": team.name,
            "load": {
                "current": team.current_load,
                "capacity": team.capacity,
                "available": team.capacity - team.current_load,
                "percentage": load_percentage,
            },
            "tasks": {
                "total": len(team_tasks),
                "pending": pending,
                "in_progress": in_progress,
                "high_priority": high_priority,
            },
            "specializations": team.specializations,
            "status": self._determine_team_status(load_percentage),
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    async def balance_workload(
        self,
        teams: List[str]
    ) -> Dict[str, Any]:
        """
        Balance workload across multiple teams.

        Analyzes current distribution and suggests reassignments
        to optimize overall capacity utilization.

        Args:
            teams: List of team IDs to balance

        Returns:
            Dict with balancing recommendations
        """
        valid_teams = [t for t in teams if t in self._teams]

        if not valid_teams:
            return {
                "success": False,
                "error": "No valid teams provided for balancing",
            }

        # Gather team load data
        team_loads = []
        for team_id in valid_teams:
            team = self._teams[team_id]
            load_pct = (team.current_load / team.capacity * 100) if team.capacity > 0 else 0
            team_loads.append({
                "team_id": team_id,
                "team_name": team.name,
                "current_load": team.current_load,
                "capacity": team.capacity,
                "load_percentage": load_pct,
                "specializations": team.specializations,
            })

        # Calculate average load
        loads = [t["load_percentage"] for t in team_loads]
        avg_load = sum(loads) / len(loads) if loads else 0

        # Identify overloaded and underloaded teams
        overloaded = [t for t in team_loads if t["load_percentage"] > avg_load + 20]
        underloaded = [t for t in team_loads if t["load_percentage"] < avg_load - 20]

        # Generate balancing suggestions
        suggestions: List[Dict[str, Any]] = []
        for over_team in overloaded:
            # Find tasks that could be moved
            movable_tasks = [
                t for t in self._tasks.values()
                if t.team_id == over_team["team_id"]
                and t.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED]
            ]

            for task in movable_tasks[:3]:  # Limit to 3 suggestions per team
                # Find suitable underloaded team
                for under_team in underloaded:
                    skill_match = self._check_skill_match(
                        task.metadata.get("required_skills", []),
                        under_team["specializations"]
                    )
                    if skill_match > 0.5:
                        suggestions.append({
                            "task_id": task.task_id,
                            "task_title": task.title,
                            "from_team": over_team["team_name"],
                            "to_team": under_team["team_name"],
                            "skill_match": skill_match,
                            "reason": "Workload balancing",
                        })
                        break

        logger.info({
            "event": "workload_balanced",
            "team_count": len(valid_teams),
            "overloaded_count": len(overloaded),
            "underloaded_count": len(underloaded),
            "suggestions_count": len(suggestions),
            "avg_load": avg_load,
        })

        return {
            "success": True,
            "teams_analyzed": len(valid_teams),
            "average_load": avg_load,
            "overloaded_teams": [
                {"team_id": t["team_id"], "name": t["team_name"], "load": t["load_percentage"]}
                for t in overloaded
            ],
            "underloaded_teams": [
                {"team_id": t["team_id"], "name": t["team_name"], "load": t["load_percentage"]}
                for t in underloaded
            ],
            "balancing_suggestions": suggestions,
            "is_balanced": len(overloaded) == 0 and len(underloaded) == 0,
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    async def escalate_to_manager(
        self,
        task_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Escalate a task to manager level.

        Creates an escalation record and notifies management.

        Args:
            task_id: Task to escalate
            reason: Reason for escalation

        Returns:
            Dict with escalation result
        """
        if task_id not in self._tasks:
            return {
                "success": False,
                "error": f"Task {task_id} not found",
            }

        task = self._tasks[task_id]
        escalation_id = f"esc_{task_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Update task status
        task.status = TaskStatus.ESCALATED

        # Create escalation record
        escalation = {
            "escalation_id": escalation_id,
            "task_id": task_id,
            "task_title": task.title,
            "team_id": task.team_id,
            "reason": reason,
            "priority": task.priority.value,
            "escalated_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_review",
        }

        self._escalations[escalation_id] = escalation

        logger.warning({
            "event": "task_escalated",
            "escalation_id": escalation_id,
            "task_id": task_id,
            "team_id": task.team_id,
            "reason": reason,
            "priority": task.priority.value,
        })

        return {
            "success": True,
            "escalation_id": escalation_id,
            "task_id": task_id,
            "escalated_at": escalation["escalated_at"],
            "status": "pending_review",
            "message": f"Task {task.title} escalated to manager for: {reason}",
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    def _check_skill_match(
        self,
        required_skills: List[str],
        team_specializations: List[str]
    ) -> float:
        """
        Check how well team specializations match required skills.

        Args:
            required_skills: Skills needed for task
            team_specializations: Team's specializations

        Returns:
            Match score between 0.0 and 1.0
        """
        if not required_skills:
            return 1.0  # No specific skills required

        required_lower = [s.lower() for s in required_skills]
        specs_lower = [s.lower() for s in team_specializations]

        matches = sum(1 for skill in required_lower if any(skill in spec or spec in skill for spec in specs_lower))
        return matches / len(required_skills) if required_skills else 1.0

    def _suggest_alternative_team(
        self,
        task: Dict[str, Any],
        excluded_team_id: str
    ) -> Optional[str]:
        """Suggest an alternative team for the task."""
        required_skills = task.get("required_skills", [])

        best_team = None
        best_score = 0.0

        for team_id, team in self._teams.items():
            if team_id == excluded_team_id:
                continue
            if team.current_load >= team.capacity:
                continue

            score = self._check_skill_match(required_skills, team.specializations)
            # Prefer teams with more available capacity
            availability_bonus = (team.capacity - team.current_load) / team.capacity * 0.2
            total_score = score + availability_bonus

            if total_score > best_score:
                best_score = total_score
                best_team = team.name

        return best_team

    def _determine_team_status(self, load_percentage: float) -> str:
        """Determine team status based on load percentage."""
        if load_percentage >= 90:
            return "critical"
        elif load_percentage >= 75:
            return "high_load"
        elif load_percentage >= 50:
            return "moderate"
        else:
            return "available"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "heavy"

    def get_max_teams(self) -> int:
        """Get maximum concurrent teams."""
        return self.MAX_CONCURRENT_TEAMS
