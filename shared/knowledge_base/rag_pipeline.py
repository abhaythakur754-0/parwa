"""
PARWA RAG Pipeline.

Complete Retrieval-Augmented Generation pipeline combining
vector store, knowledge base manager, HyDE, and multi-query
for enhanced retrieval and answer generation.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID, uuid4
from datetime import datetime, timezone
import json

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.knowledge_base.vector_store import VectorStore, Document, SearchResult
from shared.knowledge_base.kb_manager import KnowledgeBaseManager
from shared.knowledge_base.hyde import HyDEGenerator, HyDEResult
from shared.knowledge_base.multi_query import MultiQueryGenerator, MultiQueryResult

logger = get_logger(__name__)


class RAGResponse(BaseModel):
    """
    Response from RAG pipeline.
    """
    query: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_method: str = "standard"
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        use_enum_values=True)


class RAGConfig(BaseModel):
    """
    Configuration for RAG Pipeline.
    """
    top_k: int = Field(default=5, ge=1, le=20)
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0)
    use_hyde: bool = Field(default=True)
    use_multi_query: bool = Field(default=True)
    num_query_variations: int = Field(default=3, ge=1, le=10)
    max_context_length: int = Field(default=4000, ge=100)
    rerank_results: bool = Field(default=True)
    include_sources: bool = Field(default=True)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    model_config = ConfigDict(
        use_enum_values=True)


class RAGPipeline:
    """
    Complete RAG Pipeline for knowledge retrieval and generation.

    Features:
    - Document ingestion and indexing
    - Multiple retrieval strategies (standard, HyDE, multi-query)
    - Source attribution
    - Confidence scoring
    - Company-scoped isolation
    - Performance tracking
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        kb_manager: Optional[KnowledgeBaseManager] = None,
        hyde_generator: Optional[HyDEGenerator] = None,
        multi_query_generator: Optional[MultiQueryGenerator] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        llm_client: Optional[Any] = None,
        config: Optional[RAGConfig] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize RAG Pipeline.

        Args:
            vector_store: VectorStore instance
            kb_manager: KnowledgeBaseManager instance
            hyde_generator: HyDEGenerator instance
            multi_query_generator: MultiQueryGenerator instance
            embedding_fn: Function to generate embeddings
            llm_client: LLM client for answer generation
            config: Pipeline configuration
            company_id: Company UUID for data isolation
        """
        self.config = config or RAGConfig()
        self.company_id = company_id
        self.embedding_fn = embedding_fn
        self.llm_client = llm_client

        # Initialize components
        self.vector_store = vector_store or VectorStore(
            company_id=company_id
        )

        self.kb_manager = kb_manager or KnowledgeBaseManager(
            vector_store=self.vector_store,
            company_id=company_id,
            embedding_fn=embedding_fn
        )

        self.hyde_generator = hyde_generator or HyDEGenerator(
            llm_client=llm_client,
            embedding_fn=embedding_fn
        )

        self.multi_query_generator = multi_query_generator or MultiQueryGenerator(
            llm_client=llm_client
        )

        # Performance tracking
        self._queries_processed = 0
        self._total_processing_time = 0.0
        self._total_tokens_used = 0

        logger.info({
            "event": "rag_pipeline_initialized",
            "company_id": str(company_id) if company_id else None,
            "use_hyde": self.config.use_hyde,
            "use_multi_query": self.config.use_multi_query,
        })

    def ingest(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Ingest a document into the knowledge base.

        Args:
            content: Document content
            metadata: Optional metadata

        Returns:
            Document ID
        """
        result = self.kb_manager.ingest_document(
            content=content,
            metadata=metadata
        )
        return result.document_id

    def ingest_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[UUID]:
        """
        Ingest multiple documents.

        Args:
            documents: List of documents with 'content' and optional 'metadata'

        Returns:
            List of document IDs
        """
        results = self.kb_manager.ingest_batch(documents)
        return [r.document_id for r in results if r.status == "success"]

    def query(
        self,
        query: str,
        retrieval_strategy: Optional[str] = None
    ) -> RAGResponse:
        """
        Execute a RAG query.

        Args:
            query: User query
            retrieval_strategy: Override default strategy
                ("standard", "hyde", "multi_query", "hybrid")

        Returns:
            RAGResponse with answer and sources

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Determine retrieval strategy
        strategy = retrieval_strategy or self._determine_strategy(query)

        # Retrieve documents
        documents = self._retrieve(query, strategy)

        # Generate answer
        answer, tokens = self._generate_answer(query, documents)

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Calculate confidence
        confidence = self._calculate_confidence(documents)

        # Prepare sources
        sources = []
        if self.config.include_sources:
            sources = [
                {
                    "document_id": str(doc.document.id),
                    "content_preview": doc.document.content[:200],
                    "relevance_score": doc.score,
                    "metadata": doc.document.metadata,
                }
                for doc in documents[:3]  # Top 3 sources
            ]

        # Update stats
        self._queries_processed += 1
        self._total_processing_time += processing_time
        self._total_tokens_used += tokens

        logger.info({
            "event": "rag_query_completed",
            "query_length": len(query),
            "strategy": strategy,
            "documents_retrieved": len(documents),
            "confidence": confidence,
            "processing_time_ms": processing_time,
        })

        return RAGResponse(
            query=query,
            answer=answer,
            sources=sources,
            confidence=confidence,
            retrieval_method=strategy,
            tokens_used=tokens,
            processing_time_ms=processing_time,
            metadata={
                "company_id": str(self.company_id) if self.company_id else None,
                "top_k": self.config.top_k,
            }
        )

    def retrieve_only(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Retrieve documents without generating answer.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of SearchResult
        """
        top_k = top_k or self.config.top_k

        if self.config.use_hyde:
            return self._retrieve_with_hyde(query, top_k)
        elif self.config.use_multi_query:
            return self._retrieve_with_multi_query(query, top_k)
        else:
            return self._retrieve_standard(query, top_k)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.

        Returns:
            Dict with pipeline stats
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
            "kb_stats": self.kb_manager.get_stats(),
        }

    def _retrieve(
        self,
        query: str,
        strategy: str
    ) -> List[SearchResult]:
        """
        Retrieve documents using specified strategy.

        Args:
            query: Search query
            strategy: Retrieval strategy

        Returns:
            List of SearchResult
        """
        if strategy == "hyde":
            return self._retrieve_with_hyde(query, self.config.top_k)
        elif strategy == "multi_query":
            return self._retrieve_with_multi_query(query, self.config.top_k)
        elif strategy == "hybrid":
            return self._retrieve_hybrid(query, self.config.top_k)
        else:
            return self._retrieve_standard(query, self.config.top_k)

    def _retrieve_standard(
        self,
        query: str,
        top_k: int
    ) -> List[SearchResult]:
        """
        Standard vector similarity retrieval.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of SearchResult
        """
        if not self.embedding_fn:
            logger.warning({
                "event": "embedding_fn_missing",
                "message": "No embedding function configured"
            })
            return []

        try:
            query_embedding = self.embedding_fn(query)
            return self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                min_score=self.config.min_relevance_score
            )
        except Exception as e:
            logger.error({
                "event": "standard_retrieval_failed",
                "error": str(e),
            })
            return []

    def _retrieve_with_hyde(
        self,
        query: str,
        top_k: int
    ) -> List[SearchResult]:
        """
        HyDE-based retrieval.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of SearchResult
        """
        try:
            # Generate hypothetical document
            hyde_result = self.hyde_generator.generate(query)

            if not hyde_result.embedding:
                # Fallback to standard retrieval
                return self._retrieve_standard(query, top_k)

            return self.vector_store.search(
                query_embedding=hyde_result.embedding,
                top_k=top_k,
                min_score=self.config.min_relevance_score
            )
        except Exception as e:
            logger.error({
                "event": "hyde_retrieval_failed",
                "error": str(e),
            })
            return self._retrieve_standard(query, top_k)

    def _retrieve_with_multi_query(
        self,
        query: str,
        top_k: int
    ) -> List[SearchResult]:
        """
        Multi-query retrieval.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of SearchResult
        """
        if not self.embedding_fn:
            return self._retrieve_standard(query, top_k)

        try:
            # Generate query variations
            multi_result = self.multi_query_generator.generate(
                query,
                num_variations=self.config.num_query_variations
            )

            # Retrieve for each variation
            all_results: Dict[str, SearchResult] = {}

            for variation in multi_result.variations:
                try:
                    var_embedding = self.embedding_fn(variation.variation)
                    results = self.vector_store.search(
                        query_embedding=var_embedding,
                        top_k=top_k,
                        min_score=self.config.min_relevance_score
                    )

                    for result in results:
                        doc_id = str(result.document.id)
                        if doc_id not in all_results:
                            all_results[doc_id] = result
                        else:
                            # Keep higher score
                            if result.score > all_results[doc_id].score:
                                all_results[doc_id] = result
                except Exception:
                    continue

            # Sort by score and return top_k
            sorted_results = sorted(
                all_results.values(),
                key=lambda x: x.score,
                reverse=True
            )

            return sorted_results[:top_k]
        except Exception as e:
            logger.error({
                "event": "multi_query_retrieval_failed",
                "error": str(e),
            })
            return self._retrieve_standard(query, top_k)

    def _retrieve_hybrid(
        self,
        query: str,
        top_k: int
    ) -> List[SearchResult]:
        """
        Hybrid retrieval combining multiple strategies.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of SearchResult
        """
        # Get results from different strategies
        standard_results = self._retrieve_standard(query, top_k)
        hyde_results = self._retrieve_with_hyde(query, top_k)

        # Combine and deduplicate
        combined: Dict[str, SearchResult] = {}

        for result in standard_results:
            doc_id = str(result.document.id)
            combined[doc_id] = result

        for result in hyde_results:
            doc_id = str(result.document.id)
            if doc_id in combined:
                # Average the scores
                combined[doc_id] = SearchResult(
                    document=result.document,
                    score=(combined[doc_id].score + result.score) / 2
                )
            else:
                combined[doc_id] = result

        # Sort and return
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x.score,
            reverse=True
        )

        return sorted_results[:top_k]

    def _generate_answer(
        self,
        query: str,
        documents: List[SearchResult]
    ) -> tuple[str, int]:
        """
        Generate answer from retrieved documents.

        Args:
            query: User query
            documents: Retrieved documents

        Returns:
            Tuple of (answer, tokens_used)
        """
        if not documents:
            return "I couldn't find any relevant information to answer your question.", 0

        # Build context from documents
        context = self._build_context(documents)

        if not self.llm_client:
            # Return context-based answer without LLM
            return self._format_context_answer(documents), 0

        try:
            prompt = self._build_generation_prompt(query, context)
            answer = self._call_llm(prompt)
            tokens = len(answer.split())  # Approximate
            return answer, tokens
        except Exception as e:
            logger.error({
                "event": "answer_generation_failed",
                "error": str(e),
            })
            return self._format_context_answer(documents), 0

    def _build_context(
        self,
        documents: List[SearchResult],
        max_length: Optional[int] = None
    ) -> str:
        """
        Build context string from documents.

        Args:
            documents: Retrieved documents
            max_length: Maximum context length

        Returns:
            Context string
        """
        max_length = max_length or self.config.max_context_length
        context_parts: List[str] = []
        current_length = 0

        for i, result in enumerate(documents):
            content = result.document.content
            if current_length + len(content) > max_length:
                break

            context_parts.append(f"[Document {i+1}]\n{content}")
            current_length += len(content)

        return "\n\n".join(context_parts)

    def _build_generation_prompt(
        self,
        query: str,
        context: str
    ) -> str:
        """
        Build prompt for answer generation.

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Formatted prompt
        """
        return f"""Based on the following context, please answer the user's question.
If the context doesn't contain relevant information, say so.

Context:
{context}

Question: {query}

Answer:"""

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM for generation.

        Args:
            prompt: Generation prompt

        Returns:
            Generated text
        """
        if hasattr(self.llm_client, "invoke"):
            response = self.llm_client.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)

        if hasattr(self.llm_client, "chat") and hasattr(self.llm_client.chat, "completions"):
            response = self.llm_client.chat.completions.create(
                model=getattr(self.llm_client, "model_name", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content

        if callable(self.llm_client):
            return str(self.llm_client(prompt))

        raise ValueError("Unsupported LLM client interface")

    def _format_context_answer(
        self,
        documents: List[SearchResult]
    ) -> str:
        """
        Format answer from context without LLM.

        Args:
            documents: Retrieved documents

        Returns:
            Formatted answer string
        """
        if not documents:
            return "No relevant documents found."

        top_doc = documents[0].document
        return f"Based on the knowledge base: {top_doc.content[:500]}..."

    def _calculate_confidence(
        self,
        documents: List[SearchResult]
    ) -> float:
        """
        Calculate confidence score for the response.

        Args:
            documents: Retrieved documents

        Returns:
            Confidence score between 0 and 1
        """
        if not documents:
            return 0.0

        # Use average of top 3 scores
        top_scores = [d.score for d in documents[:3]]
        return sum(top_scores) / len(top_scores)

    def _determine_strategy(self, query: str) -> str:
        """
        Determine best retrieval strategy for query.

        Args:
            query: User query

        Returns:
            Strategy name
        """
        # Simple heuristic-based strategy selection
        query_lower = query.lower()

        # Technical or specific queries benefit from HyDE
        if any(word in query_lower for word in ["how to", "explain", "why", "what is"]):
            if self.config.use_hyde:
                return "hyde"

        # Broad queries benefit from multi-query
        if any(word in query_lower for word in ["tell me", "show me", "list"]):
            if self.config.use_multi_query:
                return "multi_query"

        # Default to hybrid if both enabled
        if self.config.use_hyde and self.config.use_multi_query:
            return "hybrid"

        if self.config.use_hyde:
            return "hyde"

        if self.config.use_multi_query:
            return "multi_query"

        return "standard"
