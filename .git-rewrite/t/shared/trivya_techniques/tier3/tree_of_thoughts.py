"""
PARWA TRIVYA Tier 3 - Tree of Thoughts (ToT).

Tree of Thoughts structures reasoning as a search tree where each node
represents a partial reasoning state. The algorithm explores branches,
evaluates promising paths, and can backtrack from dead ends.

Key Features:
- Tree-structured reasoning with branching
- Evaluation of thought states
- Pruning of unpromising branches
- Backtracking and recovery
- Optimal path selection
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class NodeStatus(str, Enum):
    """Status of a tree node."""
    PENDING = "pending"
    EVALUATING = "evaluating"
    PROMISING = "promising"
    UNPROMISING = "unpromising"
    EXPLORED = "explored"
    PRUNED = "pruned"


class SearchStrategy(str, Enum):
    """Tree search strategies."""
    BFS = "bfs"  # Breadth-first search
    DFS = "dfs"  # Depth-first search
    BEST_FIRST = "best_first"  # Greedy best-first
    BEAM = "beam"  # Beam search


class ThoughtNode(BaseModel):
    """A node in the reasoning tree."""
    node_id: str
    depth: int = Field(ge=0)
    thought: str
    evaluation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: NodeStatus = NodeStatus.PENDING
    parent_id: Optional[str] = None
    children_ids: List[str] = Field(default_factory=list)
    reasoning_path: List[str] = Field(default_factory=list)
    is_solution: bool = False
    is_leaf: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class TreeResult(BaseModel):
    """Result from Tree of Thoughts reasoning."""
    query: str
    root: Optional[ThoughtNode] = None
    nodes: Dict[str, ThoughtNode] = Field(default_factory=dict)
    best_path: List[str] = Field(default_factory=list)
    best_solution: str = ""
    total_nodes: int = Field(default=0, ge=0)
    max_depth_reached: int = Field(default=0, ge=0)
    pruned_branches: int = Field(default=0, ge=0)
    solution_found: bool = False
    search_strategy: str = ""
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class TreeConfig(BaseModel):
    """Configuration for Tree of Thoughts."""
    max_depth: int = Field(default=5, ge=1, le=10)
    max_branches: int = Field(default=3, ge=1, le=5)
    max_nodes: int = Field(default=50, ge=1, le=200)
    beam_width: int = Field(default=3, ge=1, le=10)
    evaluation_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    solution_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    search_strategy: SearchStrategy = SearchStrategy.BEST_FIRST
    enable_pruning: bool = Field(default=True)
    allow_backtracking: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class TreeOfThoughts:
    """
    Tree of Thoughts (ToT) technique.

    Structures reasoning as a tree search problem:
    1. Generate initial thought nodes (branches)
    2. Evaluate each node for promise
    3. Explore promising branches deeper
    4. Prune unpromising branches
    5. Select best solution path

    Effective for:
    - Complex multi-step problems
    - Decision trees with many options
    - Problems requiring exploration
    - Creative problem-solving
    """

    def __init__(
        self,
        config: Optional[TreeConfig] = None,
        llm_client: Optional[Any] = None,
        evaluate_fn: Optional[Callable[[str, str], float]] = None
    ) -> None:
        """
        Initialize Tree of Thoughts.

        Args:
            config: Optional configuration override
            llm_client: LLM client for generation
            evaluate_fn: Optional custom evaluation function
        """
        self.config = config or TreeConfig()
        self.llm_client = llm_client
        self.evaluate_fn = evaluate_fn

        # Performance tracking
        self._queries_processed = 0
        self._total_nodes_created = 0
        self._total_solutions_found = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "tree_of_thoughts_initialized",
            "max_depth": self.config.max_depth,
            "max_branches": self.config.max_branches,
            "search_strategy": self.config.search_strategy.value if hasattr(self.config.search_strategy, 'value') else self.config.search_strategy,
        })

    def reason(
        self,
        query: str,
        context: Optional[str] = None,
        initial_thoughts: Optional[List[str]] = None
    ) -> TreeResult:
        """
        Build and search reasoning tree for a query.

        Args:
            query: The query to reason about
            context: Additional context from T1/T2
            initial_thoughts: Optional initial thought seeds

        Returns:
            TreeResult with best solution path

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()

        result = TreeResult(
            query=query.strip(),
            search_strategy=self.config.search_strategy.value if hasattr(self.config.search_strategy, 'value') else self.config.search_strategy
        )

        try:
            # Create root node
            root = ThoughtNode(
                node_id="root",
                depth=0,
                thought=f"Initial problem: {query.strip()[:100]}",
                status=NodeStatus.PENDING,
                reasoning_path=[]
            )
            result.root = root
            result.nodes["root"] = root
            result.total_nodes = 1

            # Generate initial branches
            if initial_thoughts:
                branches = initial_thoughts[:self.config.max_branches]
            else:
                branches = self._generate_branches(query, context)

            # Create child nodes
            for i, branch in enumerate(branches):
                node_id = f"0_{i}"
                child = ThoughtNode(
                    node_id=node_id,
                    depth=1,
                    thought=branch,
                    parent_id="root",
                    reasoning_path=[branch],
                    status=NodeStatus.PENDING
                )
                root.children_ids.append(node_id)
                root.is_leaf = False
                result.nodes[node_id] = child
                result.total_nodes += 1
                self._total_nodes_created += 1

            # Execute search
            self._execute_search(result, query, context)

            # Find best solution
            result.best_path, result.best_solution = self._find_best_path(result)
            result.solution_found = bool(result.best_solution)
            result.max_depth_reached = max(
                n.depth for n in result.nodes.values()
            ) if result.nodes else 0

            # Calculate confidence
            result.overall_confidence = self._calculate_confidence(result)

        except Exception as e:
            logger.error({
                "event": "tree_reasoning_failed",
                "error": str(e),
            })
            result.metadata["error"] = str(e)

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        if result.solution_found:
            self._total_solutions_found += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "tree_reasoning_complete",
            "total_nodes": result.total_nodes,
            "max_depth": result.max_depth_reached,
            "solution_found": result.solution_found,
            "pruned_branches": result.pruned_branches,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Tree of Thoughts statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_nodes_created": self._total_nodes_created,
            "average_nodes_per_query": (
                self._total_nodes_created / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "solutions_found": self._total_solutions_found,
            "solution_rate": (
                self._total_solutions_found / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _generate_branches(
        self,
        query: str,
        context: Optional[str]
    ) -> List[str]:
        """Generate initial thought branches."""
        query_lower = query.lower()

        # Generate branches based on query type
        branches = []

        if self._is_decision_query(query_lower):
            branches = [
                "Consider the pros of option A",
                "Consider the pros of option B",
                "Evaluate trade-offs between options",
            ]
        elif self._is_procedural_query(query_lower):
            branches = [
                "Identify the first step in the process",
                "Determine prerequisites needed",
                "Consider alternative approaches",
            ]
        elif self._is_diagnostic_query(query_lower):
            branches = [
                "List potential causes of the issue",
                "Gather more diagnostic information",
                "Consider common failure modes",
            ]
        else:
            branches = [
                "Break down the problem into components",
                "Consider the simplest solution first",
                "Explore an unconventional approach",
            ]

        return branches[:self.config.max_branches]

    def _execute_search(
        self,
        result: TreeResult,
        query: str,
        context: Optional[str]
    ) -> None:
        """Execute tree search strategy."""
        if self.config.search_strategy == SearchStrategy.BFS:
            self._bfs_search(result, query, context)
        elif self.config.search_strategy == SearchStrategy.DFS:
            self._dfs_search(result, query, context)
        elif self.config.search_strategy == SearchStrategy.BEAM:
            self._beam_search(result, query, context)
        else:  # BEST_FIRST
            self._best_first_search(result, query, context)

    def _bfs_search(
        self,
        result: TreeResult,
        query: str,
        context: Optional[str]
    ) -> None:
        """Breadth-first search implementation."""
        from collections import deque

        queue = deque(result.root.children_ids) if result.root else deque()

        while queue and result.total_nodes < self.config.max_nodes:
            node_id = queue.popleft()
            node = result.nodes.get(node_id)

            if not node or node.depth >= self.config.max_depth:
                continue

            # Evaluate node
            node.evaluation_score = self._evaluate_node(node, query)
            node.status = NodeStatus.EVALUATED if hasattr(NodeStatus, 'EVALUATED') else NodeStatus.EXPLORED

            if node.evaluation_score >= self.config.evaluation_threshold:
                node.status = NodeStatus.PROMISING

                # Expand node
                self._expand_node(node, result, query, context)

                for child_id in node.children_ids:
                    queue.append(child_id)
            else:
                node.status = NodeStatus.UNPROMISING
                if self.config.enable_pruning:
                    node.status = NodeStatus.PRUNED
                    result.pruned_branches += 1

    def _dfs_search(
        self,
        result: TreeResult,
        query: str,
        context: Optional[str]
    ) -> None:
        """Depth-first search implementation."""
        def dfs_visit(node_id: str) -> None:
            if result.total_nodes >= self.config.max_nodes:
                return

            node = result.nodes.get(node_id)
            if not node or node.depth >= self.config.max_depth:
                return

            # Evaluate node
            node.evaluation_score = self._evaluate_node(node, query)

            if node.evaluation_score >= self.config.evaluation_threshold:
                node.status = NodeStatus.PROMISING

                # Check if solution found
                if node.evaluation_score >= self.config.solution_threshold:
                    node.is_solution = True
                    return

                # Expand and continue DFS
                self._expand_node(node, result, query, context)

                for child_id in node.children_ids:
                    dfs_visit(child_id)
                    if any(n.is_solution for n in result.nodes.values()):
                        return
            else:
                node.status = NodeStatus.UNPROMISING
                if self.config.enable_pruning:
                    node.status = NodeStatus.PRUNED
                    result.pruned_branches += 1

        if result.root:
            for child_id in result.root.children_ids:
                dfs_visit(child_id)
                if any(n.is_solution for n in result.nodes.values()):
                    break

    def _best_first_search(
        self,
        result: TreeResult,
        query: str,
        context: Optional[str]
    ) -> None:
        """Greedy best-first search implementation."""
        import heapq

        # Priority queue: (-score, node_id) for max-heap behavior
        pq = []

        # Evaluate and add initial nodes
        for node_id in (result.root.children_ids if result.root else []):
            node = result.nodes.get(node_id)
            if node:
                node.evaluation_score = self._evaluate_node(node, query)
                heapq.heappush(pq, (-node.evaluation_score, node_id))

        while pq and result.total_nodes < self.config.max_nodes:
            _, node_id = heapq.heappop(pq)
            node = result.nodes.get(node_id)

            if not node or node.depth >= self.config.max_depth:
                continue

            node.status = NodeStatus.EXPLORED

            # Check if solution found
            if node.evaluation_score >= self.config.solution_threshold:
                node.is_solution = True
                break

            # Expand node
            self._expand_node(node, result, query, context)

            # Add children to queue
            for child_id in node.children_ids:
                child = result.nodes.get(child_id)
                if child:
                    child.evaluation_score = self._evaluate_node(child, query)
                    if child.evaluation_score >= self.config.evaluation_threshold:
                        child.status = NodeStatus.PROMISING
                        heapq.heappush(pq, (-child.evaluation_score, child_id))
                    else:
                        child.status = NodeStatus.UNPROMISING
                        if self.config.enable_pruning:
                            child.status = NodeStatus.PRUNED
                            result.pruned_branches += 1

    def _beam_search(
        self,
        result: TreeResult,
        query: str,
        context: Optional[str]
    ) -> None:
        """Beam search implementation."""
        current_beam = list(result.root.children_ids) if result.root else []

        while current_beam and result.total_nodes < self.config.max_nodes:
            # Evaluate all nodes in current beam
            scored_nodes = []
            for node_id in current_beam:
                node = result.nodes.get(node_id)
                if node and node.depth < self.config.max_depth:
                    node.evaluation_score = self._evaluate_node(node, query)
                    scored_nodes.append((node.evaluation_score, node_id))

            # Sort by score and keep top beam_width
            scored_nodes.sort(reverse=True)
            current_beam = [nid for _, nid in scored_nodes[:self.config.beam_width]]

            # Expand nodes in beam
            next_beam = []
            for node_id in current_beam:
                node = result.nodes.get(node_id)
                if node:
                    node.status = NodeStatus.PROMISING

                    # Check if solution
                    if node.evaluation_score >= self.config.solution_threshold:
                        node.is_solution = True
                        return

                    self._expand_node(node, result, query, context)
                    next_beam.extend(node.children_ids)

            current_beam = next_beam

    def _expand_node(
        self,
        node: ThoughtNode,
        result: TreeResult,
        query: str,
        context: Optional[str]
    ) -> None:
        """Expand a node by generating child thoughts."""
        # Generate child thoughts
        child_thoughts = self._generate_child_thoughts(node, query, context)

        for i, thought in enumerate(child_thoughts[:self.config.max_branches]):
            child_id = f"{node.node_id}_{i}"
            child = ThoughtNode(
                node_id=child_id,
                depth=node.depth + 1,
                thought=thought,
                parent_id=node.node_id,
                reasoning_path=node.reasoning_path + [thought],
                status=NodeStatus.PENDING
            )
            node.children_ids.append(child_id)
            node.is_leaf = False
            result.nodes[child_id] = child
            result.total_nodes += 1
            self._total_nodes_created += 1

    def _generate_child_thoughts(
        self,
        node: ThoughtNode,
        query: str,
        context: Optional[str]
    ) -> List[str]:
        """Generate child thoughts for a node."""
        # Use LLM if available
        if self.llm_client:
            return self._llm_generate_thoughts(node, query, context)

        # Template-based generation
        thought = node.thought.lower()

        if "option" in thought or "choice" in thought:
            return [
                f"Analyze the implications of: {node.thought[:50]}",
                f"Consider the consequences of: {node.thought[:50]}",
                f"Evaluate the feasibility of: {node.thought[:50]}",
            ]
        elif "cause" in thought or "issue" in thought:
            return [
                f"Investigate deeper: {node.thought[:50]}",
                f"Test this hypothesis: {node.thought[:50]}",
                f"Consider alternative: {node.thought[:50]}",
            ]
        else:
            return [
                f"Explore: {node.thought[:60]}",
                f"Elaborate: {node.thought[:60]}",
                f"Refine: {node.thought[:60]}",
            ]

    def _llm_generate_thoughts(
        self,
        node: ThoughtNode,
        query: str,
        context: Optional[str]
    ) -> List[str]:
        """Use LLM to generate child thoughts."""
        # Placeholder for LLM integration
        return [f"LLM thought {i+1} from: {node.thought[:30]}" for i in range(3)]

    def _evaluate_node(self, node: ThoughtNode, query: str) -> float:
        """Evaluate a node's promise."""
        if self.evaluate_fn:
            return self.evaluate_fn(node.thought, query)

        # Heuristic evaluation
        score = 0.5  # Base score

        # Adjust for thought quality
        if len(node.thought) > 30:
            score += 0.1

        # Adjust for reasoning path length (deeper = more specific)
        if len(node.reasoning_path) > 1:
            score += 0.1 * min(len(node.reasoning_path), 3)

        # Adjust for thought content
        thought_lower = node.thought.lower()
        positive_indicators = ["solution", "answer", "found", "resolved", "complete"]
        negative_indicators = ["failed", "impossible", "cannot", "invalid"]

        if any(p in thought_lower for p in positive_indicators):
            score += 0.2
        if any(n in thought_lower for n in negative_indicators):
            score -= 0.2

        return min(1.0, max(0.0, score))

    def _find_best_path(self, result: TreeResult) -> tuple:
        """Find the best solution path in the tree."""
        # Look for solution nodes first
        solution_nodes = [
            n for n in result.nodes.values()
            if n.is_solution
        ]

        if solution_nodes:
            best = max(solution_nodes, key=lambda n: n.evaluation_score)
            return best.reasoning_path, best.thought

        # Otherwise, find highest-scoring node
        evaluated_nodes = [
            n for n in result.nodes.values()
            if n.evaluation_score > 0 and n.status not in [NodeStatus.PRUNED, NodeStatus.UNPROMISING]
        ]

        if evaluated_nodes:
            best = max(evaluated_nodes, key=lambda n: n.evaluation_score)
            return best.reasoning_path, best.thought

        return [], ""

    def _calculate_confidence(self, result: TreeResult) -> float:
        """Calculate overall confidence from tree result."""
        if result.solution_found:
            return 0.9

        if not result.best_path:
            return 0.0

        # Base on best node score
        best_nodes = [
            n for n in result.nodes.values()
            if n.reasoning_path == result.best_path
        ]

        if best_nodes:
            return best_nodes[0].evaluation_score * 0.8

        return 0.5

    def _is_decision_query(self, query: str) -> bool:
        """Check if query is decision-making."""
        patterns = ["should i", "which", "choose", "decide", "better"]
        return any(p in query for p in patterns)

    def _is_procedural_query(self, query: str) -> bool:
        """Check if query is procedural."""
        patterns = ["how do i", "how to", "steps", "process"]
        return any(p in query for p in patterns)

    def _is_diagnostic_query(self, query: str) -> bool:
        """Check if query is diagnostic."""
        patterns = ["why is", "what's wrong", "not working", "error"]
        return any(p in query for p in patterns)
