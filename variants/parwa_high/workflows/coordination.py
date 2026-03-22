"""
PARWA High Coordination Workflow.

End-to-end workflow for team coordination:
- Analyze task requirements
- Assign to appropriate teams
- Monitor progress
- Complete and report

PARWA High Features:
- Heavy AI tier for intelligent assignment
- Support for up to 5 concurrent teams
- Automatic workload balancing
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum

from variants.parwa_high.tools.team_coordination import TeamCoordinationTool
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CoordinationStatus(Enum):
    """Coordination workflow status."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    ASSIGNING = "assigning"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    ERROR = "error"


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    HIGH_STAKES = "high_stakes"


@dataclass
class CoordinationResult:
    """Result from coordination workflow."""
    workflow_id: str
    task_id: str
    status: CoordinationStatus
    assigned_teams: List[str] = field(default_factory=list)
    completion_time: Optional[float] = None
    resolution: Optional[str] = None
    escalation_required: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CoordinationWorkflow:
    """
    Coordination workflow for PARWA High variant.

    Manages the complete team coordination process:
    1. Analyze task requirements and complexity
    2. Assign to appropriate teams
    3. Monitor progress across teams
    4. Complete and generate report

    PARWA High Specifics:
    - Up to 5 concurrent teams managed
    - Heavy AI tier for intelligent assignment
    - Automatic workload balancing

    Example:
        workflow = CoordinationWorkflow()
        result = await workflow.execute({
            "task_id": "task_123",
            "title": "Customer Issue Resolution",
            "description": "Complex billing issue",
            "priority": "high"
        })
        # result contains task_id, assigned_teams, status, completion_time
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None,
        coordination_tool: Optional[TeamCoordinationTool] = None
    ) -> None:
        """
        Initialize Coordination Workflow.

        Args:
            company_id: Company UUID for data isolation
            coordination_tool: Optional coordination tool instance
        """
        self._company_id = company_id
        self._coordination_tool = coordination_tool or TeamCoordinationTool(company_id=company_id)
        self._workflows: Dict[str, CoordinationResult] = {}

        logger.info({
            "event": "coordination_workflow_initialized",
            "company_id": str(company_id) if company_id else None,
            "variant": "parwa_high",
            "tier": "heavy",
            "max_teams": 5,
        })

    async def execute(
        self,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the complete coordination workflow.

        Runs through all steps of team coordination:
        1. Analyze task complexity
        2. Assign to appropriate teams
        3. Monitor progress
        4. Complete and report

        Args:
            task: Dict with task details:
                - task_id: Unique task identifier
                - title: Task title
                - description: Task description
                - priority: Priority level
                - required_skills: Optional list of required skills

        Returns:
            Dict with:
                - task_id: str
                - assigned_teams: List[str]
                - status: str
                - completion_time: float
        """
        task_id = task.get("task_id", f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        workflow_id = f"coordination_{task_id}"
        start_time = datetime.now(timezone.utc)

        logger.info({
            "event": "coordination_workflow_started",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "title": task.get("title", "Unknown"),
        })

        # Initialize result
        result = CoordinationResult(
            workflow_id=workflow_id,
            task_id=task_id,
            status=CoordinationStatus.PENDING,
        )
        self._workflows[workflow_id] = result

        try:
            # Step 1: Analyze task
            result.status = CoordinationStatus.ANALYZING
            analysis = await self._analyze_task(task)
            complexity = analysis.get("complexity", TaskComplexity.MODERATE)

            # Step 2: Assign to teams
            result.status = CoordinationStatus.ASSIGNING
            assignment = await self._assign_to_teams(task, analysis)

            if not assignment["success"]:
                # Try alternative assignment
                assignment = await self._try_alternative_assignment(task, assignment)

            result.assigned_teams = assignment.get("assigned_teams", [])

            if not result.assigned_teams:
                # No teams available - escalate
                escalation = await self._coordination_tool.escalate_to_manager(
                    task_id, "No available teams for assignment"
                )
                result.status = CoordinationStatus.ESCALATED
                result.escalation_required = True
            else:
                # Step 3: Monitor progress
                result.status = CoordinationStatus.MONITORING
                progress = await self._monitor_progress(task_id, result.assigned_teams)

                # Step 4: Complete
                if progress.get("completed"):
                    result.status = CoordinationStatus.COMPLETED
                    result.resolution = progress.get("resolution")
                else:
                    result.status = CoordinationStatus.ESCALATED
                    result.escalation_required = True

            result.completed_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            result.status = CoordinationStatus.ERROR
            logger.error({
                "event": "coordination_workflow_error",
                "workflow_id": workflow_id,
                "error": str(e),
            })

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        result.completion_time = execution_time

        logger.info({
            "event": "coordination_workflow_completed",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "status": result.status.value,
            "assigned_teams": result.assigned_teams,
            "completion_time_seconds": execution_time,
        })

        return {
            "success": result.status == CoordinationStatus.COMPLETED,
            "task_id": task_id,
            "assigned_teams": result.assigned_teams,
            "status": result.status.value,
            "completion_time": execution_time,
            "resolution": result.resolution,
            "escalation_required": result.escalation_required,
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
                "workflow_id": workflow_id,
            },
        }

    async def _analyze_task(
        self,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze task to determine complexity and requirements.

        Args:
            task: Task details

        Returns:
            Dict with complexity analysis
        """
        title = task.get("title", "").lower()
        description = task.get("description", "").lower()
        priority = task.get("priority", "medium")

        # Determine complexity
        complexity = TaskComplexity.MODERATE

        # Check for complexity indicators
        complex_indicators = ["api", "integration", "migration", "enterprise", "multi-team"]
        high_stakes_indicators = ["legal", "compliance", "security", "breach", "urgent"]

        for indicator in complex_indicators:
            if indicator in title or indicator in description:
                complexity = TaskComplexity.COMPLEX
                break

        for indicator in high_stakes_indicators:
            if indicator in title or indicator in description:
                complexity = TaskComplexity.HIGH_STAKES
                break

        if priority == "critical":
            complexity = TaskComplexity.HIGH_STAKES
        elif priority == "high":
            complexity = TaskComplexity.COMPLEX
        elif priority == "low":
            complexity = TaskComplexity.SIMPLE

        # Extract required skills
        required_skills = task.get("required_skills", [])
        if not required_skills:
            # Infer from description
            skill_keywords = {
                "billing": ["billing"],
                "technical": ["api", "integration", "technical"],
                "support": ["support", "help", "issue"],
                "retention": ["churn", "retention", "cancel"],
            }
            for skill, keywords in skill_keywords.items():
                if any(kw in description for kw in keywords):
                    required_skills.append(skill)

        return {
            "complexity": complexity,
            "required_skills": required_skills,
            "priority": priority,
            "estimated_time_minutes": self._estimate_time(complexity),
        }

    def _estimate_time(
        self,
        complexity: TaskComplexity
    ) -> int:
        """Estimate time needed based on complexity."""
        time_map = {
            TaskComplexity.SIMPLE: 15,
            TaskComplexity.MODERATE: 30,
            TaskComplexity.COMPLEX: 60,
            TaskComplexity.HIGH_STAKES: 120,
        }
        return time_map.get(complexity, 30)

    async def _assign_to_teams(
        self,
        task: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assign task to appropriate teams.

        Args:
            task: Task details
            analysis: Task analysis result

        Returns:
            Dict with assignment result
        """
        task_id = task.get("task_id", "")
        required_skills = analysis.get("required_skills", [])
        assigned_teams: List[str] = []
        assignment_results: List[Dict[str, Any]] = []

        # Find best matching team
        best_team = await self._find_best_team(required_skills)

        if best_team:
            # Assign to best team
            assign_result = await self._coordination_tool.assign_task(task, best_team)
            if assign_result.get("success"):
                assigned_teams.append(best_team)
                assignment_results.append(assign_result)

        # For complex tasks, assign to multiple teams
        if analysis.get("complexity") in [TaskComplexity.COMPLEX, TaskComplexity.HIGH_STAKES]:
            # Balance workload across teams
            balance_result = await self._coordination_tool.balance_workload(list(
                self._get_available_teams()
            ))

            # Assign to additional team if available
            if balance_result.get("underloaded_teams"):
                additional_team = balance_result["underloaded_teams"][0]["team_id"]
                assign_result = await self._coordination_tool.assign_task(task, additional_team)
                if assign_result.get("success"):
                    assigned_teams.append(additional_team)
                    assignment_results.append(assign_result)

        return {
            "success": len(assigned_teams) > 0,
            "assigned_teams": assigned_teams,
            "assignment_results": assignment_results,
        }

    async def _find_best_team(
        self,
        required_skills: List[str]
    ) -> Optional[str]:
        """Find the best team for the required skills."""
        # Get all available teams and their loads
        available_teams = self._get_available_teams()

        best_team = None
        best_score = -1

        for team_id in available_teams:
            load_result = await self._coordination_tool.get_team_load(team_id)
            if not load_result.get("success"):
                continue

            # Check if team has capacity
            if load_result["load"]["available"] <= 0:
                continue

            # Calculate match score
            specializations = load_result.get("specializations", [])
            skill_match = sum(
                1 for skill in required_skills
                if any(skill.lower() in spec.lower() for spec in specializations)
            )

            # Factor in availability
            availability_score = load_result["load"]["available"] / load_result["load"]["capacity"]
            total_score = skill_match * 10 + availability_score * 5

            if total_score > best_score:
                best_score = total_score
                best_team = team_id

        return best_team

    def _get_available_teams(self) -> List[str]:
        """Get list of available team IDs."""
        return [
            "team_support_t1",
            "team_support_t2",
            "team_billing",
            "team_customer_success",
            "team_technical",
        ]

    async def _try_alternative_assignment(
        self,
        task: Dict[str, Any],
        failed_assignment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Try alternative assignment strategies."""
        task_id = task.get("task_id", "")

        # Try escalating to manager
        escalation = await self._coordination_tool.escalate_to_manager(
            task_id, "Primary assignment failed, seeking manager intervention"
        )

        return {
            "success": False,
            "assigned_teams": [],
            "escalation": escalation,
        }

    async def _monitor_progress(
        self,
        task_id: str,
        assigned_teams: List[str]
    ) -> Dict[str, Any]:
        """
        Monitor progress of assigned teams.

        Args:
            task_id: Task identifier
            assigned_teams: List of assigned team IDs

        Returns:
            Dict with progress status
        """
        # Simulate progress monitoring
        # In production, this would check actual task status

        all_teams_complete = True
        team_statuses: List[Dict[str, Any]] = []

        for team_id in assigned_teams:
            load = await self._coordination_tool.get_team_load(team_id)
            team_statuses.append({
                "team_id": team_id,
                "status": "processing",
                "load": load.get("load", {}),
            })

        # Simulate completion for demo
        return {
            "completed": True,
            "resolution": "Task completed successfully by assigned teams",
            "team_statuses": team_statuses,
        }

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "heavy"

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "CoordinationWorkflow"
