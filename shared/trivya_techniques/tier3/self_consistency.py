"""
PARWA TRIVYA Tier 3 - Self-Consistency.

Self-Consistency aggregates multiple reasoning paths and selects the
most consistent answer through majority voting. This technique improves
reliability by sampling diverse reasoning chains and finding consensus.

Key Features:
- Multiple reasoning chain generation
- Answer extraction and normalization
- Majority voting mechanism
- Confidence from consensus strength
- Divergence detection for edge cases
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from collections import Counter
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class VoteStrategy(str, Enum):
    """Voting strategies for consensus."""
    MAJORITY = "majority"  # Most common answer wins
    WEIGHTED = "weighted"  # Weighted by confidence
    UNANIMOUS = "unanimous"  # Only if all agree
    SUPERMAJORITY = "supermajority"  # 2/3 majority required


class ReasoningChain(BaseModel):
    """A single reasoning chain with conclusion."""
    chain_id: int = Field(ge=1)
    reasoning: str = ""
    conclusion: str = ""
    normalized_answer: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    approach: str = ""
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class ConsensusResult(BaseModel):
    """Result from self-consistency voting."""
    query: str
    chains: List[ReasoningChain] = Field(default_factory=list)
    total_chains: int = Field(default=0, ge=0)
    unique_answers: int = Field(default=0, ge=0)
    winning_answer: str = ""
    winning_chain: Optional[ReasoningChain] = None
    vote_distribution: Dict[str, int] = Field(default_factory=dict)
    consensus_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    has_consensus: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    divergent_answers: List[str] = Field(default_factory=list)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class SelfConsistencyConfig(BaseModel):
    """Configuration for Self-Consistency."""
    num_chains: int = Field(default=5, ge=3, le=10)
    min_consensus_ratio: float = Field(default=0.6, ge=0.5, le=1.0)
    vote_strategy: VoteStrategy = VoteStrategy.MAJORITY
    temperature_range: tuple = Field(default=(0.3, 0.9))
    normalize_answers: bool = Field(default=True)
    require_agreement: bool = Field(default=False)
    min_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class SelfConsistency:
    """
    Self-Consistency technique.

    Generates multiple reasoning chains for the same query and
    aggregates results through voting. The consensus answer is
    more reliable than any single chain.

    Process:
    1. Generate N diverse reasoning chains
    2. Extract and normalize answers
    3. Apply voting strategy
    4. Calculate consensus strength
    5. Return most consistent answer

    Best for:
    - Questions with definitive answers
    - Complex multi-step reasoning
    - High-stakes decisions
    - Reducing hallucination
    """

    def __init__(
        self,
        config: Optional[SelfConsistencyConfig] = None,
        llm_client: Optional[Any] = None,
        answer_extractor: Optional[Callable[[str], str]] = None
    ) -> None:
        """
        Initialize Self-Consistency.

        Args:
            config: Optional configuration override
            llm_client: LLM client for generation
            answer_extractor: Optional custom answer extractor
        """
        self.config = config or SelfConsistencyConfig()
        self.llm_client = llm_client
        self.answer_extractor = answer_extractor

        # Performance tracking
        self._queries_processed = 0
        self._total_chains_generated = 0
        self._consensus_reached = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "self_consistency_initialized",
            "num_chains": self.config.num_chains,
            "vote_strategy": self.config.vote_strategy,
        })

    def reason(
        self,
        query: str,
        context: Optional[str] = None,
        num_chains: Optional[int] = None
    ) -> ConsensusResult:
        """
        Generate multiple chains and find consensus answer.

        Args:
            query: The query to reason about
            context: Additional context from T1/T2
            num_chains: Override number of chains

        Returns:
            ConsensusResult with voting results

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        n_chains = num_chains or self.config.num_chains

        result = ConsensusResult(query=query.strip())

        try:
            # Generate multiple reasoning chains
            chains = self._generate_chains(query, context, n_chains)
            result.chains = chains
            result.total_chains = len(chains)

            # Extract and normalize answers
            for chain in chains:
                chain.normalized_answer = self._normalize_answer(chain.conclusion)

            # Perform voting
            result.vote_distribution = self._count_votes(chains)
            result.unique_answers = len(result.vote_distribution)

            # Determine winner
            result.winning_answer = self._determine_winner(
                chains, result.vote_distribution
            )

            # Find winning chain
            result.winning_chain = next(
                (c for c in chains if c.normalized_answer == result.winning_answer),
                chains[0] if chains else None
            )

            # Calculate consensus strength
            result.consensus_strength = self._calculate_consensus_strength(
                result.vote_distribution, result.total_chains
            )

            # Determine if consensus achieved
            result.has_consensus = (
                result.consensus_strength >= self.config.min_consensus_ratio
            )

            # Identify divergent answers
            result.divergent_answers = [
                answer for answer, count in result.vote_distribution.items()
                if count < result.total_chains / 3
            ]

            # Calculate overall confidence
            result.confidence = self._calculate_confidence(result)

        except Exception as e:
            logger.error({
                "event": "self_consistency_failed",
                "error": str(e),
            })
            result.metadata["error"] = str(e)

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_chains_generated += result.total_chains
        if result.has_consensus:
            self._consensus_reached += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "self_consistency_complete",
            "total_chains": result.total_chains,
            "has_consensus": result.has_consensus,
            "consensus_strength": result.consensus_strength,
            "winning_answer": result.winning_answer[:50] if result.winning_answer else None,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Self-Consistency statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_chains_generated": self._total_chains_generated,
            "average_chains_per_query": (
                self._total_chains_generated / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "consensus_rate": (
                self._consensus_reached / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _generate_chains(
        self,
        query: str,
        context: Optional[str],
        n_chains: int
    ) -> List[ReasoningChain]:
        """
        Generate multiple diverse reasoning chains.

        Args:
            query: User query
            context: Additional context
            n_chains: Number of chains to generate

        Returns:
            List of ReasoningChain objects
        """
        chains = []

        # Define diverse approaches
        approaches = [
            "analytical",
            "intuitive",
            "cautious",
            "thorough",
            "creative",
            "pragmatic",
            "systematic",
            "heuristic",
            "first_principles",
            "comparative",
        ]

        for i in range(n_chains):
            approach = approaches[i % len(approaches)]

            chain = ReasoningChain(
                chain_id=i + 1,
                approach=approach,
                reasoning=self._generate_reasoning(query, context, approach),
                conclusion=self._generate_conclusion(query, approach),
                confidence=self._estimate_chain_confidence(approach)
            )
            chains.append(chain)

        return chains

    def _generate_reasoning(
        self,
        query: str,
        context: Optional[str],
        approach: str
    ) -> str:
        """Generate reasoning for a chain."""
        if self.llm_client:
            return self._llm_generate_reasoning(query, context, approach)

        # Template-based reasoning
        templates = {
            "analytical": f"Applying analytical reasoning to '{query[:50]}...': breaking down into logical components, evaluating each systematically.",
            "intuitive": f"Using intuitive pattern recognition for '{query[:50]}...': drawing on experiential knowledge and quick judgment.",
            "cautious": f"Taking cautious approach to '{query[:50]}...': considering all potential risks and worst-case scenarios.",
            "thorough": f"Thoroughly examining '{query[:50]}...': exploring all aspects and gathering comprehensive information.",
            "creative": f"Applying creative thinking to '{query[:50]}...': considering novel approaches and unconventional solutions.",
            "pragmatic": f"Pragmatic analysis of '{query[:50]}...': focusing on practical, actionable solutions.",
            "systematic": f"Systematic evaluation of '{query[:50]}...': following structured methodology step by step.",
            "heuristic": f"Applying heuristics to '{query[:50]}...': using rule-of-thumb shortcuts based on experience.",
            "first_principles": f"First principles thinking for '{query[:50]}...': breaking down to fundamental truths.",
            "comparative": f"Comparative analysis of '{query[:50]}...': evaluating against similar known cases.",
        }
        return templates.get(approach, f"Reasoning about: {query[:50]}...")

    def _generate_conclusion(self, query: str, approach: str) -> str:
        """Generate conclusion for a chain."""
        query_lower = query.lower()

        # Extract question type
        if "should i" in query_lower or "which" in query_lower:
            return self._generate_decision_conclusion(query, approach)
        elif "what is" in query_lower or "define" in query_lower:
            return self._generate_definition_conclusion(query, approach)
        elif "how do i" in query_lower or "how to" in query_lower:
            return self._generate_procedural_conclusion(query, approach)
        else:
            return self._generate_generic_conclusion(query, approach)

    def _generate_decision_conclusion(self, query: str, approach: str) -> str:
        """Generate decision conclusion."""
        # Different approaches may yield different answers
        outcomes = {
            "analytical": "Based on data analysis, option A is recommended.",
            "intuitive": "My intuition suggests option B would be better.",
            "cautious": "Taking a conservative approach, option A minimizes risk.",
            "thorough": "After thorough review, option A is optimal.",
            "creative": "An innovative hybrid of both options could work best.",
            "pragmatic": "Practically speaking, option A is easier to implement.",
            "systematic": "Systematic evaluation points to option A.",
            "heuristic": "Based on past similar cases, option A is typical choice.",
            "first_principles": "Fundamentally, option A aligns better with goals.",
            "comparative": "Compared to similar decisions, option A prevails.",
        }
        return outcomes.get(approach, "Option A appears to be the better choice.")

    def _generate_definition_conclusion(self, query: str, approach: str) -> str:
        """Generate definition conclusion."""
        return f"The answer is: {query.split()[-1] if query else 'undefined'} refers to a concept in the relevant domain."

    def _generate_procedural_conclusion(self, query: str, approach: str) -> str:
        """Generate procedural conclusion."""
        return "The process involves: step 1) identify requirements, step 2) gather resources, step 3) execute, step 4) verify."

    def _generate_generic_conclusion(self, query: str, approach: str) -> str:
        """Generate generic conclusion."""
        return f"Based on {approach} reasoning, the solution involves addressing the core issue presented in the query."

    def _llm_generate_reasoning(
        self,
        query: str,
        context: Optional[str],
        approach: str
    ) -> str:
        """Use LLM to generate reasoning."""
        # Placeholder for LLM integration
        return f"LLM-generated {approach} reasoning for: {query[:50]}..."

    def _normalize_answer(self, answer: str) -> str:
        """
        Normalize answer for comparison.

        Args:
            answer: Raw answer string

        Returns:
            Normalized answer string
        """
        if not self.config.normalize_answers:
            return answer

        # Convert to lowercase
        normalized = answer.lower().strip()

        # Remove common filler words
        fillers = ["the answer is:", "answer:", "conclusion:", "result:", "therefore,"]
        for filler in fillers:
            if normalized.startswith(filler):
                normalized = normalized[len(filler):].strip()

        # Normalize specific entities
        # Extract key terms for comparison
        words = normalized.split()
        if len(words) > 10:
            # Keep only key terms for long answers
            normalized = " ".join(words[:10])

        return normalized

    def _count_votes(self, chains: List[ReasoningChain]) -> Dict[str, int]:
        """
        Count votes for each answer.

        Args:
            chains: List of reasoning chains

        Returns:
            Dict mapping normalized answers to vote counts
        """
        answers = [c.normalized_answer for c in chains]
        return dict(Counter(answers))

    def _determine_winner(
        self,
        chains: List[ReasoningChain],
        vote_distribution: Dict[str, int]
    ) -> str:
        """
        Determine winning answer based on vote strategy.

        Args:
            chains: List of chains
            vote_distribution: Vote counts

        Returns:
            Winning normalized answer
        """
        if not vote_distribution:
            return ""

        if self.config.vote_strategy == VoteStrategy.MAJORITY:
            return max(vote_distribution, key=vote_distribution.get)

        elif self.config.vote_strategy == VoteStrategy.WEIGHTED:
            # Weight by confidence
            weighted_scores: Dict[str, float] = {}
            for chain in chains:
                answer = chain.normalized_answer
                if answer not in weighted_scores:
                    weighted_scores[answer] = 0.0
                weighted_scores[answer] += chain.confidence

            return max(weighted_scores, key=weighted_scores.get)

        elif self.config.vote_strategy == VoteStrategy.UNANIMOUS:
            if len(vote_distribution) == 1:
                return list(vote_distribution.keys())[0]
            return ""  # No unanimous agreement

        elif self.config.vote_strategy == VoteStrategy.SUPERMAJORITY:
            total = sum(vote_distribution.values())
            for answer, count in vote_distribution.items():
                if count / total >= 0.67:  # 2/3 majority
                    return answer
            return max(vote_distribution, key=vote_distribution.get)

        return max(vote_distribution, key=vote_distribution.get)

    def _calculate_consensus_strength(
        self,
        vote_distribution: Dict[str, int],
        total_chains: int
    ) -> float:
        """
        Calculate strength of consensus.

        Args:
            vote_distribution: Vote counts
            total_chains: Total number of chains

        Returns:
            Consensus strength (0.0-1.0)
        """
        if not vote_distribution or total_chains == 0:
            return 0.0

        max_votes = max(vote_distribution.values())
        return max_votes / total_chains

    def _estimate_chain_confidence(self, approach: str) -> float:
        """Estimate confidence for an approach."""
        # Different approaches have different base confidences
        confidences = {
            "analytical": 0.85,
            "systematic": 0.85,
            "thorough": 0.80,
            "pragmatic": 0.75,
            "first_principles": 0.80,
            "comparative": 0.75,
            "heuristic": 0.70,
            "intuitive": 0.65,
            "cautious": 0.70,
            "creative": 0.60,
        }
        return confidences.get(approach, 0.7)

    def _calculate_confidence(self, result: ConsensusResult) -> float:
        """
        Calculate overall confidence from result.

        Args:
            result: Consensus result

        Returns:
            Confidence score
        """
        if not result.has_consensus:
            return result.consensus_strength * 0.5

        # Base confidence on consensus strength
        confidence = result.consensus_strength

        # Adjust for number of chains
        if result.total_chains >= 5:
            confidence += 0.1

        # Adjust for unique answers (fewer is better)
        if result.unique_answers == 1:
            confidence = min(1.0, confidence + 0.1)
        elif result.unique_answers > 3:
            confidence -= 0.1

        # Adjust for winning chain confidence
        if result.winning_chain:
            confidence = (confidence + result.winning_chain.confidence) / 2

        return min(1.0, max(0.0, confidence))
