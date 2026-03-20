"""
PARWA TRIVYA Tier 3 - Reflexion.

Reflexion is a self-improvement technique that uses reflection loops
to critique and improve previous reasoning. It generates feedback on
failures and uses that feedback to produce better solutions.

Key Features:
- Self-critique and reflection
- Failure analysis
- Iterative improvement
- Learning from mistakes
- Memory of past reflections
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ReflectionStatus(str, Enum):
    """Status of a reflection iteration."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    IMPROVING = "improving"
    SATISFIED = "satisfied"
    MAX_ITERATIONS = "max_iterations"
    FAILED = "failed"


class ReflectionIteration(BaseModel):
    """A single reflection iteration."""
    iteration: int = Field(ge=1)
    initial_answer: str = ""
    critique: str = ""
    improvements: List[str] = Field(default_factory=list)
    refined_answer: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_improvement: float = Field(default=0.0)
    status: ReflectionStatus = ReflectionStatus.PENDING
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class ReflexionResult(BaseModel):
    """Result from Reflexion process."""
    query: str
    iterations: List[ReflectionIteration] = Field(default_factory=list)
    total_iterations: int = Field(default=0, ge=0)
    initial_answer: str = ""
    final_answer: str = ""
    final_score: float = Field(default=0.0, ge=0.0, le=1.0)
    total_improvement: float = Field(default=0.0)
    converged: bool = False
    convergence_reason: str = ""
    lessons_learned: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class ReflexionConfig(BaseModel):
    """Configuration for Reflexion."""
    max_iterations: int = Field(default=3, ge=1, le=5)
    min_score_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    min_improvement_threshold: float = Field(default=0.05, ge=0.0, le=0.5)
    enable_memory: bool = Field(default=True)
    critique_aspects: List[str] = Field(default_factory=lambda: [
        "accuracy", "completeness", "clarity", "relevance"
    ])
    early_stopping: bool = Field(default=True)

    model_config = ConfigDict()


class Reflexion:
    """
    Reflexion technique.

    Uses self-reflection to iteratively improve reasoning:
    1. Generate initial answer
    2. Critique the answer for weaknesses
    3. Generate improvements based on critique
    4. Refine answer with improvements
    5. Repeat until satisfied or max iterations

    Effective for:
    - Complex problems requiring quality
    - Situations where initial attempts fail
    - Learning from mistakes
    - High-stakes decisions
    """

    def __init__(
        self,
        config: Optional[ReflexionConfig] = None,
        llm_client: Optional[Any] = None,
        scorer: Optional[Callable[[str, str], float]] = None
    ) -> None:
        """
        Initialize Reflexion.

        Args:
            config: Optional configuration override
            llm_client: LLM client for generation
            scorer: Optional scoring function
        """
        self.config = config or ReflexionConfig()
        self.llm_client = llm_client
        self.scorer = scorer

        # Memory for learned lessons
        self._memory: List[str] = []

        # Performance tracking
        self._queries_processed = 0
        self._total_iterations = 0
        self._converged_count = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "reflexion_initialized",
            "max_iterations": self.config.max_iterations,
            "min_score_threshold": self.config.min_score_threshold,
        })

    def reason(
        self,
        query: str,
        context: Optional[str] = None,
        initial_answer: Optional[str] = None
    ) -> ReflexionResult:
        """
        Apply reflexion to improve reasoning for a query.

        Args:
            query: The query to reason about
            context: Additional context from T1/T2
            initial_answer: Optional starting answer

        Returns:
            ReflexionResult with improved answer

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()

        result = ReflexionResult(query=query.strip())

        try:
            # Generate initial answer if not provided
            if initial_answer:
                result.initial_answer = initial_answer
            else:
                result.initial_answer = self._generate_initial_answer(query, context)

            current_answer = result.initial_answer
            current_score = self._score_answer(current_answer, query)
            previous_score = 0.0

            # Reflection loop
            for i in range(self.config.max_iterations):
                iteration = self._run_iteration(
                    iteration_num=i + 1,
                    current_answer=current_answer,
                    current_score=current_score,
                    query=query,
                    context=context
                )

                result.iterations.append(iteration)
                result.total_iterations += 1
                self._total_iterations += 1

                # Check for convergence
                if iteration.status == ReflectionStatus.SATISFIED:
                    result.converged = True
                    result.convergence_reason = "Score threshold reached"
                    current_answer = iteration.refined_answer
                    current_score = iteration.score
                    break

                # Check for early stopping (no improvement)
                improvement = iteration.score - previous_score
                if (self.config.early_stopping and
                    i > 0 and improvement < self.config.min_improvement_threshold):
                    result.converged = False
                    result.convergence_reason = "Minimal improvement detected"
                    break

                current_answer = iteration.refined_answer
                current_score = iteration.score
                previous_score = current_score

            # Check if max iterations reached
            if not result.converged and result.total_iterations >= self.config.max_iterations:
                result.convergence_reason = "Maximum iterations reached"

            # Finalize
            result.final_answer = current_answer
            result.final_score = current_score
            result.total_improvement = current_score - self._score_answer(
                result.initial_answer, query
            )

            # Extract lessons learned
            result.lessons_learned = self._extract_lessons(result.iterations)

            # Add to memory if enabled
            if self.config.enable_memory:
                self._memory.extend(result.lessons_learned[:3])

            # Calculate confidence
            result.confidence = self._calculate_confidence(result)

        except Exception as e:
            logger.error({
                "event": "reflexion_failed",
                "error": str(e),
            })
            result.metadata["error"] = str(e)

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        if result.converged:
            self._converged_count += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "reflexion_complete",
            "total_iterations": result.total_iterations,
            "converged": result.converged,
            "final_score": result.final_score,
            "total_improvement": result.total_improvement,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def get_memory(self) -> List[str]:
        """
        Get accumulated lessons from reflection memory.

        Returns:
            List of learned lessons
        """
        return self._memory.copy()

    def clear_memory(self) -> None:
        """Clear reflection memory."""
        self._memory.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Reflexion statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_iterations": self._total_iterations,
            "average_iterations_per_query": (
                self._total_iterations / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "convergence_rate": (
                self._converged_count / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "memory_size": len(self._memory),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _generate_initial_answer(
        self,
        query: str,
        context: Optional[str]
    ) -> str:
        """Generate initial answer for query."""
        if self.llm_client:
            return self._llm_generate_answer(query, context)

        # Template-based initial answer
        return f"Initial analysis suggests addressing the core aspects of: {query[:100]}..."

    def _run_iteration(
        self,
        iteration_num: int,
        current_answer: str,
        current_score: float,
        query: str,
        context: Optional[str]
    ) -> ReflectionIteration:
        """
        Run a single reflection iteration.

        Args:
            iteration_num: Current iteration number
            current_answer: Current answer
            current_score: Current score
            query: Original query
            context: Additional context

        Returns:
            ReflectionIteration with results
        """
        start_time = datetime.now()

        iteration = ReflectionIteration(
            iteration=iteration_num,
            initial_answer=current_answer,
            status=ReflectionStatus.ANALYZING
        )

        try:
            # Step 1: Generate critique
            iteration.critique = self._generate_critique(
                current_answer, query, iteration_num
            )

            # Step 2: Identify improvements
            iteration.improvements = self._identify_improvements(
                iteration.critique, current_answer
            )

            iteration.status = ReflectionStatus.IMPROVING

            # Step 3: Generate refined answer
            iteration.refined_answer = self._refine_answer(
                current_answer, iteration.improvements, query
            )

            # Step 4: Score refined answer
            iteration.score = self._score_answer(iteration.refined_answer, query)
            iteration.score_improvement = iteration.score - current_score

            # Step 5: Check if satisfied
            if iteration.score >= self.config.min_score_threshold:
                iteration.status = ReflectionStatus.SATISFIED
            else:
                iteration.status = ReflectionStatus.PENDING

        except Exception as e:
            iteration.status = ReflectionStatus.FAILED
            iteration.metadata["error"] = str(e)
            iteration.refined_answer = current_answer
            iteration.score = current_score

        iteration.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        return iteration

    def _generate_critique(
        self,
        answer: str,
        query: str,
        iteration: int
    ) -> str:
        """
        Generate critique of current answer.

        Args:
            answer: Current answer
            query: Original query
            iteration: Current iteration number

        Returns:
            Critique string
        """
        if self.llm_client:
            return self._llm_generate_critique(answer, query)

        # Template-based critique
        aspects = self.config.critique_aspects
        critiques = []

        for aspect in aspects:
            if aspect == "accuracy":
                critiques.append(
                    f"The answer may not fully address all aspects of the query."
                )
            elif aspect == "completeness":
                critiques.append(
                    f"Some important considerations may be missing from the response."
                )
            elif aspect == "clarity":
                critiques.append(
                    f"The explanation could be clearer and more structured."
                )
            elif aspect == "relevance":
                critiques.append(
                    f"Ensure all parts of the response directly relate to the query."
                )

        return f"Iteration {iteration} critique: " + " ".join(critiques[:2])

    def _identify_improvements(
        self,
        critique: str,
        current_answer: str
    ) -> List[str]:
        """
        Identify specific improvements based on critique.

        Args:
            critique: Generated critique
            current_answer: Current answer

        Returns:
            List of improvement suggestions
        """
        improvements = []

        # Check for common issues
        if "missing" in critique.lower() or "incomplete" in critique.lower():
            improvements.append("Add more comprehensive coverage of the topic")

        if "clarity" in critique.lower() or "clearer" in critique.lower():
            improvements.append("Restructure answer for better readability")

        if "accuracy" in critique.lower():
            improvements.append("Verify facts and provide more precise information")

        if "relevance" in critique.lower():
            improvements.append("Focus more directly on the query's intent")

        # Add general improvements if none found
        if not improvements:
            improvements = [
                "Add supporting details and examples",
                "Strengthen the conclusion",
                "Consider edge cases",
            ]

        return improvements[:3]  # Limit to 3 improvements

    def _refine_answer(
        self,
        current_answer: str,
        improvements: List[str],
        query: str
    ) -> str:
        """
        Refine answer based on improvements.

        Args:
            current_answer: Current answer
            improvements: List of improvements
            query: Original query

        Returns:
            Refined answer
        """
        if self.llm_client:
            return self._llm_refine_answer(current_answer, improvements, query)

        # Template-based refinement
        improvement_text = "; ".join(improvements)
        refined = f"Refined answer: {current_answer}"

        if improvements:
            refined += f" [Applied improvements: {improvement_text}]"

        return refined

    def _score_answer(self, answer: str, query: str) -> float:
        """
        Score an answer's quality.

        Args:
            answer: Answer to score
            query: Original query

        Returns:
            Score (0.0-1.0)
        """
        if self.scorer:
            return self.scorer(answer, query)

        # Heuristic scoring
        score = 0.5  # Base score

        # Check length (too short = incomplete, too long = unfocused)
        length = len(answer)
        if 50 <= length <= 500:
            score += 0.2
        elif 20 <= length < 50 or 500 < length <= 1000:
            score += 0.1

        # Check for structure
        if any(marker in answer.lower() for marker in ["first", "second", "finally"]):
            score += 0.1

        # Check for completeness indicators
        if any(marker in answer.lower() for marker in ["in conclusion", "to summarize", "therefore"]):
            score += 0.1

        # Check for specificity
        if any(marker in answer for marker in ["specifically", "for example", "such as"]):
            score += 0.1

        return min(1.0, score)

    def _extract_lessons(self, iterations: List[ReflectionIteration]) -> List[str]:
        """
        Extract lessons learned from iterations.

        Args:
            iterations: List of reflection iterations

        Returns:
            List of lessons
        """
        lessons = []

        for iteration in iterations:
            if iteration.improvements:
                # Convert improvements to lessons
                for improvement in iteration.improvements:
                    lesson = f"Learned: {improvement.lower()}"
                    if lesson not in lessons:
                        lessons.append(lesson)

        return lessons[:5]  # Limit to 5 lessons

    def _calculate_confidence(self, result: ReflexionResult) -> float:
        """
        Calculate overall confidence from result.

        Args:
            result: Reflexion result

        Returns:
            Confidence score
        """
        # Base on final score
        confidence = result.final_score

        # Adjust for convergence
        if result.converged:
            confidence = min(1.0, confidence + 0.1)

        # Adjust for improvement
        if result.total_improvement > 0.2:
            confidence = min(1.0, confidence + 0.05)

        # Adjust for iterations (more iterations = more refined)
        if result.total_iterations >= 2:
            confidence = min(1.0, confidence + 0.05)

        return confidence

    def _llm_generate_answer(self, query: str, context: Optional[str]) -> str:
        """Use LLM to generate answer."""
        return f"LLM-generated answer for: {query[:50]}..."

    def _llm_generate_critique(self, answer: str, query: str) -> str:
        """Use LLM to generate critique."""
        return f"LLM critique of answer regarding: {query[:30]}..."

    def _llm_refine_answer(
        self,
        answer: str,
        improvements: List[str],
        query: str
    ) -> str:
        """Use LLM to refine answer."""
        return f"LLM-refined answer with {len(improvements)} improvements"
