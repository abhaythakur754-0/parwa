"""
PARWA CLARA (Contextual Learning and Retrieval for Accurate Answers).

CLARA is the primary Tier 1 technique for TRIVYA. It retrieves relevant
context from the knowledge base and uses HyDE for enhanced retrieval.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.knowledge_base.rag_pipeline import RAGPipeline, RAGResponse, RAGConfig
from shared.knowledge_base.hyde import HyDEGenerator, HyDEResult

logger = get_logger(__name__)


class CLARAResult(BaseModel):
    """
    Result from CLARA processing.
    """
    query: str
    retrieved_context: str = ""
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_method: str = "clara"
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class CLARAConfig(BaseModel):
    """
    Configuration for CLARA.
    """
    top_k: int = Field(default=5, ge=1, le=20)
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0)
    use_hyde: bool = Field(default=True)
    max_context_length: int = Field(default=4000, ge=100)
    fallback_enabled: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class CLARA:
    """
    CLARA - Contextual Learning and Retrieval for Accurate Answers.

    Tier 1 technique that retrieves relevant context from the knowledge base
    to ground AI responses in factual information.

    Features:
    - RAG-based context retrieval
    - HyDE-enhanced queries for better retrieval
    - Source attribution
    - Relevance scoring
    - Company-scoped knowledge isolation
    """

    def __init__(
        self,
        rag_pipeline: Optional[RAGPipeline] = None,
        hyde_generator: Optional[HyDEGenerator] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        llm_client: Optional[Any] = None,
        config: Optional[CLARAConfig] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize CLARA.

        Args:
            rag_pipeline: RAGPipeline instance for retrieval
            hyde_generator: HyDEGenerator for query enhancement
            embedding_fn: Function to generate embeddings
            llm_client: LLM client for generation
            config: CLARA configuration
            company_id: Company UUID for data isolation
        """
        self.config = config or CLARAConfig()
        self.company_id = company_id
        self.embedding_fn = embedding_fn
        self.llm_client = llm_client

        # Initialize RAG pipeline
        self.rag_pipeline = rag_pipeline or RAGPipeline(
            embedding_fn=embedding_fn,
            llm_client=llm_client,
            company_id=company_id,
            config=RAGConfig(
                top_k=self.config.top_k,
                min_relevance_score=self.config.min_relevance_score,
                use_hyde=self.config.use_hyde,
                max_context_length=self.config.max_context_length,
            )
        )

        # Initialize HyDE generator
        self.hyde_generator = hyde_generator or HyDEGenerator(
            llm_client=llm_client,
            embedding_fn=embedding_fn
        )

        # Performance tracking
        self._queries_processed = 0
        self._total_processing_time = 0.0
        self._total_tokens_used = 0

        logger.info({
            "event": "clara_initialized",
            "company_id": str(company_id) if company_id else None,
            "use_hyde": self.config.use_hyde,
            "top_k": self.config.top_k,
        })

    def retrieve(
        self,
        query: str,
        context_override: Optional[str] = None
    ) -> CLARAResult:
        """
        Retrieve relevant context for a query.

        This is the main CLARA method - always called on every query
        to provide grounded context for AI responses.

        Args:
            query: User query text
            context_override: Optional context to use instead of retrieval

        Returns:
            CLARAResult with retrieved context and metadata

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Use override context if provided
        if context_override:
            result = CLARAResult(
                query=query,
                retrieved_context=context_override,
                retrieval_method="override",
                metadata={"override": True}
            )
            return self._finalize_result(result, start_time)

        # Perform retrieval
        try:
            # Use HyDE if enabled
            if self.config.use_hyde:
                retrieval_result = self._retrieve_with_hyde(query)
            else:
                retrieval_result = self._retrieve_standard(query)

            result = CLARAResult(
                query=query,
                retrieved_context=retrieval_result["context"],
                sources=retrieval_result["sources"],
                relevance_score=retrieval_result["relevance"],
                retrieval_method=retrieval_result["method"],
                tokens_used=retrieval_result["tokens"],
            )

        except Exception as e:
            logger.error({
                "event": "clara_retrieval_failed",
                "error": str(e),
            })

            # Fallback to empty context if enabled
            if self.config.fallback_enabled:
                result = CLARAResult(
                    query=query,
                    retrieved_context="",
                    retrieval_method="fallback",
                    metadata={"error": str(e)}
                )
            else:
                raise

        return self._finalize_result(result, start_time)

    def retrieve_with_hyde(
        self,
        query: str
    ) -> CLARAResult:
        """
        Retrieve using HyDE-enhanced query.

        Args:
            query: User query text

        Returns:
            CLARAResult with HyDE-enhanced retrieval
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        retrieval_result = self._retrieve_with_hyde(query)

        result = CLARAResult(
            query=query,
            retrieved_context=retrieval_result["context"],
            sources=retrieval_result["sources"],
            relevance_score=retrieval_result["relevance"],
            retrieval_method="hyde",
            tokens_used=retrieval_result["tokens"],
        )

        return self._finalize_result(result, start_time)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get CLARA statistics.

        Returns:
            Dict with CLARA stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "total_tokens_used": self._total_tokens_used,
            "average_tokens_per_query": (
                self._total_tokens_used / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "config": self.config.model_dump(),
        }

    def _retrieve_standard(
        self,
        query: str
    ) -> Dict[str, Any]:
        """
        Standard retrieval without HyDE.

        Args:
            query: User query

        Returns:
            Dict with context, sources, relevance, tokens
        """
        try:
            rag_response = self.rag_pipeline.query(
                query,
                retrieval_strategy="standard"
            )

            return {
                "context": self._build_context_from_rag(rag_response),
                "sources": rag_response.sources,
                "relevance": rag_response.confidence,
                "method": "standard",
                "tokens": rag_response.tokens_used,
            }
        except Exception as e:
            logger.warning({
                "event": "clara_standard_retrieval_failed",
                "error": str(e),
            })
            return {
                "context": "",
                "sources": [],
                "relevance": 0.0,
                "method": "standard_failed",
                "tokens": 0,
            }

    def _retrieve_with_hyde(
        self,
        query: str
    ) -> Dict[str, Any]:
        """
        HyDE-enhanced retrieval.

        Args:
            query: User query

        Returns:
            Dict with context, sources, relevance, tokens
        """
        try:
            # Generate hypothetical document
            hyde_result = self.hyde_generator.generate(query)

            # Use HyDE embedding for retrieval
            rag_response = self.rag_pipeline.query(
                query,
                retrieval_strategy="hyde"
            )

            return {
                "context": self._build_context_from_rag(rag_response),
                "sources": rag_response.sources,
                "relevance": rag_response.confidence,
                "method": "hyde",
                "tokens": rag_response.tokens_used + hyde_result.tokens_used,
            }
        except Exception as e:
            logger.warning({
                "event": "clara_hyde_retrieval_failed",
                "error": str(e),
                "falling_back": True,
            })
            # Fallback to standard
            return self._retrieve_standard(query)

    def _build_context_from_rag(
        self,
        rag_response: RAGResponse
    ) -> str:
        """
        Build context string from RAG response.

        Args:
            rag_response: RAG response

        Returns:
            Context string
        """
        if not rag_response.sources:
            return ""

        context_parts = []
        for i, source in enumerate(rag_response.sources[:5]):
            preview = source.get("content_preview", "")
            if preview:
                context_parts.append(f"[Source {i+1}]\n{preview}")

        return "\n\n".join(context_parts)

    def _finalize_result(
        self,
        result: CLARAResult,
        start_time: datetime
    ) -> CLARAResult:
        """
        Finalize result with timing and stats.

        Args:
            result: CLARAResult to finalize
            start_time: Processing start time

        Returns:
            Finalized CLARAResult
        """
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        result.processing_time_ms = processing_time

        # Update stats
        self._queries_processed += 1
        self._total_processing_time += processing_time
        self._total_tokens_used += result.tokens_used

        logger.info({
            "event": "clara_retrieval_complete",
            "query_length": len(result.query),
            "context_length": len(result.retrieved_context),
            "relevance_score": result.relevance_score,
            "retrieval_method": result.retrieval_method,
            "processing_time_ms": processing_time,
        })

        return result
