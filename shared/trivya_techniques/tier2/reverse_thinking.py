"""
PARWA TRIVYA Tier 2 Reverse Thinking Technique.

Works backward from a desired goal to determine the steps needed
to achieve it. Useful for planning and troubleshooting.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ReverseStep(BaseModel):
    """Single step in reverse reasoning."""
    step_number: int = Field(ge=1)
    current_state: str
    required_precondition: str
    action_needed: Optional[str] = None
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class ReverseThinkingResult(BaseModel):
    """Result from Reverse Thinking processing."""
    query: str
    goal: str
    starting_point: str = ""
    steps: List[ReverseStep] = Field(default_factory=list)
    forward_plan: List[str] = Field(default_factory=list)
    total_steps: int = Field(default=0)
    feasibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class ReverseThinkingConfig(BaseModel):
    """Configuration for Reverse Thinking."""
    max_steps: int = Field(default=8, ge=1, le=15)
    min_feasibility: float = Field(default=0.3, ge=0.0, le=1.0)
    include_difficulty: bool = Field(default=True)
    check_dependencies: bool = Field(default=True)
    generate_forward_plan: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class ReverseThinking:
    """
    Reverse Thinking technique for TRIVYA Tier 2.

    Works backward from a desired goal to determine what steps
    or conditions are needed to achieve it. Particularly useful
    for planning, troubleshooting, and goal-oriented queries.

    Features:
    - Goal-to-start reasoning
    - Dependency identification
    - Feasibility assessment
    - Forward plan generation
    """

    def __init__(
        self,
        config: Optional[ReverseThinkingConfig] = None,
        llm_client: Optional[Any] = None
    ) -> None:
        """
        Initialize Reverse Thinking.

        Args:
            config: Reverse Thinking configuration
            llm_client: LLM client for generation
        """
        self.config = config or ReverseThinkingConfig()
        self.llm_client = llm_client

        # Performance tracking
        self._queries_processed = 0
        self._total_steps_generated = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "reverse_thinking_initialized",
            "max_steps": self.config.max_steps,
        })

    def reason_backward(
        self,
        query: str,
        goal: Optional[str] = None,
        context: Optional[str] = None
    ) -> ReverseThinkingResult:
        """
        Apply reverse thinking to find path to goal.

        Args:
            query: User query text
            goal: Optional explicit goal (extracted if not provided)
            context: Optional context from T1

        Returns:
            ReverseThinkingResult with backward steps

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Extract goal if not provided
        goal = goal or self._extract_goal(query)

        # Generate backward steps
        steps = self._generate_backward_steps(goal, context)

        # Determine starting point
        starting_point = self._find_starting_point(steps)

        # Generate forward plan
        forward_plan = []
        if self.config.generate_forward_plan:
            forward_plan = self._create_forward_plan(steps)

        # Calculate feasibility
        feasibility = self._calculate_feasibility(steps)

        result = ReverseThinkingResult(
            query=query,
            goal=goal,
            starting_point=starting_point,
            steps=steps,
            forward_plan=forward_plan,
            total_steps=len(steps),
            feasibility_score=feasibility,
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_steps_generated += len(steps)
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "reverse_thinking_complete",
            "total_steps": len(steps),
            "feasibility": feasibility,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def generate_prompt(
        self,
        query: str,
        goal: Optional[str] = None
    ) -> str:
        """
        Generate a reverse thinking prompt for an LLM.

        Args:
            query: User query
            goal: Optional explicit goal

        Returns:
            Formatted prompt string
        """
        goal = goal or self._extract_goal(query)

        prompt_parts = [
            "Work backward from the goal to find the path to achieve it.",
            "",
            f"Goal: {goal}",
            "",
            "For each step, identify:",
            "- Current state (what needs to be true)",
            "- Required precondition (what must be true before)",
            "- Action needed (how to get from precondition to current)",
            "",
            "Start from the goal and work backward to the starting point.",
            "",
            "Step 1 (Goal): [Goal state]",
            "Required precondition: [What must be true]",
            "Action: [What gets you here]",
            "",
            "Continue until you reach a starting state.",
        ]

        return "\n".join(prompt_parts)

    def parse_response(
        self,
        response: str,
        query: str,
        goal: str
    ) -> ReverseThinkingResult:
        """
        Parse an LLM response into structured result.

        Args:
            response: LLM response text
            query: Original query
            goal: Identified goal

        Returns:
            ReverseThinkingResult with parsed steps
        """
        start_time = datetime.now()

        steps = []
        current_step = None
        step_number = 0

        lines = response.split("\n")

        for line in lines:
            line = line.strip()

            if line.lower().startswith("step "):
                if current_step:
                    steps.append(current_step)

                step_number += 1
                current_step = ReverseStep(
                    step_number=step_number,
                    current_state=line.split(":", 1)[-1].strip() if ":" in line else "",
                    required_precondition="",
                )

            elif "precondition" in line.lower() and current_step:
                current_step.required_precondition = line.split(":", 1)[-1].strip()

            elif line.lower().startswith("action:") and current_step:
                current_step.action_needed = line.split(":", 1)[-1].strip()

        if current_step and current_step not in steps:
            steps.append(current_step)

        # Reverse steps to get forward order
        steps = list(reversed(steps))

        # Generate forward plan
        forward_plan = [s.action_needed or s.current_state for s in steps if s.action_needed or s.current_state]

        feasibility = self._calculate_feasibility(steps)

        result = ReverseThinkingResult(
            query=query,
            goal=goal,
            steps=steps,
            forward_plan=forward_plan,
            total_steps=len(steps),
            feasibility_score=feasibility,
        )

        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Reverse Thinking statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_steps_generated": self._total_steps_generated,
            "average_steps_per_query": (
                self._total_steps_generated / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _extract_goal(self, query: str) -> str:
        """
        Extract the goal from a query.

        Args:
            query: User query

        Returns:
            Extracted goal string
        """
        query_lower = query.lower()

        # Look for goal indicators
        goal_patterns = [
            "i want to",
            "i need to",
            "trying to",
            "goal is to",
            "aim is to",
        ]

        for pattern in goal_patterns:
            if pattern in query_lower:
                # Extract text after pattern
                idx = query_lower.find(pattern)
                return query[idx + len(pattern):].strip().rstrip(".")

        # Default: use query as goal
        return query

    def _generate_backward_steps(
        self,
        goal: str,
        context: Optional[str]
    ) -> List[ReverseStep]:
        """
        Generate backward reasoning steps.

        Args:
            goal: Identified goal
            context: Optional context

        Returns:
            List of ReverseStep
        """
        # Generate steps based on goal type
        goal_lower = goal.lower()

        max_steps = self.config.max_steps
        if any(w in goal_lower for w in ["get", "reach", "achieve", "become"]):
            return self._generate_achievement_steps(goal)[:max_steps]
        elif any(w in goal_lower for w in ["fix", "solve", "resolve"]):
            return self._generate_problem_solving_steps(goal)[:max_steps]
        elif any(w in goal_lower for w in ["buy", "purchase", "acquire"]):
            return self._generate_acquisition_steps(goal)[:max_steps]
        else:
            return self._generate_generic_steps(goal)[:max_steps]

    def _generate_achievement_steps(self, goal: str) -> List[ReverseStep]:
        """Generate achievement-type steps."""
        return [
            ReverseStep(
                step_number=1,
                current_state=goal,
                required_precondition="Milestone just before goal achieved",
                action_needed="Complete final action",
                difficulty=0.3,
            ),
            ReverseStep(
                step_number=2,
                current_state="Near-goal milestone reached",
                required_precondition="Key prerequisites met",
                action_needed="Execute milestone plan",
                difficulty=0.4,
            ),
            ReverseStep(
                step_number=3,
                current_state="Prerequisites in place",
                required_precondition="Initial preparation complete",
                action_needed="Set up prerequisites",
                difficulty=0.5,
            ),
            ReverseStep(
                step_number=4,
                current_state="Initial state ready",
                required_precondition="Starting point",
                action_needed="Begin preparation",
                difficulty=0.6,
            ),
        ]

    def _generate_problem_solving_steps(self, goal: str) -> List[ReverseStep]:
        """Generate problem-solving steps."""
        return [
            ReverseStep(
                step_number=1,
                current_state="Problem resolved",
                required_precondition="Solution implemented",
                action_needed="Verify resolution",
                difficulty=0.2,
            ),
            ReverseStep(
                step_number=2,
                current_state="Solution implemented",
                required_precondition="Solution identified and prepared",
                action_needed="Apply solution",
                difficulty=0.4,
            ),
            ReverseStep(
                step_number=3,
                current_state="Solution identified",
                required_precondition="Root cause understood",
                action_needed="Formulate solution",
                difficulty=0.5,
            ),
            ReverseStep(
                step_number=4,
                current_state="Root cause identified",
                required_precondition="Problem analyzed",
                action_needed="Diagnose root cause",
                difficulty=0.6,
            ),
            ReverseStep(
                step_number=5,
                current_state="Problem analyzed",
                required_precondition="Problem observed",
                action_needed="Analyze symptoms",
                difficulty=0.7,
            ),
        ]

    def _generate_acquisition_steps(self, goal: str) -> List[ReverseStep]:
        """Generate acquisition/purchase steps."""
        return [
            ReverseStep(
                step_number=1,
                current_state="Item acquired",
                required_precondition="Transaction completed",
                action_needed="Take possession",
                difficulty=0.2,
            ),
            ReverseStep(
                step_number=2,
                current_state="Transaction completed",
                required_precondition="Payment processed",
                action_needed="Finalize transaction",
                difficulty=0.3,
            ),
            ReverseStep(
                step_number=3,
                current_state="Payment ready",
                required_precondition="Item selected",
                action_needed="Process payment",
                difficulty=0.4,
            ),
            ReverseStep(
                step_number=4,
                current_state="Item selected",
                required_precondition="Options evaluated",
                action_needed="Make selection",
                difficulty=0.5,
            ),
            ReverseStep(
                step_number=5,
                current_state="Options evaluated",
                required_precondition="Requirements defined",
                action_needed="Compare options",
                difficulty=0.6,
            ),
        ]

    def _generate_generic_steps(self, goal: str) -> List[ReverseStep]:
        """Generate generic backward steps."""
        return [
            ReverseStep(
                step_number=1,
                current_state=goal,
                required_precondition="Previous milestone achieved",
                action_needed="Complete final step",
                difficulty=0.3,
            ),
            ReverseStep(
                step_number=2,
                current_state="Final milestone",
                required_precondition="Intermediate progress made",
                action_needed="Reach milestone",
                difficulty=0.5,
            ),
            ReverseStep(
                step_number=3,
                current_state="Intermediate state",
                required_precondition="Initial steps taken",
                action_needed="Make progress",
                difficulty=0.6,
            ),
            ReverseStep(
                step_number=4,
                current_state="Started",
                required_precondition="Ready to begin",
                action_needed="Take first step",
                difficulty=0.7,
            ),
        ]

    def _find_starting_point(self, steps: List[ReverseStep]) -> str:
        """
        Find the starting point from backward steps.

        Args:
            steps: Backward reasoning steps

        Returns:
            Starting point string
        """
        if not steps:
            return "Starting point unclear"

        # Last step in backward order is starting point
        last_step = steps[-1] if steps else None
        return last_step.required_precondition if last_step else "Beginning"

    def _create_forward_plan(self, steps: List[ReverseStep]) -> List[str]:
        """
        Create forward plan from backward steps.

        Args:
            steps: Backward reasoning steps

        Returns:
            List of forward plan steps
        """
        forward = []

        # Reverse the backward steps
        for step in reversed(steps):
            if step.action_needed:
                forward.append(step.action_needed)

        return forward

    def _calculate_feasibility(self, steps: List[ReverseStep]) -> float:
        """
        Calculate feasibility score from steps.

        Args:
            steps: Reasoning steps

        Returns:
            Feasibility score 0-1
        """
        if not steps:
            return 0.0

        # Average inverse difficulty (lower difficulty = higher feasibility)
        total_difficulty = sum(s.difficulty for s in steps)
        avg_difficulty = total_difficulty / len(steps)

        # More steps = slightly lower feasibility
        step_factor = max(0.7, 1.0 - len(steps) * 0.03)

        feasibility = (1.0 - avg_difficulty) * step_factor

        return round(max(0.0, min(1.0, feasibility)), 2)
