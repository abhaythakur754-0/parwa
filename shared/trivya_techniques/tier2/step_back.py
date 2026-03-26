"""
PARWA TRIVYA Tier 2 Step Back Technique.

Abstracts from specific details to understand underlying principles
before solving the problem. Provides broader context for better reasoning.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class AbstractionLayer(BaseModel):
    """A layer of abstraction in step-back reasoning."""
    level: int = Field(ge=1)
    specific_problem: str
    abstract_concept: str
    underlying_principle: str
    relevance: float = Field(default=0.8, ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class StepBackResult(BaseModel):
    """Result from Step Back processing."""
    query: str
    original_problem: str
    abstraction_layers: List[AbstractionLayer] = Field(default_factory=list)
    core_principle: str = ""
    abstracted_understanding: str = ""
    solution_approach: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class StepBackConfig(BaseModel):
    """Configuration for Step Back technique."""
    max_abstraction_levels: int = Field(default=3, ge=1, le=5)
    include_examples: bool = Field(default=True)
    find_analogies: bool = Field(default=True)
    validate_relevance: bool = Field(default=True)
    min_relevance_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class StepBack:
    """
    Step Back technique for TRIVYA Tier 2.

    Takes a step back from the specific problem to understand
    the underlying principles and concepts. This abstraction
    helps provide more generalizable and well-grounded solutions.

    Features:
    - Multi-level abstraction
    - Core principle identification
    - Analogy finding
    - Relevance validation
    """

    def __init__(
        self,
        config: Optional[StepBackConfig] = None,
        llm_client: Optional[Any] = None
    ) -> None:
        """
        Initialize Step Back technique.

        Args:
            config: Step Back configuration
            llm_client: LLM client for generation
        """
        self.config = config or StepBackConfig()
        self.llm_client = llm_client

        # Performance tracking
        self._queries_processed = 0
        self._total_abstractions_made = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "step_back_initialized",
            "max_abstraction_levels": self.config.max_abstraction_levels,
        })

    def analyze(
        self,
        query: str,
        context: Optional[str] = None
    ) -> StepBackResult:
        """
        Apply step-back analysis to a query.

        Args:
            query: User query text
            context: Optional context from T1

        Returns:
            StepBackResult with abstraction analysis

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Generate abstraction layers
        layers = self._create_abstraction_layers(query, context)

        # Extract core principle
        core_principle = self._extract_core_principle(layers)

        # Build abstracted understanding
        abstracted = self._build_abstracted_understanding(layers, core_principle)

        # Derive solution approach
        solution = self._derive_solution_approach(query, core_principle, layers)

        # Calculate confidence
        confidence = self._calculate_confidence(layers)

        result = StepBackResult(
            query=query,
            original_problem=query,
            abstraction_layers=layers,
            core_principle=core_principle,
            abstracted_understanding=abstracted,
            solution_approach=solution,
            confidence=confidence,
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_abstractions_made += len(layers)
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "step_back_complete",
            "abstraction_levels": len(layers),
            "confidence": confidence,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def generate_prompt(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a step-back prompt for an LLM.

        Args:
            query: User query
            context: Optional context

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Take a step back from this specific problem to understand the",
            "underlying principles and concepts.",
            "",
            f"Specific Problem: {query}",
            "",
            "Analyze:",
            "1. What is the underlying concept here?",
            "2. What general principle applies?",
            "3. What is a similar or analogous situation?",
            "4. How does understanding the principle help solve the specific?",
            "",
            "Step-back Analysis:",
            "Abstract Concept: [The general category]",
            "Underlying Principle: [The fundamental rule or concept]",
            "Analogy: [A similar situation]",
            "Application: [How to apply this understanding]",
        ]

        if context:
            prompt_parts.insert(3, f"Context: {context}")

        return "\n".join(prompt_parts)

    def parse_response(
        self,
        response: str,
        query: str
    ) -> StepBackResult:
        """
        Parse an LLM response into structured result.

        Args:
            response: LLM response text
            query: Original query

        Returns:
            StepBackResult with parsed analysis
        """
        start_time = datetime.now()

        layers = []
        core_principle = ""
        abstracted = ""
        solution = ""

        lines = response.split("\n")

        current_section = None

        for line in lines:
            line = line.strip()

            if "abstract concept" in line.lower():
                current_section = "abstract"
                abstracted = line.split(":", 1)[-1].strip() if ":" in line else ""
                layers.append(AbstractionLayer(
                    level=1,
                    specific_problem=query,
                    abstract_concept=abstracted,
                    underlying_principle="",
                ))

            elif "underlying principle" in line.lower():
                current_section = "principle"
                core_principle = line.split(":", 1)[-1].strip() if ":" in line else ""
                if layers:
                    layers[-1].underlying_principle = core_principle

            elif "analogy" in line.lower():
                current_section = "analogy"

            elif "application" in line.lower():
                current_section = "application"
                solution = line.split(":", 1)[-1].strip() if ":" in line else ""

        # Ensure we have at least one layer
        if not layers:
            layers.append(AbstractionLayer(
                level=1,
                specific_problem=query,
                abstract_concept=response[:100],
                underlying_principle=response[:50],
            ))
            core_principle = response[:50]
            abstracted = response[:100]

        confidence = self._calculate_confidence(layers)

        result = StepBackResult(
            query=query,
            original_problem=query,
            abstraction_layers=layers,
            core_principle=core_principle,
            abstracted_understanding=abstracted,
            solution_approach=solution,
            confidence=confidence,
        )

        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Step Back statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_abstractions_made": self._total_abstractions_made,
            "average_abstractions_per_query": (
                self._total_abstractions_made / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _create_abstraction_layers(
        self,
        query: str,
        context: Optional[str]
    ) -> List[AbstractionLayer]:
        """
        Create abstraction layers for a query.

        Args:
            query: User query
            context: Optional context

        Returns:
            List of AbstractionLayer
        """
        query_lower = query.lower()
        layers = []

        # Detect query domain and create appropriate abstractions
        if any(w in query_lower for w in ["why", "reason", "cause"]):
            layers = self._create_causal_abstractions(query)
        elif any(w in query_lower for w in ["how", "process", "work"]):
            layers = self._create_process_abstractions(query)
        elif any(w in query_lower for w in ["what is", "define", "explain"]):
            layers = self._create_conceptual_abstractions(query)
        elif any(w in query_lower for w in ["compare", "difference", "better"]):
            layers = self._create_comparative_abstractions(query)
        else:
            layers = self._create_generic_abstractions(query)

        return layers[:self.config.max_abstraction_levels]

    def _create_causal_abstractions(self, query: str) -> List[AbstractionLayer]:
        """Create abstractions for causal queries."""
        return [
            AbstractionLayer(
                level=1,
                specific_problem=query,
                abstract_concept="Causation and effect relationships",
                underlying_principle="Every effect has one or more causes",
                relevance=0.9,
            ),
            AbstractionLayer(
                level=2,
                specific_problem="Causation and effect relationships",
                abstract_concept="Systems thinking and interconnections",
                underlying_principle="Events are connected in complex systems",
                relevance=0.8,
            ),
            AbstractionLayer(
                level=3,
                specific_problem="Systems thinking",
                abstract_concept="Fundamental laws of nature/society",
                underlying_principle="Predictable patterns emerge from complexity",
                relevance=0.7,
            ),
        ]

    def _create_process_abstractions(self, query: str) -> List[AbstractionLayer]:
        """Create abstractions for process queries."""
        return [
            AbstractionLayer(
                level=1,
                specific_problem=query,
                abstract_concept="Process and workflow design",
                underlying_principle="Processes transform inputs to outputs",
                relevance=0.9,
            ),
            AbstractionLayer(
                level=2,
                specific_problem="Process design",
                abstract_concept="Systems and operations theory",
                underlying_principle="Efficient systems minimize friction",
                relevance=0.8,
            ),
            AbstractionLayer(
                level=3,
                specific_problem="Systems theory",
                abstract_concept="Universal principles of transformation",
                underlying_principle="All processes follow patterns",
                relevance=0.7,
            ),
        ]

    def _create_conceptual_abstractions(self, query: str) -> List[AbstractionLayer]:
        """Create abstractions for conceptual queries."""
        return [
            AbstractionLayer(
                level=1,
                specific_problem=query,
                abstract_concept="Definition and classification",
                underlying_principle="Things are defined by their attributes",
                relevance=0.9,
            ),
            AbstractionLayer(
                level=2,
                specific_problem="Definition",
                abstract_concept="Categorization and taxonomy",
                underlying_principle="Knowledge is organized hierarchically",
                relevance=0.8,
            ),
            AbstractionLayer(
                level=3,
                specific_problem="Categorization",
                abstract_concept="Fundamental nature of things",
                underlying_principle="Essence transcends categories",
                relevance=0.7,
            ),
        ]

    def _create_comparative_abstractions(self, query: str) -> List[AbstractionLayer]:
        """Create abstractions for comparative queries."""
        return [
            AbstractionLayer(
                level=1,
                specific_problem=query,
                abstract_concept="Comparison and evaluation",
                underlying_principle="Value is determined by criteria",
                relevance=0.9,
            ),
            AbstractionLayer(
                level=2,
                specific_problem="Comparison",
                abstract_concept="Decision theory and trade-offs",
                underlying_principle="Every choice involves trade-offs",
                relevance=0.8,
            ),
            AbstractionLayer(
                level=3,
                specific_problem="Decision theory",
                abstract_concept="Value systems and priorities",
                underlying_principle="Values determine optimal choices",
                relevance=0.7,
            ),
        ]

    def _create_generic_abstractions(self, query: str) -> List[AbstractionLayer]:
        """Create generic abstractions."""
        return [
            AbstractionLayer(
                level=1,
                specific_problem=query,
                abstract_concept="Problem solving approach",
                underlying_principle="Problems have structure and patterns",
                relevance=0.8,
            ),
            AbstractionLayer(
                level=2,
                specific_problem="Problem solving",
                abstract_concept="Universal problem-solving principles",
                underlying_principle="Understanding precedes solution",
                relevance=0.7,
            ),
        ]

    def _extract_core_principle(
        self,
        layers: List[AbstractionLayer]
    ) -> str:
        """
        Extract core principle from abstraction layers.

        Args:
            layers: Abstraction layers

        Returns:
            Core principle string
        """
        if not layers:
            return "General problem-solving principle: understand before solving"

        # Get the deepest layer's principle
        return layers[-1].underlying_principle

    def _build_abstracted_understanding(
        self,
        layers: List[AbstractionLayer],
        core_principle: str
    ) -> str:
        """
        Build abstracted understanding from layers.

        Args:
            layers: Abstraction layers
            core_principle: Core principle

        Returns:
            Abstracted understanding string
        """
        if not layers:
            return "Understanding requires abstraction"

        concepts = [layer.abstract_concept for layer in layers]
        return " -> ".join(concepts)

    def _derive_solution_approach(
        self,
        query: str,
        core_principle: str,
        layers: List[AbstractionLayer]
    ) -> str:
        """
        Derive solution approach from analysis.

        Args:
            query: Original query
            core_principle: Core principle
            layers: Abstraction layers

        Returns:
            Solution approach string
        """
        if not layers:
            return "Apply the core principle to the specific problem"

        return f"Apply '{core_principle}' to address the specific problem"

    def _calculate_confidence(self, layers: List[AbstractionLayer]) -> float:
        """
        Calculate confidence from abstraction layers.

        Args:
            layers: Abstraction layers

        Returns:
            Confidence score 0-1
        """
        if not layers:
            return 0.0

        # Average relevance across layers
        total_relevance = sum(layer.relevance for layer in layers)
        avg_relevance = total_relevance / len(layers)

        # More layers with good relevance = higher confidence
        layer_bonus = min(0.1, len(layers) * 0.03)

        confidence = avg_relevance + layer_bonus

        return round(min(1.0, confidence), 2)
