"""
PARWA High Learning Agent.

Learning agent with feedback recording and negative_reward creation.
CRITICAL: Creates negative_reward record on rejection.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class FeedbackType(str, Enum):
    """Type of feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    CORRECTION = "correction"


class TrainingDataType(str, Enum):
    """Type of training data."""
    SUCCESSFUL_RESOLUTION = "successful_resolution"
    ESCALATION = "escalation"
    REJECTION = "rejection"
    CORRECTION = "correction"
    USER_FEEDBACK = "user_feedback"


@dataclass
class NegativeReward:
    """Negative reward record for training."""
    reward_id: str
    interaction_id: str
    reason: str
    severity: float = 0.5  # 0.0-1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    training_applied: bool = False


@dataclass
class TrainingDataPoint:
    """A single training data point."""
    data_id: str
    data_type: TrainingDataType
    interaction_id: str
    input_data: Dict[str, Any]
    expected_output: Optional[Dict[str, Any]] = None
    actual_output: Optional[Dict[str, Any]] = None
    feedback_type: Optional[FeedbackType] = None
    quality_score: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ParwaHighLearningAgent(BaseAgent):
    """
    PARWA High Learning Agent.

    Provides learning and feedback capabilities including:
    - Recording user feedback
    - Creating negative_reward on rejection
    - Collecting training data
    - Model fine-tuning preparation

    CRITICAL: Creates negative_reward record when feedback indicates rejection.
    """

    # PARWA High specific settings
    PARWA_HIGH_ESCALATION_THRESHOLD = 0.50
    MAX_TRAINING_DATA = 10000
    MIN_QUALITY_THRESHOLD = 0.7

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize PARWA High Learning Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
        """
        super().__init__(agent_id, config, company_id)

        # Training data storage
        self._training_data: Dict[str, TrainingDataPoint] = {}
        self._negative_rewards: Dict[str, NegativeReward] = {}
        self._feedback_history: List[Dict[str, Any]] = []

        # Statistics
        self._positive_feedback_count = 0
        self._negative_feedback_count = 0
        self._corrections_count = 0
        self._training_applied_count = 0

        logger.info({
            "event": "parwa_high_learning_agent_initialized",
            "agent_id": agent_id,
            "tier": self.get_tier(),
            "variant": self.get_variant(),
        })

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA High uses 'heavy'."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the PARWA High variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process learning request.

        Args:
            input_data: Must contain 'action' key
                - 'record_feedback': Record user feedback
                - 'create_negative_reward': Create negative reward
                - 'get_training_data': Get training data
                - 'fine_tune': Fine-tune model
                - 'get_stats': Get learning statistics

        Returns:
            AgentResponse with processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_high_learning_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "record_feedback":
            return await self._handle_record_feedback(input_data)
        elif action == "create_negative_reward":
            return await self._handle_create_negative_reward(input_data)
        elif action == "get_training_data":
            return await self._handle_get_training_data(input_data)
        elif action == "fine_tune":
            return await self._handle_fine_tune(input_data)
        elif action == "get_stats":
            return await self._handle_get_stats()
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def record_feedback(
        self,
        interaction_id: str,
        feedback: str,
        feedback_type: FeedbackType = FeedbackType.NEUTRAL
    ) -> Dict[str, Any]:
        """
        Record user feedback for an interaction.

        Args:
            interaction_id: Interaction identifier
            feedback: Feedback content
            feedback_type: Type of feedback

        Returns:
            Dict with feedback recording result
        """
        feedback_id = f"FB-{datetime.now().strftime('%Y%m%d%H%M%S')}-{interaction_id[:8]}"

        feedback_record = {
            "feedback_id": feedback_id,
            "interaction_id": interaction_id,
            "feedback": feedback,
            "feedback_type": feedback_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._feedback_history.append(feedback_record)

        # Update statistics
        if feedback_type == FeedbackType.POSITIVE:
            self._positive_feedback_count += 1
        elif feedback_type == FeedbackType.NEGATIVE:
            self._negative_feedback_count += 1
        elif feedback_type == FeedbackType.CORRECTION:
            self._corrections_count += 1

        # Create training data point
        training_id = f"TD-{feedback_id}"
        training_point = TrainingDataPoint(
            data_id=training_id,
            data_type=TrainingDataType.USER_FEEDBACK,
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            quality_score=0.8 if feedback_type == FeedbackType.POSITIVE else 0.3,
        )
        self._training_data[training_id] = training_point

        # Auto-create negative reward for negative feedback
        if feedback_type == FeedbackType.NEGATIVE:
            await self.create_negative_reward(
                interaction_id=interaction_id,
                reason=feedback,
                severity=0.5
            )

        self.log_action("parwa_high_feedback_recorded", {
            "feedback_id": feedback_id,
            "interaction_id": interaction_id,
            "feedback_type": feedback_type.value,
        })

        return {
            "feedback_id": feedback_id,
            "interaction_id": interaction_id,
            "feedback_type": feedback_type.value,
            "recorded": True,
            "negative_reward_created": feedback_type == FeedbackType.NEGATIVE,
        }

    async def create_negative_reward(
        self,
        interaction_id: str,
        reason: str,
        severity: float = 0.5
    ) -> Dict[str, Any]:
        """
        CRITICAL: Create a negative reward record.

        This is called when an interaction is rejected or receives
        negative feedback, marking it for model adjustment.

        Args:
            interaction_id: Interaction identifier
            reason: Reason for negative reward
            severity: Severity score (0.0-1.0)

        Returns:
            Dict with negative reward details
        """
        reward_id = f"NR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{interaction_id[:8]}"

        negative_reward = NegativeReward(
            reward_id=reward_id,
            interaction_id=interaction_id,
            reason=reason,
            severity=min(1.0, max(0.0, severity)),
        )

        self._negative_rewards[reward_id] = negative_reward

        # Create training data point for rejection
        training_id = f"TD-{reward_id}"
        training_point = TrainingDataPoint(
            data_id=training_id,
            data_type=TrainingDataType.REJECTION,
            interaction_id=interaction_id,
            quality_score=1.0 - severity,
        )
        self._training_data[training_id] = training_point

        self.log_action("parwa_high_negative_reward_created", {
            "reward_id": reward_id,
            "interaction_id": interaction_id,
            "reason": reason[:100],  # Truncate for logging
            "severity": severity,
        })

        return {
            "reward_id": reward_id,
            "interaction_id": interaction_id,
            "reason": reason,
            "severity": severity,
            "created_at": negative_reward.created_at.isoformat(),
        }

    async def get_training_data(
        self,
        limit: int = 100,
        data_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get training data for model fine-tuning.

        Args:
            limit: Maximum number of records to return
            data_type: Optional filter by data type

        Returns:
            List of training data points
        """
        data_points = list(self._training_data.values())

        # Filter by type if specified
        if data_type:
            try:
                target_type = TrainingDataType(data_type)
                data_points = [
                    dp for dp in data_points
                    if dp.data_type == target_type
                ]
            except ValueError:
                pass

        # Sort by quality score (higher is better)
        data_points.sort(key=lambda x: x.quality_score, reverse=True)

        # Limit results
        data_points = data_points[:limit]

        return [
            {
                "data_id": dp.data_id,
                "data_type": dp.data_type.value,
                "interaction_id": dp.interaction_id,
                "quality_score": dp.quality_score,
                "created_at": dp.created_at.isoformat(),
            }
            for dp in data_points
        ]

    async def fine_tune_model(
        self,
        training_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Prepare model for fine-tuning with training data.

        Note: This is a preparation step. Actual fine-tuning
        would be handled by an external ML pipeline.

        Args:
            training_data: List of training data points

        Returns:
            Dict with fine-tuning preparation result
        """
        if not training_data:
            return {
                "success": False,
                "message": "No training data provided",
            }

        # Validate training data
        valid_count = 0
        for data_point in training_data:
            quality = data_point.get("quality_score", 0)
            if quality >= self.MIN_QUALITY_THRESHOLD:
                valid_count += 1

        fine_tune_id = f"FT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        result = {
            "fine_tune_id": fine_tune_id,
            "total_data_points": len(training_data),
            "valid_data_points": valid_count,
            "quality_threshold": self.MIN_QUALITY_THRESHOLD,
            "status": "prepared",
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }

        self._training_applied_count += 1

        self.log_action("parwa_high_fine_tune_prepared", {
            "fine_tune_id": fine_tune_id,
            "data_points": len(training_data),
            "valid_count": valid_count,
        })

        return result

    async def _handle_record_feedback(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle record_feedback action."""
        interaction_id = input_data.get("interaction_id")
        feedback = input_data.get("feedback")

        if not interaction_id or not feedback:
            return AgentResponse(
                success=False,
                message="Missing required fields: interaction_id, feedback",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        feedback_type_str = input_data.get("feedback_type", "neutral")
        try:
            feedback_type = FeedbackType(feedback_type_str)
        except ValueError:
            feedback_type = FeedbackType.NEUTRAL

        result = await self.record_feedback(interaction_id, feedback, feedback_type)

        return AgentResponse(
            success=True,
            message=f"Feedback recorded for {interaction_id}",
            data=result,
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_create_negative_reward(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle create_negative_reward action."""
        interaction_id = input_data.get("interaction_id")
        reason = input_data.get("reason")

        if not interaction_id or not reason:
            return AgentResponse(
                success=False,
                message="Missing required fields: interaction_id, reason",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        severity = input_data.get("severity", 0.5)

        result = await self.create_negative_reward(interaction_id, reason, severity)

        return AgentResponse(
            success=True,
            message=f"Negative reward created for {interaction_id}",
            data=result,
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_training_data(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle get_training_data action."""
        limit = input_data.get("limit", 100)
        data_type = input_data.get("data_type")

        result = await self.get_training_data(limit, data_type)

        return AgentResponse(
            success=True,
            message=f"Retrieved {len(result)} training data points",
            data={
                "training_data": result,
                "count": len(result),
                "limit": limit,
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_fine_tune(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle fine_tune action."""
        training_data = input_data.get("training_data", [])

        # If no data provided, get from storage
        if not training_data:
            training_data = await self.get_training_data(limit=100)

        result = await self.fine_tune_model(training_data)

        return AgentResponse(
            success=result.get("success", True),
            message=f"Fine-tuning prepared: {result.get('valid_data_points', 0)} valid points",
            data=result,
            confidence=0.90,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_stats(self) -> AgentResponse:
        """Handle get_stats action."""
        return AgentResponse(
            success=True,
            message="Learning agent statistics",
            data={
                "training_data_count": len(self._training_data),
                "negative_rewards_count": len(self._negative_rewards),
                "feedback_history_count": len(self._feedback_history),
                "positive_feedback_count": self._positive_feedback_count,
                "negative_feedback_count": self._negative_feedback_count,
                "corrections_count": self._corrections_count,
                "training_applied_count": self._training_applied_count,
                "variant": self.get_variant(),
                "tier": self.get_tier(),
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )
