"""PARWA Self-Improvement Engine — Learns from outcomes to automatically improve the pipeline.

The self-improvement engine is the mechanism that makes Month 3-4 improvements
happen automatically. It works in 4 stages:

  1. COLLECT: Every resolved/escalated ticket gets its outcome recorded
  2. ANALYZE: Patterns are identified in failed tickets
  3. ADJUST: Prompts, technique priorities, and KB boosting are auto-tuned
  4. VERIFY: Adjustments are validated against a holdout set before going live

This is NOT fine-tuning (which hurts CoT reasoning). This is prompt/technique
adjustment — we change the instructions, not the model weights.
"""

from parwa.self_improvement.feedback_collector import FeedbackCollector, TicketOutcome
from parwa.self_improvement.pattern_learner import PatternLearner, FailurePattern
from parwa.self_improvement.prompt_adjuster import PromptAdjuster, PromptAdjustment
from parwa.self_improvement.technique_tuner import TechniqueTuner, TechniqueAdjustment

__all__ = [
    "FeedbackCollector",
    "TicketOutcome",
    "PatternLearner",
    "FailurePattern",
    "PromptAdjuster",
    "PromptAdjustment",
    "TechniqueTuner",
    "TechniqueAdjustment",
]
