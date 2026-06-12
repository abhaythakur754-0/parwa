"""Technique registry — registers all 25 AI techniques with metadata.

The registry is the single source of truth for which techniques exist,
which nodes they apply to, and their metadata. FrameworkBrain queries
the registry to find available techniques for a given node.

Phase 2 registers 6 reasoning techniques. Phase 3 registers 8 RAG + Quality
techniques. Phase 4 registers 3 Memory techniques. Phase 5 registers 8
Proprietary techniques. Total: 25 techniques.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory

logger = logging.getLogger("parwa.frameworks.registry")


class TechniqueRegistry:
    """Registry of all available AI techniques.

    Techniques register themselves with metadata. FrameworkBrain queries
    the registry by node name to find applicable techniques.

    Usage:
        registry = get_registry()
        techniques = registry.get_techniques_for_node("REASONING_ENGINE")
        # Returns [ChainOfThoughtTechnique, ReactTechnique, UncertaintyOfThoughtTechnique]
    """

    def __init__(self) -> None:
        self._techniques: dict[str, BaseTechnique] = {}

    def register(self, technique: BaseTechnique) -> None:
        """Register a technique.

        Args:
            technique: The technique instance to register.

        Raises:
            ValueError: If a technique with the same name is already registered.
        """
        if technique.name in self._techniques:
            raise ValueError(
                f"Technique '{technique.name}' already registered. "
                f"Existing: {self._techniques[technique.name]}, "
                f"New: {technique}"
            )
        self._techniques[technique.name] = technique
        logger.debug("registry: registered technique %s", technique.name)

    def get(self, name: str) -> BaseTechnique | None:
        """Get a technique by name. Returns None if not found."""
        return self._techniques.get(name)

    def get_techniques_for_node(self, node_name: str) -> list[BaseTechnique]:
        """Get all techniques applicable to a given node.

        Args:
            node_name: The node name (e.g. 'REASONING_ENGINE').

        Returns:
            List of techniques that list this node in their applicable_nodes.
        """
        return [
            t for t in self._techniques.values()
            if node_name in t.applicable_nodes
        ]

    def get_techniques_by_category(self, category: TechniqueCategory) -> list[BaseTechnique]:
        """Get all techniques in a given category."""
        return [
            t for t in self._techniques.values()
            if t.category == category
        ]

    def get_technique_names(self) -> list[str]:
        """Get all registered technique names."""
        return list(self._techniques.keys())

    def get_technique_names_for_node(self, node_name: str) -> list[str]:
        """Get technique names applicable to a node."""
        return [t.name for t in self.get_techniques_for_node(node_name)]

    def all_techniques(self) -> list[BaseTechnique]:
        """Get all registered techniques."""
        return list(self._techniques.values())

    def count(self) -> int:
        """Number of registered techniques."""
        return len(self._techniques)

    def summary(self) -> dict[str, Any]:
        """Get a summary of registered techniques for debugging."""
        by_category: dict[str, list[str]] = {}
        for t in self._techniques.values():
            cat = t.category.value
            by_category.setdefault(cat, []).append(t.name)

        by_node: dict[str, list[str]] = {}
        for t in self._techniques.values():
            for node in t.applicable_nodes:
                by_node.setdefault(node, []).append(t.name)

        return {
            "total_techniques": len(self._techniques),
            "by_category": by_category,
            "by_node": by_node,
        }


# ─── Singleton Registry ──────────────────────────────────────────────────────

_registry: TechniqueRegistry | None = None


def get_registry() -> TechniqueRegistry:
    """Get or create the singleton technique registry.

    On first call, creates the registry and registers all available techniques.
    Subsequent calls return the same instance.
    """
    global _registry
    if _registry is not None:
        return _registry

    _registry = TechniqueRegistry()

    # ─── Register Phase 2: Reasoning techniques ─────────────────────────────
    from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
    from parwa.frameworks.reasoning.react import ReactTechnique
    from parwa.frameworks.reasoning.tot import TreeOfThoughtsTechnique
    from parwa.frameworks.reasoning.reverse import ReverseThinkingTechnique
    from parwa.frameworks.reasoning.uot import UncertaintyOfThoughtTechnique
    from parwa.frameworks.reasoning.gst import GraphOfStrategicThoughtTechnique

    _registry.register(ChainOfThoughtTechnique())
    _registry.register(ReactTechnique())
    _registry.register(TreeOfThoughtsTechnique())
    _registry.register(ReverseThinkingTechnique())
    _registry.register(UncertaintyOfThoughtTechnique())
    _registry.register(GraphOfStrategicThoughtTechnique())

    # ─── Register Phase 3: RAG techniques ──────────────────────────────────
    from parwa.frameworks.rag.clara import ClaraTechnique
    from parwa.frameworks.rag.hyde import HyDETechnique
    from parwa.frameworks.rag.multi_query import MultiQueryTechnique
    from parwa.frameworks.rag.step_back import StepBackTechnique

    _registry.register(ClaraTechnique())
    _registry.register(HyDETechnique())
    _registry.register(MultiQueryTechnique())
    _registry.register(StepBackTechnique())

    # ─── Register Phase 3: Quality techniques ──────────────────────────────
    from parwa.frameworks.quality.reflexion import ReflexionTechnique
    from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
    from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
    from parwa.frameworks.quality.least_to_most import LeastToMostTechnique

    _registry.register(ReflexionTechnique())
    _registry.register(SelfConsistencyTechnique())
    _registry.register(ConstrainedResponseTechnique())
    _registry.register(LeastToMostTechnique())

    # ─── Register Phase 4: Memory techniques ──────────────────────────────
    from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
    from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
    from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique

    _registry.register(ThreadOfThoughtTechnique())
    _registry.register(DynamicContextTechnique())
    _registry.register(ContextualCompressionTechnique())

    # ─── Register Phase 5: Proprietary techniques ─────────────────────────
    from parwa.frameworks.proprietary.gsd import GSDTechnique
    from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
    from parwa.frameworks.proprietary.maker import MAKERTechnique
    from parwa.frameworks.proprietary.adaptive_budget import AdaptiveBudgetTechnique
    from parwa.frameworks.proprietary.turbo_compress import TurboCompressTechnique
    from parwa.frameworks.proprietary.federated_reasoning import FederatedReasoningTechnique
    from parwa.frameworks.proprietary.zero_shot_validator import ZeroShotValidatorTechnique
    from parwa.frameworks.proprietary.meta_learner import MetaLearnerTechnique

    _registry.register(GSDTechnique())
    _registry.register(SmartRouterTechnique())
    _registry.register(MAKERTechnique())
    _registry.register(AdaptiveBudgetTechnique())
    _registry.register(TurboCompressTechnique())
    _registry.register(FederatedReasoningTechnique())
    _registry.register(ZeroShotValidatorTechnique())
    _registry.register(MetaLearnerTechnique())

    logger.info(
        "registry: initialized with %d techniques: %s",
        _registry.count(),
        _registry.get_technique_names(),
    )

    return _registry


def reset_registry() -> None:
    """Reset the singleton registry. Used for testing."""
    global _registry
    _registry = None
