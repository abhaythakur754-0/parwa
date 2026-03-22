"""
PARWA Base Agent.

Abstract base class for all PARWA agents. Provides common functionality
for agent lifecycle, health checks, confidence scoring, escalation logic,
and input validation.

CRITICAL: This is the foundation for ALL agents in Week 9.
All variant agents must inherit from this class.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class AgentState(Enum):
    """Agent state enumeration."""
    IDLE = "idle"
    PROCESSING = "processing"
    ESCALATING = "escalating"
    ERROR = "error"
    STOPPED = "stopped"


class AgentTier(Enum):
    """Agent complexity tier."""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class AgentVariant(Enum):
    """Agent variant type."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


class AgentResponse(BaseModel):
    """
    Response from an agent processing operation.

    Attributes:
        success: Whether the processing succeeded
        message: Response message or error description
        data: Result data from processing
        confidence: Confidence score (0.0 to 1.0)
        tier_used: Which tier was used for processing
        variant: Which variant processed this
        escalated: Whether this was escalated
        escalation_reason: Reason for escalation if escalated
        execution_time_ms: Time taken to process
    """
    success: bool = Field(default=True)
    message: str = Field(default="")
    data: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tier_used: str = Field(default="light")
    variant: str = Field(default="mini")
    escalated: bool = Field(default=False)
    escalation_reason: Optional[str] = None
    execution_time_ms: float = Field(default=0.0)
    agent_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(
        use_enum_values=True
    )


class AgentConfig(BaseModel):
    """
    Configuration for an agent.

    Attributes:
        agent_id: Unique identifier for the agent
        variant: Agent variant type
        escalation_threshold: Confidence threshold for escalation
        max_retries: Maximum retries on failure
        timeout_seconds: Maximum processing time
        enable_logging: Whether to log all actions
    """
    agent_id: str = Field(default="unknown")
    variant: str = Field(default="mini")
    escalation_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=300)
    enable_logging: bool = Field(default=True)

    model_config = ConfigDict(
        use_enum_values=True
    )


@dataclass
class AgentAction:
    """
    Record of an agent action for audit logging.

    Attributes:
        action: Name of the action performed
        timestamp: When the action occurred
        details: Additional details about the action
        success: Whether the action succeeded
    """
    action: str
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True


class BaseAgent(ABC):
    """
    Abstract base class for all PARWA agents.

    Provides:
    - Agent lifecycle management
    - Health checks
    - Confidence calculation
    - Escalation logic
    - Input validation
    - Audit logging

    All PARWA agents must inherit from this class and implement
    the process() method.

    Example:
        class MyAgent(BaseAgent):
            def get_tier(self) -> str:
                return "light"

            def get_variant(self) -> str:
                return "mini"

            async def process(self, input_data: dict) -> AgentResponse:
                # Process input and return response
                return AgentResponse(
                    success=True,
                    message="Processed successfully",
                    data={"result": "value"}
                )
    """

    DEFAULT_ESCALATION_THRESHOLD = 0.70
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize agent.

        Args:
            agent_id: Unique identifier for this agent instance
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy isolation
        """
        self._agent_id = agent_id
        self._company_id = company_id
        self._config = AgentConfig(
            agent_id=agent_id,
            **(config or {})
        )
        self._state = AgentState.IDLE
        self._action_log: List[AgentAction] = []
        self._start_time: Optional[datetime] = None
        self._process_count = 0
        self._error_count = 0
        self._escalation_count = 0

        logger.info({
            "event": "agent_initialized",
            "agent_id": self._agent_id,
            "variant": self.get_variant(),
            "tier": self.get_tier(),
            "company_id": str(company_id) if company_id else None,
        })

    @property
    def agent_id(self) -> str:
        """Get agent ID."""
        return self._agent_id

    @property
    def company_id(self) -> Optional[UUID]:
        """Get company ID."""
        return self._company_id

    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self._state

    @property
    def is_processing(self) -> bool:
        """Check if agent is processing."""
        return self._state == AgentState.PROCESSING

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process input data and return response.

        This is the main method that all agents must implement.
        It should:
        1. Validate input
        2. Process according to agent type
        3. Calculate confidence
        4. Determine if escalation needed
        5. Return appropriate response

        Args:
            input_data: Input data to process

        Returns:
            AgentResponse with processing results
        """
        pass

    @abstractmethod
    def get_tier(self) -> str:
        """
        Return the complexity tier for this agent.

        Returns:
            "light", "medium", or "heavy"
        """
        pass

    @abstractmethod
    def get_variant(self) -> str:
        """
        Return the variant type for this agent.

        Returns:
            "mini", "parwa", or "parwa_high"
        """
        pass

    async def health_check(self) -> Dict[str, Any]:
        """
        Return agent health status.

        Returns:
            Health status dictionary with:
            - healthy: bool
            - state: str
            - process_count: int
            - error_count: int
            - escalation_count: int
        """
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return {
            "healthy": self._state != AgentState.ERROR,
            "state": self._state.value,
            "agent_id": self._agent_id,
            "variant": self.get_variant(),
            "tier": self.get_tier(),
            "uptime_seconds": uptime,
            "process_count": self._process_count,
            "error_count": self._error_count,
            "escalation_count": self._escalation_count,
            "company_id": str(self._company_id) if self._company_id else None,
        }

    def get_confidence(self, result: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a result.

        Override this method in subclasses for custom confidence
        calculation logic.

        Args:
            result: Processing result dictionary

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Default confidence calculation
        if not result:
            return 0.0

        # Check for explicit confidence in result
        if "confidence" in result:
            return min(1.0, max(0.0, float(result["confidence"])))

        # Calculate based on result quality indicators
        confidence = 0.5  # Base confidence

        # Increase confidence for successful results
        if result.get("success", False):
            confidence += 0.2

        # Increase confidence for results with data
        if result.get("data"):
            confidence += 0.1

        # Increase confidence for results with matches
        if result.get("matches_found", 0) > 0:
            confidence += min(0.2, result["matches_found"] * 0.05)

        return min(1.0, max(0.0, confidence))

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation to human is needed.

        Args:
            confidence: Confidence score from processing
            context: Additional context for escalation decision

        Returns:
            True if should escalate, False otherwise
        """
        context = context or {}

        # Check confidence threshold
        threshold = self._config.escalation_threshold
        if confidence < threshold:
            logger.info({
                "event": "escalation_triggered",
                "agent_id": self._agent_id,
                "confidence": confidence,
                "threshold": threshold,
                "reason": "low_confidence",
            })
            return True

        # Check for explicit escalation request
        if context.get("force_escalate", False):
            logger.info({
                "event": "escalation_triggered",
                "agent_id": self._agent_id,
                "reason": "forced_escalation",
            })
            return True

        # Check for error indicators in context
        if context.get("error_count", 0) >= 3:
            logger.info({
                "event": "escalation_triggered",
                "agent_id": self._agent_id,
                "reason": "repeated_errors",
            })
            return True

        return False

    def log_action(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """
        Log an agent action for audit trail.

        Args:
            action: Name of the action
            details: Additional details about the action
            success: Whether the action succeeded
        """
        action_record = AgentAction(
            action=action,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details or {},
            success=success,
        )
        self._action_log.append(action_record)

        if self._config.enable_logging:
            logger.info({
                "event": "agent_action",
                "agent_id": self._agent_id,
                "action": action,
                "success": success,
                "details": details,
            })

    def validate_input(
        self,
        input_data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Optional[str]:
        """
        Validate input data against a schema.

        Args:
            input_data: Data to validate
            schema: Validation schema with required fields

        Returns:
            Error message if validation fails, None if valid
        """
        if not input_data:
            return "Input data is required"

        # Check required fields
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in input_data:
                return f"Missing required field: {field_name}"

            # Check for empty values
            value = input_data[field_name]
            if value is None or (isinstance(value, str) and not value.strip()):
                return f"Field '{field_name}' cannot be empty"

        # Check field types
        properties = schema.get("properties", {})
        for field_name, value in input_data.items():
            if field_name in properties:
                expected_type = properties[field_name].get("type")
                if expected_type:
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }
                    expected_python_type = type_map.get(expected_type)
                    if expected_python_type and not isinstance(value, expected_python_type):
                        return f"Field '{field_name}' must be of type {expected_type}"

        return None

    def get_action_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent action log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of action log entries
        """
        actions = self._action_log[-limit:]
        return [
            {
                "action": a.action,
                "timestamp": a.timestamp,
                "details": a.details,
                "success": a.success,
            }
            for a in actions
        ]

    def _set_state(self, state: AgentState) -> None:
        """Set agent state."""
        old_state = self._state
        self._state = state

        logger.debug({
            "event": "agent_state_change",
            "agent_id": self._agent_id,
            "old_state": old_state.value,
            "new_state": state.value,
        })

    def _record_process_start(self) -> None:
        """Record the start of processing."""
        if not self._start_time:
            self._start_time = datetime.now(timezone.utc)
        self._set_state(AgentState.PROCESSING)
        self._process_count += 1

    def _record_process_end(
        self,
        success: bool = True,
        escalated: bool = False
    ) -> None:
        """Record the end of processing."""
        if not success:
            self._error_count += 1

        if escalated:
            self._escalation_count += 1
            self._set_state(AgentState.ESCALATING)
        else:
            self._set_state(AgentState.IDLE)

    def _record_error(self) -> None:
        """Record an error."""
        self._error_count += 1
        self._set_state(AgentState.ERROR)
