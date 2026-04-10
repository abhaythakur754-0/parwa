"""
Base Technique Node interface and shared types.

Defines BaseTechniqueNode ABC, ConversationState, GSDState, and
the node registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    ExecutionResultStatus,
    QuerySignals,
    TECHNIQUE_REGISTRY,
)


# ── GSD State Engine ──────────────────────────────────────────────


class GSDState(str, Enum):
    """GSD State Engine states (F-053)."""
    NEW = "new"
    GREETING = "greeting"
    DIAGNOSIS = "diagnosis"
    RESOLUTION = "resolution"
    FOLLOW_UP = "follow_up"
    CLOSED = "closed"
    ESCALATE = "escalate"
    HUMAN_HANDOFF = "human_handoff"


# ── Conversation State ────────────────────────────────────────────


@dataclass
class ConversationState:
    """
    Mutable state passed through the LangGraph pipeline.
    Each technique node reads and updates this state.
    """

    query: str = ""
    signals: QuerySignals = field(default_factory=QuerySignals)
    gsd_state: GSDState = GSDState.NEW
    gsd_history: List[GSDState] = field(default_factory=list)

    # Technique results keyed by technique_id
    technique_results: Dict[str, Any] = field(default_factory=dict)

    # Token tracking
    token_usage: int = 0
    technique_token_budget: int = 1500  # default medium

    # Response building
    response_parts: List[str] = field(default_factory=list)
    final_response: str = ""

    # Metadata
    ticket_id: Optional[str] = None
    conversation_id: Optional[str] = None
    company_id: Optional[str] = None

    # Reasoning thread (for ThoT)
    reasoning_thread: List[str] = field(default_factory=list)

    # Reflexion trace
    reflexion_trace: Optional[Dict[str, Any]] = None


# ── Base Technique Node ───────────────────────────────────────────


class BaseTechniqueNode(ABC):
    """
    Abstract base class for all technique implementations.
    Each technique implements this interface and registers in TECHNIQUE_REGISTRY.
    """

    def __init__(self):
        self.technique_info = TECHNIQUE_REGISTRY[self.technique_id]

    @property
    @abstractmethod
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        ...

    @abstractmethod
    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if this technique should activate for the given state.
        Called by the Technique Router during evaluation.
        """
        ...

    @abstractmethod
    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the technique and update the conversation state.
        Returns the updated state.
        """
        ...

    def check_token_budget(self, state: ConversationState) -> bool:
        """Check if enough token budget remains."""
        overhead = self.technique_info.estimated_tokens
        return (state.token_usage + overhead) <= state.technique_token_budget

    def record_result(
        self,
        state: ConversationState,
        result: Any,
        tokens_used: int = 0,
    ) -> None:
        """Record technique execution result in state."""
        state.technique_results[self.technique_id.value] = {
            "status": ExecutionResultStatus.SUCCESS.value,
            "result": result,
            "tokens_used": tokens_used or self.technique_info.estimated_tokens,
            "executed_at": datetime.utcnow().isoformat(),
        }
        state.token_usage += tokens_used or self.technique_info.estimated_tokens

    def record_skip(
        self,
        state: ConversationState,
        reason: str = "budget_exceeded",
    ) -> None:
        """Record that technique was skipped."""
        state.technique_results[self.technique_id.value] = {
            "status": ExecutionResultStatus.SKIPPED_BUDGET.value,
            "reason": reason,
            "executed_at": datetime.utcnow().isoformat(),
        }


# ── Node Registry (populated by stub_nodes) ──────────────────────

TECHNIQUE_NODES: Dict[TechniqueID, BaseTechniqueNode] = {}
