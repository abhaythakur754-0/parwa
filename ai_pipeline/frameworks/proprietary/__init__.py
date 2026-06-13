"""PARWA Proprietary AI techniques.

These 8 techniques are PARWA-specific — not found in any framework.
They're the secret sauce that makes PARWA smarter than generic AI.

1. GSD (Global State Decompression) — State compression (12,000→180 tokens)
2. Smart Router — Model selection based on node + complexity + variant
3. MAKER (Multi-Agent Knowledge Extraction & Reasoning) — Cross-agent knowledge synthesis
4. AdaptiveBudget — Dynamic token budget reallocation across nodes
5. TurboCompress — Prompt compression for token savings
6. FederatedReasoning — Combines conclusions from multiple reasoning paths
7. ZeroShotValidator — Validates outputs without training examples
8. MetaLearner — Learns optimal technique combinations from interaction patterns
"""

from parwa.frameworks.proprietary.gsd import GSDTechnique
from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
from parwa.frameworks.proprietary.maker import MAKERTechnique
from parwa.frameworks.proprietary.adaptive_budget import AdaptiveBudgetTechnique
from parwa.frameworks.proprietary.turbo_compress import TurboCompressTechnique
from parwa.frameworks.proprietary.federated_reasoning import FederatedReasoningTechnique
from parwa.frameworks.proprietary.zero_shot_validator import ZeroShotValidatorTechnique
from parwa.frameworks.proprietary.meta_learner import MetaLearnerTechnique

__all__ = [
    "GSDTechnique",
    "SmartRouterTechnique",
    "MAKERTechnique",
    "AdaptiveBudgetTechnique",
    "TurboCompressTechnique",
    "FederatedReasoningTechnique",
    "ZeroShotValidatorTechnique",
    "MetaLearnerTechnique",
]
