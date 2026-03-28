"""
Enterprise Support - Knowledge Base
Enterprise knowledge base management
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ArticleType(str, Enum):
    HOW_TO = "how_to"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    REFERENCE = "reference"


class KnowledgeArticle(BaseModel):
    """Knowledge base article"""
    article_id: str = Field(default_factory=lambda: f"kb_{uuid.uuid4().hex[:8]}")
    title: str
    content: str
    article_type: ArticleType = ArticleType.FAQ
    status: ArticleStatus = ArticleStatus.DRAFT
    category: str = "general"
    tags: List[str] = Field(default_factory=list)
    author: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    views: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    client_specific: Optional[str] = None

    model_config = ConfigDict()


class KnowledgeBase:
    """
    Enterprise knowledge base management.
    """

    def __init__(self):
        self.articles: Dict[str, KnowledgeArticle] = {}
        self.categories: Dict[str, List[str]] = {}

    def create_article(
        self,
        title: str,
        content: str,
        article_type: ArticleType = ArticleType.FAQ,
        category: str = "general",
        tags: Optional[List[str]] = None,
        author: str = "system",
        client_specific: Optional[str] = None
    ) -> KnowledgeArticle:
        """Create a new article"""
        article = KnowledgeArticle(
            title=title,
            content=content,
            article_type=article_type,
            category=category,
            tags=tags or [],
            author=author,
            client_specific=client_specific
        )

        self.articles[article.article_id] = article

        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(article.article_id)

        return article

    def publish_article(self, article_id: str) -> bool:
        """Publish an article"""
        if article_id not in self.articles:
            return False

        self.articles[article_id].status = ArticleStatus.PUBLISHED
        return True

    def update_article(
        self,
        article_id: str,
        updates: Dict[str, Any]
    ) -> Optional[KnowledgeArticle]:
        """Update an article"""
        if article_id not in self.articles:
            return None

        article = self.articles[article_id]
        for key, value in updates.items():
            if hasattr(article, key):
                setattr(article, key, value)
        article.updated_at = datetime.utcnow()

        return article

    def get_article(self, article_id: str) -> Optional[KnowledgeArticle]:
        """Get an article by ID"""
        return self.articles.get(article_id)

    def search(
        self,
        query: str,
        client_id: Optional[str] = None
    ) -> List[KnowledgeArticle]:
        """Search articles"""
        results = []
        query_lower = query.lower()

        for article in self.articles.values():
            if article.status != ArticleStatus.PUBLISHED:
                continue

            # Skip non-client articles if client-specific search
            if client_id and article.client_specific and article.client_specific != client_id:
                continue

            # Simple search in title and content
            if query_lower in article.title.lower() or query_lower in article.content.lower():
                results.append(article)

        return results

    def get_by_category(self, category: str) -> List[KnowledgeArticle]:
        """Get articles by category"""
        article_ids = self.categories.get(category, [])
        return [
            self.articles[aid] for aid in article_ids
            if self.articles[aid].status == ArticleStatus.PUBLISHED
        ]

    def mark_helpful(self, article_id: str, helpful: bool = True) -> bool:
        """Mark article as helpful or not"""
        if article_id not in self.articles:
            return False

        article = self.articles[article_id]
        if helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1

        return True

    def get_popular_articles(self, limit: int = 10) -> List[KnowledgeArticle]:
        """Get most viewed articles"""
        published = [
            a for a in self.articles.values()
            if a.status == ArticleStatus.PUBLISHED
        ]
        return sorted(published, key=lambda x: x.views, reverse=True)[:limit]
