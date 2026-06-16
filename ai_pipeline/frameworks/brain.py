"""FrameworkBrain — Decision engine that selects and runs AI techniques.

The FrameworkBrain is the core of Phase 2. It sits inside each node and:
  1. Looks at the ticket complexity and node name
  2. Selects which technique(s) to activate
  3. Runs the selected techniques (one at a time, in order)
  4. Combines results into a single TechniqueResult
  5. Tracks which frameworks were activated in state

Usage inside a node:
    brain = FrameworkBrain(node="REASONING_ENGINE", state=state)
    result = await brain.think(
        prompt="Reason about this ticket",
        techniques=["cot", "react", "uot"],  # candidates, not all will activate
    )
    # result.chain, result.output, result.frameworks_used, etc.

Complexity-based activation:
    Simple   → CoT only
    Medium   → CoT + ReAct
    Complex  → CoT + ReAct + ToT + Reverse + GST
    Critical → All techniques + UoT (uncertainty triggers deeper analysis)

Selection strategy (v2 — priority-based, not hard cap):
    Techniques are sorted by relevance to the current complexity level,
    not by registration order. The technique whose min_complexity most
    closely matches the ticket complexity runs first. This ensures:
    - UoT actually fires on critical tickets (was dead before)
    - ToT/GST fire on complex tickets (were cut before)
    - CoT always runs as baseline (unchanged)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import TechniqueResult
from parwa.frameworks.registry import get_registry

logger = logging.getLogger("parwa.frameworks.brain")

# Complexity ordering for priority-based selection
_COMPLEXITY_ORDER = {"simple": 0, "medium": 1, "complex": 2, "critical": 3}

# Maximum techniques per node — now a SOFT cap that respects priority.
# On critical tickets, all applicable techniques can run (up to 4).
# On simpler tickets, fewer techniques are needed.
_MAX_TECHNIQUES_BY_COMPLEXITY = {
    "simple": 3,     # Was 1 — even simple tickets deserve CoT + 1 verification + 1 specialized
    "medium": 4,     # Was 2 — medium needs CoT + primary + verification + fallback
    "complex": 5,    # Was 3 — complex needs full technique stack
    "critical": 6,   # Was 4 — critical gets everything applicable
}


class FrameworkBrain:
    """Decision engine that selects and runs AI techniques inside a node.

    The brain does NOT replace the node. It makes the node smarter by
    selecting the right technique(s) based on ticket complexity and
    running them with the production-hardened LLM client.

    Args:
        node: The node name (e.g. "REASONING_ENGINE").
        state: The current ticket state dict.
    """

    def __init__(self, node: str, state: dict[str, Any]) -> None:
        self.node = node
        self.state = state
        self._registry = get_registry()

    @staticmethod
    def _technique_priority(technique: Any, complexity: str) -> float:
        """Score a technique's relevance to the current complexity.

        Higher score = higher priority for activation.
        Strategy:
          - Techniques whose min_complexity exactly matches get highest priority
          - Techniques that are "close" to the complexity level get medium priority
          - CoT (min_complexity="simple") always runs as baseline but with lower
            priority than specialized techniques for higher complexities
        """
        min_c = getattr(technique, '_min_complexity', 'simple')
        min_level = _COMPLEXITY_ORDER.get(min_c, 0)
        ticket_level = _COMPLEXITY_ORDER.get(complexity, 0)

        # Exact match → highest priority
        if min_level == ticket_level:
            return 100.0

        # For the current complexity, prefer techniques that are "designed for it"
        # Techniques with min_complexity <= ticket_level are eligible
        # Those closer to the ticket level get higher priority
        if min_level <= ticket_level:
            # Distance from the ticket complexity — closer is better
            distance = ticket_level - min_level
            return 50.0 - (distance * 10.0)  # 50, 40, 30, 20

        # min_complexity is ABOVE ticket level — should not activate
        return -1.0

    async def think(
        self,
        prompt: str,
        techniques: list[str] | None = None,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Select and run techniques based on ticket complexity.

        v2: Priority-based selection instead of hard cap.
        Techniques are sorted by relevance to the current complexity,
        ensuring the RIGHT techniques activate for each ticket level.

        Args:
            prompt: The reasoning prompt for the technique.
            techniques: Optional list of candidate technique names.
                       If None, uses all techniques applicable to this node.
            ticket_id: Current ticket ID for tracking.
            variant: Current variant for budget allocation.

        Returns:
            Combined TechniqueResult from all activated techniques.
        """
        complexity = self.state.get("complexity", "simple")
        candidate_names = techniques or self._registry.get_technique_names_for_node(self.node)

        # Filter candidates: only activate techniques that match complexity
        activated = []
        for name in candidate_names:
            technique = self._registry.get(name)
            if technique is None:
                logger.warning("brain: technique '%s' not found in registry, skipping", name)
                continue
            if technique.can_apply(self.node, complexity):
                activated.append(technique)

        # v2: Sort by priority — techniques designed for this complexity run FIRST
        activated.sort(
            key=lambda t: self._technique_priority(t, complexity),
            reverse=True,
        )

        # v2: Dynamic cap based on complexity — not a hard 2
        max_techniques = _MAX_TECHNIQUES_BY_COMPLEXITY.get(complexity, 2)
        if len(activated) > max_techniques:
            logger.debug(
                "brain: priority-selecting %d/%d techniques for node=%s complexity=%s (candidates: %s → selected: %s)",
                max_techniques, len(activated), self.node, complexity,
                [t.name for t in activated],
                [t.name for t in activated[:max_techniques]],
            )
            activated = activated[:max_techniques]

        if not activated:
            logger.debug("brain: no techniques activated for node=%s complexity=%s", self.node, complexity)
            return TechniqueResult(
                output="",
                chain=[],
                confidence=0.0,
                frameworks_used=[],
                metadata={"activated_count": 0, "complexity": complexity},
            )

        logger.info(
            "brain: activated %d technique(s) for node=%s complexity=%s → %s",
            len(activated), self.node, complexity,
            [t.name for t in activated],
        )

        # Run techniques in priority order, combining results
        combined_chain: list[str] = []
        combined_output = ""
        combined_frameworks: list[str] = []
        combined_metadata: dict[str, Any] = {
            "activated_count": len(activated),
            "complexity": complexity,
            "node": self.node,
            "technique_results": {},
        }
        total_tokens = 0
        best_confidence = 0.0
        last_error: str | None = None

        for i, technique in enumerate(activated):
            try:
                # Rate limit: add small delay between technique calls to avoid 429s
                if i > 0:
                    import asyncio
                    await asyncio.sleep(0.3)

                result = await technique.think(
                    prompt,
                    self.state,
                    ticket_id=ticket_id,
                    variant=variant,
                )

                # Merge results
                if result.chain:
                    combined_chain.extend(result.chain)
                if result.output:
                    # Use highest-confidence technique's output as primary.
                    # Previous "last wins" approach caused CoT conclusions
                    # to be overwritten by lower-priority technique outputs.
                    # Strict ">" ensures higher-priority techniques keep the
                    # output when confidence ties (they run first due to sort).
                    if result.confidence > best_confidence or not combined_output:
                        combined_output = result.output
                if result.frameworks_used:
                    combined_frameworks.extend(result.frameworks_used)
                if result.confidence > best_confidence:
                    best_confidence = result.confidence
                total_tokens += result.token_estimate

                combined_metadata["technique_results"][technique.name] = {
                    "output_length": len(result.output),
                    "chain_length": len(result.chain),
                    "confidence": result.confidence,
                    "token_estimate": result.token_estimate,
                    "error": result.error,
                    # Forward the technique's own metadata so consumers
                    # (e.g. kb_retriever) can extract enhanced queries,
                    # hypothetical documents, broader concepts, etc.
                    "metadata": result.metadata if result.metadata else {},
                }

                logger.debug(
                    "brain: technique=%s node=%s chain=%d confidence=%.2f tokens=%d",
                    technique.name, self.node, len(result.chain),
                    result.confidence, result.token_estimate,
                )

            except Exception as exc:
                logger.warning(
                    "brain: technique=%s FAILED on node=%s: %s",
                    technique.name, self.node, exc,
                )
                last_error = str(exc)
                combined_metadata["technique_results"][technique.name] = {
                    "error": str(exc),
                    "failed": True,
                }
                # Don't crash — continue with other techniques

        return TechniqueResult(
            output=combined_output,
            chain=combined_chain,
            confidence=best_confidence,
            frameworks_used=list(dict.fromkeys(combined_frameworks)),  # dedupe, preserve order
            metadata=combined_metadata,
            token_estimate=total_tokens,
            error=last_error,
        )

    async def think_single(
        self,
        technique_name: str,
        prompt: str,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Run a single specific technique by name.

        Useful when a node knows exactly which technique it needs
        (e.g. reverse_thinker always uses Reverse Thinking).

        Args:
            technique_name: The technique to run.
            prompt: The reasoning prompt.
            ticket_id: Current ticket ID.
            variant: Current variant.

        Returns:
            TechniqueResult from the single technique.

        Raises:
            ValueError: If the technique name is not found in registry.
        """
        technique = self._registry.get(technique_name)
        if technique is None:
            raise ValueError(f"Technique '{technique_name}' not found in registry")

        return await technique.think(
            prompt,
            self.state,
            ticket_id=ticket_id,
            variant=variant,
        )
