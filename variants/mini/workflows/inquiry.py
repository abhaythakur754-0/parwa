"""
PARWA Mini Inquiry Workflow.

Handles customer inquiries by classifying, searching FAQs,
and escalating complex queries.
"""
from typing import Dict, Any, Optional
from variants.mini.tools.faq_search import FAQSearchTool
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class InquiryWorkflow:
    """
    Workflow for handling customer inquiries.

    Steps:
    1. Classify the inquiry type
    2. Search FAQ for answers
    3. Return answer or escalate if complex
    """

    INQUIRY_TYPES = ["faq", "order_status", "refund", "complaint", "other"]

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None
    ) -> None:
        """
        Initialize inquiry workflow.

        Args:
            mini_config: Mini configuration
        """
        self._config = mini_config or get_mini_config()
        self._faq_tool = FAQSearchTool()

    async def execute(self, inquiry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the inquiry workflow.

        Args:
            inquiry_data: Dict with:
                - query: Customer's question/query
                - customer_id: Optional customer identifier
                - channel: Communication channel (chat, email, sms)

        Returns:
            Dict with workflow result
        """
        query = inquiry_data.get("query", "")
        customer_id = inquiry_data.get("customer_id")
        channel = inquiry_data.get("channel", "chat")

        logger.info({
            "event": "inquiry_workflow_started",
            "query": query[:100],  # Truncate for logging
            "customer_id": customer_id,
            "channel": channel,
        })

        # Step 1: Classify inquiry
        inquiry_type = await self._classify_inquiry(query)

        # Step 2: Search FAQ
        faq_results = await self._faq_tool.search(query, limit=3)

        # Step 3: Calculate confidence
        confidence = self._calculate_confidence(faq_results, inquiry_type)

        # Step 4: Determine if escalate
        should_escalate = confidence < self._config.escalation_threshold

        if should_escalate:
            return {
                "status": "escalated",
                "reason": "low_confidence",
                "inquiry_type": inquiry_type,
                "confidence": confidence,
                "threshold": self._config.escalation_threshold,
                "message": "Your inquiry requires additional assistance. A human agent will help you shortly.",
            }

        # Step 5: Format response
        if faq_results:
            top_result = faq_results[0]
            return {
                "status": "resolved",
                "inquiry_type": inquiry_type,
                "confidence": confidence,
                "answer": top_result.get("answer"),
                "faq_id": top_result.get("id"),
                "question_matched": top_result.get("question"),
                "message": f"I found an answer to your question.",
            }

        return {
            "status": "no_match",
            "inquiry_type": inquiry_type,
            "confidence": confidence,
            "message": "I couldn't find a matching answer. Let me connect you with a human agent.",
            "escalate": True,
        }

    async def _classify_inquiry(self, query: str) -> str:
        """
        Classify the type of inquiry.

        Args:
            query: Customer query

        Returns:
            Inquiry type string
        """
        query_lower = query.lower()

        # Check for order status keywords
        order_keywords = ["order", "track", "shipping", "delivery", "status"]
        if any(kw in query_lower for kw in order_keywords):
            return "order_status"

        # Check for refund keywords
        refund_keywords = ["refund", "money back", "return", "cancel"]
        if any(kw in query_lower for kw in refund_keywords):
            return "refund"

        # Check for complaint keywords
        complaint_keywords = ["complaint", "unhappy", "disappointed", "angry", "terrible"]
        if any(kw in query_lower for kw in complaint_keywords):
            return "complaint"

        # Default to FAQ
        return "faq"

    def _calculate_confidence(
        self,
        faq_results: list,
        inquiry_type: str
    ) -> float:
        """
        Calculate confidence score for the result.

        Args:
            faq_results: FAQ search results
            inquiry_type: Classified inquiry type

        Returns:
            Confidence score (0.0-1.0)
        """
        base_confidence = 0.5

        if not faq_results:
            return 0.3

        # Boost for high relevance
        top_score = faq_results[0].get("relevance_score", 0)
        if top_score >= 5:
            base_confidence += 0.3
        elif top_score >= 3:
            base_confidence += 0.2
        elif top_score >= 1:
            base_confidence += 0.1

        # Reduce for complex inquiry types
        if inquiry_type == "complaint":
            base_confidence -= 0.2
        elif inquiry_type == "refund":
            base_confidence -= 0.1

        return min(1.0, max(0.0, base_confidence))

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "InquiryWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"
