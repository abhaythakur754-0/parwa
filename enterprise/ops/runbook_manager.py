# Runbook Manager - Week 50 Builder 5
# Runbook management for operations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RunbookStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class RunbookPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RunbookStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: int = 0
    title: str = ""
    description: str = ""
    command: str = ""
    expected_result: str = ""
    timeout_seconds: int = 300
    rollback_command: str = ""


@dataclass
class RunbookExecution:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    executor: str = ""
    status: str = "pending"
    current_step: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    steps_completed: List[str] = field(default_factory=list)
    notes: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Runbook:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: RunbookStatus = RunbookStatus.DRAFT
    priority: RunbookPriority = RunbookPriority.MEDIUM
    category: str = ""
    tags: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    author: str = ""
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class RunbookManager:
    """Manages operational runbooks"""

    def __init__(self):
        self._runbooks: Dict[str, Runbook] = {}
        self._steps: Dict[str, RunbookStep] = {}
        self._executions: Dict[str, RunbookExecution] = {}
        self._metrics = {
            "total_runbooks": 0,
            "total_executions": 0,
            "by_status": {},
            "by_priority": {}
        }

    def create_runbook(
        self,
        title: str,
        description: str = "",
        category: str = "",
        priority: RunbookPriority = RunbookPriority.MEDIUM,
        author: str = "",
        tags: Optional[List[str]] = None
    ) -> Runbook:
        """Create a new runbook"""
        runbook = Runbook(
            title=title,
            description=description,
            category=category,
            priority=priority,
            author=author,
            tags=tags or []
        )
        self._runbooks[runbook.id] = runbook
        self._metrics["total_runbooks"] += 1

        status_key = runbook.status.value
        self._metrics["by_status"][status_key] = self._metrics["by_status"].get(status_key, 0) + 1

        priority_key = runbook.priority.value
        self._metrics["by_priority"][priority_key] = self._metrics["by_priority"].get(priority_key, 0) + 1

        return runbook

    def add_step(
        self,
        runbook_id: str,
        title: str,
        description: str = "",
        command: str = "",
        expected_result: str = "",
        timeout_seconds: int = 300,
        rollback_command: str = ""
    ) -> Optional[RunbookStep]:
        """Add a step to a runbook"""
        runbook = self._runbooks.get(runbook_id)
        if not runbook:
            return None

        step = RunbookStep(
            order=len(runbook.steps),
            title=title,
            description=description,
            command=command,
            expected_result=expected_result,
            timeout_seconds=timeout_seconds,
            rollback_command=rollback_command
        )
        self._steps[step.id] = step
        runbook.steps.append(step.id)
        runbook.updated_at = datetime.utcnow()

        return step

    def get_step(self, step_id: str) -> Optional[RunbookStep]:
        """Get step by ID"""
        return self._steps.get(step_id)

    def update_step(self, step_id: str, **kwargs) -> bool:
        """Update a step"""
        step = self._steps.get(step_id)
        if not step:
            return False

        for key, value in kwargs.items():
            if hasattr(step, key):
                setattr(step, key, value)
        return True

    def remove_step(self, runbook_id: str, step_id: str) -> bool:
        """Remove a step from a runbook"""
        runbook = self._runbooks.get(runbook_id)
        if not runbook or step_id not in runbook.steps:
            return False

        runbook.steps.remove(step_id)
        if step_id in self._steps:
            del self._steps[step_id]

        # Reorder remaining steps
        for i, sid in enumerate(runbook.steps):
            if sid in self._steps:
                self._steps[sid].order = i

        runbook.updated_at = datetime.utcnow()
        return True

    def publish_runbook(self, runbook_id: str) -> bool:
        """Publish a runbook"""
        runbook = self._runbooks.get(runbook_id)
        if not runbook or runbook.status != RunbookStatus.DRAFT:
            return False

        old_status = runbook.status.value
        runbook.status = RunbookStatus.PUBLISHED
        runbook.updated_at = datetime.utcnow()

        self._metrics["by_status"][old_status] -= 1
        new_status = runbook.status.value
        self._metrics["by_status"][new_status] = self._metrics["by_status"].get(new_status, 0) + 1

        return True

    def deprecate_runbook(self, runbook_id: str) -> bool:
        """Deprecate a runbook"""
        runbook = self._runbooks.get(runbook_id)
        if not runbook:
            return False

        runbook.status = RunbookStatus.DEPRECATED
        runbook.updated_at = datetime.utcnow()
        return True

    def execute_runbook(
        self,
        runbook_id: str,
        executor: str = ""
    ) -> Optional[RunbookExecution]:
        """Start a runbook execution"""
        runbook = self._runbooks.get(runbook_id)
        if not runbook or runbook.status != RunbookStatus.PUBLISHED:
            return None

        execution = RunbookExecution(
            runbook_id=runbook_id,
            executor=executor,
            status="running",
            started_at=datetime.utcnow()
        )
        self._executions[execution.id] = execution
        self._metrics["total_executions"] += 1

        return execution

    def complete_step(self, execution_id: str, step_id: str, note: str = "") -> bool:
        """Mark a step as completed in execution"""
        execution = self._executions.get(execution_id)
        if not execution or execution.status != "running":
            return False

        execution.steps_completed.append(step_id)
        if note:
            execution.notes.append({
                "step_id": step_id,
                "note": note,
                "timestamp": datetime.utcnow().isoformat()
            })

        runbook = self._runbooks.get(execution.runbook_id)
        if runbook and len(execution.steps_completed) >= len(runbook.steps):
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()

        return True

    def fail_execution(self, execution_id: str, reason: str = "") -> bool:
        """Mark execution as failed"""
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        execution.status = "failed"
        execution.completed_at = datetime.utcnow()
        if reason:
            execution.notes.append({
                "error": reason,
                "timestamp": datetime.utcnow().isoformat()
            })

        return True

    def get_runbook(self, runbook_id: str) -> Optional[Runbook]:
        """Get runbook by ID"""
        return self._runbooks.get(runbook_id)

    def get_execution(self, execution_id: str) -> Optional[RunbookExecution]:
        """Get execution by ID"""
        return self._executions.get(execution_id)

    def get_runbooks_by_category(self, category: str) -> List[Runbook]:
        """Get runbooks by category"""
        return [r for r in self._runbooks.values() if r.category == category]

    def get_runbooks_by_tag(self, tag: str) -> List[Runbook]:
        """Get runbooks by tag"""
        return [r for r in self._runbooks.values() if tag in r.tags]

    def get_published_runbooks(self) -> List[Runbook]:
        """Get all published runbooks"""
        return [r for r in self._runbooks.values() if r.status == RunbookStatus.PUBLISHED]

    def get_active_executions(self) -> List[RunbookExecution]:
        """Get all active executions"""
        return [e for e in self._executions.values() if e.status == "running"]

    def search_runbooks(self, query: str) -> List[Runbook]:
        """Search runbooks by title or description"""
        query_lower = query.lower()
        return [
            r for r in self._runbooks.values()
            if query_lower in r.title.lower() or query_lower in r.description.lower()
        ]

    def add_prerequisite(self, runbook_id: str, prerequisite: str) -> bool:
        """Add a prerequisite to a runbook"""
        runbook = self._runbooks.get(runbook_id)
        if not runbook:
            return False
        runbook.prerequisites.append(prerequisite)
        runbook.updated_at = datetime.utcnow()
        return True

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
