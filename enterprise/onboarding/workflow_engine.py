"""
Enterprise Onboarding - Workflow Engine
Orchestrates onboarding workflows
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStep(BaseModel):
    """Single workflow step"""
    step_id: str
    name: str
    order: int
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = ConfigDict()


class Workflow(BaseModel):
    """Onboarding workflow"""
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    client_id: str
    name: str
    steps: List[WorkflowStep] = Field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class WorkflowEngine:
    """
    Orchestrates enterprise onboarding workflows.
    """

    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.step_handlers: Dict[str, Callable] = {}

    def create_workflow(
        self,
        client_id: str,
        name: str,
        steps: List[Dict[str, Any]]
    ) -> Workflow:
        """Create a new workflow"""
        workflow = Workflow(
            client_id=client_id,
            name=name,
            steps=[
                WorkflowStep(
                    step_id=step["id"],
                    name=step["name"],
                    order=i
                )
                for i, step in enumerate(steps)
            ]
        )
        self.workflows[workflow.workflow_id] = workflow
        return workflow

    def register_step_handler(self, step_id: str, handler: Callable):
        """Register a handler for a step"""
        self.step_handlers[step_id] = handler

    def run_workflow(self, workflow_id: str) -> Workflow:
        """Run a workflow"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self.workflows[workflow_id]
        workflow.status = WorkflowStatus.RUNNING

        for i, step in enumerate(workflow.steps):
            workflow.current_step = i
            step.status = WorkflowStatus.RUNNING
            step.started_at = datetime.utcnow()

            try:
                handler = self.step_handlers.get(step.step_id)
                if handler:
                    handler(workflow.client_id)

                step.status = WorkflowStatus.COMPLETED
                step.completed_at = datetime.utcnow()
            except Exception as e:
                step.status = WorkflowStatus.FAILED
                step.error = str(e)
                workflow.status = WorkflowStatus.FAILED
                return workflow

        workflow.status = WorkflowStatus.COMPLETED
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID"""
        return self.workflows.get(workflow_id)

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id].status = WorkflowStatus.PAUSED
            return True
        return False
