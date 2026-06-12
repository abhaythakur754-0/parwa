"""Reasoning techniques — Phase 2 implementations.

These 6 techniques are wired into the 4 Reasoning Agent nodes:
  - Node 6  (REASONING_ENGINE) — CoT, ReAct, UoT
  - Node 10 (REVERSE_THINKER)  — Reverse Thinking
  - Node 12 (TREE_OF_THOUGHTS) — ToT
  - Node 11 (STRATEGY_PLANNER) — GST
"""

from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
from parwa.frameworks.reasoning.react import ReactTechnique
from parwa.frameworks.reasoning.tot import TreeOfThoughtsTechnique
from parwa.frameworks.reasoning.reverse import ReverseThinkingTechnique
from parwa.frameworks.reasoning.uot import UncertaintyOfThoughtTechnique
from parwa.frameworks.reasoning.gst import GraphOfStrategicThoughtTechnique

__all__ = [
    "ChainOfThoughtTechnique",
    "ReactTechnique",
    "TreeOfThoughtsTechnique",
    "ReverseThinkingTechnique",
    "UncertaintyOfThoughtTechnique",
    "GraphOfStrategicThoughtTechnique",
]
