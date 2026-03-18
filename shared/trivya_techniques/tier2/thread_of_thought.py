"""
PARWA TRIVYA Tier 2 Thread of Thought Technique.

Provides structured exploration of topics through interconnected
thought threads. Enables comprehensive coverage of complex topics.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ThoughtThread(BaseModel):
    """A single thread of thought."""
    thread_id: str
    topic: str
    key_points: List[str] = Field(default_factory=list)
    connections: List[str] = Field(default_factory=list)
    depth: int = Field(default=1, ge=1)
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class ToTResult(BaseModel):
    """Result from Thread of Thought processing."""
    query: str
    main_thread: ThoughtThread
    sub_threads: List[ThoughtThread] = Field(default_factory=list)
    explored_aspects: List[str] = Field(default_factory=list)
    synthesis: str = ""
    total_threads: int = Field(default=1)
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class ToTConfig(BaseModel):
    """Configuration for Thread of Thought."""
    max_threads: int = Field(default=5, ge=1, le=10)
    max_depth: int = Field(default=3, ge=1, le=5)
    min_points_per_thread: int = Field(default=2, ge=1, le=5)
    explore_connections: bool = Field(default=True)
    synthesize_results: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class ThreadOfThought:
    """
    Thread of Thought technique for TRIVYA Tier 2.

    Explores topics through interconnected thought threads,
    providing comprehensive coverage of complex topics with
    multiple perspectives and aspects.

    Features:
    - Multi-thread exploration
    - Connection discovery
    - Hierarchical depth
    - Comprehensive synthesis
    """

    def __init__(
        self,
        config: Optional[ToTConfig] = None,
        llm_client: Optional[Any] = None
    ) -> None:
        """
        Initialize Thread of Thought.

        Args:
            config: ToT configuration
            llm_client: LLM client for generation
        """
        self.config = config or ToTConfig()
        self.llm_client = llm_client

        # Performance tracking
        self._queries_processed = 0
        self._total_threads_created = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "thread_of_thought_initialized",
            "max_threads": self.config.max_threads,
        })

    def explore(
        self,
        query: str,
        context: Optional[str] = None,
        focus_areas: Optional[List[str]] = None
    ) -> ToTResult:
        """
        Apply thread of thought exploration to a query.

        Args:
            query: User query text
            context: Optional context from T1
            focus_areas: Optional specific areas to explore

        Returns:
            ToTResult with exploration threads

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Create main thread
        main_thread = self._create_main_thread(query, context)

        # Create sub-threads for exploration
        sub_threads = self._create_sub_threads(
            query, main_thread, focus_areas
        )

        # Discover connections
        if self.config.explore_connections:
            self._discover_connections(main_thread, sub_threads)

        # Collect explored aspects
        explored = self._collect_explored_aspects(main_thread, sub_threads)

        # Synthesize results
        synthesis = ""
        if self.config.synthesize_results:
            synthesis = self._synthesize(main_thread, sub_threads)

        # Calculate coverage
        coverage = self._calculate_coverage(main_thread, sub_threads)

        result = ToTResult(
            query=query,
            main_thread=main_thread,
            sub_threads=sub_threads,
            explored_aspects=explored,
            synthesis=synthesis,
            total_threads=1 + len(sub_threads),
            coverage_score=coverage,
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_processed += 1
        self._total_threads_created += result.total_threads
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "thread_of_thought_complete",
            "total_threads": result.total_threads,
            "coverage": coverage,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def generate_prompt(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a thread of thought prompt for an LLM.

        Args:
            query: User query
            context: Optional context

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "Explore this topic through multiple thought threads.",
            "",
            f"Topic: {query}",
            "",
            "Create threads for:",
            "1. Main Thread: Core aspects of the topic",
            "2. Context Thread: Background and history",
            "3. Implications Thread: Effects and consequences",
            "4. Applications Thread: Practical uses",
            "5. Connections Thread: Related topics",
            "",
            "For each thread:",
            "Thread: [Thread name]",
            "Key Points:",
            "- [Point 1]",
            "- [Point 2]",
            "Connections: [Related threads]",
            "",
            "Synthesis: [Overall understanding]",
        ]

        if context:
            prompt_parts.insert(3, f"Context: {context}")

        return "\n".join(prompt_parts)

    def parse_response(
        self,
        response: str,
        query: str
    ) -> ToTResult:
        """
        Parse an LLM response into structured result.

        Args:
            response: LLM response text
            query: Original query

        Returns:
            ToTResult with parsed threads
        """
        start_time = datetime.now()

        threads = []
        current_thread = None
        synthesis = ""

        lines = response.split("\n")

        for line in lines:
            line = line.strip()

            if line.lower().startswith("thread:"):
                if current_thread:
                    threads.append(current_thread)

                thread_name = line.split(":", 1)[-1].strip()
                current_thread = ThoughtThread(
                    thread_id=f"thread_{len(threads) + 1}",
                    topic=thread_name,
                    key_points=[],
                    connections=[],
                )

            elif line.startswith("-") and current_thread:
                point = line.lstrip("-").strip()
                current_thread.key_points.append(point)

            elif "connection" in line.lower() and current_thread:
                connections = line.split(":", 1)[-1].strip()
                current_thread.connections = [c.strip() for c in connections.split(",")]

            elif line.lower().startswith("synthesis:"):
                synthesis = line.split(":", 1)[-1].strip()

        if current_thread and current_thread not in threads:
            threads.append(current_thread)

        # Ensure we have at least main thread
        if not threads:
            threads.append(ThoughtThread(
                thread_id="main",
                topic=query,
                key_points=[response[:100]],
                connections=[],
            ))

        main_thread = threads[0] if threads else ThoughtThread(
            thread_id="main", topic=query
        )
        sub_threads = threads[1:] if len(threads) > 1 else []

        coverage = self._calculate_coverage(main_thread, sub_threads)

        result = ToTResult(
            query=query,
            main_thread=main_thread,
            sub_threads=sub_threads,
            synthesis=synthesis,
            total_threads=len(threads),
            coverage_score=coverage,
        )

        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Thread of Thought statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_threads_created": self._total_threads_created,
            "average_threads_per_query": (
                self._total_threads_created / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
        }

    def _create_main_thread(
        self,
        query: str,
        context: Optional[str]
    ) -> ThoughtThread:
        """
        Create the main thought thread.

        Args:
            query: User query
            context: Optional context

        Returns:
            Main ThoughtThread
        """
        # Determine key points based on query type
        query_lower = query.lower()

        if any(w in query_lower for w in ["tell me about", "explain", "describe"]):
            key_points = [
                "Definition and core concept",
                "Key characteristics",
                "Important aspects",
            ]
        elif any(w in query_lower for w in ["how", "process", "steps"]):
            key_points = [
                "Overview of the process",
                "Key stages involved",
                "Important considerations",
            ]
        else:
            key_points = [
                "Core aspects of the topic",
                "Key considerations",
                "Important details",
            ]

        return ThoughtThread(
            thread_id="main",
            topic=query,
            key_points=key_points,
            connections=[],
            depth=1,
            completeness=0.8,
        )

    def _create_sub_threads(
        self,
        query: str,
        main_thread: ThoughtThread,
        focus_areas: Optional[List[str]]
    ) -> List[ThoughtThread]:
        """
        Create sub-threads for exploration.

        Args:
            query: User query
            main_thread: Main thread
            focus_areas: Optional focus areas

        Returns:
            List of sub-threads
        """
        sub_threads = []

        # Determine sub-thread topics based on query
        thread_configs = self._determine_sub_thread_topics(query)

        for i, (topic, points) in enumerate(thread_configs[:self.config.max_threads - 1]):
            thread = ThoughtThread(
                thread_id=f"sub_{i + 1}",
                topic=topic,
                key_points=points,
                connections=["main"],
                depth=2,
                completeness=0.7,
            )
            sub_threads.append(thread)

        return sub_threads

    def _determine_sub_thread_topics(
        self,
        query: str
    ) -> List[tuple]:
        """
        Determine sub-thread topics for a query.

        Args:
            query: User query

        Returns:
            List of (topic, key_points) tuples
        """
        query_lower = query.lower()

        if any(w in query_lower for w in ["tell me about", "explain", "elaborate"]):
            return [
                ("Background & Context", ["History and origin", "Evolution over time", "Current state"]),
                ("Key Components", ["Main elements", "How they relate", "Dependencies"]),
                ("Practical Applications", ["Real-world uses", "Examples", "Best practices"]),
                ("Implications", ["Effects and impact", "Future outlook", "Considerations"]),
            ]
        elif any(w in query_lower for w in ["how", "process", "steps"]):
            return [
                ("Prerequisites", ["What's needed", "Requirements", "Preparation"]),
                ("Step-by-Step Process", ["Main steps", "Key actions", "Timeline"]),
                ("Common Challenges", ["Typical issues", "How to avoid", "Solutions"]),
                ("Best Practices", ["Tips for success", "Optimizations", "Expert advice"]),
            ]
        else:
            return [
                ("Key Aspects", ["Primary factors", "Important details", "Core elements"]),
                ("Related Topics", ["Connections", "Similar concepts", "Dependencies"]),
                ("Practical Relevance", ["Applications", "Use cases", "Real-world impact"]),
            ]

    def _discover_connections(
        self,
        main_thread: ThoughtThread,
        sub_threads: List[ThoughtThread]
    ) -> None:
        """
        Discover connections between threads.

        Args:
            main_thread: Main thread to update
            sub_threads: Sub-threads to update
        """
        # Connect main to all sub-threads
        main_thread.connections = [t.thread_id for t in sub_threads]

        # Find inter-thread connections
        for i, thread in enumerate(sub_threads):
            for j, other in enumerate(sub_threads):
                if i != j:
                    # Check for topic overlap
                    if any(word in other.topic.lower() for word in thread.topic.lower().split()):
                        thread.connections.append(other.thread_id)

    def _collect_explored_aspects(
        self,
        main_thread: ThoughtThread,
        sub_threads: List[ThoughtThread]
    ) -> List[str]:
        """
        Collect all explored aspects from threads.

        Args:
            main_thread: Main thread
            sub_threads: Sub-threads

        Returns:
            List of explored aspect strings
        """
        aspects = []

        # Add main thread topics
        aspects.append(f"Main: {main_thread.topic}")
        aspects.extend(main_thread.key_points)

        # Add sub-thread topics
        for thread in sub_threads:
            aspects.append(f"Thread: {thread.topic}")
            aspects.extend(thread.key_points)

        return aspects

    def _synthesize(
        self,
        main_thread: ThoughtThread,
        sub_threads: List[ThoughtThread]
    ) -> str:
        """
        Synthesize findings from all threads.

        Args:
            main_thread: Main thread
            sub_threads: Sub-threads

        Returns:
            Synthesis string
        """
        parts = [f"Comprehensive exploration of '{main_thread.topic}'"]

        if sub_threads:
            topics = [t.topic for t in sub_threads]
            parts.append(f"covering aspects: {', '.join(topics)}")

        total_points = len(main_thread.key_points) + sum(
            len(t.key_points) for t in sub_threads
        )
        parts.append(f"with {total_points} key insights identified.")

        return " ".join(parts)

    def _calculate_coverage(
        self,
        main_thread: ThoughtThread,
        sub_threads: List[ThoughtThread]
    ) -> float:
        """
        Calculate coverage score from threads.

        Args:
            main_thread: Main thread
            sub_threads: Sub-threads

        Returns:
            Coverage score 0-1
        """
        # Base coverage from main thread
        base_coverage = min(0.4, main_thread.completeness * 0.4)

        # Additional coverage from sub-threads
        sub_coverage = 0.0
        for thread in sub_threads:
            sub_coverage += min(0.15, thread.completeness * 0.15)

        # Bonus for connections
        connection_bonus = 0.0
        total_connections = len(main_thread.connections) + sum(
            len(t.connections) for t in sub_threads
        )
        connection_bonus = min(0.15, total_connections * 0.02)

        coverage = base_coverage + sub_coverage + connection_bonus

        return round(min(1.0, coverage), 2)
