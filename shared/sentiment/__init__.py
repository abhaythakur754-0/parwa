"""
PARWA Sentiment Analysis Module.

Provides sentiment analysis and routing capabilities for customer interactions.
"""

from shared.sentiment.analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    SentimentAnalyzerConfig,
    SentimentType,
    SentimentIntensity,
)
from shared.sentiment.routing_rules import (
    SentimentRouter,
    RoutingDecision,
    SentimentRoutingConfig,
    RoutingPathway,
    RoutingThresholds,
    create_sentiment_router,
)

__all__ = [
    # Analyzer
    "SentimentAnalyzer",
    "SentimentResult",
    "SentimentAnalyzerConfig",
    "SentimentType",
    "SentimentIntensity",
    # Router
    "SentimentRouter",
    "RoutingDecision",
    "SentimentRoutingConfig",
    "RoutingPathway",
    "RoutingThresholds",
    "create_sentiment_router",
]
