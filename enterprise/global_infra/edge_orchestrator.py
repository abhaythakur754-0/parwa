# Edge Orchestrator - Week 51 Builder 3
# Edge orchestration

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class OrchestrationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(Enum):
    FUNCTION = "function"
    HTTP = "http"
    PARALLEL = "parallel"
    CONDITION = "condition"
    DELAY = "delay"


@dataclass
class OrchestrationStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    step_type: StepType = StepType.FUNCTION
    function_id: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    next_steps: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class OrchestrationExecution:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    steps: List[str] = field(default_factory=list)
    current_step: int = 0
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Workflow:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    steps: List[str] = field(default_factory=list)
    entry_step: str = ""
    timeout_seconds: int = 300
    enabled: bool = True
    execution_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


class EdgeOrchestrator:
    """Orchestrates edge workflows"""

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._steps: Dict[str, OrchestrationStep] = {}
        self._executions: Dict[str, OrchestrationExecution] = []
        self._metrics = {
            "total_workflows": 0,
            "total_executions": 0,
            "successful": 0,
            "failed": 0
        }

    def create_workflow(
        self,
        name: str,
        description: str = "",
        timeout_seconds: int = 300
    ) -> Workflow:
        """Create a new workflow"""
        workflow = Workflow(
            name=name,
            description=description,
            timeout_seconds=timeout_seconds
        )
        self._workflows[workflow.id] = workflow
        self._metrics["total_workflows"] += 1
        return workflow

    def add_step(
        self,
        workflow_id: str,
        name: str,
        step_type: StepType,
        function_id: str = "",
        config: Optional[Dict[str, Any]] = None,
        next_steps: Optional[List[str]] = None
    ) -> Optional[OrchestrationStep]:
        """Add a step to a workflow"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None

        step = OrchestrationStep(
            name=name,
            step_type=step_type,
            function_id=function_id,
            config=config or {},
            next_steps=next_steps or []
        )

        self._steps[step.id] = step
        workflow.steps.append(step.id)

        if not workflow.entry_step:
            workflow.entry_step = step.id

        return step

    def remove_step(self, workflow_id: str, step_id: str) -> bool:
        """Remove a step from a workflow"""
        workflow = self._workflows.get(workflow_id)
        if not workflow or step_id not in workflow.steps:
            return False

        workflow.steps.remove(step_id)

        if workflow.entry_step == step_id:
            workflow.entry_step = workflow.steps[0] if workflow.steps else ""

        if step_id in self._steps:
            del self._steps[step_id]

        return True

    def start_execution(
        self,
        workflow_id: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Optional[OrchestrationExecution]:
        """Start a workflow execution"""
        workflow = self._workflows.get(workflow_id)
        if not workflow or not workflow.enabled:
            return None

        execution = OrchestrationExecution(
            workflow_id=workflow_id,
            steps=workflow.steps.copy(),
            input_data=input_data or {},
            status=OrchestrationStatus.RUNNING,
            started_at=datetime.utcnow()
        )

        self._executions.append(execution)
        self._metrics["total_executions"] += 1
        workflow.execution_count += 1

        return execution

    def complete_step(
        self,
        execution_id: str,
        step_id: str,
        result: Any
    ) -> bool:
        """Complete a step in execution"""
        for execution in self._executions:
            if execution.id == execution_id:
                execution.step_results[step_id] = result
                execution.current_step += 1

                # Check if all steps complete
                if execution.current_step >= len(execution.steps):
                    execution.status = OrchestrationStatus.COMPLETED
                    execution.completed_at = datetime.utcnow()
                    self._metrics["successful"] += 1

                return True
        return False

    def fail_execution(
        self,
        execution_id: str,
        error: str = ""
    ) -> bool:
        """Mark execution as failed"""
        for execution in self._executions:
            if execution.id == execution_id:
                execution.status = OrchestrationStatus.FAILED
                execution.completed_at = datetime.utcnow()
                execution.output_data = {"error": error}
                self._metrics["failed"] += 1
                return True
        return False

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution"""
        for execution in self._executions:
            if execution.id == execution_id:
                execution.status = OrchestrationStatus.CANCELLED
                execution.completed_at = datetime.utcnow()
                return True
        return False

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID"""
        return self._workflows.get(workflow_id)

    def get_step(self, step_id: str) -> Optional[OrchestrationStep]:
        """Get step by ID"""
        return self._steps.get(step_id)

    def get_execution(self, execution_id: str) -> Optional[OrchestrationExecution]:
        """Get execution by ID"""
        for execution in self._executions:
            if execution.id == execution_id:
                return execution
        return None

    def get_executions_by_workflow(
        self,
        workflow_id: str,
        limit: int = 100
    ) -> List[OrchestrationExecution]:
        """Get executions for a workflow"""
        executions = [e for e in self._executions if e.workflow_id == workflow_id]
        return executions[-limit:]

    def get_active_executions(self) -> List[OrchestrationExecution]:
        """Get all active executions"""
        return [
            e for e in self._executions
            if e.status == OrchestrationStatus.RUNNING
        ]

    def enable_workflow(self, workflow_id: str) -> bool:
        """Enable a workflow"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False
        workflow.enabled = True
        return True

    def disable_workflow(self, workflow_id: str) -> bool:
        """Disable a workflow"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False
        workflow.enabled = False
        return True

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        if workflow_id in self._workflows:
            # Remove all steps
            for step_id in self._workflows[workflow_id].steps:
                if step_id in self._steps:
                    del self._steps[step_id]
            del self._workflows[workflow_id]
            return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics"""
        return self._metrics.copy()
