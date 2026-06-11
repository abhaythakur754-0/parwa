"""PARWA AI Frameworks — 25 techniques that make nodes intelligent.

Architecture Decision: NO new nodes. All 25 techniques go INSIDE existing
nodes via FrameworkBrain. Same 22 nodes, same 6 agents, same graph —
just smarter inside.

Categories:
  - reasoning/   — CoT, ReAct, ToT, Reverse, UoT, GST (Phase 2)
  - rag/         — CLARA, HyDE, Multi-Query, Step-Back (Phase 3)
  - quality/     — Reflexion, Self-Consistency, CRP, Least-to-Most (Phase 3)
  - memory/      — ThoT, Dynamic Context, Contextual Compression (Phase 4)
  - proprietary/ — GSD, Smart Router, MAKER (Phase 5)
"""

from parwa.frameworks.base import BaseTechnique, TechniqueResult
from parwa.frameworks.brain import FrameworkBrain
from parwa.frameworks.registry import TechniqueRegistry, get_registry

__all__ = [
    "BaseTechnique",
    "TechniqueResult",
    "FrameworkBrain",
    "TechniqueRegistry",
    "get_registry",
]
