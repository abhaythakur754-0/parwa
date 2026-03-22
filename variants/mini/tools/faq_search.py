"""
PARWA Mini FAQ Search Tool.

Provides FAQ search functionality for Mini PARWA agents.
"""
from typing import Dict, Any, List, Optional
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class FAQSearchTool:
    """
    Tool for searching FAQ database.

    Provides:
    - Search FAQ by query
    - Get FAQ by ID
    - List FAQ categories
    """

    def __init__(self) -> None:
        """Initialize FAQ search tool with mock data."""
        self._faqs: Dict[str, Dict[str, Any]] = {
            "FAQ-001": {
                "id": "FAQ-001",
                "question": "How do I reset my password?",
                "answer": "You can reset your password by clicking the 'Forgot Password' link on the login page. Follow the instructions sent to your email.",
                "category": "account",
                "keywords": ["password", "reset", "login", "account"],
            },
            "FAQ-002": {
                "id": "FAQ-002",
                "question": "What is your return policy?",
                "answer": "We accept returns within 30 days of purchase. Items must be unused and in original packaging.",
                "category": "returns",
                "keywords": ["return", "policy", "refund", "money back"],
            },
            "FAQ-003": {
                "id": "FAQ-003",
                "question": "How do I track my order?",
                "answer": "You can track your order by logging into your account and viewing your order history. A tracking link will be available once your order ships.",
                "category": "orders",
                "keywords": ["track", "order", "shipping", "delivery", "status"],
            },
            "FAQ-004": {
                "id": "FAQ-004",
                "question": "How do I contact customer support?",
                "answer": "You can reach our customer support team via email at support@example.com or by phone at 1-800-EXAMPLE. Support hours are 9am-5pm EST.",
                "category": "support",
                "keywords": ["contact", "support", "help", "phone", "email"],
            },
            "FAQ-005": {
                "id": "FAQ-005",
                "question": "What payment methods do you accept?",
                "answer": "We accept all major credit cards (Visa, MasterCard, American Express), PayPal, and Apple Pay.",
                "category": "payment",
                "keywords": ["payment", "credit card", "paypal", "pay"],
            },
        }

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search FAQs by query.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching FAQ entries
        """
        logger.info({
            "event": "faq_search",
            "query": query,
            "limit": limit,
        })

        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []
        for faq in self._faqs.values():
            # Calculate relevance score
            score = 0

            # Check keywords match
            keywords = set(faq.get("keywords", []))
            keyword_matches = query_words & keywords
            score += len(keyword_matches) * 3

            # Check question contains query words
            question_lower = faq["question"].lower()
            for word in query_words:
                if word in question_lower:
                    score += 2

            # Check answer contains query words
            answer_lower = faq["answer"].lower()
            for word in query_words:
                if word in answer_lower:
                    score += 1

            if score > 0:
                results.append({
                    **faq,
                    "relevance_score": score,
                })

        # Sort by relevance and limit
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]

    async def get_by_id(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """
        Get FAQ by ID.

        Args:
            faq_id: FAQ identifier

        Returns:
            FAQ entry or None if not found
        """
        logger.info({
            "event": "faq_get_by_id",
            "faq_id": faq_id,
        })

        return self._faqs.get(faq_id)

    async def get_categories(self) -> List[str]:
        """
        Get list of FAQ categories.

        Returns:
            List of unique category names
        """
        categories = set()
        for faq in self._faqs.values():
            categories.add(faq.get("category", "general"))
        return list(categories)

    async def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get FAQs by category.

        Args:
            category: Category name

        Returns:
            List of FAQs in the category
        """
        results = []
        for faq in self._faqs.values():
            if faq.get("category") == category.lower():
                results.append(faq)
        return results
