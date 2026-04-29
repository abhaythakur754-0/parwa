"""
F-142: ReAct (Reasoning + Acting) — Tier 2 Conditional AI Reasoning Technique

Implements the ReAct pattern: interleaved Thought → Action → Observation
loops to gather external data before formulating a final answer.

Pipeline (6 steps):
  1. Thought  — Analyze query to determine what information is needed
  2. Action   — Select and invoke appropriate tool(s) from ToolRegistry
  3. Observation — Process tool results (template-based, deterministic)
  4. Thought  — Reason about observation in context
  5. Action/Observation Loop — Repeat up to max_iterations
  6. Final Answer — Synthesize observations into coherent response

Trigger: state.signals.external_data_required is True

Performance: deterministic/heuristic-based (NO LLM calls).
Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.technique_router import (
    TECHNIQUE_REGISTRY,
    TechniqueID,
)
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.core.techniques.react_tools import (
    ToolRegistry,
    default_tool_registry,
)
from app.logger import get_logger

logger = get_logger("react")


# ── ActionType Enum ─────────────────────────────────────────────────


class ActionType(str, Enum):
    """Types of actions the ReAct loop can take."""

    TOOL_CALL = "tool_call"
    WAIT = "wait"
    DELEGATE = "delegate"
    RESPOND = "respond"


# ── Query Pattern Detection ────────────────────────────────────────


# Order reference patterns: ORD-123, #12345, order 123, etc.
_ORDER_PATTERNS: Tuple[str, ...] = (
    r"\bORD[-_]\w+",
    r"\bORD\d+\b",
    r"\border\s*(?:#|num(?:ber)?)?\s*\w+",
    r"#\d{4,}",
    r"\border\s+id\s*[:=]?\s*\w+",
)

# Account / customer reference patterns
_CUSTOMER_PATTERNS: Tuple[str, ...] = (
    r"\bcustomer\s*(?:#|id|num(?:ber)?)?\s*\w+",
    r"\baccount\s*(?:#|id|num(?:ber)?)?\s*\w+",
    r"\bclient\s*(?:#|id)?\s*\w+",
    r"\buser\s*(?:#|id)?\s*\w+",
    r"\bCUST[-_]\w+",
)

# Billing / subscription query patterns
_BILLING_PATTERNS: Tuple[str, ...] = (
    r"\b(bill|billing|invoice|charg\w*|payment|fee)\b",
    r"\b(subscription|plan|upgrade|downgrade|renew|trial|tier)\b",
    r"\b(refund|credit|debit|prorat)\b",
    r"\b(pric|cost|amount)\w*\b",
)

# Technical issue keywords
_TECHNICAL_PATTERNS: Tuple[str, ...] = (
    r"\b(bug|error|crash\w*|broken|not\s+work|fail\w*|slow)\b",
    r"\b(login|password|auth|sso)\b",
    r"\b(install|setup|config|connect|sync|integration)\b",
    r"\b(api|webhook|endpoint|timeout)\b",
)

# Policy / FAQ query patterns
_KNOWLEDGE_PATTERNS: Tuple[str, ...] = (
    r"\b(policy|policies|faq|help|how\s+to|what\s+is)\b",
    r"\b(return|exchange|warranty|guarantee)\b",
    r"\b(shipping|delivery|track)\b",
    r"\b(support|contact|hours)\b",
)

# Past issue patterns (for ticket history search)
_TICKET_HISTORY_PATTERNS: Tuple[str, ...] = (
    r"\b(previous|past|before|earlier|last\s+time)\b",
    r"\b(ticket|case|issue|problem)\s*(?:#|num(?:ber)?)?\s*\w+",
    r"\bagain\b",
    r"\b(still|yet)\s+(?:not\s+)?(?:work|fix|resolv)\w*\b",
)

# Compiled pattern lists
_COMPILED_ORDER = [re.compile(p, re.I) for p in _ORDER_PATTERNS]
_COMPILED_CUSTOMER = [re.compile(p, re.I) for p in _CUSTOMER_PATTERNS]
_COMPILED_BILLING = [re.compile(p, re.I) for p in _BILLING_PATTERNS]
_COMPILED_TECHNICAL = [re.compile(p, re.I) for p in _TECHNICAL_PATTERNS]
_COMPILED_KNOWLEDGE = [re.compile(p, re.I) for p in _KNOWLEDGE_PATTERNS]
_COMPILED_TICKET_HISTORY = [re.compile(p, re.I) for p in _TICKET_HISTORY_PATTERNS]


# ── Tool Selection Mapping ─────────────────────────────────────────


# Maps detected query category → primary tool name
_QUERY_TO_TOOL: Dict[str, str] = {
    "order_reference": "order_status_check",
    "account_reference": "customer_lookup",
    "billing_query": "knowledge_base_search",
    "technical_issue": "knowledge_base_search",
    "policy_faq": "knowledge_base_search",
    "past_issue": "ticket_history_search",
}

# Parameters extraction patterns per tool
_ORDER_ID_EXTRACT = re.compile(
    r"(?:ORD[-_]|order\s*(?:#|num(?:ber)?)?\s*|#\s*)(\w+)",
    re.I,
)
_CUSTOMER_ID_EXTRACT = re.compile(
    r"(?:customer|account|client|user|CUST)[-_\s]*(?:#|id|num(?:ber)?)?\s*[:=]?\s*(\w+)",
    re.I,
)


# ── Data Structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class ReActConfig:
    """
    Immutable configuration for ReAct processing (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        max_iterations: Maximum thought-action-observation cycles.
        tool_timeout: Timeout for individual tool calls in seconds.
    """

    company_id: str = ""
    max_iterations: int = 3
    tool_timeout: float = 30.0


@dataclass
class ReActStep:
    """
    A single step in the ReAct reasoning chain.

    Attributes:
        step_number: Sequential step number in the chain.
        step_type: Type of step ('thought', 'action', or 'observation').
        content: The text content of this step.
        tool_name: Name of the tool invoked (action steps only).
        tool_params: Parameters passed to the tool (action steps only).
        tool_result: Result dict returned by the tool (observation steps).
        reasoning: Free-text reasoning or context.
    """

    step_number: int = 0
    step_type: str = "thought"
    content: str = ""
    tool_name: str = ""
    tool_params: Dict[str, Any] = field(default_factory=dict)
    tool_result: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize step to dictionary."""
        return {
            "step_number": self.step_number,
            "step_type": self.step_type,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "tool_result": self.tool_result,
            "reasoning": self.reasoning,
        }


@dataclass
class ReActResult:
    """
    Output of the ReAct processing loop.

    Attributes:
        thought_chain: List of thought steps in order.
        actions_taken: List of action types executed.
        observations: List of observation contents.
        final_answer: Synthesized response.
        iterations_used: Number of iterations actually executed.
        steps_applied: Names of processing steps that ran.
        tools_used: List of tool names that were invoked.
    """

    thought_chain: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    final_answer: str = ""
    iterations_used: int = 0
    steps_applied: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "thought_chain": self.thought_chain,
            "actions_taken": self.actions_taken,
            "observations": self.observations,
            "final_answer": self.final_answer,
            "iterations_used": self.iterations_used,
            "steps_applied": self.steps_applied,
            "tools_used": self.tools_used,
        }


# ── ReAct Processor ────────────────────────────────────────────────


class ReActProcessor:
    """
    ReAct (Reasoning + Acting) processor.

    Deterministic, heuristic-based (no LLM calls).
    Implements the thought-action-observation loop to gather external
    data and synthesize a coherent response.

    Pipeline:
      1. Thought  — Analyze query information needs
      2. Action   — Select and invoke tools
      3. Observation — Process tool results
      4. Thought  — Reason about observations
      5. Loop     — Repeat up to max_iterations
      6. Answer   — Synthesize final response
    """

    def __init__(
        self,
        config: Optional[ReActConfig] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.config = config or ReActConfig()
        self.tool_registry = tool_registry or default_tool_registry

    # ── Step 1: Thought — Query Analysis ───────────────────────────

    def _detect_query_categories(self, query: str) -> List[str]:
        """
        Detect what type of information the query needs.

        Returns a list of category strings that indicate which tools
        should be consulted.
        """
        if not query or not query.strip():
            return []

        categories: List[str] = []

        # Detect order references
        if any(p.search(query) for p in _COMPILED_ORDER):
            categories.append("order_reference")

        # Detect account/customer references
        if any(p.search(query) for p in _COMPILED_CUSTOMER):
            categories.append("account_reference")

        # Detect billing/subscription queries
        if any(p.search(query) for p in _COMPILED_BILLING):
            categories.append("billing_query")

        # Detect technical issues
        if any(p.search(query) for p in _COMPILED_TECHNICAL):
            categories.append("technical_issue")

        # Detect policy/FAQ queries
        if any(p.search(query) for p in _COMPILED_KNOWLEDGE):
            categories.append("policy_faq")

        # Detect past issue references
        if any(p.search(query) for p in _COMPILED_TICKET_HISTORY):
            categories.append("past_issue")

        return categories

    async def generate_thought(self, query: str) -> str:
        """
        Generate a thought analyzing what information is needed.

        Uses pattern detection to produce a deterministic thought
        string describing the information needs.
        """
        categories = self._detect_query_categories(query)

        if not categories:
            return (
                f"Analyzing query: '{query}'. "
                "No specific entity references detected. "
                "Will search knowledge base for general information."
            )

        category_descriptions: Dict[str, str] = {
            "order_reference": "order status and tracking information",
            "account_reference": "customer account details and history",
            "billing_query": "billing, subscription, and payment information",
            "technical_issue": "technical troubleshooting information",
            "policy_faq": "policy and FAQ information from knowledge base",
            "past_issue": "past ticket history and resolution patterns",
        }

        needs = [
            category_descriptions.get(cat, cat)
            for cat in categories
            if cat in category_descriptions
        ]

        tools_needed: List[str] = []
        for cat in categories:
            tool = _QUERY_TO_TOOL.get(cat)
            if tool and tool not in tools_needed:
                tools_needed.append(tool)

        thought = f"Analyzing query: '{query}'. " f"Detected information needs: {
                ', '.join(needs)}. " f"Tools to consult: {
                ', '.join(tools_needed) if tools_needed else 'none identified'}."

        return thought

    # ── Step 2: Action — Tool Selection ─────────────────────────────

    def _select_tools_for_categories(
        self,
        categories: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Map detected query categories to tool calls.

        Returns a list of dicts with 'tool_name' and 'params' keys.
        """
        tool_calls: List[Dict[str, Any]] = []
        seen_tools: Set[str] = set()

        for category in categories:
            tool_name = _QUERY_TO_TOOL.get(category)
            if not tool_name or tool_name in seen_tools:
                continue

            seen_tools.add(tool_name)
            params: Dict[str, Any] = {}

            if tool_name == "order_status_check":
                params["order_id"] = (
                    self._extract_order_id(
                        self._last_query,
                    )
                    or "unknown"
                )

            elif tool_name == "customer_lookup":
                params["customer_id"] = (
                    self._extract_customer_id(
                        self._last_query,
                    )
                    or "unknown"
                )

            elif tool_name == "knowledge_base_search":
                params["query"] = self._last_query or ""
                params["max_results"] = 5

            elif tool_name == "ticket_history_search":
                params["query"] = self._last_query or ""
                params["limit"] = 5

            tool_calls.append(
                {
                    "tool_name": tool_name,
                    "params": params,
                }
            )

        # If no categories matched, default to knowledge base search
        if not tool_calls:
            tool_calls.append(
                {
                    "tool_name": "knowledge_base_search",
                    "params": {"query": self._last_query or "", "max_results": 5},
                }
            )

        return tool_calls

    @staticmethod
    def _extract_order_id(query: str) -> Optional[str]:
        """Extract order ID from query text."""
        if not query:
            return None
        match = _ORDER_ID_EXTRACT.search(query)
        if match:
            return match.group(1).strip()
        # Try ORD- prefix pattern specifically
        ord_match = re.search(r"(ORD[-_]\w+)", query, re.I)
        if ord_match:
            return ord_match.group(1).strip()
        return None

    @staticmethod
    def _extract_customer_id(query: str) -> Optional[str]:
        """Extract customer ID from query text."""
        if not query:
            return None
        match = _CUSTOMER_ID_EXTRACT.search(query)
        if match:
            return match.group(1).strip()
        # Try CUST- prefix specifically
        cust_match = re.search(r"(CUST[-_]\w+)", query, re.I)
        if cust_match:
            return cust_match.group(1).strip()
        return None

    async def select_action(
        self,
        query: str,
        categories: List[str],
    ) -> Dict[str, Any]:
        """
        Select the appropriate action and tool for the current step.

        Returns a dict with 'action_type', 'tool_name', and 'params'.
        """
        tool_calls = self._select_tools_for_categories(categories)

        if tool_calls:
            primary = tool_calls[0]
            return {
                "action_type": ActionType.TOOL_CALL.value,
                "tool_name": primary["tool_name"],
                "params": primary["params"],
            }

        return {
            "action_type": ActionType.WAIT.value,
            "tool_name": "",
            "params": {},
        }

    # ── Step 3: Observation — Process Tool Results ──────────────────

    async def process_observation(
        self,
        tool_name: str,
        tool_result: Dict[str, Any],
    ) -> str:
        """
        Process tool result into an observation string.

        Template-based since tools return placeholder data.
        """
        if not tool_result:
            return f"Tool '{tool_name}' returned no results."

        success = tool_result.get("success", False)

        if not success:
            error = tool_result.get("error", "Unknown error")
            return f"Tool '{tool_name}' reported an error: {error}."

        data = tool_result.get("data", {})
        tool_from_result = tool_result.get("tool", tool_name)
        message = data.get("message", "")

        # Build observation based on tool type
        if tool_from_result == "knowledge_base_search":
            total = data.get("total", 0)
            results = data.get("results", [])
            if total > 0:
                observation = (
                    f"Knowledge base search returned {total} result(s). "
                    "Top articles found matching the query."
                )
            else:
                observation = (
                    "Knowledge base search returned 0 results. "
                    "No matching articles found. "
                    f"{message}"
                    if message
                    else ""
                ).strip()

        elif tool_from_result == "customer_lookup":
            customer_id = data.get("customer_id", "unknown")
            name = data.get("name")
            tier = data.get("tier")
            status = data.get("status")
            parts = [f"Customer lookup for '{customer_id}'."]
            if name:
                parts.append(f"Name: {name}")
            if tier:
                parts.append(f"Tier: {tier}")
            if status:
                parts.append(f"Status: {status}")
            if message:
                parts.append(message)
            observation = " ".join(parts)

        elif tool_from_result == "ticket_history_search":
            total = data.get("total", 0)
            tickets = data.get("tickets", [])
            status_text = (
                "Relevant past tickets found."
                if total > 0
                else "No matching past tickets found."
            )
            observation = (
                f"Ticket history search returned {total} result(s). "
                f"{status_text} "
                f"{message}"
            )
            if message:
                observation = observation.rstrip()
            else:
                observation = (
                    f"Ticket history search returned {total} result(s). "
                    f"{status_text}"
                )
            observation = observation.strip()

        elif tool_from_result == "order_status_check":
            order_id = data.get("order_id", "unknown")
            status = data.get("status")
            tracking = data.get("tracking_number")
            delivery = data.get("estimated_delivery")
            parts = [f"Order status check for '{order_id}'."]
            if status:
                parts.append(f"Status: {status}")
            if tracking:
                parts.append(f"Tracking: {tracking}")
            if delivery:
                parts.append(f"Estimated delivery: {delivery}")
            if message:
                parts.append(message)
            observation = " ".join(parts)

        else:
            observation = (
                f"Tool '{tool_from_result}' returned data. {message}"
                if message
                else f"Tool '{tool_from_result}' returned data."
            )

        return observation

    # ── Step 4: Thought — Reason About Observation ──────────────────

    async def reason_about_observation(
        self,
        query: str,
        observation: str,
        categories: List[str],
        iteration: int,
    ) -> str:
        """
        Generate a thought reasoning about the observation in context.

        Determines whether more information is needed or if a final
        answer can be synthesized.
        """
        if not observation or "error" in observation.lower():
            if iteration < self.config.max_iterations - 1:
                return (
                    "The tool returned limited or no useful data. "
                    "Will try an alternative approach or knowledge base "
                    "search to gather more context."
                )
            return (
                "Insufficient data gathered after multiple attempts. "
                "Will synthesize best possible response with available "
                "information."
            )

        if "returned 0" in observation:
            if iteration < self.config.max_iterations - 1:
                return (
                    "No direct matches found. Will broaden the search "
                    "or try a different tool to find relevant information."
                )
            return (
                "Could not find specific matches. Will provide a "
                "general helpful response based on the query intent."
            )

        if iteration < self.config.max_iterations - 1 and len(categories) > 1:
            return (
                "Received useful information. Additional categories "
                "detected — gathering more data before finalizing response."
            )

        return (
            "Sufficient information gathered. Ready to synthesize "
            "a coherent response addressing the customer's query."
        )

    def _should_continue(
        self,
        thought: str,
        iteration: int,
        categories: List[str],
        tools_already_used: Set[str],
    ) -> bool:
        """
        Determine whether the ReAct loop should continue.

        Stops when:
          - max_iterations reached
          - thought indicates readiness to answer
          - no more untried tools for detected categories
        """
        if iteration >= self.config.max_iterations:
            return False

        # Check if thought signals readiness
        if "sufficient" in thought.lower() or "synthesize" in thought.lower():
            return True  # One more iteration to synthesize

        # Check if there are still untried tools
        remaining_categories = list(categories)
        for cat in remaining_categories:
            tool = _QUERY_TO_TOOL.get(cat)
            if tool and tool not in tools_already_used:
                return True

        return False

    # ── Step 5: Loop ───────────────────────────────────────────────

    # ── Step 6: Final Answer Synthesis ──────────────────────────────

    async def synthesize_final_answer(
        self,
        query: str,
        steps: List[ReActStep],
        observations: List[str],
        categories: List[str],
    ) -> str:
        """
        Synthesize all observations into a coherent final answer.

        Template-based deterministic synthesis.
        """
        if not observations:
            return (
                "I'd be happy to help with your query about "
                f"'{query}'. Let me search our knowledge base for "
                "relevant information to assist you."
            )

        # Determine answer type based on categories
        if "order_reference" in categories:
            answer = (
                "Based on the information retrieved, I can help "
                "you with your order inquiry. "
            )
        elif "billing_query" in categories:
            answer = (
                "Based on the information retrieved, I can help "
                "you with your billing question. "
            )
        elif "technical_issue" in categories:
            answer = (
                "Based on the troubleshooting information available, "
                "here's what I can help with regarding your issue. "
            )
        elif "account_reference" in categories:
            answer = "Based on your account information, " "here's what I found. "
        elif "past_issue" in categories:
            answer = (
                "Based on your past ticket history, "
                "here's the relevant information. "
            )
        else:
            answer = (
                "Based on the information available, "
                "here's what I can help you with. "
            )

        # Append summarized observations
        if len(observations) == 1:
            answer += f"{observations[0]} "
        else:
            answer += "Key findings: "
            answer += " | ".join(obs[:200] for obs in observations[:3])
            answer += " "

        answer += "Is there anything specific you'd like me to " "clarify further?"

        return answer

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(self, query: str) -> ReActResult:
        """
        Run the full 6-step ReAct pipeline.

        Args:
            query: The customer query to reason about.

        Returns:
            ReActResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        thought_chain: List[str] = []
        actions_taken: List[str] = []
        observations: List[str] = []
        tools_used: List[str] = []
        all_steps: List[ReActStep] = []
        self._last_query = query

        if not query or not query.strip():
            return ReActResult(
                final_answer="",
                steps_applied=["empty_input"],
            )

        try:
            # Step 1: Thought — Analyze query
            categories = self._detect_query_categories(query)
            thought = await self.generate_thought(query)
            thought_chain.append(thought)
            steps_applied.append("thought_analysis")

            step_num = 1
            all_steps.append(
                ReActStep(
                    step_number=step_num,
                    step_type="thought",
                    content=thought,
                    reasoning=f"Categories: {categories}",
                )
            )

            # Steps 2-5: Action/Observation loop
            tools_already_used: Set[str] = set()
            iteration = 0

            while iteration < self.config.max_iterations:
                iteration += 1

                # Step 2: Action — Select tool
                action = await self.select_action(query, categories)
                action_type = action.get("action_type", ActionType.WAIT.value)
                tool_name = action.get("tool_name", "")
                tool_params = action.get("params", {})
                actions_taken.append(action_type)

                step_num += 1
                all_steps.append(
                    ReActStep(
                        step_number=step_num,
                        step_type="action",
                        content=f"Action: {action_type} using {tool_name}",
                        tool_name=tool_name,
                        tool_params=tool_params,
                        reasoning=f"Iteration {iteration}",
                    )
                )

                if action_type == ActionType.TOOL_CALL.value and tool_name:
                    steps_applied.append("action_tool_call")

                    # Execute tool with company isolation
                    tool_result = await self.tool_registry.execute_tool(
                        name=tool_name,
                        company_id=self.config.company_id,
                        params=tool_params,
                        timeout=self.config.tool_timeout,
                    )

                    # Step 3: Observation — Process results
                    observation = await self.process_observation(
                        tool_name,
                        tool_result,
                    )
                    observations.append(observation)
                    tools_already_used.add(tool_name)
                    if tool_name not in tools_used:
                        tools_used.append(tool_name)

                    step_num += 1
                    all_steps.append(
                        ReActStep(
                            step_number=step_num,
                            step_type="observation",
                            content=observation,
                            tool_name=tool_name,
                            tool_result=tool_result,
                            reasoning="Processed tool output",
                        )
                    )

                    steps_applied.append("observation_processing")

                    # Step 4: Thought — Reason about observation
                    thought = await self.reason_about_observation(
                        query,
                        observation,
                        categories,
                        iteration,
                    )
                    thought_chain.append(thought)

                    step_num += 1
                    all_steps.append(
                        ReActStep(
                            step_number=step_num,
                            step_type="thought",
                            content=thought,
                            reasoning=f"Iteration {iteration} reasoning",
                        )
                    )

                    steps_applied.append("thought_reasoning")

                    # Check if we should continue the loop
                    if not self._should_continue(
                        thought,
                        iteration,
                        categories,
                        tools_already_used,
                    ):
                        break

                    # Update categories to remove processed ones
                    remaining = []
                    for cat in categories:
                        tool = _QUERY_TO_TOOL.get(cat)
                        if tool is None or tool not in tools_already_used:
                            remaining.append(cat)
                    categories = remaining

                elif action_type == ActionType.RESPOND.value:
                    steps_applied.append("action_respond")
                    break
                else:
                    steps_applied.append("action_wait")
                    break

            # Step 6: Final Answer — Synthesize
            final_answer = await self.synthesize_final_answer(
                query,
                all_steps,
                observations,
                categories,
            )
            steps_applied.append("final_answer_synthesis")

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "react_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return ReActResult(
                thought_chain=thought_chain,
                actions_taken=actions_taken,
                observations=observations,
                final_answer="",
                iterations_used=iteration if "iteration" in dir() else 0,
                steps_applied=(
                    (steps_applied + ["error_fallback"])
                    if "steps_applied" in dir()
                    else ["error_fallback"]
                ),
                tools_used=tools_used,
            )

        return ReActResult(
            thought_chain=thought_chain,
            actions_taken=actions_taken,
            observations=observations,
            final_answer=final_answer,
            iterations_used=iteration if "iteration" in dir() else 0,
            steps_applied=steps_applied,
            tools_used=tools_used,
        )


# ── ReActNode (LangGraph compatible) ──────────────────────────────


class ReActNode(BaseTechniqueNode):
    """
    ReAct (Reasoning + Acting) Engine — Tier 2 Conditional.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation trigger:
      - external_data_required is True
    """

    def __init__(
        self,
        config: Optional[ReActConfig] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self._config = config or ReActConfig()
        self._processor = ReActProcessor(
            config=self._config,
            tool_registry=tool_registry,
        )
        # Initialize technique_info from registry
        # type: ignore[assignment]
        self.technique_info = TECHNIQUE_REGISTRY[TechniqueID.REACT]

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.REACT

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if ReAct should activate.

        Triggers when external_data_required is True.
        """
        return state.signals.external_data_required

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the ReAct thought-action-observation loop.

        Implements the 6-step ReAct pipeline:
          1. Thought  — Analyze query
          2. Action   — Select and invoke tool(s)
          3. Observation — Process tool results
          4. Thought  — Reason about observations
          5. Loop     — Repeat up to max_iterations
          6. Answer   — Synthesize final response

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            # Use company_id from state for BC-001 isolation
            config = ReActConfig(
                company_id=state.company_id or self._config.company_id,
                max_iterations=self._config.max_iterations,
                tool_timeout=self._config.tool_timeout,
            )
            processor = ReActProcessor(
                config=config,
                tool_registry=self._processor.tool_registry,
            )

            result = await processor.process(state.query)

            # Record result in state
            self.record_result(state, result.to_dict())

            # If we have a final answer, append to response parts
            if result.final_answer:
                state.response_parts.append(result.final_answer)

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "react_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            self.record_skip(state, reason="execution_error")
            return original_state
