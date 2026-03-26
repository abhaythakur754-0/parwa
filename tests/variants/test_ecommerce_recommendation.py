"""Tests for E-commerce Recommendation Engine."""

import pytest
from decimal import Decimal

from variants.ecommerce.advanced import (
    RecommendationEngine,
    ProductMatcher,
    BehaviorAnalyzer,
    CrossSellEngine
)
from variants.ecommerce.advanced.recommendation_engine import Product, Recommendation
from variants.ecommerce.advanced.product_matcher import ProductMatch
from variants.ecommerce.advanced.behavior_analyzer import CustomerSegment, BehaviorAnalysis
from variants.ecommerce.advanced.cross_sell import CrossSellType, UpsellType


class TestRecommendationEngine:
    """Tests for RecommendationEngine."""

    def test_recommendation_engine_initializes(self):
        """Test RecommendationEngine initializes correctly."""
        engine = RecommendationEngine(client_id="test_client")
        assert engine.client_id == "test_client"
        assert engine.max_recommendations == 10
        assert engine.min_confidence == 0.5

    def test_recommendation_engine_custom_config(self):
        """Test RecommendationEngine with custom config."""
        engine = RecommendationEngine(
            client_id="test_client",
            config={"max_recommendations": 5, "min_confidence": 0.7}
        )
        assert engine.max_recommendations == 5
        assert engine.min_confidence == 0.7

    def test_get_recommendations_returns_result(self):
        """Test get_recommendations returns results."""
        engine = RecommendationEngine(client_id="test_client")
        result = engine.get_recommendations(
            context="I'm looking for headphones",
            customer_id="cust_001"
        )

        assert result is not None
        assert result.context is not None
        assert result.total_products_considered >= 0
        assert result.processing_time_ms >= 0

    def test_get_recommendations_with_product_ids(self):
        """Test get_recommendations with product IDs."""
        engine = RecommendationEngine(client_id="test_client")
        result = engine.get_recommendations(
            context="Looking for similar products",
            product_ids=["prod_001", "prod_002"]
        )

        assert result is not None

    def test_get_similar_products(self):
        """Test get_similar_products returns similar items."""
        engine = RecommendationEngine(client_id="test_client")
        similar = engine.get_similar_products("prod_headphones_001", limit=3)

        assert isinstance(similar, list)
        assert len(similar) <= 3

    def test_get_personalized_recommendations(self):
        """Test personalized recommendations."""
        engine = RecommendationEngine(client_id="test_client")
        recommendations = engine.get_personalized_recommendations(
            customer_id="cust_001",
            limit=5
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5

    def test_extract_keywords(self):
        """Test keyword extraction."""
        engine = RecommendationEngine(client_id="test_client")
        keywords = engine._extract_keywords("I need a new phone and laptop")

        assert "phone" in keywords
        assert "laptop" in keywords

    def test_calculate_score(self):
        """Test recommendation scoring."""
        engine = RecommendationEngine(client_id="test_client")
        product = Product(
            product_id="prod_001",
            name="Test Product",
            sku="SKU-001",
            price=Decimal("49.99"),
            category="electronics",
            tags=["phone"],
            availability=True
        )

        score = engine._calculate_score(
            product=product,
            keywords=["phone"],
            customer_id=None
        )

        assert 0.0 <= score <= 1.0


class TestProductMatcher:
    """Tests for ProductMatcher."""

    def test_product_matcher_initializes(self):
        """Test ProductMatcher initializes correctly."""
        matcher = ProductMatcher(client_id="test_client")
        assert matcher.client_id == "test_client"
        assert matcher.min_similarity == 0.6

    def test_match_by_name(self):
        """Test matching products by name."""
        matcher = ProductMatcher(client_id="test_client")
        matches = matcher.match_by_name("wireless headphones")

        assert isinstance(matches, list)
        for match in matches:
            assert isinstance(match, ProductMatch)
            assert match.similarity_score >= 0.6

    def test_match_by_name_with_category_filter(self):
        """Test matching with category filter."""
        matcher = ProductMatcher(client_id="test_client")
        matches = matcher.match_by_name(
            "headphones",
            category="electronics"
        )

        assert isinstance(matches, list)

    def test_match_by_sku_exact(self):
        """Test exact SKU matching."""
        matcher = ProductMatcher(client_id="test_client")
        matches = matcher.match_by_sku("SKU-HEAD-001", exact_match=True)

        assert isinstance(matches, list)

    def test_match_by_sku_partial(self):
        """Test partial SKU matching."""
        matcher = ProductMatcher(client_id="test_client")
        matches = matcher.match_by_sku("SKU-HEAD", exact_match=False)

        assert isinstance(matches, list)

    def test_detect_variants(self):
        """Test variant detection."""
        matcher = ProductMatcher(client_id="test_client")
        variants = matcher.detect_variants("prod_001")

        assert isinstance(variants, dict)

    def test_filter_by_price_range(self):
        """Test price range filtering."""
        matcher = ProductMatcher(client_id="test_client")
        products = [
            ProductMatch(
                product_id="1", name="A", sku="SKU1",
                price=Decimal("50"), similarity_score=0.8,
                match_type="fuzzy", availability=True
            ),
            ProductMatch(
                product_id="2", name="B", sku="SKU2",
                price=Decimal("150"), similarity_score=0.7,
                match_type="fuzzy", availability=True
            )
        ]

        filtered = matcher.filter_by_price_range(
            products,
            min_price=Decimal("40"),
            max_price=Decimal("100")
        )

        assert len(filtered) == 1
        assert filtered[0].product_id == "1"

    def test_filter_by_availability(self):
        """Test availability filtering."""
        matcher = ProductMatcher(client_id="test_client")
        products = [
            ProductMatch(
                product_id="1", name="A", sku="SKU1",
                price=Decimal("50"), similarity_score=0.8,
                match_type="fuzzy", availability=True
            ),
            ProductMatch(
                product_id="2", name="B", sku="SKU2",
                price=Decimal("150"), similarity_score=0.7,
                match_type="fuzzy", availability=False
            )
        ]

        filtered = matcher.filter_by_availability(products, available_only=True)

        assert len(filtered) == 1
        assert filtered[0].availability is True

    def test_search(self):
        """Test comprehensive search."""
        matcher = ProductMatcher(client_id="test_client")
        results = matcher.search(
            "headphones",
            filters={"category": "electronics", "available_only": True}
        )

        assert isinstance(results, list)


class TestBehaviorAnalyzer:
    """Tests for BehaviorAnalyzer."""

    def test_behavior_analyzer_initializes(self):
        """Test BehaviorAnalyzer initializes correctly."""
        analyzer = BehaviorAnalyzer(client_id="test_client")
        assert analyzer.client_id == "test_client"

    def test_analyze_customer(self):
        """Test customer analysis."""
        analyzer = BehaviorAnalyzer(client_id="test_client")
        analysis = analyzer.analyze_customer("cust_001")

        assert isinstance(analysis, BehaviorAnalysis)
        assert analysis.customer_id == "cust_001"
        assert isinstance(analysis.segment, CustomerSegment)
        assert isinstance(analysis.lifetime_value, Decimal)

    def test_identify_segment(self):
        """Test segment identification."""
        analyzer = BehaviorAnalyzer(client_id="test_client")
        segment = analyzer.identify_segment("cust_001")

        assert isinstance(segment, CustomerSegment)

    def test_calculate_ltv(self):
        """Test LTV calculation."""
        analyzer = BehaviorAnalyzer(client_id="test_client")
        ltv = analyzer.calculate_ltv("cust_001")

        assert isinstance(ltv, Decimal)
        assert ltv >= 0

    def test_get_purchase_history(self):
        """Test purchase history retrieval."""
        analyzer = BehaviorAnalyzer(client_id="test_client")
        history = analyzer.get_purchase_history("cust_001", limit=10)

        assert isinstance(history, list)
        assert len(history) <= 10

    def test_analyze_trends(self):
        """Test trend analysis."""
        analyzer = BehaviorAnalyzer(client_id="test_client")
        trends = analyzer.analyze_trends(["cust_001", "cust_002", "cust_003"])

        assert "total_customers" in trends
        assert "segment_distribution" in trends
        assert trends["total_customers"] == 3


class TestCrossSellEngine:
    """Tests for CrossSellEngine."""

    def test_cross_sell_engine_initializes(self):
        """Test CrossSellEngine initializes correctly."""
        engine = CrossSellEngine(client_id="test_client")
        assert engine.client_id == "test_client"
        assert engine.max_recommendations == 5

    def test_get_cross_sell_recommendations(self):
        """Test cross-sell recommendations."""
        engine = CrossSellEngine(client_id="test_client")
        recommendations = engine.get_cross_sell_recommendations(
            product_id="prod_001",
            product_category="electronics",
            customer_id="cust_001"
        )

        assert isinstance(recommendations, list)
        for rec in recommendations:
            assert rec.cross_sell_type in CrossSellType

    def test_identify_upsell_opportunities(self):
        """Test upsell opportunity identification."""
        engine = CrossSellEngine(client_id="test_client")
        opportunities = engine.identify_upsell_opportunities(
            product_id="prod_001",
            product_price=Decimal("100"),
            product_category="electronics"
        )

        assert isinstance(opportunities, list)
        for opp in opportunities:
            assert isinstance(opp.upsell_type, UpsellType)

    def test_generate_bundle_suggestions(self):
        """Test bundle suggestion generation."""
        engine = CrossSellEngine(client_id="test_client")
        cart = [
            {"id": "prod_001", "price": 100, "category": "electronics"},
            {"id": "prod_002", "price": 50, "category": "accessories"}
        ]

        suggestions = engine.generate_bundle_suggestions(cart)

        assert isinstance(suggestions, list)
        for s in suggestions:
            assert s.savings_percentage >= 0

    def test_get_ab_test_variant(self):
        """Test A/B test variant assignment."""
        engine = CrossSellEngine(client_id="test_client")
        variant = engine.get_ab_test_variant("cust_001", "test_recommendations")

        assert variant in ["control", "variant_a", "variant_b"]

    def test_ab_test_consistency(self):
        """Test A/B test variant is consistent."""
        engine = CrossSellEngine(client_id="test_client")

        variant1 = engine.get_ab_test_variant("cust_001", "test")
        variant2 = engine.get_ab_test_variant("cust_001", "test")

        assert variant1 == variant2

    def test_score_cross_sell_potential(self):
        """Test cross-sell potential scoring."""
        engine = CrossSellEngine(client_id="test_client")
        score = engine.score_cross_sell_potential("prod_001", "electronics")

        assert 0.0 <= score <= 1.0

    def test_high_cross_sell_categories(self):
        """Test high cross-sell categories score higher."""
        engine = CrossSellEngine(client_id="test_client")

        electronics_score = engine.score_cross_sell_potential("p1", "electronics")
        books_score = engine.score_cross_sell_potential("p2", "books")

        assert electronics_score > books_score


class TestModuleImports:
    """Test module imports correctly."""

    def test_import_recommendation_engine(self):
        """Test RecommendationEngine import."""
        from variants.ecommerce.advanced import RecommendationEngine
        assert RecommendationEngine is not None

    def test_import_product_matcher(self):
        """Test ProductMatcher import."""
        from variants.ecommerce.advanced import ProductMatcher
        assert ProductMatcher is not None

    def test_import_behavior_analyzer(self):
        """Test BehaviorAnalyzer import."""
        from variants.ecommerce.advanced import BehaviorAnalyzer
        assert BehaviorAnalyzer is not None

    def test_import_cross_sell_engine(self):
        """Test CrossSellEngine import."""
        from variants.ecommerce.advanced import CrossSellEngine
        assert CrossSellEngine is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
