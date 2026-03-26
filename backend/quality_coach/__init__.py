"""
PARWA Quality Coach Module.

AI-powered quality analysis for customer support conversations.

Components:
- QualityAnalyzer: Analyze conversation quality using LLM
- QualityReporter: Generate quality reports
- QualityNotifier: Real-time quality alerts

CRITICAL: Scores accuracy/empathy/efficiency for each interaction.
"""
from backend.quality_coach.analyzer import QualityAnalyzer
from backend.quality_coach.reporter import QualityReporter
from backend.quality_coach.notifier import QualityNotifier


__all__ = [
    "QualityAnalyzer",
    "QualityReporter",
    "QualityNotifier",
]
