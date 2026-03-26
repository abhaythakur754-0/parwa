"""
PARWA Mini FAQ Agent.

Mini PARWA's FAQ agent handles frequently asked questions using
the Light tier for fast, efficient responses. Complex queries
are escalated to higher variants.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_faq_agent import BaseFAQAgent, AgentResponse
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniFAQAgent(BaseFAQAgent):
    """
    Mini PARWA FAQ Agent.

    Handles FAQ queries with the following characteristics:
    - Always routes to 'light' tier for fast responses
    - Escalates when confidence < 70%
    - Uses MiniConfig for escalation threshold
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        mini_config: Optional[MiniConfig] = None,
    ) -> None:
        """
        Initialize Mini FAQ Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            mini_config: Optional MiniConfig instance
        """
        super().__init__(agent_id, config, company_id)
        self._mini_config = mini_config or get_mini_config()

    def get_tier(self) -> str:
        """Get the AI tier for this agent. Mini always uses 'light'."""
        return "light"

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "mini"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process an FAQ query.

        Routes simple queries to light tier and escalates complex ones.

        Args:
            input_data: Must contain 'query' key

        Returns:
            AgentResponse with FAQ answer or escalation notice
        """
        # Validate input
        validation_error = self.validate_input(input_data, {
            "required": ["query"],
            "properties": {"query": {"type": "string"}}
        })
        if validation_error:
            return AgentResponse(
                success=False,
                message=validation_error,
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        query = input_data["query"]
        self.log_action("mini_faq_process", {
            "query": query,
            "tier": self.get_tier(),
        })

        # Search for FAQ matches
        results = await self.search_faq(query)

        # Calculate confidence based on results
        confidence = self.calculate_faq_confidence(results)

        # Check escalation based on Mini config threshold
        escalated = confidence < self._mini_config.escalation_threshold

        if escalated:
            self.log_action("mini_faq_escalate", {
                "query": query,
                "confidence": confidence,
                "threshold": self._mini_config.escalation_threshold,
            })

        # Format response
        if results and not escalated:
            top_result = results[0]
            formatted = self.format_faq_response(top_result, confidence)
            data = {"result": formatted, "matches": len(results)}
            message = "FAQ answer found"
        else:
            data = {"results": results, "count": len(results)}
            message = "Query escalated due to low confidence" if escalated else "No FAQ match found"

        return AgentResponse(
            success=True,
            message=message,
            data=data,
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Uses Mini config's escalation threshold (default 70%).

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        return confidence < self._mini_config.escalation_threshold
