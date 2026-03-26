"""
PARWA Learning Agent.

Handles feedback recording, negative reward creation for rejected responses,
and training data preparation for Agent Lightning fine-tuning.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class FeedbackRecord:
    """Record of user feedback on an interaction."""

    def __init__(
        self,
        interaction_id: str,
        feedback: str,
        feedback_type: str,
        created_at: str
    ) -> None:
        self.interaction_id = interaction_id
        self.feedback = feedback
        self.feedback_type = feedback_type
        self.created_at = created_at


class NegativeRewardRecord:
    """Record of negative reward for rejected responses."""

    def __init__(
        self,
        reward_id: str,
        interaction_id: str,
        reason: str,
        created_at: str
    ) -> None:
        self.reward_id = reward_id
        self.interaction_id = interaction_id
        self.reason = reason
        self.created_at = created_at


class ParwaLearningAgent(BaseAgent):
    """
    PARWA Learning Agent.

    Handles feedback collection and negative reward creation for
    rejected responses. This enables continuous improvement through
    Agent Lightning fine-tuning.

    Key Features:
    - Records user feedback on interactions
    - Creates negative_reward records for rejected responses
    - Prepares training data for fine-tuning
    - Company-isolated learning data
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize PARWA Learning Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for data isolation
        """
        super().__init__(agent_id, config, company_id)
        self._feedback_records: Dict[str, FeedbackRecord] = {}
        self._negative_rewards: Dict[str, NegativeRewardRecord] = {}
        self._interaction_data: Dict[str, Dict[str, Any]] = {}

    def get_tier(self) -> str:
        """Return the processing tier for PARWA agents."""
        return "medium"

    def get_variant(self) -> str:
        """Return the PARWA variant identifier."""
        return "parwa"

    async def record_feedback(
        self,
        interaction_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """
        Record user feedback on an interaction.

        Args:
            interaction_id: ID of the interaction receiving feedback
            feedback: User feedback text (positive or negative)

        Returns:
            Dict with feedback_id and status
        """
        if not interaction_id:
            return {
                "status": "error",
                "message": "interaction_id is required",
            }

        feedback_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Determine feedback type
        feedback_lower = feedback.lower()
        if any(word in feedback_lower for word in ["good", "great", "helpful", "thanks"]):
            feedback_type = "positive"
        elif any(word in feedback_lower for word in ["bad", "wrong", "incorrect", "unhelpful"]):
            feedback_type = "negative"
        else:
            feedback_type = "neutral"

        record = FeedbackRecord(
            interaction_id=interaction_id,
            feedback=feedback,
            feedback_type=feedback_type,
            created_at=created_at,
        )
        self._feedback_records[feedback_id] = record

        self.log_action("record_feedback", {
            "feedback_id": feedback_id,
            "interaction_id": interaction_id,
            "feedback_type": feedback_type,
        })

        # If negative feedback, create negative reward
        if feedback_type == "negative":
            await self.create_negative_reward(interaction_id, feedback)

        return {
            "feedback_id": feedback_id,
            "status": "recorded",
            "feedback_type": feedback_type,
            "interaction_id": interaction_id,
        }

    async def create_negative_reward(
        self,
        interaction_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Create a negative reward record for a rejected response.

        This is called when a response is rejected or receives negative
        feedback. The negative reward is used for RLHF fine-tuning.

        Args:
            interaction_id: ID of the interaction that was rejected
            reason: Reason for the rejection

        Returns:
            Dict with reward_id and status
        """
        if not interaction_id:
            return {
                "status": "error",
                "message": "interaction_id is required",
            }

        reward_id = f"neg_reward_{uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        record = NegativeRewardRecord(
            reward_id=reward_id,
            interaction_id=interaction_id,
            reason=reason,
            created_at=created_at,
        )
        self._negative_rewards[reward_id] = record

        logger.warning({
            "event": "negative_reward_created",
            "agent_id": self._agent_id,
            "reward_id": reward_id,
            "interaction_id": interaction_id,
            "reason": reason,
            "company_id": str(self._company_id) if self._company_id else None,
        })

        self.log_action("create_negative_reward", {
            "reward_id": reward_id,
            "interaction_id": interaction_id,
        })

        return {
            "reward_id": reward_id,
            "status": "created",
            "interaction_id": interaction_id,
            "reason": reason,
            "created_at": created_at,
        }

    async def get_training_data(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get training data for fine-tuning.

        Returns interaction data with associated feedback and
        negative rewards for Agent Lightning fine-tuning.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of training data records
        """
        training_data: List[Dict[str, Any]] = []

        # Combine feedback with interaction data
        for feedback_id, feedback in list(self._feedback_records.items())[:limit]:
            interaction_id = feedback.interaction_id
            interaction = self._interaction_data.get(interaction_id, {})

            record = {
                "feedback_id": feedback_id,
                "interaction_id": interaction_id,
                "feedback": feedback.feedback,
                "feedback_type": feedback.feedback_type,
                "created_at": feedback.created_at,
                "interaction_data": interaction,
                "has_negative_reward": any(
                    r.interaction_id == interaction_id
                    for r in self._negative_rewards.values()
                ),
            }
            training_data.append(record)

        self.log_action("get_training_data", {
            "records_returned": len(training_data),
            "limit": limit,
        })

        return training_data

    def store_interaction(
        self,
        interaction_id: str,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Store interaction data for later training.

        Args:
            interaction_id: Unique interaction identifier
            query: User query
            response: Agent response
            metadata: Additional metadata
        """
        self._interaction_data[interaction_id] = {
            "query": query,
            "response": response,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a learning request.

        Args:
            input_data: Must contain 'action' ('record_feedback',
                        'create_negative_reward', 'get_training_data')

        Returns:
            AgentResponse with result
        """
        action = input_data.get("action", "")

        if action == "record_feedback":
            result = await self.record_feedback(
                input_data.get("interaction_id", ""),
                input_data.get("feedback", "")
            )
        elif action == "create_negative_reward":
            result = await self.create_negative_reward(
                input_data.get("interaction_id", ""),
                input_data.get("reason", "")
            )
        elif action == "get_training_data":
            result = await self.get_training_data(
                input_data.get("limit", 100)
            )
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Learning action '{action}' completed",
            data=result if isinstance(result, dict) else {"records": result},
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get learning agent statistics."""
        return {
            "total_feedback": len(self._feedback_records),
            "positive_feedback": sum(
                1 for f in self._feedback_records.values()
                if f.feedback_type == "positive"
            ),
            "negative_feedback": sum(
                1 for f in self._feedback_records.values()
                if f.feedback_type == "negative"
            ),
            "total_negative_rewards": len(self._negative_rewards),
            "stored_interactions": len(self._interaction_data),
        }
