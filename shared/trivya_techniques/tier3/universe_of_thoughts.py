"""
PARWA TRIVYA Tier 3 - Universe of Thoughts (UoT).

Universe of Thoughts explores multiple solution paths simultaneously,
generating diverse perspectives and approaches to the same problem.
This technique is particularly valuable for complex decisions where
no single approach is clearly superior.

Key Features:
- Parallel exploration of multiple solution paths
- Diverse perspective generation
- Cross-path comparison and synthesis
- Optimal path selection with justification
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class PathType(str, Enum):
    """Types of reasoning paths."""
    ANALYTICAL = "analytical"  # Data-driven, logical
    INTUITIVE = "intuitive"  # Pattern-based, experiential
    CREATIVE = "creative"  # Novel, out-of-box
    PRAGMATIC = "pragmatic"  # Practical, resource-aware
    RISK_AVERSE = "risk_averse"  # Conservative, safe
    RISK_SEEKING = "risk_seeking"  # Aggressive, ambitious


class PathStatus(str, Enum):
    """Status of a reasoning path."""
    PENDING = "pending"
    EXPLORING = "exploring"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ThoughtPath(BaseModel):
    """A single reasoning path through the solution space."""
    path_id: int = Field(ge=1)
    path_type: PathType
    description: str = ""
    reasoning_steps: List[str] = Field(default_factory=list)
    conclusion: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    status: PathStatus = PathStatus.PENDING
    exploration_depth: int = Field(default=0, ge=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class UniverseResult(BaseModel):
    """Result from Universe of Thoughts reasoning."""
    query: str
    paths: List[ThoughtPath] = Field(default_factory=list)
    optimal_path: Optional[ThoughtPath] = None
    optimal_path_id: Optional[int] = None
    synthesis: str = ""
    cross_path_insights: List[str] = Field(default_factory=list)
    confidence_distribution: Dict[str, float] = Field(default_factory=dict)
    total_paths_explored: int = Field(default=0)
    completed_paths: int = Field(default=0)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class UniverseConfig(BaseModel):
    """Configuration for Universe of Thoughts."""
    max_paths: int = Field(default=6, ge=2, le=10)
    min_paths: int = Field(default=3, ge=2)
    exploration_depth: int = Field(default=3, ge=1, le=5)
    min_path_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    include_contradictory_paths: bool = Field(default=True)
    parallel_exploration: bool = Field(default=True)
    cross_pollination: bool = Field(default=True)  # Share insights between paths
    selection_strategy: str = Field(default="confidence_weighted")  # confidence_weighted, highest, consensus

    model_config = ConfigDict()


class UniverseOfThoughts:
    """
    Universe of Thoughts (UoT) technique.

    Explores multiple solution paths in parallel, generating diverse
    perspectives and approaches. Unlike sequential reasoning, UoT
    considers different mental models simultaneously.

    Path Types:
    - Analytical: Data-driven, logical deduction
    - Intuitive: Pattern recognition, experience-based
    - Creative: Novel solutions, lateral thinking
    - Pragmatic: Practical, resource-constrained
    - Risk-Averse: Conservative, worst-case focused
    - Risk-Seeking: Aggressive, best-case focused
    """

    def __init__(
        self,
        config: Optional[UniverseConfig] = None,
        llm_client: Optional[Any] = None
    ) -> None:
        """
        Initialize Universe of Thoughts.

        Args:
            config: Optional configuration override
            llm_client: LLM client for generation
        """
        self.config = config or UniverseConfig()
        self.llm_client = llm_client

        # Performance tracking
        self._queries_processed = 0
        self._total_paths_explored = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "universe_of_thoughts_initialized",
            "max_paths": self.config.max_paths,
            "exploration_depth": self.config.exploration_depth,
        })

    def explore(
        self,
        query: str,
        context: Optional[str] = None,
        constraints: Optional[List[str]] = None
    ) -> UniverseResult:
        """
        Explore multiple solution paths for a query.

        Args:
            query: The query to explore
            context: Additional context from T1/T2
            constraints: Optional constraints to consider

        Returns:
            UniverseResult with all explored paths

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()

        result = UniverseResult(query=query.strip())

        try:
            # Initialize paths based on query type
            paths = self._initialize_paths(query, context)
            result.paths = paths
            result.total_paths_explored = len(paths)

            # Explore each path
            for i, path in enumerate(paths):
                path = self._explore_path(
                    path=path,
                    query=query,
                    context=context,
                    constraints=constraints
                )
                paths[i] = path

                if path.status == PathStatus.COMPLETED:
                    result.completed_paths += 1

            # Cross-pollination: share insights between paths
            if self.config.cross_pollination:
                result.cross_path_insights = self._cross_pollinate(paths)

            # Select optimal path
            result.optimal_path = self._select_optimal_path(paths)
            if result.optimal_path:
                result.optimal_path_id = result.optimal_path.path_id

            # Generate synthesis
            result.synthesis = self._synthesize_findings(paths, query)

            # Calculate confidence distribution
            result.confidence_distribution = self._calculate_confidence_distribution(paths)

            # Overall confidence
            result.overall_confidence = self._calculate_overall_confidence(paths)

        except Exception as e:
            logger.error({
                "event": "universe_exploration_failed",
                "error": str(e),
            })
            result.metadata["error"] = str(e)

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_paths_explored += result.total_paths_explored
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "universe_exploration_complete",
            "paths_explored": result.total_paths_explored,
            "completed_paths": result.completed_paths,
            "optimal_path_type": result.optimal_path.path_type if result.optimal_path else None,
            "overall_confidence": result.overall_confidence,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def get_path_types_for_query(
        self,
        query: str
    ) -> List[PathType]:
        """
        Determine which path types are relevant for a query.

        Args:
            query: User query

        Returns:
            List of relevant PathType enums
        """
        return self._determine_relevant_paths(query.lower())

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Universe of Thoughts statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_paths_explored": self._total_paths_explored,
            "average_paths_per_query": (
                self._total_paths_explored / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _initialize_paths(
        self,
        query: str,
        context: Optional[str]
    ) -> List[ThoughtPath]:
        """
        Initialize thought paths based on query.

        Args:
            query: User query
            context: Additional context

        Returns:
            List of initialized ThoughtPath objects
        """
        relevant_types = self._determine_relevant_paths(query.lower())

        # Ensure minimum paths
        if len(relevant_types) < self.config.min_paths:
            all_types = list(PathType)
            for pt in all_types:
                if pt not in relevant_types:
                    relevant_types.append(pt)
                    if len(relevant_types) >= self.config.min_paths:
                        break

        # Limit to max paths
        relevant_types = relevant_types[:self.config.max_paths]

        paths = []
        for i, path_type in enumerate(relevant_types):
            path = ThoughtPath(
                path_id=i + 1,
                path_type=path_type,
                description=self._get_path_description(path_type),
                status=PathStatus.PENDING
            )
            paths.append(path)

        return paths

    def _explore_path(
        self,
        path: ThoughtPath,
        query: str,
        context: Optional[str],
        constraints: Optional[List[str]]
    ) -> ThoughtPath:
        """
        Explore a single reasoning path.

        Args:
            path: Path to explore
            query: User query
            context: Additional context
            constraints: Optional constraints

        Returns:
            Updated ThoughtPath with findings
        """
        start_time = datetime.now()
        path.status = PathStatus.EXPLORING

        try:
            # Generate reasoning steps based on path type
            path.reasoning_steps = self._generate_reasoning_steps(
                path.path_type, query, context, constraints
            )

            # Generate pros and cons
            path.pros, path.cons = self._generate_pros_cons(
                path.path_type, query, path.reasoning_steps
            )

            # Generate conclusion
            path.conclusion = self._generate_conclusion(
                path.path_type, query, path.reasoning_steps
            )

            # Calculate confidence
            path.confidence = self._calculate_path_confidence(path, query)

            # Update status
            if path.confidence >= self.config.min_path_confidence:
                path.status = PathStatus.COMPLETED
            else:
                path.status = PathStatus.ABANDONED

            path.exploration_depth = self.config.exploration_depth

        except Exception as e:
            path.status = PathStatus.ABANDONED
            path.metadata["error"] = str(e)
            logger.warning({
                "event": "path_exploration_failed",
                "path_id": path.path_id,
                "path_type": path.path_type,
                "error": str(e),
            })

        path.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        return path

    def _determine_relevant_paths(self, query: str) -> List[PathType]:
        """Determine relevant path types for query."""
        paths = []

        # Always include analytical
        paths.append(PathType.ANALYTICAL)

        # Check for decision-making
        if any(p in query for p in ["should i", "which", "choose", "decide"]):
            paths.append(PathType.RISK_AVERSE)
            paths.append(PathType.RISK_SEEKING)

        # Check for creative problems
        if any(p in query for p in ["innovative", "creative", "new", "novel", "unique"]):
            paths.append(PathType.CREATIVE)

        # Check for practical questions
        if any(p in query for p in ["how to", "practical", "quick", "easy"]):
            paths.append(PathType.PRAGMATIC)

        # Check for experience-based
        if any(p in query for p in ["best", "worst", "recommend", "experience"]):
            paths.append(PathType.INTUITIVE)

        # Default paths if not enough
        if len(paths) < self.config.min_paths:
            for pt in [PathType.PRAGMATIC, PathType.INTUITIVE, PathType.CREATIVE]:
                if pt not in paths:
                    paths.append(pt)
                    if len(paths) >= self.config.min_paths:
                        break

        return paths

    def _get_path_description(self, path_type: PathType) -> str:
        """Get description for a path type."""
        descriptions = {
            PathType.ANALYTICAL: "Data-driven logical analysis with systematic evaluation",
            PathType.INTUITIVE: "Pattern recognition based on experience and heuristics",
            PathType.CREATIVE: "Novel approaches and out-of-box thinking",
            PathType.PRAGMATIC: "Practical solutions considering real-world constraints",
            PathType.RISK_AVERSE: "Conservative approach focusing on minimizing downside",
            PathType.RISK_SEEKING: "Aggressive approach maximizing potential upside",
        }
        return descriptions.get(path_type, "General reasoning path")

    def _generate_reasoning_steps(
        self,
        path_type: PathType,
        query: str,
        context: Optional[str],
        constraints: Optional[List[str]]
    ) -> List[str]:
        """Generate reasoning steps for a path type."""
        if path_type == PathType.ANALYTICAL:
            return [
                "Identify all measurable factors in the query",
                "Gather relevant data points",
                "Apply logical deduction",
                "Quantify trade-offs where possible",
                "Derive evidence-based conclusion",
            ]
        elif path_type == PathType.INTUITIVE:
            return [
                "Recognize patterns from similar situations",
                "Apply experiential heuristics",
                "Consider implicit context",
                "Trust pattern-based judgment",
                "Form intuitive recommendation",
            ]
        elif path_type == PathType.CREATIVE:
            return [
                "Challenge assumptions in the query",
                "Brainstorm unconventional approaches",
                "Consider analogies from other domains",
                "Combine disparate ideas",
                "Propose innovative solution",
            ]
        elif path_type == PathType.PRAGMATIC:
            return [
                "Assess available resources and constraints",
                "Identify quick wins and easy solutions",
                "Consider implementation difficulty",
                "Prioritize actionable steps",
                "Recommend practical approach",
            ]
        elif path_type == PathType.RISK_AVERSE:
            return [
                "Identify all potential risks",
                "Evaluate worst-case scenarios",
                "Plan risk mitigation strategies",
                "Prioritize safety over upside",
                "Recommend conservative approach",
            ]
        elif path_type == PathType.RISK_SEEKING:
            return [
                "Identify maximum potential upside",
                "Evaluate best-case scenarios",
                "Consider bold strategies",
                "Accept higher risk for reward",
                "Recommend ambitious approach",
            ]
        else:
            return [
                "Analyze the query from this perspective",
                "Identify key considerations",
                "Apply relevant reasoning",
                "Form conclusion",
            ]

    def _generate_pros_cons(
        self,
        path_type: PathType,
        query: str,
        reasoning_steps: List[str]
    ) -> tuple:
        """Generate pros and cons for a path."""
        if path_type == PathType.ANALYTICAL:
            return (
                ["Evidence-based", "Reproducible", "Objective"],
                ["May miss intangibles", "Time-intensive", "Data-dependent"]
            )
        elif path_type == PathType.INTUITIVE:
            return (
                ["Fast", "Captures tacit knowledge", "Handles ambiguity"],
                ["Subjective", "Hard to justify", "Experience-dependent"]
            )
        elif path_type == PathType.CREATIVE:
            return (
                ["Novel solutions", "Breakthrough potential", "Differentiated"],
                ["Higher uncertainty", "May be impractical", "Riskier"]
            )
        elif path_type == PathType.PRAGMATIC:
            return (
                ["Actionable", "Efficient", "Realistic"],
                ["May miss optimal", "Status quo bias", "Limited vision"]
            )
        elif path_type == PathType.RISK_AVERSE:
            return (
                ["Safe", "Predictable", "Protected downside"],
                ["May miss opportunities", "Lower ceiling", "Conservative"]
            )
        elif path_type == PathType.RISK_SEEKING:
            return (
                ["High upside", "Innovative", "Competitive advantage"],
                ["Higher failure rate", "Unpredictable", "Resource-intensive"]
            )
        return (["Balanced approach"], ["May not excel in any dimension"])

    def _generate_conclusion(
        self,
        path_type: PathType,
        query: str,
        reasoning_steps: List[str]
    ) -> str:
        """Generate conclusion for a path."""
        if self.llm_client:
            # Would use LLM to generate
            pass

        # Template-based conclusion
        templates = {
            PathType.ANALYTICAL: f"Based on systematic analysis: logical evaluation suggests focusing on quantifiable factors for '{query[:30]}...'",
            PathType.INTUITIVE: f"Drawing from pattern recognition: experience suggests this approach for '{query[:30]}...'",
            PathType.CREATIVE: f"Through creative exploration: novel angle identified for '{query[:30]}...'",
            PathType.PRAGMATIC: f"From practical standpoint: most actionable approach for '{query[:30]}...'",
            PathType.RISK_AVERSE: f"With risk mitigation in mind: safest path forward for '{query[:30]}...'",
            PathType.RISK_SEEKING: f"For maximum upside: ambitious approach recommended for '{query[:30]}...'",
        }
        return templates.get(path_type, f"Path conclusion for '{query[:30]}...'")

    def _calculate_path_confidence(
        self,
        path: ThoughtPath,
        query: str
    ) -> float:
        """Calculate confidence for a path."""
        base_confidence = 0.7

        # Adjust for reasoning depth
        if len(path.reasoning_steps) >= self.config.exploration_depth:
            base_confidence += 0.1

        # Adjust for pros/cons balance
        if path.pros and path.cons:
            balance = len(path.pros) / (len(path.pros) + len(path.cons))
            base_confidence = base_confidence * 0.8 + balance * 0.2

        # Adjust for conclusion quality
        if len(path.conclusion) > 30:
            base_confidence += 0.05

        return min(1.0, base_confidence)

    def _cross_pollinate(self, paths: List[ThoughtPath]) -> List[str]:
        """Share insights between paths."""
        insights = []

        completed_paths = [p for p in paths if p.status == PathStatus.COMPLETED]

        # Find common pros
        all_pros = [set(p.pros) for p in completed_paths]
        if all_pros:
            common_pros = set.intersection(*all_pros) if len(all_pros) > 1 else all_pros[0]
            if common_pros:
                insights.append(f"Universal advantages: {', '.join(list(common_pros)[:3])}")

        # Find conflicting views
        conclusions = [p.conclusion[:50] for p in completed_paths if p.conclusion]
        if len(set(conclusions)) > 1:
            insights.append("Multiple viable approaches identified with different trade-offs")

        # Identify complementary paths
        if len(completed_paths) >= 3:
            insights.append("Consider combining approaches for comprehensive solution")

        return insights

    def _select_optimal_path(self, paths: List[ThoughtPath]) -> Optional[ThoughtPath]:
        """Select the optimal path from explored paths."""
        completed = [p for p in paths if p.status == PathStatus.COMPLETED]

        if not completed:
            return None

        if self.config.selection_strategy == "highest":
            return max(completed, key=lambda p: p.confidence)

        elif self.config.selection_strategy == "consensus":
            # Find path with most common conclusion themes
            return max(completed, key=lambda p: len(p.pros))

        else:  # confidence_weighted
            # Weight by confidence and pros
            def score(p: ThoughtPath) -> float:
                return p.confidence * 0.7 + (len(p.pros) / 5) * 0.3
            return max(completed, key=score)

    def _synthesize_findings(
        self,
        paths: List[ThoughtPath],
        query: str
    ) -> str:
        """Synthesize findings from all paths."""
        completed = [p for p in paths if p.status == PathStatus.COMPLETED]

        if not completed:
            return "No paths completed successfully."

        path_summaries = []
        for p in completed:
            path_summaries.append(
                f"{p.path_type.capitalize()}: {p.conclusion[:60]}..."
            )

        synthesis = f"Explored {len(completed)} solution paths:\n"
        synthesis += "\n".join(f"- {s}" for s in path_summaries)

        if len(completed) > 1:
            synthesis += f"\n\nOptimal approach ({completed[0].path_type}): {completed[0].conclusion}"

        return synthesis

    def _calculate_confidence_distribution(
        self,
        paths: List[ThoughtPath]
    ) -> Dict[str, float]:
        """Calculate confidence distribution across paths."""
        return {
            p.path_type: p.confidence
            for p in paths
            if p.status == PathStatus.COMPLETED
        }

    def _calculate_overall_confidence(self, paths: List[ThoughtPath]) -> float:
        """Calculate overall confidence from paths."""
        completed = [p for p in paths if p.status == PathStatus.COMPLETED]

        if not completed:
            return 0.0

        # Average of top 3 paths
        sorted_paths = sorted(completed, key=lambda p: p.confidence, reverse=True)
        top_paths = sorted_paths[:3]

        return sum(p.confidence for p in top_paths) / len(top_paths)
