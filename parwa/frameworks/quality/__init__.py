"""Quality techniques for PARWA.

Phase 3 implements 4 quality techniques:
  - Reflexion: Self-reflective improvement after generating output
  - Self-Consistency: Majority vote across multiple answers
  - CRP: Constrained Response Generation (70% token reduction)
  - Least-to-Most: Decompose complex problems into sub-problems
"""

from parwa.frameworks.quality.reflexion import ReflexionTechnique
from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
from parwa.frameworks.quality.least_to_most import LeastToMostTechnique

__all__ = [
    "ReflexionTechnique",
    "SelfConsistencyTechnique",
    "ConstrainedResponseTechnique",
    "LeastToMostTechnique",
]
