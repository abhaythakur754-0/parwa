"""
Base Technique Node interface and shared types.

Defines BaseTechniqueNode ABC, ConversationState, GSDState, and
the node registry.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    ExecutionResultStatus,
    QuerySignals,
    TECHNIQUE_REGISTRY,
)
from app.core.techniques.llm_client import (
    LLMResponse,
    llm_gateway,
)

logger = logging.getLogger("parwa.techniques.base")


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
            "executed_at": datetime.now(timezone.utc).isoformat(),
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
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def execute_with_llm(
        self,
        prompt: str,
        state: Optional[ConversationState] = None,
        *,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> Optional[LLMResponse]:
        """Call the LLM gateway with graceful error handling.

        This is a convenience method so that technique subclasses do not
        need to import the gateway directly.  On failure it logs the
        error and returns ``None`` rather than propagating the
        exception (BC-008: never crash).

        Args:
            prompt: The primary user message / query to send.
            state: Optional conversation state.  When provided the
                technique's ``technique_id`` and ``company_id`` are
                automatically extracted.
            system_prompt: Optional system-level instruction.  Falls
                back to the technique description from the registry.
            max_tokens: Override ``max_tokens``.  When ``None`` the
                gateway default is used.
            temperature: Override ``temperature``.
            **kwargs: Forwarded verbatim to
                :pymeth:`LLMGateway.generate` (e.g. ``messages``,
                ``company_id``).

        Returns:
            :class:`LLMResponse` on success, ``None`` on failure.
        """
        technique_id = self.technique_id.value

        # Derive defaults from the technique's registered metadata
        if not system_prompt and self.technique_info:
            system_prompt = self.technique_info.description or ""

        # Pull company_id from state when available
        company_id: str = kwargs.pop("company_id", "")
        if not company_id and state is not None:
            company_id = state.company_id or ""

        try:
            response = await llm_gateway.generate(
                system_prompt=system_prompt,
                user_message=prompt,
                technique_id=technique_id,
                max_tokens=max_tokens,
                temperature=temperature,
                company_id=company_id,
                **kwargs,
            )

            if response.error:
                logger.warning(
                    "execute_with_llm returned error [technique=%s]: %s",
                    technique_id,
                    response.error[:200],
                )
                return None

            return response

        except Exception as exc:
            logger.error(
                "execute_with_llm unexpected error [technique=%s]: %s",
                technique_id,
                str(exc)[:300],
            )
            return None


# ── Node Registry (populated by stub_nodes) ──────────────────────

TECHNIQUE_NODES: Dict[TechniqueID, BaseTechniqueNode] = {}
