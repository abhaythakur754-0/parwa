"""Proprietary techniques — Phase 5: PARWA-specific AI techniques.

These 3 techniques are PARWA's proprietary IP — they don't exist in
academic literature as standalone methods. They're built specifically
for the PARWA customer support pipeline:

  - GSD: Get Stuff Done — aggressive state compression + focus technique
  - Smart Router: Technique selection optimizer inside FrameworkBrain
  - MAKER: Multi-step task decomposition with verification at each step
"""

from parwa.frameworks.proprietary.gsd import GSDTechnique
from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
from parwa.frameworks.proprietary.maker import MAKERTechnique

__all__ = [
    "GSDTechnique",
    "SmartRouterTechnique",
    "MAKERTechnique",
]
