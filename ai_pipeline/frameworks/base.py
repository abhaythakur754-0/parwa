"""Base interface for all PARWA AI techniques.

Every technique (CoT, ReAct, ToT, etc.) implements this interface.
The FrameworkBrain calls think() on the selected technique(s) and
combines the results.

Design principles:
  - Every technique is async (all PARWA nodes are async)
  - Every technique receives (prompt, state) and returns TechniqueResult
  - Every technique can work in MOCK_MODE (no real LLM calls)
  - Every technique has a token_cost_estimate for budget tracking
  - Every technique tracks which frameworks were activated
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TechniqueCategory(str, Enum):
    """Categories for the 25 AI techniques."""
    REASONING = "reasoning"
    RAG = "rag"
    QUALITY = "quality"
    MEMORY = "memory"
    PROPRIETARY = "proprietary"


class TechniqueResult(BaseModel):
    """Standard result from any technique's think() method.

    Every technique returns this so FrameworkBrain can combine results
    from multiple techniques in a consistent way.
    """
    output: str = ""
    chain: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    frameworks_used: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_estimate: int = 0
    error: str | None = None

    model_config = {"extra": "allow"}


class BaseTechnique(ABC):
    """Abstract base class for all PARWA AI techniques.

    Every technique must implement:
      - name: unique identifier (e.g. "chain_of_thought")
      - category: which category this technique belongs to
      - applicable_nodes: which node names this technique can run in
      - token_cost_estimate: rough token cost for budget tracking
      - think(): the actual technique logic

    Usage:
        technique = ChainOfThoughtTechnique()
        result = await technique.think("Reason about this", state)
        assert result.frameworks_used == ["chain_of_thought"]
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique technique identifier (e.g. 'chain_of_thought')."""
        ...

    @property
    @abstractmethod
    def category(self) -> TechniqueCategory:
        """Category this technique belongs to."""
        ...

    @property
    @abstractmethod
    def applicable_nodes(self) -> list[str]:
        """Node names where this technique can be activated.

        Example: ['REASONING_ENGINE', 'ACTION_PLANNER']
        """
        ...

    @property
    @abstractmethod
    def token_cost_estimate(self) -> int:
        """Estimated token cost per think() call.

        Used by FrameworkBrain for budget-aware technique selection.
        This is a rough estimate, not exact.
        """
        ...

    @abstractmethod
    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute the technique's reasoning logic.

        Args:
            prompt: The reasoning prompt (what to think about).
            state: The current ticket state dict.
            ticket_id: Current ticket ID for tracking.
            variant: Current variant for budget allocation.

        Returns:
            TechniqueResult with the technique's output.
        """
        ...

    def can_apply(self, node_name: str, complexity: str) -> bool:
        """Check if this technique should activate for the given node + complexity.

        Default logic: technique must be applicable to the node AND
        the complexity must be sufficient for the technique's minimum level.

        Subclasses can override for custom activation logic.
        """
        if node_name not in self.applicable_nodes:
            return False

        # Complexity thresholds — subclasses can override
        min_complexity = getattr(self, "_min_complexity", "simple")
        complexity_order = {"simple": 0, "medium": 1, "complex": 2, "critical": 3}
        return complexity_order.get(complexity, 0) >= complexity_order.get(min_complexity, 0)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} category={self.category.value}>"
