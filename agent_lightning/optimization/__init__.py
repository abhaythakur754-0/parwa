"""
Optimization Module for Agent Lightning 94% Accuracy.

Provides optimization components for accuracy improvement.
"""

from agent_lightning.optimization.industry_tuner import (
    IndustryTuner,
    TuningResult,
    tune_for_industry,
)
from agent_lightning.optimization.query_enhancer import (
    QueryEnhancer,
    EnhancementResult,
    enhance_query,
)
from agent_lightning.optimization.context_integrator import (
    ContextIntegrator,
    ContextFeatures,
)
from agent_lightning.optimization.ensemble_voter import (
    EnsembleVoter,
    VotingResult,
)

__all__ = [
    "IndustryTuner",
    "TuningResult",
    "tune_for_industry",
    "QueryEnhancer",
    "EnhancementResult",
    "enhance_query",
    "ContextIntegrator",
    "ContextFeatures",
    "EnsembleVoter",
    "VotingResult",
]
