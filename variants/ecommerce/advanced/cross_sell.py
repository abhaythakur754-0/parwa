"""Cross-Sell and Upsell Engine.

Provides cross-sell and upsell capabilities:
- Complementary product identification
- Bundle recommendation logic
- Upsell opportunity detection
- Price optimization for bundles
- Conversion probability scoring
- A/B test support
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from enum import Enum
import logging
import random

logger = logging.getLogger(__name__)


class UpsellType(str, Enum):
    """Type of upsell opportunity."""
    PREMIUM = "premium"
    BUNDLE = "bundle"
    QUANTITY = "quantity"
    ACCESSORY = "accessory"


class CrossSellType(str, Enum):
    """Type of cross-sell recommendation."""
    COMPLEMENTARY = "complementary"
    FREQUENTLY_BOUGHT_TOGETHER = "frequently_bought_together"
    SIMILAR_PRICE_POINT = "similar_price_point"
    CATEGORY_BASED = "category_based"


@dataclass
class CrossSellRecommendation:
    """Cross-sell recommendation."""
    product_id: str
    product_name: str
    price: Decimal
    cross_sell_type: CrossSellType
    confidence: float
    reasoning: str
    estimated_conversion_rate: float


@dataclass
class UpsellOpportunity:
    """Upsell opportunity."""
    current_product_id: str
    upsell_product_id: str
    upsell_product_name: str
    price_difference: Decimal
    upsell_type: UpsellType
    value_score: float  # Customer value increase
    conversion_probability: float


@dataclass
class BundleSuggestion:
    """Bundle suggestion."""
    bundle_name: str
    product_ids: List[str]
    original_total: Decimal
    bundle_price: Decimal
    savings_amount: Decimal
    savings_percentage: float
    conversion_lift: float


class CrossSellEngine:
    """Cross-sell and upsell recommendation engine."""

    # Category compatibility matrix (what goes well together)
    CATEGORY_SYNERGIES = {
        "electronics": ["accessories", "software", "protection_plans"],
        "clothing": ["shoes", "accessories", "jewelry"],
        "home": ["kitchen", "decor", "outdoor"],
        "sports": ["apparel", "equipment", "nutrition"],
        "beauty": ["skincare", "makeup", "tools"],
    }

    # Frequently bought together patterns
    BUNDLE_PATTERNS = [
        {
            "primary_category": "electronics",
            "bundle_categories": ["accessories"],
            "bundle_name": "Complete Setup Bundle",
            "discount": 0.10
        },
        {
            "primary_category": "clothing",
            "bundle_categories": ["shoes", "accessories"],
            "bundle_name": "Outfit Complete Bundle",
            "discount": 0.15
        },
    ]

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize cross-sell engine.

        Args:
            client_id: Client identifier for tenant isolation
            config: Optional configuration overrides
        """
        self.client_id = client_id
        self.config = config or {}
        self.max_recommendations = self.config.get("max_recommendations", 5)
        self.min_confidence = self.config.get("min_confidence", 0.3)
        self.max_bundle_discount = self.config.get("max_bundle_discount", 0.25)
        self._ab_test_variants: Dict[str, str] = {}

    def get_cross_sell_recommendations(
        self,
        product_id: str,
        product_category: str,
        customer_id: Optional[str] = None,
        limit: int = 5
    ) -> List[CrossSellRecommendation]:
        """Get cross-sell recommendations for a product.

        Args:
            product_id: Product to find cross-sells for
            product_category: Category of the product
            customer_id: Optional customer for personalization
            limit: Maximum recommendations

        Returns:
            List of cross-sell recommendations
        """
        recommendations = []

        # Get complementary categories
        complementary_categories = self._get_complementary_categories(product_category)

        for cat in complementary_categories:
            products = self._get_products_by_category(cat)

            for product in products[:2]:
                confidence = self._calculate_cross_sell_confidence(
                    product_category, cat
                )

                if confidence >= self.min_confidence:
                    recommendations.append(CrossSellRecommendation(
                        product_id=product["id"],
                        product_name=product["name"],
                        price=Decimal(str(product["price"])),
                        cross_sell_type=CrossSellType.COMPLEMENTARY,
                        confidence=confidence,
                        reasoning=f"Customers often buy {cat} products with {product_category}",
                        estimated_conversion_rate=confidence * 0.3
                    ))

        # Sort by confidence
        recommendations.sort(key=lambda x: x.confidence, reverse=True)

        logger.info(
            "Generated cross-sell recommendations",
            extra={
                "client_id": self.client_id,
                "product_id": product_id,
                "recommendations_count": len(recommendations)
            }
        )

        return recommendations[:limit]

    def identify_upsell_opportunities(
        self,
        product_id: str,
        product_price: Decimal,
        product_category: str,
        customer_id: Optional[str] = None
    ) -> List[UpsellOpportunity]:
        """Identify upsell opportunities.

        Args:
            product_id: Current product ID
            product_price: Current product price
            product_category: Product category
            customer_id: Optional customer for personalization

        Returns:
            List of upsell opportunities
        """
        opportunities = []

        # Find premium alternatives
        premium_products = self._find_premium_alternatives(
            product_category, product_price
        )

        for premium in premium_products:
            price_diff = Decimal(str(premium["price"])) - product_price

            # Only suggest if price increase is reasonable (max 50% more)
            if price_diff <= product_price * Decimal("0.5"):
                opportunities.append(UpsellOpportunity(
                    current_product_id=product_id,
                    upsell_product_id=premium["id"],
                    upsell_product_name=premium["name"],
                    price_difference=price_diff,
                    upsell_type=UpsellType.PREMIUM,
                    value_score=self._calculate_value_score(product_price, premium["price"]),
                    conversion_probability=self._estimate_upsell_conversion(
                        price_diff, product_price
                    )
                ))

        # Find accessories/add-ons
        accessories = self._find_accessories(product_category)
        for accessory in accessories[:2]:
            opportunities.append(UpsellOpportunity(
                current_product_id=product_id,
                upsell_product_id=accessory["id"],
                upsell_product_name=accessory["name"],
                price_difference=Decimal(str(accessory["price"])),
                upsell_type=UpsellType.ACCESSORY,
                value_score=Decimal(str(accessory["price"])),
                conversion_probability=0.4
            ))

        # Sort by value score * conversion probability
        opportunities.sort(
            key=lambda x: float(x.value_score) * x.conversion_probability,
            reverse=True
        )

        return opportunities[:self.max_recommendations]

    def generate_bundle_suggestions(
        self,
        cart_products: List[Dict[str, Any]],
        customer_id: Optional[str] = None
    ) -> List[BundleSuggestion]:
        """Generate bundle suggestions for cart.

        Args:
            cart_products: List of products in cart
            customer_id: Optional customer for personalization

        Returns:
            List of bundle suggestions
        """
        suggestions = []

        # Group products by category
        categories = {}
        for product in cart_products:
            cat = product.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(product)

        # Check bundle patterns
        for pattern in self.BUNDLE_PATTERNS:
            primary_cat = pattern["primary_category"]
            if primary_cat in categories:
                bundle_products = list(cart_products)
                original_total = sum(
                    Decimal(str(p["price"])) for p in bundle_products
                )

                # Add complementary products
                for bundle_cat in pattern["bundle_categories"]:
                    add_ons = self._get_products_by_category(bundle_cat)
                    if add_ons:
                        bundle_products.append(add_ons[0])

                # Calculate bundle price with discount
                discount = Decimal(str(pattern["discount"]))
                new_total = sum(
                    Decimal(str(p["price"])) for p in bundle_products
                )
                bundle_price = new_total * (Decimal("1") - discount)

                savings = new_total - bundle_price
                savings_pct = float(savings / new_total) * 100

                # Limit discount
                if discount <= Decimal(str(self.max_bundle_discount)):
                    suggestions.append(BundleSuggestion(
                        bundle_name=pattern["bundle_name"],
                        product_ids=[p["id"] for p in bundle_products],
                        original_total=new_total,
                        bundle_price=bundle_price,
                        savings_amount=savings,
                        savings_percentage=savings_pct,
                        conversion_lift=0.15 + (savings_pct * 0.01)
                    ))

        # Sort by conversion lift
        suggestions.sort(key=lambda x: x.conversion_lift, reverse=True)

        return suggestions[:3]

    def get_ab_test_variant(
        self,
        customer_id: str,
        test_name: str
    ) -> str:
        """Get A/B test variant for customer.

        Args:
            customer_id: Customer identifier
            test_name: Name of the A/B test

        Returns:
            Variant identifier (e.g., 'control', 'variant_a', 'variant_b')
        """
        key = f"{customer_id}:{test_name}"
        if key in self._ab_test_variants:
            return self._ab_test_variants[key]

        # Deterministic assignment based on customer ID
        variants = ["control", "variant_a", "variant_b"]
        variant = variants[hash(customer_id) % len(variants)]

        self._ab_test_variants[key] = variant
        return variant

    def score_cross_sell_potential(
        self,
        product_id: str,
        product_category: str
    ) -> float:
        """Score cross-sell potential for a product.

        Args:
            product_id: Product identifier
            product_category: Product category

        Returns:
            Cross-sell potential score (0-1)
        """
        # High cross-sell categories
        high_potential = ["electronics", "clothing", "home"]
        medium_potential = ["sports", "beauty", "toys"]
        low_potential = ["books", "groceries"]

        category_lower = product_category.lower()

        if category_lower in high_potential:
            base_score = 0.8
        elif category_lower in medium_potential:
            base_score = 0.5
        else:
            base_score = 0.3

        # Adjust based on synergies
        synergies = len(self._get_complementary_categories(product_category))
        synergy_boost = min(synergies * 0.05, 0.2)

        return min(base_score + synergy_boost, 1.0)

    def _get_complementary_categories(self, category: str) -> List[str]:
        """Get categories that complement the given category."""
        return self.CATEGORY_SYNERGIES.get(category.lower(), [])

    def _get_products_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get products by category (mock)."""
        return [
            {
                "id": f"{category}_prod_001",
                "name": f"Premium {category.title()} Item",
                "price": 59.99,
                "category": category
            },
            {
                "id": f"{category}_prod_002",
                "name": f"Standard {category.title()} Item",
                "price": 39.99,
                "category": category
            }
        ]

    def _calculate_cross_sell_confidence(
        self,
        primary_category: str,
        cross_sell_category: str
    ) -> float:
        """Calculate confidence for cross-sell."""
        # Base confidence
        base = 0.4

        # Boost if in synergies
        synergies = self.CATEGORY_SYNERGIES.get(primary_category.lower(), [])
        if cross_sell_category.lower() in synergies:
            base += 0.3

        return min(base, 0.9)

    def _find_premium_alternatives(
        self,
        category: str,
        current_price: Decimal
    ) -> List[Dict[str, Any]]:
        """Find premium alternatives in same category."""
        products = self._get_products_by_category(category)
        premium = []

        for p in products:
            if Decimal(str(p["price"])) > current_price:
                premium.append(p)

        return premium

    def _find_accessories(self, category: str) -> List[Dict[str, Any]]:
        """Find accessories for category."""
        complementary = self._get_complementary_categories(category)
        accessories = []

        for cat in complementary:
            accessories.extend(self._get_products_by_category(cat))

        return accessories

    def _calculate_value_score(
        self,
        current_price: Decimal,
        upsell_price: float
    ) -> Decimal:
        """Calculate value score for upsell."""
        # Higher price difference = higher value for business
        diff = Decimal(str(upsell_price)) - current_price
        return diff

    def _estimate_upsell_conversion(
        self,
        price_diff: Decimal,
        base_price: Decimal
    ) -> float:
        """Estimate conversion probability for upsell."""
        # Conversion decreases as price gap increases
        ratio = float(price_diff / base_price) if base_price > 0 else 0

        if ratio < 0.1:  # < 10% price increase
            return 0.4
        elif ratio < 0.25:  # < 25% price increase
            return 0.25
        elif ratio < 0.5:  # < 50% price increase
            return 0.15
        else:
            return 0.05
