"""
PARWA Mini Answer FAQ Task.

Task for answering FAQ queries using the Mini FAQ agent.
Routes to Light tier for fast, efficient responses.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass

from variants.mini.agents.faq_agent import MiniFAQAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FAQTaskResult:
    """Result from FAQ task execution."""
    success: bool
    answer: Optional[str] = None
    faq_id: Optional[str] = None
    confidence: float = 0.0
    escalated: bool = False
    escalation_reason: Optional[str] = None
    matches_found: int = 0


class AnswerFAQTask:
    """
    Task for answering FAQ queries.

    Uses MiniFAQAgent to:
    1. Search FAQ knowledge base
    2. Return best matching answer
    3. Escalate if confidence < 70%

    Example:
        task = AnswerFAQTask()
        result = await task.execute({
            "query": "What are your business hours?",
            "customer_id": "cust_123"
        })
    """

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_faq_task"
    ) -> None:
        """
        Initialize FAQ task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniFAQAgent(
            agent_id=agent_id,
            mini_config=self._config
        )

    async def execute(self, input_data: Dict[str, Any]) -> FAQTaskResult:
        """
        Execute the FAQ answer task.

        Args:
            input_data: Must contain:
                - query: The FAQ question to answer
                - customer_id: Optional customer identifier

        Returns:
            FAQTaskResult with answer or escalation status
        """
        query = input_data.get("query", "")
        customer_id = input_data.get("customer_id")

        logger.info({
            "event": "faq_task_started",
            "query": query[:100],
            "customer_id": customer_id,
        })

        # Process through Mini FAQ agent
        response = await self._agent.process({
            "query": query,
            "customer_id": customer_id
        })

        # Build result
        result = FAQTaskResult(
            success=response.success,
            confidence=response.confidence,
            escalated=response.escalated,
            escalation_reason=response.escalation_reason if response.escalated else None,
        )

        if response.success and not response.escalated:
            # Extract answer from response data
            data = response.data or {}
            if "result" in data:
                result.answer = data["result"].get("answer")
                result.faq_id = data["result"].get("id")
            result.matches_found = data.get("matches", 0)

        logger.info({
            "event": "faq_task_completed",
            "success": result.success,
            "escalated": result.escalated,
            "confidence": result.confidence,
            "matches_found": result.matches_found,
        })

        return result

    def get_task_name(self) -> str:
        """Get task name."""
        return "answer_faq"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
