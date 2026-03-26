"""
PARWA TRIVYA Tier 2 Chain of Thought Technique.

Implements step-by-step reasoning for complex problems.
Produces structured reasoning chains that lead to answers.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ReasoningStep(BaseModel):
    """Single step in a reasoning chain."""
    step_number: int = Field(ge=1)
    thought: str
    conclusion: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class CoTResult(BaseModel):
    """Result from Chain of Thought processing."""
    query: str
    steps: List[ReasoningStep] = Field(default_factory=list)
    final_answer: str = ""
    total_steps: int = Field(default=0)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class CoTConfig(BaseModel):
    """Configuration for Chain of Thought."""
    max_steps: int = Field(default=8, ge=1, le=15)
    min_steps: int = Field(default=2, ge=1)
    include_intermediate_conclusions: bool = Field(default=True)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    show_work: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class ChainOfThought:
    """
    Chain of Thought technique for TRIVYA Tier 2.

    Produces step-by-step reasoning chains that break down complex
    problems into manageable steps, leading to well-reasoned answers.

    Features:
    - Structured reasoning steps
    - Intermediate conclusions
    - Confidence tracking per step
    - Configurable depth
    """

    def __init__(
        self,
        config: Optional[CoTConfig] = None,
        llm_client: Optional[Any] = None
    ) -> None:
        """
        Initialize Chain of Thought.

        Args:
            config: CoT configuration
            llm_client: LLM client for generation
        """
        self.config = config or CoTConfig()
        self.llm_client = llm_client

        # Performance tracking
        self._queries_processed = 0
        self._total_steps_generated = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "chain_of_thought_initialized",
            "max_steps": self.config.max_steps,
        })

    def reason(
        self,
        query: str,
        context: Optional[str] = None,
        max_steps: Optional[int] = None
    ) -> CoTResult:
        """
        Apply chain of thought reasoning to a query.

        Args:
            query: User query text
            context: Optional context from T1
            max_steps: Override max steps

        Returns:
            CoTResult with reasoning steps

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()
        max_steps = max_steps or self.config.max_steps

        # Generate reasoning steps
        steps = self._generate_steps(query, context, max_steps)

        # Build final answer from steps
        final_answer = self._synthesize_answer(query, steps)

        # Calculate overall confidence
        overall_confidence = self._calculate_confidence(steps)

        result = CoTResult(
            query=query,
            steps=steps,
            final_answer=final_answer,
            total_steps=len(steps),
            overall_confidence=overall_confidence,
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_steps_generated += len(steps)
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "chain_of_thought_complete",
            "total_steps": len(steps),
            "confidence": overall_confidence,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def generate_prompt(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a CoT prompt for an LLM.

        Args:
            query: User query
            context: Optional context

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Think through this step by step.",
            "",
            f"Question: {query}",
        ]

        if context:
            prompt_parts.append(f"\nContext: {context}")

        prompt_parts.extend([
            "",
            "Show your reasoning step by step:",
            "Step 1: [First thought]",
            "Step 2: [Build on previous step]",
            "...",
            "Final Answer: [Your conclusion]",
        ])

        return "\n".join(prompt_parts)

    def parse_response(
        self,
        response: str,
        query: str
    ) -> CoTResult:
        """
        Parse an LLM response into structured CoT result.

        Args:
            response: LLM response text
            query: Original query

        Returns:
            CoTResult with parsed steps
        """
        start_time = datetime.now()

        steps = []
        current_step = None
        step_number = 0
        final_answer = ""

        lines = response.split("\n")

        for line in lines:
            line = line.strip()

            # Detect step markers
            if line.lower().startswith("step "):
                # Save previous step
                if current_step:
                    steps.append(current_step)

                step_number += 1
                # Extract thought after step marker
                thought = line.split(":", 1)[-1].strip() if ":" in line else ""
                current_step = ReasoningStep(
                    step_number=step_number,
                    thought=thought,
                )

            elif line.lower().startswith("final answer"):
                if current_step:
                    steps.append(current_step)
                final_answer = line.split(":", 1)[-1].strip() if ":" in line else ""
                break

            elif current_step:
                # Append to current step's thought
                current_step.thought += " " + line

        # Add last step if not added
        if current_step and current_step not in steps:
            steps.append(current_step)

        # If no steps detected, create default
        if not steps:
            steps.append(ReasoningStep(
                step_number=1,
                thought=response[:500],
                confidence=0.5,
            ))
            final_answer = response[:500]

        overall_confidence = self._calculate_confidence(steps)

        result = CoTResult(
            query=query,
            steps=steps,
            final_answer=final_answer,
            total_steps=len(steps),
            overall_confidence=overall_confidence,
        )

        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Chain of Thought statistics.

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

    def _generate_steps(
        self,
        query: str,
        context: Optional[str],
        max_steps: int
    ) -> List[ReasoningStep]:
        """
        Generate reasoning steps.

        Args:
            query: User query
            context: Optional context
            max_steps: Maximum steps

        Returns:
            List of ReasoningStep
        """
        # This is a heuristic step generator for testing
        # In production, this would call an LLM

        steps = []

        # Analyze query type
        query_lower = query.lower()

        if any(w in query_lower for w in ["compare", "difference", "vs", "versus"]):
            steps = self._generate_comparison_steps(query, max_steps)
        elif any(w in query_lower for w in ["how to", "how do i", "steps"]):
            steps = self._generate_procedural_steps(query, max_steps)
        elif any(w in query_lower for w in ["why", "explain", "reason"]):
            steps = self._generate_explanation_steps(query, max_steps)
        else:
            steps = self._generate_generic_steps(query, max_steps)

        return steps[:max_steps]

    def _generate_comparison_steps(
        self,
        query: str,
        max_steps: int
    ) -> List[ReasoningStep]:
        """Generate comparison reasoning steps."""
        steps = [
            ReasoningStep(
                step_number=1,
                thought="Identify the options being compared",
                confidence=0.9,
            ),
            ReasoningStep(
                step_number=2,
                thought="List key attributes of each option",
                confidence=0.85,
            ),
            ReasoningStep(
                step_number=3,
                thought="Compare attributes systematically",
                confidence=0.8,
            ),
            ReasoningStep(
                step_number=4,
                thought="Evaluate trade-offs between options",
                confidence=0.75,
            ),
            ReasoningStep(
                step_number=5,
                thought="Determine which option best fits the needs",
                confidence=0.7,
            ),
        ]
        return steps[:max_steps]

    def _generate_procedural_steps(
        self,
        query: str,
        max_steps: int
    ) -> List[ReasoningStep]:
        """Generate procedural reasoning steps."""
        steps = [
            ReasoningStep(
                step_number=1,
                thought="Identify the end goal or desired outcome",
                confidence=0.9,
            ),
            ReasoningStep(
                step_number=2,
                thought="Determine prerequisites and requirements",
                confidence=0.85,
            ),
            ReasoningStep(
                step_number=3,
                thought="Outline the sequence of actions needed",
                confidence=0.8,
            ),
            ReasoningStep(
                step_number=4,
                thought="Identify potential obstacles and solutions",
                confidence=0.75,
            ),
            ReasoningStep(
                step_number=5,
                thought="Verify the complete process achieves the goal",
                confidence=0.7,
            ),
        ]
        return steps[:max_steps]

    def _generate_explanation_steps(
        self,
        query: str,
        max_steps: int
    ) -> List[ReasoningStep]:
        """Generate explanation reasoning steps."""
        steps = [
            ReasoningStep(
                step_number=1,
                thought="Identify the core concept or phenomenon",
                confidence=0.9,
            ),
            ReasoningStep(
                step_number=2,
                thought="Examine the underlying causes or mechanisms",
                confidence=0.85,
            ),
            ReasoningStep(
                step_number=3,
                thought="Consider relevant examples or analogies",
                confidence=0.8,
            ),
            ReasoningStep(
                step_number=4,
                thought="Connect to broader context or implications",
                confidence=0.75,
            ),
        ]
        return steps[:max_steps]

    def _generate_generic_steps(
        self,
        query: str,
        max_steps: int
    ) -> List[ReasoningStep]:
        """Generate generic reasoning steps."""
        steps = [
            ReasoningStep(
                step_number=1,
                thought="Understand what is being asked",
                confidence=0.9,
            ),
            ReasoningStep(
                step_number=2,
                thought="Identify relevant information and constraints",
                confidence=0.85,
            ),
            ReasoningStep(
                step_number=3,
                thought="Consider possible approaches or solutions",
                confidence=0.8,
            ),
            ReasoningStep(
                step_number=4,
                thought="Evaluate and select the best approach",
                confidence=0.75,
            ),
            ReasoningStep(
                step_number=5,
                thought="Formulate the answer based on reasoning",
                confidence=0.7,
            ),
        ]
        return steps[:max_steps]

    def _synthesize_answer(
        self,
        query: str,
        steps: List[ReasoningStep]
    ) -> str:
        """
        Synthesize final answer from steps.

        Args:
            query: Original query
            steps: Reasoning steps

        Returns:
            Synthesized answer
        """
        if not steps:
            return "Unable to determine answer through reasoning."

        # Build answer from step conclusions
        conclusions = []
        for step in steps:
            if step.conclusion:
                conclusions.append(step.conclusion)

        if conclusions:
            return " ".join(conclusions)

        # Use last step as answer
        return f"Based on {len(steps)} reasoning steps: {steps[-1].thought}"

    def _calculate_confidence(
        self,
        steps: List[ReasoningStep]
    ) -> float:
        """
        Calculate overall confidence from steps.

        Args:
            steps: Reasoning steps

        Returns:
            Confidence score 0-1
        """
        if not steps:
            return 0.0

        # Weighted average with later steps weighted less
        total_weight = 0.0
        weighted_sum = 0.0

        for i, step in enumerate(steps):
            weight = 1.0 - (i * 0.1)  # Decreasing weight
            weighted_sum += step.confidence * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0
