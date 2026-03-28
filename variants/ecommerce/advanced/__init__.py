"""E-commerce Advanced Module.

This module provides advanced e-commerce features including:
- AI-powered product recommendations
- Cart abandonment recovery
- Dynamic pricing support
- Order tracking and proactive updates
- E-commerce analytics dashboard
"""

from variants.ecommerce.advanced.recommendation_engine import RecommendationEngine
from variants.ecommerce.advanced.product_matcher import ProductMatcher
from variants.ecommerce.advanced.behavior_analyzer import BehaviorAnalyzer
from variants.ecommerce.advanced.cross_sell import CrossSellEngine

__version__ = "1.0.0"
__all__ = [
    "RecommendationEngine",
    "ProductMatcher",
    "BehaviorAnalyzer",
    "CrossSellEngine",
]
