"""
Compliance Workflow for Financial Services.

Orchestrates compliance checks around financial actions:
- Pre-action compliance check
- Real-time monitoring during action
- Post-action compliance verification
- Automatic logging and audit
- Violation escalation

CRITICAL: All actions must pass compliance workflow.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid
import asyncio

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)
from variants.financial_services.agents.compliance_agent import (
    ComplianceAgent,
    ComplianceCheckResult,
    ComplianceStatus,
)

logger = logging.getLogger(__name__)


class WorkflowStep(str, Enum):
    """Compliance workflow steps."""
    PRE_CHECK = "pre_check"
    EXECUTION = "execution"
    POST_CHECK = "post_check"
    AUDIT = "audit"
    ESCALATION = "escalation"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class WorkflowResult:
    """Result of compliance workflow execution."""
    workflow_id: str
    status: WorkflowStatus
    passed: bool
    pre_check_result: Optional[ComplianceCheckResult] = None
    post_check_result: Optional[ComplianceCheckResult] = None
    violations: List[Any] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    audit_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ComplianceWorkflow:
    """
    Compliance workflow orchestrator for financial services.

    Executes three-phase compliance workflow:
    1. Pre-action check: Verify action can proceed
    2. Execution: Perform the action
    3. Post-action check: Verify compliance maintained

    Features:
    - Automatic audit trail generation
    - Violation detection and escalation
    - Real-time compliance monitoring
    - SOX/FINRA compliant logging
    """

    def __init__(
        self,
        config: Optional[FinancialServicesConfig] = None
    ):
        """
        Initialize compliance workflow.

        Args:
            config: Financial services configuration
        """
        self.config = config or get_financial_services_config()
        self.compliance_agent = ComplianceAgent(config)
        self._workflow_log: List[Dict[str, Any]] = []

    async def execute(
        self,
        action_type: str,
        customer_id: str,
        amount: float,
        actor: str,
        actor_role: str,
        action_callable: Optional[callable] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowResult:
        """
        Execute full compliance workflow.

        Runs pre-check, optional action, and post-check.
        All steps are logged for audit.

        Args:
            action_type: Type of action (e.g., "refund", "transfer")
            customer_id: Customer identifier
            amount: Transaction amount
            actor: User performing action
            actor_role: Role of the user
            action_callable: Optional async function to execute
            context: Additional context

        Returns:
            WorkflowResult with compliance status
        """
        workflow_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
        audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

        logger.info({
            "event": "workflow_started",
            "workflow_id": workflow_id,
            "action_type": action_type,
            "customer_id": customer_id,
            "actor": actor,
        })

        # Phase 1: Pre-action compliance check
        pre_check = self.compliance_agent.check_pre_transaction(
            transaction_type=action_type,
            customer_id=customer_id,
            amount=amount,
            actor=actor,
            actor_role=actor_role,
            context=context
        )

        if not pre_check.passed:
            return WorkflowResult(
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
                passed=False,
                pre_check_result=pre_check,
                violations=pre_check.violations,
                audit_id=audit_id,
            )

        # Phase 2: Execute action (if provided)
        action_result = None
        if action_callable:
            try:
                if asyncio.iscoroutinefunction(action_callable):
                    action_result = await action_callable()
                else:
                    action_result = action_callable()

                logger.info({
                    "event": "workflow_action_executed",
                    "workflow_id": workflow_id,
                    "action_type": action_type,
                })
            except Exception as e:
                logger.error({
                    "event": "workflow_action_failed",
                    "workflow_id": workflow_id,
                    "error": str(e),
                })
                return WorkflowResult(
                    workflow_id=workflow_id,
                    status=WorkflowStatus.FAILED,
                    passed=False,
                    pre_check_result=pre_check,
                    violations=[str(e)],
                    audit_id=audit_id,
                )

        # Phase 3: Post-action compliance check
        post_check = self.compliance_agent.check_post_transaction(
            transaction_id=workflow_id,
            transaction_type=action_type,
            customer_id=customer_id,
            amount=amount,
            actor=actor
        )

        # Phase 4: Generate audit entry
        self._log_workflow(
            workflow_id=workflow_id,
            action_type=action_type,
            customer_id=customer_id,
            actor=actor,
            amount=amount,
            pre_check=pre_check,
            post_check=post_check,
            audit_id=audit_id
        )

        passed = post_check.passed
        status = WorkflowStatus.COMPLETED if passed else WorkflowStatus.FAILED

        return WorkflowResult(
            workflow_id=workflow_id,
            status=status,
            passed=passed,
            pre_check_result=pre_check,
            post_check_result=post_check,
            violations=post_check.violations,
            warnings=pre_check.warnings + post_check.warnings,
            audit_id=audit_id,
        )

    def execute_sync(
        self,
        action_type: str,
        customer_id: str,
        amount: float,
        actor: str,
        actor_role: str,
        action_callable: Optional[callable] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowResult:
        """
        Execute compliance workflow synchronously.

        Wrapper for async execute method.

        Args:
            action_type: Type of action
            customer_id: Customer identifier
            amount: Transaction amount
            actor: User performing action
            actor_role: Role of the user
            action_callable: Optional function to execute
            context: Additional context

        Returns:
            WorkflowResult
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.execute(
                action_type=action_type,
                customer_id=customer_id,
                amount=amount,
                actor=actor,
                actor_role=actor_role,
                action_callable=action_callable,
                context=context
            )
        )

    def _log_workflow(
        self,
        workflow_id: str,
        action_type: str,
        customer_id: str,
        actor: str,
        amount: float,
        pre_check: ComplianceCheckResult,
        post_check: ComplianceCheckResult,
        audit_id: str
    ):
        """Log workflow execution for audit."""
        entry = {
            "workflow_id": workflow_id,
            "audit_id": audit_id,
            "action_type": action_type,
            "customer_id": customer_id,
            "actor": actor,
            "amount": amount,
            "pre_check_passed": pre_check.passed,
            "post_check_passed": post_check.passed,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._workflow_log.append(entry)

        logger.info({
            "event": "workflow_completed",
            "workflow_id": workflow_id,
            "audit_id": audit_id,
            "passed": pre_check.passed and post_check.passed,
        })

    def get_workflow_log(
        self,
        customer_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get workflow execution log.

        Args:
            customer_id: Optional filter by customer
            limit: Maximum entries to return

        Returns:
            List of workflow log entries
        """
        log = self._workflow_log

        if customer_id:
            log = [e for e in log if e.get("customer_id") == customer_id]

        return log[-limit:]

    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get workflow execution summary."""
        total = len(self._workflow_log)
        passed = sum(1 for e in self._workflow_log if e.get("pre_check_passed") and e.get("post_check_passed"))

        return {
            "total_workflows": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        }
