"""
PARWA RAG MCP Server.

MCP server for RAG-based document retrieval operations.
Provides tools for document retrieval, ingestion, and collection stats.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import uuid4

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RAGServer(BaseMCPServer):
    """
    MCP Server for RAG operations.

    Provides tools for:
    - retrieve: RAG-based document retrieval
    - ingest: Ingest documents into the collection
    - get_collection_stats: Get collection statistics

    Example:
        server = RAGServer()
        await server.start()
        result = await server.handle_tool_call("retrieve", {"query": "how to reset password"})
    """

    DEFAULT_TOP_K = 5

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        rag_pipeline: Optional[Any] = None
    ) -> None:
        """
        Initialize RAG Server.

        Args:
            config: Optional server configuration
            rag_pipeline: Optional RAGPipeline instance (from shared/knowledge_base)
        """
        self._rag_pipeline = rag_pipeline
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._total_documents = 0
        self._total_chunks = 0
        self._last_ingest_time: Optional[datetime] = None

        super().__init__(name="rag_server", config=config)

    def _register_tools(self) -> None:
        """Register RAG tools."""
        self.register_tool(
            name="retrieve",
            description="Retrieve relevant documents using RAG-based similarity search",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": f"Number of results to return (default {self.DEFAULT_TOP_K})",
                        "default": self.DEFAULT_TOP_K
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum relevance score (0-1, default 0.3)",
                        "default": 0.3
                    }
                },
                "required": ["query"]
            },
            handler=self._handle_retrieve
        )

        self.register_tool(
            name="ingest",
            description="Ingest documents into the RAG collection",
            parameters_schema={
                "type": "object",
                "properties": {
                    "documents": {
                        "type": "array",
                        "description": "List of documents to ingest",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "metadata": {"type": "object"}
                            },
                            "required": ["content"]
                        }
                    }
                },
                "required": ["documents"]
            },
            handler=self._handle_ingest
        )

        self.register_tool(
            name="get_collection_stats",
            description="Get statistics about the RAG document collection",
            parameters_schema={
                "type": "object",
                "properties": {}
            },
            handler=self._handle_get_stats
        )

    async def _handle_retrieve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle retrieve tool call.

        Args:
            params: Parameters containing query, optional top_k and min_score

        Returns:
            Dictionary with retrieved documents and scores
        """
        query = params["query"]
        top_k = params.get("top_k", self.DEFAULT_TOP_K)
        min_score = params.get("min_score", 0.3)

        if not query or not query.strip():
            return {
                "success": False,
                "error": "Query cannot be empty",
            }

        # Use real RAG pipeline if available, otherwise use mock
        if self._rag_pipeline:
            return await self._retrieve_with_pipeline(query, top_k)

        # Mock retrieval for testing
        results = self._mock_retrieve(query, top_k, min_score)

        logger.info({
            "event": "rag_retrieve_completed",
            "query_length": len(query),
            "results_found": len(results),
            "top_k": top_k,
        })

        return {
            "success": True,
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
            "results": results,
            "total_results": len(results),
        }

    async def _retrieve_with_pipeline(
        self,
        query: str,
        top_k: int
    ) -> Dict[str, Any]:
        """
        Retrieve using actual RAG pipeline.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Retrieval results
        """
        try:
            response = self._rag_pipeline.query(query)

            return {
                "success": True,
                "query": query,
                "results": [
                    {
                        "document_id": str(source.get("document_id", "unknown")),
                        "content": source.get("content_preview", ""),
                        "score": source.get("relevance_score", 0.0),
                        "metadata": source.get("metadata", {}),
                    }
                    for source in response.sources[:top_k]
                ],
                "confidence": response.confidence,
                "retrieval_method": response.retrieval_method,
            }
        except Exception as e:
            logger.error({
                "event": "rag_pipeline_error",
                "error": str(e),
            })
            return {
                "success": False,
                "error": str(e),
            }

    def _mock_retrieve(
        self,
        query: str,
        top_k: int,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """
        Mock retrieval for testing without RAG pipeline.

        Args:
            query: Search query
            top_k: Number of results
            min_score: Minimum relevance score

        Returns:
            List of mock documents
        """
        query_words = set(query.lower().split())
        results = []

        for doc_id, doc in self._documents.items():
            # Simple keyword matching
            content_words = set(doc["content"].lower().split())
            overlap = len(query_words & content_words)
            score = overlap / max(len(query_words), 1) if query_words else 0

            if score >= min_score:
                results.append({
                    "document_id": doc_id,
                    "content": doc["content"][:500] + "..." if len(doc["content"]) > 500 else doc["content"],
                    "score": round(score, 3),
                    "metadata": doc.get("metadata", {}),
                })

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def _handle_ingest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle ingest tool call.

        Args:
            params: Parameters containing documents list

        Returns:
            Dictionary with ingestion results
        """
        documents = params["documents"]

        if not documents:
            return {
                "success": False,
                "error": "No documents provided",
            }

        ingested_ids = []
        errors = []

        for doc in documents:
            content = doc.get("content")
            if not content:
                errors.append("Document missing content field")
                continue

            doc_id = str(uuid4())
            self._documents[doc_id] = {
                "content": content,
                "metadata": doc.get("metadata", {}),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            ingested_ids.append(doc_id)
            self._total_chunks += 1

        self._total_documents += len(ingested_ids)
        self._last_ingest_time = datetime.now(timezone.utc)

        logger.info({
            "event": "rag_documents_ingested",
            "documents_count": len(ingested_ids),
            "errors_count": len(errors),
        })

        return {
            "success": len(ingested_ids) > 0,
            "documents_ingested": len(ingested_ids),
            "document_ids": ingested_ids,
            "errors": errors if errors else None,
        }

    async def _handle_get_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_collection_stats tool call.

        Args:
            params: Empty parameters

        Returns:
            Dictionary with collection statistics
        """
        stats = {
            "success": True,
            "collection_name": "default",
            "total_documents": self._total_documents,
            "total_chunks": self._total_chunks,
            "last_ingest_time": (
                self._last_ingest_time.isoformat()
                if self._last_ingest_time else None
            ),
            "status": "healthy",
        }

        # Add RAG pipeline stats if available
        if self._rag_pipeline:
            try:
                pipeline_stats = self._rag_pipeline.get_stats()
                stats["pipeline_stats"] = pipeline_stats
            except Exception as e:
                stats["pipeline_stats_error"] = str(e)

        return stats
