"""
PARWA MCP — Knowledge Base Server (v2.0.0)

Provides knowledge base document query tools backed by the PARWA backend
REST API.  All tool handlers call the real backend endpoints and fall
back to graceful error responses (never mock data) when the backend
is unreachable.

Tools:
  - kb_search       — Search KB documents using semantic/hybrid search
  - kb_get_document — Retrieve a specific document by ID
  - kb_list_bases   — List all available knowledge bases
  - kb_upload_url   — Import knowledge from a URL into the KB

REST endpoints:
  - POST /knowledge/kb/search
  - GET  /knowledge/kb/bases
  - GET  /knowledge/kb/documents/{document_id}
  - POST /knowledge/kb/upload-url
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.config import get_settings
from mcp_server.models import (
    KBDocument,
    KBQueryRequest,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.kb_server")


# ═══════════════════════════════════════════════════════════════════
# Backend API Client Helper
# ═══════════════════════════════════════════════════════════════════


class _BackendClient:
    """Helper for calling the PARWA backend API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.BACKEND_URL.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def post(self, path: str, json_data: dict) -> dict:
        client = await self._get_client()
        try:
            response = await client.post(path, json=json_data)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("backend_api_error", path=path, error=str(exc))
            return {"status": "error", "data": {"message": str(exc)}}

    async def get(self, path: str) -> dict:
        client = await self._get_client()
        try:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("backend_api_error", path=path, error=str(exc))
            return {"status": "error", "data": {"message": str(exc)}}

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# ═══════════════════════════════════════════════════════════════════
# URL Content Fetcher
# ═══════════════════════════════════════════════════════════════════

_URL_FETCH_TIMEOUT = 30.0
_URL_MAX_CONTENT_LENGTH = 5_000_000  # 5 MB
_USER_AGENT = "PARWA-MCP-KBUpload/2.0"
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


async def _fetch_url_content(url: str) -> dict:
    """Fetch and extract text content from a URL.

    Returns a dict with:
      - status: "ok" or "error"
      - text: extracted plain text (or None on error)
      - title: page title if detectable
      - error: error message if status is "error"
    """
    try:
        async with httpx.AsyncClient(
            timeout=_URL_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = await client.get(url)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code} for {url}",
                }

            if len(response.content) > _URL_MAX_CONTENT_LENGTH:
                return {
                    "status": "error",
                    "error": f"Content too large ({len(response.content)} bytes) for {url}",
                }

            text = response.text

            # Extract title if possible
            title = ""
            title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = _HTML_TAG_RE.sub("", title_match.group(1)).strip()

            # Strip HTML if the content appears to be HTML
            if _looks_like_html(text):
                text = _strip_html(text)

            return {
                "status": "ok",
                "text": text,
                "title": title or url,
            }

    except httpx.TimeoutException:
        return {"status": "error", "error": f"Request timed out for {url}"}
    except httpx.HTTPError as exc:
        return {"status": "error", "error": f"HTTP error for {url}: {exc}"}
    except Exception as exc:
        return {"status": "error", "error": f"Unexpected error fetching {url}: {exc}"}


def _looks_like_html(text: str) -> bool:
    """Heuristic check: does the text contain HTML tags?"""
    return (
        "<" in text
        and ">" in text
        and (
            "<html" in text.lower()
            or "<body" in text.lower()
            or "<p" in text.lower()
            or "<div" in text.lower()
        )
    )


def _strip_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    # Remove <script> and <style> blocks
    cleaned = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
    # Remove all remaining HTML tags
    cleaned = _HTML_TAG_RE.sub(" ", cleaned)
    # Decode common HTML entities
    cleaned = cleaned.replace("&amp;", "&")
    cleaned = cleaned.replace("&lt;", "<")
    cleaned = cleaned.replace("&gt;", ">")
    cleaned = cleaned.replace("&quot;", '"')
    cleaned = cleaned.replace("&#39;", "'")
    cleaned = cleaned.replace("&nbsp;", " ")
    # Collapse whitespace
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[dict]:
    """Simple chunking of text into overlapping segments.

    Each chunk is a dict with 'content' and 'metadata' fields.
    """
    if not text or not text.strip():
        return []

    chunks: list[dict] = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        # Try to break at a sentence boundary if possible
        if end < len(text):
            # Look for the last sentence end within the chunk
            last_period = chunk_text.rfind(".")
            last_newline = chunk_text.rfind("\n")
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk_text = chunk_text[: break_point + 1]
                end = start + break_point + 1

        chunks.append({
            "content": chunk_text.strip(),
            "metadata": {"chunk_index": chunk_index},
        })

        start = end - overlap
        if start <= (end - chunk_size):
            start = end - overlap
        chunk_index += 1

    return chunks


# ═══════════════════════════════════════════════════════════════════
# KB Server
# ═══════════════════════════════════════════════════════════════════


class KBServer(MCPServerBase):
    """MCP sub-server for knowledge base document queries."""

    name = "kb_server"
    description = "Knowledge base document search and retrieval"
    category = ToolCategory.KNOWLEDGE
    version = "2.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._backend = _BackendClient()

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register KB tools."""
        registry.register_tool(
            ToolDefinition(
                name="kb_search",
                description="Search knowledge base documents using semantic or hybrid search. "
                            "Returns ranked documents with relevance scores. "
                            "Calls the backend RAG search API with the parwa variant.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query / topic",
                        },
                        "knowledge_base_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific KB IDs to search (empty = all)",
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["semantic", "keyword", "hybrid"],
                            "default": "hybrid",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Max results to return",
                        },
                    },
                    "required": ["query"],
                },
                tags=["knowledge_base", "search", "documents"],
                version="2.0.0",
            ),
            handler=self._invoke_kb_search,
        )

        registry.register_tool(
            ToolDefinition(
                name="kb_get_document",
                description="Retrieve a specific document from a knowledge base by ID. "
                            "Calls the backend RAG documents endpoint to fetch full "
                            "document content with all chunks.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to retrieve",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "Company (tenant) ID that owns the document",
                        },
                        "knowledge_base_id": {
                            "type": "string",
                            "description": "Knowledge base containing the document",
                        },
                    },
                    "required": ["document_id"],
                },
                tags=["knowledge_base", "document", "retrieve"],
                version="2.0.0",
            ),
            handler=self._invoke_kb_get_document,
        )

        registry.register_tool(
            ToolDefinition(
                name="kb_list_bases",
                description="List all available knowledge bases with statistics. "
                            "Calls the backend KB stats endpoint for real data.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                tags=["knowledge_base", "list"],
                version="2.0.0",
            ),
            handler=self._invoke_kb_list_bases,
        )

        registry.register_tool(
            ToolDefinition(
                name="kb_upload_url",
                description="Import knowledge from a URL into the knowledge base. "
                            "Fetches the URL content, chunks it, and stores it in the "
                            "vector store via the backend API for future retrieval.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to scrape and import",
                        },
                        "document_id": {
                            "type": "string",
                            "description": "Optional document ID (auto-generated if omitted)",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional document-level metadata",
                        },
                    },
                    "required": ["url"],
                },
                tags=["knowledge_base", "upload", "url", "import"],
                version="2.0.0",
            ),
            handler=self._invoke_kb_upload_url,
        )

    def get_router(self) -> APIRouter:
        """Return the KB REST router."""
        router = APIRouter(prefix="/knowledge/kb", tags=["Knowledge — KB"])

        @router.post("/search", response_model=list[KBDocument])
        async def search_kb(request: KBQueryRequest) -> list[KBDocument]:
            """Search knowledge bases via REST."""
            result = await self._invoke_kb_search(request.model_dump())
            if result.success and result.data:
                return [KBDocument(**d) for d in result.data]
            return []

        @router.get("/bases")
        async def list_bases() -> list[dict]:
            """List available knowledge bases."""
            result = await self._invoke_kb_list_bases({})
            if result.success:
                return result.data or []
            return []

        @router.get("/documents/{document_id}")
        async def get_document(document_id: str, company_id: str = "") -> dict:
            """Get a specific document from the knowledge base."""
            result = await self._invoke_kb_get_document({
                "document_id": document_id,
                "company_id": company_id,
            })
            if result.success:
                return {"status": "ok", "data": result.data}
            return {"status": "error", "data": {"message": result.error}}

        @router.post("/upload-url")
        async def upload_url(body: dict) -> dict:
            """Import knowledge from a URL."""
            result = await self._invoke_kb_upload_url(body)
            if result.success:
                return {"status": "ok", "data": result.data}
            return {"status": "error", "data": {"message": result.error}}

        return router

    # ── Tool Handlers ─────────────────────────────────────────────

    async def _invoke_kb_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_search tool invocation.

        Calls the backend RAG search API with the parwa variant
        and formats results as KB documents with sections.
        """
        start_time = time.monotonic()
        params = parameters or {}
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")

        query = params.get("query", "")
        kb_ids = params.get("knowledge_base_ids", [])
        search_type = params.get("search_type", "hybrid")
        limit = params.get("limit", 10)

        logger.info(
            "kb_search_invoked",
            query=query[:100],
            search_type=search_type,
            kb_ids=kb_ids,
            limit=limit,
            tenant_id=tenant_id,
        )

        if not query.strip():
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_search",
                error="query is required and must not be empty",
            )

        # Build request body for backend RAG search
        request_body: dict[str, Any] = {
            "query": query.strip(),
            "variant_type": "parwa",
            "top_k": limit,
        }

        # Add KB ID filters if specified
        filters: dict[str, Any] = {}
        if kb_ids:
            filters["knowledge_base_ids"] = kb_ids
        if filters:
            request_body["filters"] = filters

        # Call backend API
        backend_response = await self._backend.post("/api/rag/search", request_body)

        if backend_response.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            error_msg = backend_response.get("data", {}).get("message", "Backend unreachable")
            logger.error(
                "kb_search_backend_error",
                error=error_msg,
                elapsed_ms=elapsed_ms,
            )
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_search",
                error=f"KB search backend unavailable: {error_msg}",
                metadata={
                    "query": query,
                    "elapsed_ms": elapsed_ms,
                    "backend_status": "error",
                },
            )

        # Parse backend response and format as KB documents
        data = backend_response.get("data", {})
        chunks_raw = data.get("chunks", [])

        # Group chunks by document_id to form full KB articles with sections
        doc_sections: dict[str, list[dict]] = {}
        doc_scores: dict[str, float] = {}

        for chunk in chunks_raw:
            doc_id = chunk.get("document_id", "unknown")
            if doc_id not in doc_sections:
                doc_sections[doc_id] = []
                doc_scores[doc_id] = 0.0
            doc_sections[doc_id].append({
                "content": chunk.get("content", ""),
                "chunk_id": chunk.get("chunk_id", ""),
                "score": chunk.get("score", 0.0),
                "metadata": chunk.get("metadata", {}),
            })
            # Track the highest score per document
            score = chunk.get("score", 0.0)
            if score > doc_scores[doc_id]:
                doc_scores[doc_id] = score

        results: list[dict] = []
        for doc_id, sections in doc_sections.items():
            # Sort sections by score descending
            sections.sort(key=lambda s: s.get("score", 0.0), reverse=True)
            # Build full content from sections
            full_content = "\n\n".join(s.get("content", "") for s in sections)

            results.append({
                "id": doc_id,
                "title": sections[0].get("metadata", {}).get("title", f"Document {doc_id}"),
                "content": full_content,
                "knowledge_base_id": sections[0].get("metadata", {}).get(
                    "knowledge_base_id", kb_ids[0] if kb_ids else "default"
                ),
                "relevance_score": round(doc_scores[doc_id], 4),
                "metadata": {
                    "section_count": len(sections),
                    "sections": [
                        {
                            "chunk_id": s.get("chunk_id"),
                            "score": s.get("score"),
                        }
                        for s in sections
                    ],
                    "tenant_id": tenant_id,
                },
            })

        # Sort by relevance
        results.sort(key=lambda d: d.get("relevance_score", 0.0), reverse=True)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_search",
            data=results,
            metadata={
                "query": query,
                "search_type": search_type,
                "result_count": len(results),
                "total_found": data.get("total_found", len(results)),
                "elapsed_ms": elapsed_ms,
                "variant_tier_used": data.get("variant_tier_used", "parwa"),
                "tenant_id": tenant_id,
            },
        )

    async def _invoke_kb_get_document(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_get_document tool invocation.

        Calls the backend RAG documents endpoint to fetch a specific
        document with all its chunks.
        """
        start_time = time.monotonic()
        params = parameters or {}
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")
        # Use tenant_id as company_id fallback for per-tenant isolation
        company_id = params.get("company_id", tenant_id)
        document_id = params.get("document_id", "")

        logger.info(
            "kb_get_document_invoked",
            document_id=document_id,
            company_id=company_id,
            tenant_id=tenant_id,
        )

        if not document_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_get_document",
                error="document_id is required",
            )

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_get_document",
                error="company_id (or tenant_id in context) is required for document retrieval",
            )

        # Call backend API
        backend_response = await self._backend.get(
            f"/api/rag/documents/{company_id}/{document_id}"
        )

        if backend_response.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            error_msg = backend_response.get("data", {}).get("message", "Backend unreachable")
            logger.error(
                "kb_get_document_backend_error",
                error=error_msg,
                elapsed_ms=elapsed_ms,
            )
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_get_document",
                error=f"KB document retrieval backend unavailable: {error_msg}",
                metadata={
                    "elapsed_ms": elapsed_ms,
                    "backend_status": "error",
                },
            )

        # Parse response
        doc_data = backend_response.get("data", {})

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_get_document",
            data={
                "id": doc_data.get("document_id", document_id),
                "title": doc_data.get("metadata", {}).get("title", f"Document {document_id}"),
                "content": doc_data.get("content", ""),
                "knowledge_base_id": doc_data.get("knowledge_base_id", ""),
                "metadata": {
                    **doc_data.get("metadata", {}),
                    "chunk_count": doc_data.get("chunk_count", 0),
                    "tenant_id": tenant_id,
                },
            },
            metadata={
                "elapsed_ms": elapsed_ms,
                "tenant_id": tenant_id,
            },
        )

    async def _invoke_kb_list_bases(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_list_bases tool invocation.

        Calls the backend KB stats endpoint to retrieve real knowledge
        base statistics.
        """
        start_time = time.monotonic()
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")

        logger.info("kb_list_bases_invoked", tenant_id=tenant_id)

        # Call backend KB stats endpoint
        backend_response = await self._backend.get("/api/kb/stats")

        if backend_response.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            error_msg = backend_response.get("data", {}).get("message", "Backend unreachable")
            logger.error(
                "kb_list_bases_backend_error",
                error=error_msg,
                elapsed_ms=elapsed_ms,
            )
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_list_bases",
                error=f"KB stats backend unavailable: {error_msg}",
                metadata={
                    "elapsed_ms": elapsed_ms,
                    "backend_status": "error",
                },
            )

        # Parse stats and format as knowledge base list
        data = backend_response.get("data", {})

        bases: list[dict] = []
        total_documents = data.get("total_documents", 0)
        total_chunks = data.get("total_chunks", 0)
        completed = data.get("completed", 0)
        processing = data.get("processing", 0)
        failed = data.get("failed", 0)
        pending = data.get("pending", 0)

        # Build a comprehensive KB base entry from stats
        bases.append({
            "id": "default",
            "name": "Primary Knowledge Base",
            "doc_count": total_documents,
            "chunk_count": total_chunks,
            "status_summary": {
                "completed": completed,
                "processing": processing,
                "failed": failed,
                "pending": pending,
            },
            "health": "healthy" if failed == 0 else "degraded",
        })

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_list_bases",
            data=bases,
            metadata={
                "count": len(bases),
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "elapsed_ms": elapsed_ms,
                "tenant_id": tenant_id,
            },
        )

    async def _invoke_kb_upload_url(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_upload_url tool invocation.

        Fetches content from the given URL, chunks it, and sends it
        to the backend RAG documents endpoint for indexing.
        """
        start_time = time.monotonic()
        params = parameters or {}
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")

        url = params.get("url", "")
        document_id = params.get("document_id")
        metadata = params.get("metadata", {})

        logger.info(
            "kb_upload_url_invoked",
            url=url[:200],
            document_id=document_id,
            tenant_id=tenant_id,
        )

        if not url or not url.strip():
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_upload_url",
                error="url is required and must not be empty",
            )

        # Step 1: Fetch URL content
        fetch_result = await _fetch_url_content(url.strip())

        if fetch_result.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_upload_url",
                error=f"Failed to fetch URL: {fetch_result.get('error', 'Unknown error')}",
                metadata={
                    "url": url,
                    "elapsed_ms": elapsed_ms,
                },
            )

        text = fetch_result.get("text", "")
        title = fetch_result.get("title", url)

        if not text or not text.strip():
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_upload_url",
                error="No extractable text content found at the URL",
                metadata={
                    "url": url,
                    "elapsed_ms": elapsed_ms,
                },
            )

        # Step 2: Chunk the text
        chunks = _chunk_text(text)

        if not chunks:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_upload_url",
                error="Text chunking produced no chunks — the content may be too short",
                metadata={
                    "url": url,
                    "text_length": len(text),
                    "elapsed_ms": elapsed_ms,
                },
            )

        # Step 3: Auto-generate document_id if not provided
        if not document_id:
            raw = f"{tenant_id}:{url}".encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()[:32]
            document_id = f"doc_url_{digest}"

        # Add source metadata to chunks
        doc_metadata = {
            "source_type": "url",
            "source_url": url,
            "title": title,
            **metadata,
        }

        for chunk in chunks:
            chunk["metadata"] = {
                **chunk.get("metadata", {}),
                **doc_metadata,
            }

        # Step 4: Send to backend RAG documents endpoint
        request_body: dict[str, Any] = {
            "document_id": document_id,
            "chunks": chunks,
            "metadata": doc_metadata,
        }

        backend_response = await self._backend.post("/api/rag/documents", request_body)

        if backend_response.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            error_msg = backend_response.get("data", {}).get("message", "Backend unreachable")
            logger.error(
                "kb_upload_url_backend_error",
                error=error_msg,
                elapsed_ms=elapsed_ms,
            )
            return ToolInvokeResponse(
                success=False,
                tool_name="kb_upload_url",
                error=f"KB upload backend unavailable: {error_msg}",
                metadata={
                    "url": url,
                    "elapsed_ms": elapsed_ms,
                    "backend_status": "error",
                },
            )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        ingest_data = backend_response.get("data", {})

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_upload_url",
            data={
                "document_id": document_id,
                "url": url,
                "title": title,
                "chunks_created": len(chunks),
                "text_length": len(text),
                "message": ingest_data.get("message", "URL content imported successfully"),
            },
            metadata={
                "elapsed_ms": elapsed_ms,
                "tenant_id": tenant_id,
            },
        )


# Singleton instance
kb_server = KBServer()
