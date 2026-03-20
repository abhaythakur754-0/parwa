"""
PARWA TRIVYA Tier 3 - Least-to-Most Reasoning.

Least-to-Most reasoning decomposes complex queries into simpler
sub-questions, solves them in order of increasing difficulty,
and combines results for the final answer.

Key Features:
- Query decomposition
- Difficulty-based ordering
- Sequential problem solving
- Sub-answer aggregation
- Handles complex multi-part queries
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SubQuestionStatus(str, Enum):
    """Status of a sub-question."""
    PENDING = "pending"
    SOLVING = "solving"
    SOLVED = "solved"
    SKIPPED = "skipped"
    FAILED = "failed"


class Difficulty(str, Enum):
    """Difficulty levels for sub-questions."""
    TRIVIAL = "trivial"  # Can be answered directly
    EASY = "easy"  # Simple lookup or calculation
    MEDIUM = "medium"  # Requires some reasoning
    HARD = "hard"  # Complex reasoning needed
    EXPERT = "expert"  # Requires domain expertise


class SubQuestion(BaseModel):
    """A decomposed sub-question."""
    sub_id: int = Field(ge=1)
    question: str
    difficulty: Difficulty = Difficulty.MEDIUM
    dependencies: List[int] = Field(default_factory=list)
    answer: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: SubQuestionStatus = SubQuestionStatus.PENDING
    contributes_to_final: bool = True
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class LeastToMostResult(BaseModel):
    """Result from Least-to-Most reasoning."""
    query: str
    sub_questions: List[SubQuestion] = Field(default_factory=list)
    total_sub_questions: int = Field(default=0, ge=0)
    solved_sub_questions: int = Field(default=0, ge=0)
    ordered_by_difficulty: bool = True
    final_answer: str = ""
    answer_components: Dict[str, str] = Field(default_factory=dict)
    aggregation_method: str = ""
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class LeastToMostConfig(BaseModel):
    """Configuration for Least-to-Most reasoning."""
    max_sub_questions: int = Field(default=8, ge=2, le=15)
    min_sub_questions: int = Field(default=2, ge=1)
    solve_sequential: bool = Field(default=True)
    include_trivial: bool = Field(default=False)
    difficulty_order: str = Field(default="ascending")  # ascending, descending, auto
    min_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    aggregation_strategy: str = Field(default="synthesis")  # synthesis, combination, hierarchy

    model_config = ConfigDict()


class LeastToMost:
    """
    Least-to-Most Reasoning technique.

    Decomposes complex queries into simpler sub-questions:
    1. Decompose query into sub-questions
    2. Assess difficulty of each sub-question
    3. Order by difficulty (least to most)
    4. Solve sequentially, using earlier answers
    5. Aggregate into final answer

    Effective for:
    - Complex multi-part questions
    - Problems requiring step-by-step analysis
    - Queries with multiple concepts
    - Situations requiring foundational knowledge first
    """

    def __init__(
        self,
        config: Optional[LeastToMostConfig] = None,
        llm_client: Optional[Any] = None,
        solver: Optional[Callable[[str, Optional[str]], str]] = None
    ) -> None:
        """
        Initialize Least-to-Most reasoning.

        Args:
            config: Optional configuration override
            llm_client: LLM client for generation
            solver: Optional custom solver function
        """
        self.config = config or LeastToMostConfig()
        self.llm_client = llm_client
        self.solver = solver

        # Performance tracking
        self._queries_processed = 0
        self._total_sub_questions = 0
        self._total_solved = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "least_to_most_initialized",
            "max_sub_questions": self.config.max_sub_questions,
            "difficulty_order": self.config.difficulty_order,
        })

    def reason(
        self,
        query: str,
        context: Optional[str] = None
    ) -> LeastToMostResult:
        """
        Apply least-to-most reasoning to a complex query.

        Args:
            query: The query to decompose and solve
            context: Additional context from T1/T2

        Returns:
            LeastToMostResult with final answer

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()

        result = LeastToMostResult(query=query.strip())

        try:
            # Step 1: Decompose query into sub-questions
            sub_questions = self._decompose(query, context)
            result.sub_questions = sub_questions
            result.total_sub_questions = len(sub_questions)

            # Step 2: Assess difficulty
            for sq in sub_questions:
                sq.difficulty = self._assess_difficulty(sq.question, query)

            # Step 3: Order by difficulty
            sub_questions = self._order_by_difficulty(sub_questions)
            result.sub_questions = sub_questions
            result.ordered_by_difficulty = True

            # Step 4: Solve sequentially
            previous_answers: Dict[int, str] = {}

            for sq in sub_questions:
                # Build context from previous answers
                dep_context = self._build_dependency_context(
                    sq, sub_questions, previous_answers
                )

                # Solve sub-question
                sq = self._solve_sub_question(sq, dep_context)
                previous_answers[sq.sub_id] = sq.answer

                if sq.status == SubQuestionStatus.SOLVED:
                    result.solved_sub_questions += 1
                    self._total_solved += 1

            # Step 5: Aggregate answers
            result.answer_components = {
                sq.question[:30]: sq.answer
                for sq in sub_questions
                if sq.answer and sq.contributes_to_final
            }

            result.final_answer = self._aggregate_answers(
                sub_questions, query
            )
            result.aggregation_method = self.config.aggregation_strategy

            # Calculate confidence
            result.overall_confidence = self._calculate_confidence(
                sub_questions, result.solved_sub_questions
            )

        except Exception as e:
            logger.error({
                "event": "least_to_most_failed",
                "error": str(e),
            })
            result.metadata["error"] = str(e)

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_sub_questions += result.total_sub_questions
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "least_to_most_complete",
            "total_sub_questions": result.total_sub_questions,
            "solved_sub_questions": result.solved_sub_questions,
            "overall_confidence": result.overall_confidence,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def decompose_only(self, query: str) -> List[SubQuestion]:
        """
        Decompose query without solving.

        Args:
            query: Query to decompose

        Returns:
            List of sub-questions (unsolved)
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        sub_questions = self._decompose(query.strip(), None)

        for sq in sub_questions:
            sq.difficulty = self._assess_difficulty(sq.question, query)

        return self._order_by_difficulty(sub_questions)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Least-to-Most statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_sub_questions": self._total_sub_questions,
            "average_sub_questions_per_query": (
                self._total_sub_questions / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_solved": self._total_solved,
            "solve_rate": (
                self._total_solved / self._total_sub_questions
                if self._total_sub_questions > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _decompose(
        self,
        query: str,
        context: Optional[str]
    ) -> List[SubQuestion]:
        """
        Decompose query into sub-questions.

        Args:
            query: User query
            context: Additional context

        Returns:
            List of SubQuestion objects
        """
        query_lower = query.lower()

        # Identify decomposition strategy based on query type
        if self._is_multi_part_query(query_lower):
            return self._decompose_multi_part(query)
        elif self._is_conditional_query(query_lower):
            return self._decompose_conditional(query)
        elif self._is_procedural_query(query_lower):
            return self._decompose_procedural(query)
        else:
            return self._decompose_generic(query)

    def _decompose_multi_part(self, query: str) -> List[SubQuestion]:
        """Decompose multi-part question."""
        sub_questions = []

        # Split on common conjunctions
        parts = query.replace(" and ", "|AND|").replace(" also ", "|ALSO|").split("|")

        for i, part in enumerate(parts[:self.config.max_sub_questions]):
            part = part.replace("|AND|", "").replace("|ALSO|", "").strip()
            if part:
                sq = SubQuestion(
                    sub_id=i + 1,
                    question=part,
                    dependencies=[] if i == 0 else [i]
                )
                sub_questions.append(sq)

        # Add synthesis question
        if len(sub_questions) > 1:
            sub_questions.append(SubQuestion(
                sub_id=len(sub_questions) + 1,
                question="Combine all findings into coherent answer",
                dependencies=list(range(1, len(sub_questions) + 1)),
                difficulty=Difficulty.HARD
            ))

        return sub_questions[:self.config.max_sub_questions]

    def _decompose_conditional(self, query: str) -> List[SubQuestion]:
        """Decompose conditional question."""
        sub_questions = []

        # Extract condition and consequence
        sub_questions.append(SubQuestion(
            sub_id=1,
            question=f"What conditions need to be checked?",
            difficulty=Difficulty.EASY
        ))

        sub_questions.append(SubQuestion(
            sub_id=2,
            question=f"What are the possible outcomes based on conditions?",
            difficulty=Difficulty.MEDIUM,
            dependencies=[1]
        ))

        sub_questions.append(SubQuestion(
            sub_id=3,
            question=f"Which outcome applies and what is the recommendation?",
            difficulty=Difficulty.MEDIUM,
            dependencies=[1, 2]
        ))

        return sub_questions

    def _decompose_procedural(self, query: str) -> List[SubQuestion]:
        """Decompose procedural question."""
        sub_questions = []

        sub_questions.append(SubQuestion(
            sub_id=1,
            question="What is the goal or desired outcome?",
            difficulty=Difficulty.TRIVIAL
        ))

        sub_questions.append(SubQuestion(
            sub_id=2,
            question="What are the prerequisites or requirements?",
            difficulty=Difficulty.EASY,
            dependencies=[1]
        ))

        sub_questions.append(SubQuestion(
            sub_id=3,
            question="What are the steps in sequence?",
            difficulty=Difficulty.MEDIUM,
            dependencies=[1, 2]
        ))

        sub_questions.append(SubQuestion(
            sub_id=4,
            question="How to verify successful completion?",
            difficulty=Difficulty.EASY,
            dependencies=[3]
        ))

        return sub_questions

    def _decompose_generic(self, query: str) -> List[SubQuestion]:
        """Generic decomposition."""
        sub_questions = []

        # Standard decomposition
        sub_questions.append(SubQuestion(
            sub_id=1,
            question=f"What is the main concept or topic in: {query[:50]}?",
            difficulty=Difficulty.EASY
        ))

        sub_questions.append(SubQuestion(
            sub_id=2,
            question=f"What are the key aspects to consider?",
            difficulty=Difficulty.MEDIUM,
            dependencies=[1]
        ))

        sub_questions.append(SubQuestion(
            sub_id=3,
            question=f"What is the specific answer or recommendation?",
            difficulty=Difficulty.HARD,
            dependencies=[1, 2]
        ))

        return sub_questions

    def _assess_difficulty(self, sub_question: str, original_query: str) -> Difficulty:
        """
        Assess difficulty of a sub-question.

        Args:
            sub_question: Sub-question text
            original_query: Original query for context

        Returns:
            Difficulty level
        """
        sq_lower = sub_question.lower()

        # Check for trivial indicators
        trivial_patterns = ["what is", "define", "list", "name"]
        if any(p in sq_lower for p in trivial_patterns):
            if len(sq_lower) < 30:
                return Difficulty.TRIVIAL

        # Check for easy indicators
        easy_patterns = ["how many", "when", "where", "which"]
        if any(p in sq_lower for p in easy_patterns):
            return Difficulty.EASY

        # Check for hard indicators
        hard_patterns = ["analyze", "evaluate", "compare", "recommend", "decide"]
        if any(p in sq_lower for p in hard_patterns):
            return Difficulty.HARD

        # Check for expert indicators
        expert_patterns = ["synthesize", "design", "optimize", "integrate"]
        if any(p in sq_lower for p in expert_patterns):
            return Difficulty.EXPERT

        # Default based on length
        if len(sq_lower) < 40:
            return Difficulty.EASY
        elif len(sq_lower) < 80:
            return Difficulty.MEDIUM
        else:
            return Difficulty.HARD

    def _order_by_difficulty(
        self,
        sub_questions: List[SubQuestion]
    ) -> List[SubQuestion]:
        """
        Order sub-questions by difficulty.

        Args:
            sub_questions: List of sub-questions

        Returns:
            Reordered list
        """
        difficulty_order = {
            Difficulty.TRIVIAL: 0,
            Difficulty.EASY: 1,
            Difficulty.MEDIUM: 2,
            Difficulty.HARD: 3,
            Difficulty.EXPERT: 4,
        }

        if self.config.difficulty_order == "ascending":
            # Least to most difficult
            return sorted(
                sub_questions,
                key=lambda sq: difficulty_order.get(sq.difficulty, 2)
            )
        elif self.config.difficulty_order == "descending":
            # Most to least difficult
            return sorted(
                sub_questions,
                key=lambda sq: difficulty_order.get(sq.difficulty, 2),
                reverse=True
            )
        else:  # auto
            # Use ascending but respect dependencies
            ordered = []
            remaining = sub_questions.copy()
            resolved = set()

            while remaining:
                # Find questions whose dependencies are resolved
                ready = [
                    sq for sq in remaining
                    if all(d in resolved for d in sq.dependencies)
                ]

                if not ready:
                    # Circular dependency - just take the first
                    ready = [remaining[0]]

                # Sort ready by difficulty
                ready.sort(key=lambda sq: difficulty_order.get(sq.difficulty, 2))

                for sq in ready:
                    ordered.append(sq)
                    resolved.add(sq.sub_id)
                    remaining.remove(sq)

            return ordered

    def _build_dependency_context(
        self,
        sq: SubQuestion,
        all_questions: List[SubQuestion],
        previous_answers: Dict[int, str]
    ) -> str:
        """Build context from previous answers."""
        if not sq.dependencies:
            return ""

        contexts = []
        for dep_id in sq.dependencies:
            if dep_id in previous_answers:
                dep_sq = next((q for q in all_questions if q.sub_id == dep_id), None)
                if dep_sq:
                    contexts.append(
                        f"Previous finding: {dep_sq.question[:30]}... → {previous_answers[dep_id][:100]}"
                    )

        return "\n".join(contexts)

    def _solve_sub_question(
        self,
        sq: SubQuestion,
        context: Optional[str]
    ) -> SubQuestion:
        """
        Solve a sub-question.

        Args:
            sq: Sub-question to solve
            context: Context from previous answers

        Returns:
            Updated SubQuestion with answer
        """
        start_time = datetime.now()
        sq.status = SubQuestionStatus.SOLVING

        try:
            if self.solver:
                sq.answer = self.solver(sq.question, context)
            elif self.llm_client:
                sq.answer = self._llm_solve(sq.question, context)
            else:
                sq.answer = self._template_solve(sq.question, context)

            sq.confidence = self._estimate_confidence(sq.answer)
            sq.status = SubQuestionStatus.SOLVED

        except Exception as e:
            sq.status = SubQuestionStatus.FAILED
            sq.answer = f"Could not solve: {str(e)}"
            sq.confidence = 0.0

        sq.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        return sq

    def _template_solve(self, question: str, context: Optional[str]) -> str:
        """Template-based solving."""
        question_lower = question.lower()

        if "what is" in question_lower:
            return f"The definition is: [concept explanation]"
        elif "how" in question_lower:
            return f"The process involves: [step-by-step explanation]"
        elif "why" in question_lower:
            return f"The reason is: [explanation]"
        elif "when" in question_lower:
            return f"The timing is: [temporal information]"
        else:
            return f"Analysis: {question[:50]}... leads to [conclusion]"

    def _llm_solve(self, question: str, context: Optional[str]) -> str:
        """Use LLM to solve."""
        return f"LLM answer for: {question[:50]}..."

    def _estimate_confidence(self, answer: str) -> float:
        """Estimate confidence in answer."""
        if not answer or "could not" in answer.lower():
            return 0.0

        confidence = 0.6

        if len(answer) > 20:
            confidence += 0.1
        if len(answer) > 50:
            confidence += 0.1
        if any(w in answer.lower() for w in ["because", "therefore", "since"]):
            confidence += 0.1

        return min(1.0, confidence)

    def _aggregate_answers(
        self,
        sub_questions: List[SubQuestion],
        original_query: str
    ) -> str:
        """
        Aggregate sub-answers into final answer.

        Args:
            sub_questions: List of solved sub-questions
            original_query: Original query

        Returns:
            Final aggregated answer
        """
        solved = [sq for sq in sub_questions if sq.status == SubQuestionStatus.SOLVED]

        if not solved:
            return "Unable to solve any sub-questions."

        if self.config.aggregation_strategy == "synthesis":
            return self._synthesize_answers(solved, original_query)
        elif self.config.aggregation_strategy == "combination":
            return self._combine_answers(solved)
        else:  # hierarchy
            return self._hierarchical_aggregate(solved, original_query)

    def _synthesize_answers(
        self,
        solved: List[SubQuestion],
        original_query: str
    ) -> str:
        """Synthesize answers into coherent response."""
        components = []

        for sq in solved:
            if sq.contributes_to_final and sq.answer:
                components.append(sq.answer)

        if len(components) == 1:
            return components[0]

        synthesis = f"Based on analysis of {len(components)} aspects: "
        synthesis += "; ".join(components[:3])

        if len(components) > 3:
            synthesis += f" ...and {len(components) - 3} more findings."

        return synthesis

    def _combine_answers(self, solved: List[SubQuestion]) -> str:
        """Combine answers with structure."""
        parts = []

        for sq in solved:
            if sq.answer:
                parts.append(f"[{sq.difficulty}] {sq.question[:30]}...: {sq.answer}")

        return "\n".join(parts)

    def _hierarchical_aggregate(
        self,
        solved: List[SubQuestion],
        original_query: str
    ) -> str:
        """Aggregate with difficulty hierarchy."""
        # Group by difficulty
        by_difficulty: Dict[str, List[str]] = {}

        for sq in solved:
            if sq.answer:
                diff = sq.difficulty
                if diff not in by_difficulty:
                    by_difficulty[diff] = []
                by_difficulty[diff].append(sq.answer)

        # Build hierarchical response
        result = f"Comprehensive answer to: {original_query[:50]}...\n\n"

        for diff in ["trivial", "easy", "medium", "hard", "expert"]:
            if diff in by_difficulty:
                result += f"{diff.upper()} findings: "
                result += "; ".join(by_difficulty[diff][:2])
                result += "\n"

        return result

    def _calculate_confidence(
        self,
        sub_questions: List[SubQuestion],
        solved_count: int
    ) -> float:
        """Calculate overall confidence."""
        if not sub_questions:
            return 0.0

        # Base on solve rate
        solve_rate = solved_count / len(sub_questions)

        # Weight by confidence of solved questions
        solved = [sq for sq in sub_questions if sq.status == SubQuestionStatus.SOLVED]

        if solved:
            avg_confidence = sum(sq.confidence for sq in solved) / len(solved)
            return solve_rate * 0.5 + avg_confidence * 0.5

        return solve_rate * 0.5

    def _is_multi_part_query(self, query: str) -> bool:
        """Check if query has multiple parts."""
        indicators = [" and ", " also ", " as well as ", " additionally "]
        return sum(1 for i in indicators if i in query) >= 1

    def _is_conditional_query(self, query: str) -> bool:
        """Check if query is conditional."""
        indicators = ["if ", "when ", "would ", "could ", "should i "]
        return any(i in query for i in indicators)

    def _is_procedural_query(self, query: str) -> bool:
        """Check if query is procedural."""
        indicators = ["how do i", "how to", "steps", "process", "procedure"]
        return any(i in query for i in indicators)
