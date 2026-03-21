"""
PARWA Knowledge Base MCP Server.

MCP server for knowledge base operations.
Provides tools for searching, retrieving, and finding related articles.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import uuid4

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class KBServer(BaseMCPServer):
    """
    MCP Server for Knowledge Base operations.

    Provides tools for:
    - search: Search knowledge base for articles
    - get_article: Get a specific article by ID
    - get_related_articles: Get articles related to a specific article

    Example:
        server = KBServer()
        await server.start()
        result = await server.handle_tool_call("search", {"query": "api documentation"})
    """

    # Mock KB articles for development/testing
    DEFAULT_ARTICLES = [
        {
            "id": "kb_001",
            "title": "Getting Started Guide",
            "content": "Welcome to our platform! This guide will help you set up your account, configure your preferences, and start using our core features. Begin by creating your account, then follow the setup wizard to configure your workspace.",
            "category": "Onboarding",
            "tags": ["getting started", "setup", "beginner"],
            "author": "Documentation Team",
            "version": "1.0",
            "last_updated": "2024-01-15",
            "views": 1543,
            "helpful_votes": 89,
        },
        {
            "id": "kb_002",
            "title": "API Authentication",
            "content": "All API requests require authentication using Bearer tokens. Generate your API key from the Settings > API section. Include the token in the Authorization header: 'Authorization: Bearer YOUR_TOKEN'. Tokens expire after 30 days.",
            "category": "Technical",
            "tags": ["api", "authentication", "security", "token"],
            "author": "Engineering Team",
            "version": "2.1",
            "last_updated": "2024-02-20",
            "views": 2341,
            "helpful_votes": 156,
        },
        {
            "id": "kb_003",
            "title": "Data Export Procedures",
            "content": "To export your data, go to Settings > Data Management > Export. You can export in CSV, JSON, or Excel format. For large exports (>1GB), the system will process in the background and email you when complete.",
            "category": "Data Management",
            "tags": ["export", "data", "csv", "json"],
            "author": "Product Team",
            "version": "1.3",
            "last_updated": "2024-01-28",
            "views": 876,
            "helpful_votes": 67,
        },
        {
            "id": "kb_004",
            "title": "Integration Setup",
            "content": "Our platform integrates with 50+ popular tools including Slack, Salesforce, HubSpot, and Zapier. Navigate to Settings > Integrations to connect your accounts. Most integrations support OAuth for secure authorization.",
            "category": "Integrations",
            "tags": ["integration", "slack", "salesforce", "zapier"],
            "author": "Partnerships Team",
            "version": "3.0",
            "last_updated": "2024-02-10",
            "views": 1234,
            "helpful_votes": 98,
        },
        {
            "id": "kb_005",
            "title": "Security Best Practices",
            "content": "We recommend enabling two-factor authentication, using strong passwords, and regularly reviewing connected applications. Enable login notifications and IP restrictions for enterprise accounts. All data is encrypted at rest and in transit.",
            "category": "Security",
            "tags": ["security", "2fa", "encryption", "passwords"],
            "author": "Security Team",
            "version": "2.0",
            "last_updated": "2024-02-25",
            "views": 3102,
            "helpful_votes": 234,
        },
        {
            "id": "kb_006",
            "title": "Billing and Subscription Management",
            "content": "Manage your subscription from Settings > Billing. You can upgrade, downgrade, or cancel at any time. Invoices are generated on the 1st of each month. For billing inquiries, contact billing@example.com or use the support chat.",
            "category": "Billing",
            "tags": ["billing", "subscription", "invoice", "payment"],
            "author": "Finance Team",
            "version": "1.5",
            "last_updated": "2024-01-20",
            "views": 1890,
            "helpful_votes": 112,
        },
        {
            "id": "kb_007",
            "title": "Team Collaboration Features",
            "content": "Invite team members via Settings > Team. Assign roles (Admin, Editor, Viewer) to control access. Use @mentions in comments to notify colleagues. Shared workspaces allow real-time collaboration on documents and projects.",
            "category": "Collaboration",
            "tags": ["team", "collaboration", "roles", "permissions"],
            "author": "Product Team",
            "version": "2.2",
            "last_updated": "2024-02-05",
            "views": 1456,
            "helpful_votes": 87,
        },
        {
            "id": "kb_008",
            "title": "Troubleshooting Common Issues",
            "content": "If you experience issues, try: 1) Clearing browser cache, 2) Using incognito mode, 3) Checking our status page. For API errors, verify your token hasn't expired. Contact support with your request ID for faster resolution.",
            "category": "Support",
            "tags": ["troubleshooting", "issues", "support", "help"],
            "author": "Support Team",
            "version": "1.8",
            "last_updated": "2024-02-28",
            "views": 2789,
            "helpful_votes": 198,
        },
    ]

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        kb_manager: Optional[Any] = None
    ) -> None:
        """
        Initialize KB Server.

        Args:
            config: Optional server configuration
            kb_manager: Optional KnowledgeBaseManager instance
        """
        self._kb_manager = kb_manager
        self._articles = self.DEFAULT_ARTICLES.copy()
        self._articles_by_id = {article["id"]: article for article in self._articles}
        self._search_count = 0
        self._last_search_time: Optional[datetime] = None

        super().__init__(name="kb_server", config=config)

    def _register_tools(self) -> None:
        """Register KB tools."""
        self.register_tool(
            name="search",
            description="Search the knowledge base for relevant articles",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters (category, tags, etc.)",
                        "properties": {
                            "category": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            },
            handler=self._handle_search
        )

        self.register_tool(
            name="get_article",
            description="Get a specific article by its ID",
            parameters_schema={
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "Article ID to retrieve"
                    }
                },
                "required": ["article_id"]
            },
            handler=self._handle_get_article
        )

        self.register_tool(
            name="get_related_articles",
            description="Get articles related to a specific article",
            parameters_schema={
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "Article ID to find related content for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 3)",
                        "default": 3
                    }
                },
                "required": ["article_id"]
            },
            handler=self._handle_get_related
        )

    async def _handle_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle search tool call.

        Args:
            params: Parameters containing query, optional filters and limit

        Returns:
            Dictionary with matching articles
        """
        query = params["query"].lower()
        filters = params.get("filters", {})
        limit = params.get("limit", 10)

        self._search_count += 1
        self._last_search_time = datetime.now(timezone.utc)

        results = []
        for article in self._articles:
            # Apply category filter
            if "category" in filters:
                if article["category"] != filters["category"]:
                    continue

            # Apply tags filter
            if "tags" in filters:
                article_tags = set(t.lower() for t in article.get("tags", []))
                filter_tags = set(t.lower() for t in filters["tags"])
                if not filter_tags.issubset(article_tags):
                    continue

            # Calculate relevance
            score = self._calculate_article_relevance(article, query)
            if score > 0:
                results.append({
                    "id": article["id"],
                    "title": article["title"],
                    "category": article["category"],
                    "summary": article["content"][:150] + "...",
                    "relevance_score": score,
                    "views": article.get("views", 0),
                    "helpful_votes": article.get("helpful_votes", 0),
                })

        # Sort by relevance, then by helpful votes
        results.sort(key=lambda x: (x["relevance_score"], x["helpful_votes"]), reverse=True)
        results = results[:limit]

        logger.info({
            "event": "kb_search_completed",
            "query_length": len(query),
            "results_found": len(results),
            "filters_applied": bool(filters),
        })

        return {
            "success": True,
            "query": params["query"],
            "total_results": len(results),
            "results": results,
        }

    async def _handle_get_article(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_article tool call.

        Args:
            params: Parameters containing article_id

        Returns:
            Dictionary with full article data
        """
        article_id = params["article_id"]
        article = self._articles_by_id.get(article_id)

        if not article:
            return {
                "success": False,
                "error": f"Article with ID '{article_id}' not found",
                "article_id": article_id,
            }

        # Increment view count (mock)
        article["views"] = article.get("views", 0) + 1

        logger.info({
            "event": "kb_article_retrieved",
            "article_id": article_id,
            "title": article["title"],
        })

        return {
            "success": True,
            "article": article,
        }

    async def _handle_get_related(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_related_articles tool call.

        Args:
            params: Parameters containing article_id and optional limit

        Returns:
            Dictionary with related articles
        """
        article_id = params["article_id"]
        limit = params.get("limit", 3)

        source_article = self._articles_by_id.get(article_id)
        if not source_article:
            return {
                "success": False,
                "error": f"Article with ID '{article_id}' not found",
                "article_id": article_id,
            }

        # Find related articles based on tags and category
        related = []
        source_tags = set(t.lower() for t in source_article.get("tags", []))
        source_category = source_article.get("category")

        for article in self._articles:
            if article["id"] == article_id:
                continue

            # Calculate relatedness score
            article_tags = set(t.lower() for t in article.get("tags", []))
            tag_overlap = len(source_tags & article_tags)
            same_category = article.get("category") == source_category

            relatedness = tag_overlap * 0.3 + (0.4 if same_category else 0)

            if relatedness > 0:
                related.append({
                    "id": article["id"],
                    "title": article["title"],
                    "category": article["category"],
                    "summary": article["content"][:100] + "...",
                    "relatedness_score": round(relatedness, 2),
                    "shared_tags": list(source_tags & article_tags),
                })

        # Sort by relatedness and limit
        related.sort(key=lambda x: x["relatedness_score"], reverse=True)
        related = related[:limit]

        logger.info({
            "event": "kb_related_articles_found",
            "source_article_id": article_id,
            "related_count": len(related),
        })

        return {
            "success": True,
            "source_article_id": article_id,
            "source_title": source_article["title"],
            "related_articles": related,
        }

    def _calculate_article_relevance(
        self,
        article: Dict[str, Any],
        query: str
    ) -> float:
        """
        Calculate relevance score for article against query.

        Args:
            article: Article dictionary
            query: Lowercase search query

        Returns:
            Relevance score (0-1)
        """
        score = 0.0
        query_words = set(query.split())

        # Title match (highest weight)
        title_words = set(article["title"].lower().split())
        title_overlap = len(query_words & title_words)
        score += (title_overlap / max(len(query_words), 1)) * 0.4

        # Content match
        content_words = set(article["content"].lower().split())
        content_overlap = len(query_words & content_words)
        score += (content_overlap / max(len(query_words), 1)) * 0.3

        # Tags match
        tags = [tag.lower() for tag in article.get("tags", [])]
        tag_matches = sum(1 for word in query_words if word in tags)
        score += (tag_matches / max(len(query_words), 1)) * 0.2

        # Category match
        category_words = set(article.get("category", "").lower().split())
        category_overlap = len(query_words & category_words)
        score += (category_overlap / max(len(query_words), 1)) * 0.1

        # Boost by helpful votes (normalized)
        helpful_boost = min(article.get("helpful_votes", 0) / 300, 0.1)
        score += helpful_boost

        return round(min(score, 1.0), 3)

    async def health_check(self) -> Dict[str, Any]:
        """
        Extended health check with KB-specific stats.

        Returns:
            Health status dictionary
        """
        base_health = await super().health_check()

        base_health.update({
            "total_articles": len(self._articles),
            "categories": list(set(a["category"] for a in self._articles)),
            "search_count": self._search_count,
            "last_search_time": (
                self._last_search_time.isoformat()
                if self._last_search_time else None
            ),
        })

        return base_health
