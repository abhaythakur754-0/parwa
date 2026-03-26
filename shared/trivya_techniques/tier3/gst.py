"""
PARWA TRIVYA Tier 3 - Generated Step-by-step Thought (GST).

GST is a structured reasoning technique that breaks down complex problems
into sequential, verifiable steps. Each step builds upon the previous one,
creating a clear reasoning chain that can be validated and audited.

Key Features:
- Structured thought generation
- Step-by-step reasoning chain
- Verification at each step
- Backtracking capability
- Audit trail for compliance
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class StepStatus(str, Enum):
    """Status of a reasoning step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ThoughtStep(BaseModel):
    """A single step in the reasoning chain."""
    step_number: int = Field(default=0, ge=0)
    description: str
    reasoning: str = ""
    conclusion: str = ""
    status: StepStatus = StepStatus.PENDING
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    dependencies: List[int] = Field(default_factory=list)
    verification_result: Optional[str] = None
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class GSTResult(BaseModel):
    """Result from GST reasoning process."""
    query: str
    steps: List[ThoughtStep] = Field(default_factory=list)
    final_conclusion: str = ""
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning_chain: str = ""  # Full chain as readable text
    total_steps: int = Field(default=0)
    completed_steps: int = Field(default=0)
    failed_steps: int = Field(default=0)
    backtracking_count: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class GSTConfig(BaseModel):
    """Configuration for GST."""
    max_steps: int = Field(default=10, ge=1, le=20)
    min_step_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    enable_backtracking: bool = Field(default=True)
    max_backtracking_attempts: int = Field(default=3)
    verify_each_step: bool = Field(default=True)
    include_reasoning_chain: bool = Field(default=True)
    step_timeout_ms: float = Field(default=5000.0)

    model_config = ConfigDict()


class GeneratedStepByStepThought:
    """
    Generated Step-by-step Thought (GST) technique.

    Produces structured reasoning chains where each step is:
    1. Clearly defined with specific goals
    2. Verified for logical consistency
    3. Connected to previous steps
    4. Capable of being audited

    GST is particularly effective for:
    - Complex problem-solving
    - Multi-step procedures
    - Decision trees
    - Compliance verification
    """

    def __init__(
        self,
        config: Optional[GSTConfig] = None,
        llm_client: Optional[Any] = None,
        verify_fn: Optional[Callable[[str, str], bool]] = None
    ) -> None:
        """
        Initialize GST.

        Args:
            config: Optional configuration override
            llm_client: LLM client for generation
            verify_fn: Optional verification function for steps
        """
        self.config = config or GSTConfig()
        self.llm_client = llm_client
        self.verify_fn = verify_fn

        # Performance tracking
        self._queries_processed = 0
        self._total_steps_generated = 0
        self._total_backtracks = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "gst_initialized",
            "max_steps": self.config.max_steps,
            "enable_backtracking": self.config.enable_backtracking,
        })

    def reason(
        self,
        query: str,
        context: Optional[str] = None,
        constraints: Optional[List[str]] = None
    ) -> GSTResult:
        """
        Generate step-by-step reasoning for a query.

        Args:
            query: The query to reason about
            context: Additional context from T1/T2
            constraints: Optional constraints to follow

        Returns:
            GSTResult with reasoning chain

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()

        result = GSTResult(query=query.strip())

        try:
            # Generate reasoning steps
            steps = self._generate_steps(query, context, constraints)
            result.steps = steps
            result.total_steps = len(steps)

            # Execute each step
            for i, step in enumerate(steps):
                step = self._execute_step(
                    step=step,
                    previous_steps=steps[:i],
                    query=query,
                    context=context
                )
                steps[i] = step

                if step.status == StepStatus.COMPLETED:
                    result.completed_steps += 1
                elif step.status == StepStatus.FAILED:
                    result.failed_steps += 1

                    # Attempt backtracking if enabled
                    if self.config.enable_backtracking:
                        backtrack_result = self._attempt_backtrack(
                            steps, i, query, context
                        )
                        if backtrack_result:
                            steps[i] = backtrack_result
                            result.failed_steps -= 1
                            result.completed_steps += 1
                            result.backtracking_count += 1

            # Generate final conclusion
            result.final_conclusion = self._synthesize_conclusion(steps, query)
            result.overall_confidence = self._calculate_confidence(steps)
            result.reasoning_chain = self._build_reasoning_chain(steps)

        except Exception as e:
            logger.error({
                "event": "gst_reasoning_failed",
                "error": str(e),
            })
            result.metadata["error"] = str(e)

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_steps_generated += result.total_steps
        self._total_backtracks += result.backtracking_count
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "gst_reasoning_complete",
            "total_steps": result.total_steps,
            "completed_steps": result.completed_steps,
            "confidence": result.overall_confidence,
            "backtracking_count": result.backtracking_count,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def generate_steps_only(
        self,
        query: str,
        context: Optional[str] = None
    ) -> List[ThoughtStep]:
        """
        Generate steps without executing them.

        Args:
            query: The query to analyze
            context: Additional context

        Returns:
            List of ThoughtStep (pending status)
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        return self._generate_steps(query.strip(), context, None)

    def execute_step(
        self,
        step: ThoughtStep,
        previous_steps: List[ThoughtStep],
        query: str,
        context: Optional[str] = None
    ) -> ThoughtStep:
        """
        Execute a single reasoning step.

        Args:
            step: The step to execute
            previous_steps: Previously executed steps
            query: Original query
            context: Additional context

        Returns:
            Updated ThoughtStep with results
        """
        return self._execute_step(step, previous_steps, query, context)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get GST statistics.

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
            "total_backtracks": self._total_backtracks,
            "backtrack_rate": (
                self._total_backtracks / self._total_steps_generated
                if self._total_steps_generated > 0 else 0
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
        constraints: Optional[List[str]]
    ) -> List[ThoughtStep]:
        """
        Generate reasoning steps for a query.

        Args:
            query: User query
            context: Additional context
            constraints: Optional constraints

        Returns:
            List of ThoughtStep objects
        """
        steps = []
        query_lower = query.lower()

        # Determine step types based on query characteristics
        if self._is_procedural_query(query_lower):
            steps = self._generate_procedural_steps(query, context)
        elif self._is_decision_query(query_lower):
            steps = self._generate_decision_steps(query, context)
        elif self._is_diagnostic_query(query_lower):
            steps = self._generate_diagnostic_steps(query, context)
        else:
            steps = self._generate_generic_steps(query, context)

        # Apply constraints if provided
        if constraints:
            steps = self._apply_constraints(steps, constraints)

        # Limit to max steps
        steps = steps[:self.config.max_steps]

        # Assign step numbers and dependencies
        for i, step in enumerate(steps):
            step.step_number = i + 1
            if i > 0:
                step.dependencies = [i]

        return steps

    def _execute_step(
        self,
        step: ThoughtStep,
        previous_steps: List[ThoughtStep],
        query: str,
        context: Optional[str]
    ) -> ThoughtStep:
        """
        Execute a single reasoning step.

        Args:
            step: Step to execute
            previous_steps: Previously executed steps
            query: Original query
            context: Additional context

        Returns:
            Updated step with results
        """
        start_time = datetime.now()
        step.status = StepStatus.IN_PROGRESS

        try:
            # Check dependencies
            if step.dependencies:
                dep_results = []
                for dep_num in step.dependencies:
                    dep_step = next(
                        (s for s in previous_steps if s.step_number == dep_num),
                        None
                    )
                    if dep_step and dep_step.status != StepStatus.COMPLETED:
                        step.status = StepStatus.SKIPPED
                        step.verification_result = "Dependency not completed"
                        return step
                    if dep_step:
                        dep_results.append(dep_step.conclusion)

            # Generate reasoning for this step
            step.reasoning = self._generate_step_reasoning(
                step, previous_steps, query, context
            )

            # Generate conclusion
            step.conclusion = self._generate_step_conclusion(
                step, previous_steps, query
            )

            # Verify step if enabled
            if self.config.verify_each_step and self.verify_fn:
                verified = self.verify_fn(step.reasoning, step.conclusion)
                step.verification_result = "verified" if verified else "verification_failed"
                step.confidence = 0.9 if verified else 0.5
            else:
                step.confidence = self._estimate_step_confidence(step, previous_steps)
                step.verification_result = "skipped"

            # Determine status
            if step.confidence >= self.config.min_step_confidence:
                step.status = StepStatus.COMPLETED
            else:
                step.status = StepStatus.FAILED
                step.verification_result = "low_confidence"

        except Exception as e:
            step.status = StepStatus.FAILED
            step.verification_result = f"error: {str(e)}"
            logger.warning({
                "event": "gst_step_failed",
                "step_number": step.step_number,
                "error": str(e),
            })

        step.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        return step

    def _attempt_backtrack(
        self,
        steps: List[ThoughtStep],
        failed_index: int,
        query: str,
        context: Optional[str]
    ) -> Optional[ThoughtStep]:
        """
        Attempt to recover from a failed step.

        Args:
            steps: All steps
            failed_index: Index of failed step
            query: Original query
            context: Additional context

        Returns:
            Recovered step or None
        """
        failed_step = steps[failed_index]

        for attempt in range(self.config.max_backtracking_attempts):
            # Generate alternative reasoning
            alternative = self._generate_alternative_step(
                failed_step, steps[:failed_index], query, context, attempt
            )

            if alternative and alternative.confidence >= self.config.min_step_confidence:
                alternative.status = StepStatus.COMPLETED
                logger.info({
                    "event": "gst_backtrack_success",
                    "step_number": failed_step.step_number,
                    "attempt": attempt + 1,
                })
                return alternative

        self._total_backtracks += 1
        return None

    def _generate_step_reasoning(
        self,
        step: ThoughtStep,
        previous_steps: List[ThoughtStep],
        query: str,
        context: Optional[str]
    ) -> str:
        """Generate reasoning for a step."""
        # Build context from previous steps
        prev_context = ""
        if previous_steps:
            prev_context = "Previous conclusions: " + "; ".join(
                s.conclusion for s in previous_steps if s.conclusion
            )

        # Use LLM if available
        if self.llm_client:
            return self._llm_generate_reasoning(step, prev_context, query, context)

        # Template-based reasoning
        templates = {
            "understand": f"Analyzing the query: '{query[:100]}...' to understand the core issue.",
            "identify": f"Identifying key factors from {len(previous_steps)} previous steps.",
            "analyze": f"Examining the relationship between factors and the query goal.",
            "evaluate": f"Weighing options based on gathered information.",
            "conclude": f"Synthesizing findings to address: {query[:50]}...",
        }

        for key, template in templates.items():
            if key in step.description.lower():
                return template

        return f"Processing step {step.step_number}: {step.description}"

    def _generate_step_conclusion(
        self,
        step: ThoughtStep,
        previous_steps: List[ThoughtStep],
        query: str
    ) -> str:
        """Generate conclusion for a step."""
        # Use LLM if available
        if self.llm_client:
            return self._llm_generate_conclusion(step, previous_steps, query)

        # Template-based conclusion
        if step.step_number == 1:
            return f"Initial analysis complete for: {query[:50]}..."
        elif previous_steps:
            last_conclusion = previous_steps[-1].conclusion if previous_steps else ""
            return f"Based on {last_conclusion[:30]}..., proceeding with analysis."
        else:
            return f"Step {step.step_number} conclusion: Analysis ongoing."

    def _llm_generate_reasoning(
        self,
        step: ThoughtStep,
        prev_context: str,
        query: str,
        context: Optional[str]
    ) -> str:
        """Use LLM to generate reasoning."""
        # Placeholder for LLM integration
        # In production, this would call the LLM client
        return f"LLM-generated reasoning for step {step.step_number}"

    def _llm_generate_conclusion(
        self,
        step: ThoughtStep,
        previous_steps: List[ThoughtStep],
        query: str
    ) -> str:
        """Use LLM to generate conclusion."""
        # Placeholder for LLM integration
        return f"LLM-generated conclusion for step {step.step_number}"

    def _generate_alternative_step(
        self,
        failed_step: ThoughtStep,
        previous_steps: List[ThoughtStep],
        query: str,
        context: Optional[str],
        attempt: int
    ) -> Optional[ThoughtStep]:
        """Generate an alternative approach for a failed step."""
        alternative = ThoughtStep(
            step_number=failed_step.step_number,
            description=f"Alternative approach {attempt + 1}: {failed_step.description}",
            dependencies=failed_step.dependencies.copy(),
            metadata={"is_alternative": True, "attempt": attempt + 1}
        )

        alternative.reasoning = self._generate_step_reasoning(
            alternative, previous_steps, query, context
        )
        alternative.conclusion = self._generate_step_conclusion(
            alternative, previous_steps, query
        )
        alternative.confidence = self._estimate_step_confidence(alternative, previous_steps)

        return alternative

    def _estimate_step_confidence(
        self,
        step: ThoughtStep,
        previous_steps: List[ThoughtStep]
    ) -> float:
        """Estimate confidence for a step."""
        base_confidence = 0.7

        # Adjust based on reasoning quality
        if len(step.reasoning) > 50:
            base_confidence += 0.1
        if len(step.conclusion) > 20:
            base_confidence += 0.05

        # Adjust based on dependency completion
        if step.dependencies:
            completed_deps = sum(
                1 for s in previous_steps
                if s.step_number in step.dependencies and s.status == StepStatus.COMPLETED
            )
            dep_rate = completed_deps / len(step.dependencies)
            base_confidence *= dep_rate

        return min(1.0, base_confidence)

    def _synthesize_conclusion(
        self,
        steps: List[ThoughtStep],
        query: str
    ) -> str:
        """Synthesize final conclusion from all steps."""
        completed = [s for s in steps if s.status == StepStatus.COMPLETED]

        if not completed:
            return "Unable to reach conclusion - no steps completed successfully."

        conclusions = [s.conclusion for s in completed if s.conclusion]

        if len(conclusions) == 1:
            return conclusions[0]

        return f"After {len(completed)} reasoning steps: {'; '.join(conclusions[-3:])}"

    def _calculate_confidence(self, steps: List[ThoughtStep]) -> float:
        """Calculate overall confidence from steps."""
        if not steps:
            return 0.0

        completed = [s for s in steps if s.status == StepStatus.COMPLETED]
        if not completed:
            return 0.0

        # Weighted average of completed steps
        total_confidence = sum(s.confidence for s in completed)
        avg_confidence = total_confidence / len(completed)

        # Penalty for failed/skipped steps
        failure_rate = (len(steps) - len(completed)) / len(steps)
        adjusted_confidence = avg_confidence * (1 - failure_rate * 0.5)

        return min(1.0, max(0.0, adjusted_confidence))

    def _build_reasoning_chain(self, steps: List[ThoughtStep]) -> str:
        """Build readable reasoning chain."""
        chain_parts = []

        for step in steps:
            if step.status == StepStatus.COMPLETED:
                chain_parts.append(
                    f"Step {step.step_number}: {step.description}\n"
                    f"  Reasoning: {step.reasoning[:100]}...\n"
                    f"  Conclusion: {step.conclusion}"
                )
            elif step.status == StepStatus.FAILED:
                chain_parts.append(
                    f"Step {step.step_number}: FAILED - {step.verification_result}"
                )

        return "\n\n".join(chain_parts)

    def _is_procedural_query(self, query: str) -> bool:
        """Check if query is procedural."""
        patterns = ["how do i", "how to", "steps", "process", "procedure"]
        return any(p in query for p in patterns)

    def _is_decision_query(self, query: str) -> bool:
        """Check if query is decision-making."""
        patterns = ["should i", "which", "choose", "decide", "better"]
        return any(p in query for p in patterns)

    def _is_diagnostic_query(self, query: str) -> bool:
        """Check if query is diagnostic."""
        patterns = ["why is", "what's wrong", "not working", "error", "problem"]
        return any(p in query for p in patterns)

    def _generate_procedural_steps(
        self,
        query: str,
        context: Optional[str]
    ) -> List[ThoughtStep]:
        """Generate procedural steps."""
        return [
            ThoughtStep(description="Understand the goal of the procedure"),
            ThoughtStep(description="Identify prerequisites and requirements"),
            ThoughtStep(description="Break down into sequential actions"),
            ThoughtStep(description="Order steps logically"),
            ThoughtStep(description="Verify completeness of procedure"),
            ThoughtStep(description="Generate final step-by-step guide"),
        ]

    def _generate_decision_steps(
        self,
        query: str,
        context: Optional[str]
    ) -> List[ThoughtStep]:
        """Generate decision-making steps."""
        return [
            ThoughtStep(description="Identify the decision to be made"),
            ThoughtStep(description="List available options"),
            ThoughtStep(description="Define evaluation criteria"),
            ThoughtStep(description="Evaluate each option against criteria"),
            ThoughtStep(description="Compare options and trade-offs"),
            ThoughtStep(description="Recommend best option with reasoning"),
        ]

    def _generate_diagnostic_steps(
        self,
        query: str,
        context: Optional[str]
    ) -> List[ThoughtStep]:
        """Generate diagnostic steps."""
        return [
            ThoughtStep(description="Identify symptoms and problem description"),
            ThoughtStep(description="Gather relevant information"),
            ThoughtStep(description="Generate potential causes"),
            ThoughtStep(description="Test and eliminate causes"),
            ThoughtStep(description="Identify root cause"),
            ThoughtStep(description="Propose solution"),
        ]

    def _generate_generic_steps(
        self,
        query: str,
        context: Optional[str]
    ) -> List[ThoughtStep]:
        """Generate generic reasoning steps."""
        return [
            ThoughtStep(description="Analyze the query structure"),
            ThoughtStep(description="Identify key components and entities"),
            ThoughtStep(description="Determine relevant information"),
            ThoughtStep(description="Apply reasoning to components"),
            ThoughtStep(description="Synthesize findings"),
            ThoughtStep(description="Formulate response"),
        ]

    def _apply_constraints(
        self,
        steps: List[ThoughtStep],
        constraints: List[str]
    ) -> List[ThoughtStep]:
        """Apply constraints to steps."""
        # Add constraint verification steps
        for constraint in constraints:
            steps.append(ThoughtStep(
                description=f"Verify constraint: {constraint}",
                metadata={"is_constraint": True, "constraint": constraint}
            ))

        return steps
