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
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import TechniqueResult
from parwa.frameworks.registry import get_registry

logger = logging.getLogger("parwa.frameworks.brain")


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

    async def think(
        self,
        prompt: str,
        techniques: list[str] | None = None,
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Select and run techniques based on ticket complexity.

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

        # Rate limit: max 2 techniques per node to avoid API rate limits
        # This trades depth for reliability — in production with own API keys,
        # this limit can be increased.
        MAX_TECHNIQUES_PER_NODE = 2
        if len(activated) > MAX_TECHNIQUES_PER_NODE:
            logger.debug(
                "brain: limiting %s from %d to %d techniques for node=%s",
                [t.name for t in activated], len(activated),
                MAX_TECHNIQUES_PER_NODE, self.node,
            )
            activated = activated[:MAX_TECHNIQUES_PER_NODE]

        if not activated:
            logger.debug("brain: no techniques activated for node=%s complexity=%s", self.node, complexity)
            return TechniqueResult(
                output="",
                chain=[],
                confidence=0.0,
                frameworks_used=[],
                metadata={"activated_count": 0, "complexity": complexity},
            )

        # Run techniques in order, combining results
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
                    await asyncio.sleep(0.5)

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
                    combined_output = result.output  # Last technique wins for output
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
