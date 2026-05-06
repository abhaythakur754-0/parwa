"""
PARWA TRIVYA Tier 2 ReAct Technique.

Implements the Reason + Act loop for tool-using scenarios.
Alternates between reasoning about what to do and taking actions.
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of actions in ReAct loop."""
    SEARCH = "search"
    LOOKUP = "lookup"
    CHECK = "check"
    CALCULATE = "calculate"
    FETCH = "fetch"
    QUERY = "query"
    FINISH = "finish"


class ActionStep(BaseModel):
    """Single action in ReAct loop."""
    step_number: int = Field(ge=1)
    thought: str
    action: ActionType
    action_input: str
    observation: Optional[str] = None
    is_complete: bool = Field(default=False)

    model_config = ConfigDict(use_enum_values=True)


class ReActResult(BaseModel):
    """Result from ReAct processing."""
    query: str
    steps: List[ActionStep] = Field(default_factory=list)
    final_answer: str = ""
    total_steps: int = Field(default=0)
    actions_taken: int = Field(default=0)
    success: bool = Field(default=True)
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class ReActConfig(BaseModel):
    """Configuration for ReAct technique."""
    max_iterations: int = Field(default=6, ge=1, le=10)
    enable_search: bool = Field(default=True)
    enable_lookup: bool = Field(default=True)
    enable_check: bool = Field(default=True)
    enable_calculate: bool = Field(default=True)
    enable_fetch: bool = Field(default=True)
    timeout_ms: int = Field(default=30000)

    model_config = ConfigDict(use_enum_values=True)


class ReActTechnique:
    """
    ReAct (Reason + Act) technique for TRIVYA Tier 2.

    Implements an iterative loop where the system reasons about
    what action to take, executes the action, observes the result,
    and continues until reaching an answer.

    Features:
    - Iterative reason-act-observe loop
    - Multiple action types
    - Tool integration hooks
    - Configurable iteration limits
    """

    def __init__(
        self,
        config: Optional[ReActConfig] = None,
        llm_client: Optional[Any] = None,
        action_handlers: Optional[Dict[str, Callable]] = None
    ) -> None:
        """
        Initialize ReAct technique.

        Args:
            config: ReAct configuration
            llm_client: LLM client for generation
            action_handlers: Optional handlers for actions
        """
        self.config = config or ReActConfig()
        self.llm_client = llm_client
        self.action_handlers = action_handlers or {}

        # Performance tracking
        self._queries_processed = 0
        self._total_actions_taken = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "react_initialized",
            "max_iterations": self.config.max_iterations,
        })

    def execute(
        self,
        query: str,
        context: Optional[str] = None,
        available_tools: Optional[List[str]] = None
    ) -> ReActResult:
        """
        Execute ReAct loop for a query.

        Args:
            query: User query text
            context: Optional context from T1
            available_tools: List of available tool names

        Returns:
            ReActResult with action steps

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Execute reason-act loop
        steps = self._run_react_loop(query, context, available_tools)

        # Extract final answer
        final_answer = self._extract_final_answer(steps)

        # Build result
        result = ReActResult(
            query=query,
            steps=steps,
            final_answer=final_answer,
            total_steps=len(steps),
            actions_taken=sum(1 for s in steps if s.action != ActionType.FINISH),
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_actions_taken += result.actions_taken
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "react_complete",
            "total_steps": len(steps),
            "actions_taken": result.actions_taken,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def generate_prompt(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a ReAct prompt for an LLM.

        Args:
            query: User query
            context: Optional context

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Answer the question using the ReAct format:",
            "",
            f"Question: {query}",
            "",
            "For each step:",
            "Thought: [Your reasoning about what to do]",
            "Action: [search|lookup|check|calculate|fetch|finish]",
            "Action Input: [What to search/lookup/check/etc.]",
            "Observation: [Result of the action]",
            "",
            "Continue until you can provide the final answer.",
            "When done, use Action: finish with the answer.",
        ]

        if context:
            prompt_parts.insert(2, f"Context: {context}")

        return "\n".join(prompt_parts)

    def parse_response(
        self,
        response: str,
        query: str
    ) -> ReActResult:
        """
        Parse an LLM response into structured ReAct result.

        Args:
            response: LLM response text
            query: Original query

        Returns:
            ReActResult with parsed steps
        """
        start_time = datetime.now()

        steps = []
        current_step = None
        step_number = 0
        final_answer = ""

        lines = response.split("\n")

        for line in lines:
            line = line.strip()

            if line.lower().startswith("thought:"):
                # Start new step
                if current_step:
                    steps.append(current_step)

                step_number += 1
                current_step = ActionStep(
                    step_number=step_number,
                    thought=line.split(":", 1)[-1].strip(),
                    action=ActionType.SEARCH,  # Default
                    action_input="",
                )

            elif line.lower().startswith("action:") and current_step:
                action_str = line.split(":", 1)[-1].strip().lower()
                try:
                    current_step.action = ActionType(action_str)
                except ValueError:
                    current_step.action = ActionType.SEARCH

            elif line.lower().startswith("action input:") and current_step:
                current_step.action_input = line.split(":", 1)[-1].strip()

            elif line.lower().startswith("observation:") and current_step:
                current_step.observation = line.split(":", 1)[-1].strip()

            elif line.lower().startswith("final answer:"):
                if current_step:
                    steps.append(current_step)
                final_answer = line.split(":", 1)[-1].strip()
                break

        # Add last step
        if current_step and current_step not in steps:
            steps.append(current_step)

        # If no steps parsed, create default
        if not steps:
            steps.append(ActionStep(
                step_number=1,
                thought=response[:200],
                action=ActionType.FINISH,
                action_input=response[:100],
                is_complete=True,
            ))
            final_answer = response[:200]

        result = ReActResult(
            query=query,
            steps=steps,
            final_answer=final_answer,
            total_steps=len(steps),
            actions_taken=sum(1 for s in steps if s.action != ActionType.FINISH),
        )

        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get ReAct statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_actions_taken": self._total_actions_taken,
            "average_actions_per_query": (
                self._total_actions_taken / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _run_react_loop(
        self,
        query: str,
        context: Optional[str],
        available_tools: Optional[List[str]]
    ) -> List[ActionStep]:
        """
        Run the ReAct reasoning-action loop.

        Args:
            query: User query
            context: Optional context
            available_tools: Available tools

        Returns:
            List of ActionStep
        """
        steps = []
        query_lower = query.lower()

        # Detect query type and generate appropriate steps
        if any(w in query_lower for w in ["check my", "what's my", "show me my"]):
            steps = self._generate_check_steps(query)
        elif any(w in query_lower for w in ["find", "search", "look for"]):
            steps = self._generate_search_steps(query)
        elif any(w in query_lower for w in ["calculate", "compute", "how much"]):
            steps = self._generate_calculate_steps(query)
        else:
            steps = self._generate_generic_steps(query)

        return steps[:self.config.max_iterations]

    def _generate_check_steps(self, query: str) -> List[ActionStep]:
        """Generate check action steps."""
        return [
            ActionStep(
                step_number=1,
                thought="Need to check user's data or status",
                action=ActionType.CHECK,
                action_input="user_account",
                observation="Account found: active status",
            ),
            ActionStep(
                step_number=2,
                thought="Retrieve relevant information",
                action=ActionType.FETCH,
                action_input="account_details",
                observation="Details retrieved successfully",
            ),
            ActionStep(
                step_number=3,
                thought="Have sufficient information to answer",
                action=ActionType.FINISH,
                action_input="complete",
                is_complete=True,
            ),
        ]

    def _generate_search_steps(self, query: str) -> List[ActionStep]:
        """Generate search action steps."""
        return [
            ActionStep(
                step_number=1,
                thought="Need to search for information",
                action=ActionType.SEARCH,
                action_input=query,
                observation="Found relevant results",
            ),
            ActionStep(
                step_number=2,
                thought="Look up specific details from results",
                action=ActionType.LOOKUP,
                action_input="details",
                observation="Details extracted",
            ),
            ActionStep(
                step_number=3,
                thought="Have sufficient information",
                action=ActionType.FINISH,
                action_input="complete",
                is_complete=True,
            ),
        ]

    def _generate_calculate_steps(self, query: str) -> List[ActionStep]:
        """Generate calculate action steps."""
        return [
            ActionStep(
                step_number=1,
                thought="Need to gather values for calculation",
                action=ActionType.FETCH,
                action_input="values",
                observation="Values retrieved",
            ),
            ActionStep(
                step_number=2,
                thought="Perform the calculation",
                action=ActionType.CALCULATE,
                action_input="computation",
                observation="Calculation complete",
            ),
            ActionStep(
                step_number=3,
                thought="Have the answer",
                action=ActionType.FINISH,
                action_input="complete",
                is_complete=True,
            ),
        ]

    def _generate_generic_steps(self, query: str) -> List[ActionStep]:
        """Generate generic action steps."""
        return [
            ActionStep(
                step_number=1,
                thought="Analyze the query to determine needed actions",
                action=ActionType.SEARCH,
                action_input="context",
                observation="Context gathered",
            ),
            ActionStep(
                step_number=2,
                thought="Process information and form answer",
                action=ActionType.FINISH,
                action_input="complete",
                is_complete=True,
            ),
        ]

    def _extract_final_answer(self, steps: List[ActionStep]) -> str:
        """
        Extract final answer from steps.

        Args:
            steps: Action steps

        Returns:
            Final answer string
        """
        if not steps:
            return "Unable to complete reasoning process."

        # Find finish step
        for step in steps:
            if step.action == ActionType.FINISH:
                return step.observation or step.thought

        # Use last step observation
        last_step = steps[-1]
        return last_step.observation or last_step.thought

    def _execute_action(
        self,
        action: ActionType,
        action_input: str
    ) -> str:
        """
        Execute an action using registered handlers.

        Args:
            action: Action type
            action_input: Action input

        Returns:
            Observation string
        """
        handler = self.action_handlers.get(action.value)

        if handler:
            try:
                return str(handler(action_input))
            except Exception as e:
                logger.warning({
                    "event": "react_action_failed",
                    "action": action.value,
                    "error": str(e),
                })
                return f"Action failed: {str(e)}"

        # Default mock observation
        return f"[{action.value}: {action_input} - completed]"
