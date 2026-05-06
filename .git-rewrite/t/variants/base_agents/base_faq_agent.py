"""
PARWA Base FAQ Agent.

Abstract base class for FAQ-handling agents. Provides common
functionality for FAQ search, retrieval, and response generation.
"""
from typing import Dict, Any, List, Optional
from uuid import UUID

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


# Mock FAQ data for testing
MOCK_FAQS = [
    {
        "faq_id": "FAQ-001",
        "question": "How do I reset my password?",
        "answer": "You can reset your password by clicking 'Forgot Password' on the login page.",
        "category": "Account",
        "keywords": ["password", "reset", "login"],
    },
    {
        "faq_id": "FAQ-002",
        "question": "What are your business hours?",
        "answer": "Our support team is available 24/7 via chat and email.",
        "category": "Support",
        "keywords": ["hours", "support", "contact"],
    },
    {
        "faq_id": "FAQ-003",
        "question": "How do I track my order?",
        "answer": "You can track your order in the 'My Orders' section of your account.",
        "category": "Orders",
        "keywords": ["track", "order", "shipping"],
    },
    {
        "faq_id": "FAQ-004",
        "question": "What is your refund policy?",
        "answer": "We offer full refunds within 30 days of purchase for unused items.",
        "category": "Refunds",
        "keywords": ["refund", "policy", "return"],
    },
]


class BaseFAQAgent(BaseAgent):
    """
    Abstract base class for FAQ-handling agents.

    Provides:
    - FAQ search functionality
    - FAQ retrieval by ID
    - Answer formatting
    - Confidence calculation based on match quality

    Subclasses must implement:
    - get_tier()
    - get_variant()
    - process()
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize FAQ agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)
        self._faqs = list(MOCK_FAQS)

    async def search_faq(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search FAQ database for matching entries.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching FAQ entries with relevance scores
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []
        for faq in self._faqs:
            # Calculate relevance score
            score = 0.0

            # Check question match
            question_lower = faq["question"].lower()
            if query_lower in question_lower:
                score += 0.5
            else:
                # Check word overlap
                question_words = set(question_lower.split())
                overlap = len(query_words & question_words)
                score += min(0.3, overlap * 0.1)

            # Check keyword match
            for keyword in faq.get("keywords", []):
                if keyword.lower() in query_lower:
                    score += 0.2

            # Check category match
            if faq.get("category", "").lower() in query_lower:
                score += 0.1

            if score > 0:
                results.append({
                    **faq,
                    "relevance_score": min(1.0, score),
                })

        # Sort by relevance and limit
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]

    async def get_faq_answer(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific FAQ by ID.

        Args:
            faq_id: FAQ identifier

        Returns:
            FAQ entry or None if not found
        """
        for faq in self._faqs:
            if faq["faq_id"] == faq_id:
                return faq
        return None

    async def get_faq_categories(self) -> List[str]:
        """
        Get all FAQ categories.

        Returns:
            List of unique category names
        """
        categories = set()
        for faq in self._faqs:
            if "category" in faq:
                categories.add(faq["category"])
        return sorted(list(categories))

    def calculate_faq_confidence(
        self,
        search_results: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate confidence based on search results.

        Args:
            search_results: List of search results with relevance scores

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not search_results:
            return 0.0

        # Use top result's relevance score as base confidence
        top_score = search_results[0].get("relevance_score", 0)

        # Boost confidence if multiple good matches
        if len(search_results) > 1:
            second_score = search_results[1].get("relevance_score", 0)
            if second_score > 0.5:
                top_score = min(1.0, top_score + 0.1)

        return top_score

    def format_faq_response(
        self,
        faq: Dict[str, Any],
        confidence: float
    ) -> Dict[str, Any]:
        """
        Format an FAQ response.

        Args:
            faq: FAQ entry
            confidence: Confidence score

        Returns:
            Formatted response dictionary
        """
        return {
            "faq_id": faq.get("faq_id"),
            "question": faq.get("question"),
            "answer": faq.get("answer"),
            "category": faq.get("category"),
            "confidence": confidence,
            "source": "faq_database",
        }
