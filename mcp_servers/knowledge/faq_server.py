"""
PARWA FAQ MCP Server.

MCP server for FAQ lookup and search operations.
Provides tools for searching FAQs, getting specific FAQs,
and listing FAQ categories.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from mcp_servers.base_server import BaseMCPServer, ToolResult
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class FAQServer(BaseMCPServer):
    """
    MCP Server for FAQ operations.

    Provides tools for:
    - search_faqs: Search FAQ database by query
    - get_faq_by_id: Get specific FAQ by ID
    - get_faq_categories: List all FAQ categories

    Example:
        server = FAQServer()
        await server.start()
        result = await server.handle_tool_call("search_faqs", {"query": "refund"})
    """

    # Mock FAQ data for development/testing
    DEFAULT_FAQS = [
        {
            "id": "faq_001",
            "question": "How do I request a refund?",
            "answer": "To request a refund, contact our support team within 30 days of purchase. Provide your order number and reason for the refund request. Refunds are typically processed within 5-7 business days.",
            "category": "Billing",
            "tags": ["refund", "billing", "money"],
            "helpful_count": 150,
        },
        {
            "id": "faq_002",
            "question": "What payment methods do you accept?",
            "answer": "We accept all major credit cards (Visa, MasterCard, American Express), PayPal, and bank transfers. For enterprise customers, we also support invoicing.",
            "category": "Billing",
            "tags": ["payment", "billing", "credit card"],
            "helpful_count": 89,
        },
        {
            "id": "faq_003",
            "question": "How do I reset my password?",
            "answer": "Click 'Forgot Password' on the login page. Enter your email address and we'll send you a password reset link. The link expires in 24 hours.",
            "category": "Account",
            "tags": ["password", "login", "account", "security"],
            "helpful_count": 234,
        },
        {
            "id": "faq_004",
            "question": "How do I cancel my subscription?",
            "answer": "Go to Settings > Subscription > Cancel Subscription. Your access will continue until the end of your billing period. You can reactivate anytime.",
            "category": "Subscription",
            "tags": ["subscription", "cancel", "billing"],
            "helpful_count": 67,
        },
        {
            "id": "faq_005",
            "question": "What is your data retention policy?",
            "answer": "We retain customer data for the duration of your account plus 90 days. After account deletion, data is anonymized within 30 days per GDPR requirements.",
            "category": "Privacy",
            "tags": ["data", "privacy", "gdpr", "retention"],
            "helpful_count": 45,
        },
        {
            "id": "faq_006",
            "question": "How do I contact support?",
            "answer": "You can reach our support team via email at support@example.com, through live chat on our website (9 AM - 6 PM EST), or by submitting a ticket through your account dashboard.",
            "category": "Support",
            "tags": ["support", "contact", "help"],
            "helpful_count": 178,
        },
        {
            "id": "faq_007",
            "question": "Do you offer API access?",
            "answer": "Yes, we offer REST API access on Professional and Enterprise plans. API documentation is available at docs.example.com/api. Rate limits apply based on your plan.",
            "category": "Technical",
            "tags": ["api", "integration", "developer"],
            "helpful_count": 92,
        },
        {
            "id": "faq_008",
            "question": "Is my data secure?",
            "answer": "We use AES-256 encryption for data at rest and TLS 1.3 for data in transit. We're SOC 2 Type II certified and GDPR compliant. Regular security audits are conducted by third parties.",
            "category": "Security",
            "tags": ["security", "encryption", "compliance"],
            "helpful_count": 156,
        },
    ]

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        faqs: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Initialize FAQ Server.

        Args:
            config: Optional server configuration
            faqs: Optional custom FAQ data (uses default if not provided)
        """
        self._faqs = faqs or self.DEFAULT_FAQS.copy()
        self._faqs_by_id = {faq["id"]: faq for faq in self._faqs}
        self._categories = list(set(faq["category"] for faq in self._faqs))

        super().__init__(name="faq_server", config=config)

    def _register_tools(self) -> None:
        """Register FAQ tools."""
        self.register_tool(
            name="search_faqs",
            description="Search the FAQ database for relevant questions and answers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 5)",
                        "default": 5
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)"
                    }
                },
                "required": ["query"]
            },
            handler=self._handle_search_faqs
        )

        self.register_tool(
            name="get_faq_by_id",
            description="Get a specific FAQ by its ID",
            parameters_schema={
                "type": "object",
                "properties": {
                    "faq_id": {
                        "type": "string",
                        "description": "FAQ ID to retrieve"
                    }
                },
                "required": ["faq_id"]
            },
            handler=self._handle_get_faq_by_id
        )

        self.register_tool(
            name="get_faq_categories",
            description="List all available FAQ categories",
            parameters_schema={
                "type": "object",
                "properties": {}
            },
            handler=self._handle_get_categories
        )

    async def _handle_search_faqs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle search_faqs tool call.

        Args:
            params: Parameters containing query, optional limit and category

        Returns:
            Dictionary with matching FAQs
        """
        query = params["query"].lower()
        limit = params.get("limit", 5)
        category_filter = params.get("category")

        results = []
        for faq in self._faqs:
            # Apply category filter if specified
            if category_filter and faq["category"] != category_filter:
                continue

            # Calculate relevance score
            score = self._calculate_relevance(faq, query)
            if score > 0:
                results.append({
                    **faq,
                    "relevance_score": score
                })

        # Sort by relevance and limit
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:limit]

        logger.info({
            "event": "faq_search_completed",
            "query_length": len(query),
            "results_found": len(results),
            "category_filter": category_filter,
        })

        return {
            "success": True,
            "query": params["query"],
            "total_results": len(results),
            "results": results,
        }

    async def _handle_get_faq_by_id(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_faq_by_id tool call.

        Args:
            params: Parameters containing faq_id

        Returns:
            Dictionary with FAQ data or error
        """
        faq_id = params["faq_id"]
        faq = self._faqs_by_id.get(faq_id)

        if not faq:
            return {
                "success": False,
                "error": f"FAQ with ID '{faq_id}' not found",
                "faq_id": faq_id,
            }

        logger.info({
            "event": "faq_retrieved",
            "faq_id": faq_id,
        })

        return {
            "success": True,
            "faq": faq,
        }

    async def _handle_get_categories(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_faq_categories tool call.

        Args:
            params: Empty parameters

        Returns:
            Dictionary with list of categories and counts
        """
        category_counts = {}
        for faq in self._faqs:
            cat = faq["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

        categories = [
            {"name": cat, "faq_count": count}
            for cat, count in sorted(category_counts.items())
        ]

        logger.info({
            "event": "faq_categories_retrieved",
            "category_count": len(categories),
        })

        return {
            "success": True,
            "total_categories": len(categories),
            "categories": categories,
        }

    def _calculate_relevance(self, faq: Dict[str, Any], query: str) -> float:
        """
        Calculate relevance score for FAQ against query.

        Args:
            faq: FAQ dictionary
            query: Lowercase search query

        Returns:
            Relevance score (0-1)
        """
        score = 0.0
        query_words = set(query.split())

        # Check question match (highest weight)
        question_words = set(faq["question"].lower().split())
        question_overlap = len(query_words & question_words)
        score += (question_overlap / max(len(query_words), 1)) * 0.5

        # Check answer match
        answer_words = set(faq["answer"].lower().split())
        answer_overlap = len(query_words & answer_words)
        score += (answer_overlap / max(len(query_words), 1)) * 0.3

        # Check tags match
        tags = [tag.lower() for tag in faq.get("tags", [])]
        tag_matches = sum(1 for word in query_words if word in tags)
        score += (tag_matches / max(len(query_words), 1)) * 0.2

        # Boost by helpful count (normalized)
        helpful_boost = min(faq.get("helpful_count", 0) / 500, 0.1)
        score += helpful_boost

        return round(min(score, 1.0), 3)
