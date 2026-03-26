"""AI-Powered Product Recommendation Engine.

Provides context-aware product recommendations based on:
- Ticket content analysis
- Customer purchase history
- Product catalog integration
- Multi-factor scoring algorithm
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """Product representation."""
    product_id: str
    name: str
    sku: str
    price: Decimal
    category: str
    tags: List[str] = field(default_factory=list)
    availability: bool = True
    image_url: Optional[str] = None
    description: Optional[str] = None


@dataclass
class Recommendation:
    """Product recommendation with scoring."""
    product: Product
    confidence_score: float
    recommendation_type: str  # 'similar', 'complementary', 'trending', 'personalized'
    reasoning: str
    cross_sell_potential: float = 0.0


@dataclass
class RecommendationResult:
    """Complete recommendation result."""
    recommendations: List[Recommendation]
    context: str
    total_products_considered: int
    processing_time_ms: float


class RecommendationEngine:
    """AI-powered product recommendation engine."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize recommendation engine.

        Args:
            client_id: Client identifier for tenant isolation
            config: Optional configuration overrides
        """
        self.client_id = client_id
        self.config = config or {}
        self.max_recommendations = self.config.get("max_recommendations", 10)
        self.min_confidence = self.config.get("min_confidence", 0.5)
        self._product_cache: Dict[str, Product] = {}

    def get_recommendations(
        self,
        context: str,
        customer_id: Optional[str] = None,
        product_ids: Optional[List[str]] = None,
        category_filter: Optional[str] = None
    ) -> RecommendationResult:
        """Get product recommendations based on context.

        Args:
            context: The inquiry context (e.g., ticket content)
            customer_id: Optional customer ID for personalization
            product_ids: Optional list of product IDs to find similar/complementary
            category_filter: Optional category to filter recommendations

        Returns:
            RecommendationResult with scored recommendations
        """
        import time
        start_time = time.time()

        recommendations: List[Recommendation] = []

        # Analyze context for product keywords
        keywords = self._extract_keywords(context)

        # Get product matches based on keywords
        matched_products = self._match_products(keywords, category_filter)

        # Score and rank products
        for product in matched_products:
            score = self._calculate_score(product, keywords, customer_id)
            if score >= self.min_confidence:
                rec_type = self._determine_recommendation_type(product, product_ids)
                reasoning = self._generate_reasoning(product, keywords, rec_type)

                recommendations.append(Recommendation(
                    product=product,
                    confidence_score=score,
                    recommendation_type=rec_type,
                    reasoning=reasoning,
                    cross_sell_potential=self._calculate_cross_sell_potential(product)
                ))

        # Sort by confidence score
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)

        # Limit results
        recommendations = recommendations[:self.max_recommendations]

        processing_time = (time.time() - start_time) * 1000

        logger.info(
            "Generated recommendations",
            extra={
                "client_id": self.client_id,
                "context_length": len(context),
                "recommendations_count": len(recommendations),
                "processing_time_ms": processing_time
            }
        )

        return RecommendationResult(
            recommendations=recommendations,
            context=context[:100] + "..." if len(context) > 100 else context,
            total_products_considered=len(matched_products),
            processing_time_ms=processing_time
        )

    def get_similar_products(self, product_id: str, limit: int = 5) -> List[Recommendation]:
        """Get products similar to the given product.

        Args:
            product_id: Product ID to find similar products for
            limit: Maximum number of recommendations

        Returns:
            List of similar product recommendations
        """
        product = self._get_product(product_id)
        if not product:
            return []

        similar = self._find_similar_products(product)
        recommendations = []

        for sim_product, similarity in similar[:limit]:
            recommendations.append(Recommendation(
                product=sim_product,
                confidence_score=similarity,
                recommendation_type="similar",
                reasoning=f"Similar to {product.name}",
                cross_sell_potential=self._calculate_cross_sell_potential(sim_product)
            ))

        return recommendations

    def get_personalized_recommendations(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Recommendation]:
        """Get personalized recommendations for a customer.

        Args:
            customer_id: Customer identifier
            limit: Maximum number of recommendations

        Returns:
            List of personalized recommendations
        """
        # Get customer purchase history and preferences
        preferences = self._get_customer_preferences(customer_id)

        recommendations = []
        for pref in preferences.get("preferred_categories", []):
            products = self._get_products_by_category(pref)
            for product in products[:3]:
                score = self._calculate_personalization_score(product, preferences)
                recommendations.append(Recommendation(
                    product=product,
                    confidence_score=score,
                    recommendation_type="personalized",
                    reasoning="Based on your purchase history",
                    cross_sell_potential=self._calculate_cross_sell_potential(product)
                ))

        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:limit]

    def _extract_keywords(self, context: str) -> List[str]:
        """Extract product-related keywords from context."""
        # Simple keyword extraction (in production, use NLP)
        keywords = []
        common_product_words = [
            "shirt", "pants", "shoes", "dress", "jacket", "hat",
            "phone", "laptop", "tablet", "headphones", "camera",
            "book", "toy", "game", "furniture", "kitchen"
        ]

        context_lower = context.lower()
        for word in common_product_words:
            if word in context_lower:
                keywords.append(word)

        return keywords

    def _match_products(
        self,
        keywords: List[str],
        category_filter: Optional[str] = None
    ) -> List[Product]:
        """Match products based on keywords."""
        # Mock product matching (in production, query Shopify/database)
        matched = []

        for keyword in keywords:
            # Generate mock products matching keyword
            product = Product(
                product_id=f"prod_{keyword}_001",
                name=f"Premium {keyword.title()}",
                sku=f"SKU-{keyword.upper()}-001",
                price=Decimal("49.99"),
                category=category_filter or "general",
                tags=[keyword],
                availability=True
            )
            matched.append(product)

        return matched

    def _calculate_score(
        self,
        product: Product,
        keywords: List[str],
        customer_id: Optional[str]
    ) -> float:
        """Calculate confidence score for a product recommendation."""
        base_score = 0.5

        # Keyword match boost
        keyword_matches = sum(1 for kw in keywords if kw in product.tags)
        keyword_boost = min(keyword_matches * 0.15, 0.3)

        # Availability boost
        availability_boost = 0.1 if product.availability else -0.3

        # Customer preference boost (if available)
        customer_boost = 0.0
        if customer_id:
            preferences = self._get_customer_preferences(customer_id)
            if product.category in preferences.get("preferred_categories", []):
                customer_boost = 0.15

        total_score = base_score + keyword_boost + availability_boost + customer_boost
        return min(max(total_score, 0.0), 1.0)

    def _determine_recommendation_type(
        self,
        product: Product,
        product_ids: Optional[List[str]]
    ) -> str:
        """Determine the type of recommendation."""
        if product_ids and product.product_id in product_ids:
            return "similar"
        return "trending"

    def _generate_reasoning(
        self,
        product: Product,
        keywords: List[str],
        rec_type: str
    ) -> str:
        """Generate human-readable reasoning for recommendation."""
        if rec_type == "similar":
            return f"Similar to products you've viewed"
        elif rec_type == "personalized":
            return "Based on your purchase history"
        elif rec_type == "trending":
            return f"Popular in {product.category}"
        else:
            return f"Matches your search for {', '.join(keywords) if keywords else 'products'}"

    def _calculate_cross_sell_potential(self, product: Product) -> float:
        """Calculate cross-sell potential score."""
        # Simple heuristic based on category
        high_cross_sell_categories = ["electronics", "clothing", "home"]
        if product.category.lower() in high_cross_sell_categories:
            return 0.8
        return 0.5

    def _get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID (with caching)."""
        if product_id in self._product_cache:
            return self._product_cache[product_id]

        # Mock product fetch
        product = Product(
            product_id=product_id,
            name=f"Product {product_id}",
            sku=f"SKU-{product_id}",
            price=Decimal("29.99"),
            category="general",
            tags=[],
            availability=True
        )
        self._product_cache[product_id] = product
        return product

    def _find_similar_products(self, product: Product) -> List[tuple]:
        """Find products similar to the given product."""
        # Mock similar products
        similar = []
        for i in range(5):
            sim = Product(
                product_id=f"{product.product_id}_sim_{i}",
                name=f"Similar to {product.name}",
                sku=f"SKU-SIM-{i}",
                price=product.price * Decimal("0.9"),
                category=product.category,
                tags=product.tags,
                availability=True
            )
            similarity = 0.9 - (i * 0.1)
            similar.append((sim, similarity))
        return similar

    def _get_customer_preferences(self, customer_id: str) -> Dict[str, Any]:
        """Get customer preferences for personalization."""
        # Mock preferences (no PII stored)
        return {
            "preferred_categories": ["electronics", "clothing"],
            "price_range": "mid",
            "brand_preferences": []
        }

    def _get_products_by_category(self, category: str) -> List[Product]:
        """Get products by category."""
        products = []
        for i in range(5):
            products.append(Product(
                product_id=f"prod_{category}_{i}",
                name=f"{category.title()} Product {i+1}",
                sku=f"SKU-{category[:3].upper()}-{i}",
                price=Decimal("39.99"),
                category=category,
                tags=[category],
                availability=True
            ))
        return products

    def _calculate_personalization_score(
        self,
        product: Product,
        preferences: Dict[str, Any]
    ) -> float:
        """Calculate personalization score."""
        score = 0.5
        if product.category in preferences.get("preferred_categories", []):
            score += 0.3
        return min(score, 1.0)
