"""
PARWA RAG API Router (Week 9 Day 7)

REST endpoints for RAG retrieval and knowledge base management.

Endpoints:
  - POST /api/rag/search           — Search knowledge base
  - POST /api/rag/documents        — Add document to knowledge base
  - GET  /api/rag/documents/{company_id}/{document_id} — Get document
  - DELETE /api/rag/documents/{company_id}/{document_id} — Delete document
  - POST /api/rag/reindex          — Trigger reindexing
  - GET  /api/rag/reindex/status/{company_id} — Get reindex status
  - GET  /api/rag/health           — Health check

BC-001: All operations scoped to company_id.
BC-012: Structured JSON responses.

Import patterns:
  - Lazy service imports inside endpoint functions to avoid circular imports.
  - Dependencies: require_roles, get_company_id, get_current_user.
"""

from app.api.deps import (
    get_company_id,
    get_current_user,
    require_roles,
)
from app.exceptions import NotFoundError, ValidationError
from app.logger import get_logger
from fastapi import APIRouter, Depends

from database.models.core import User

router = APIRouter(prefix="/api/rag", tags=["rag"])
logger = get_logger("rag_api")


# ═══════════════════════════════════════════════════════════════════
# RAG Search
# ═══════════════════════════════════════════════════════════════════


@router.post("/search")
async def rag_search(
    body: dict,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> dict:
    """Search the knowledge base for relevant chunks.

    Body:
      - query (required): Search query string
      - company_id (required): Tenant identifier
      - variant_type (optional): mini_parwa | parwa | high_parwa (default: parwa)
      - top_k (optional): Maximum results (default: variant-specific)
      - filters (optional): Metadata filters dict
      - similarity_threshold (optional): Minimum similarity score
    """
    from app.core.rag_retrieval import RAGRetriever

    query = body.get("query")
    if not query or not query.strip():
        raise ValidationError(
            message="query is required and must not be empty",
            details={"required": ["query"]},
        )

    variant_type = body.get("variant_type", "parwa")
    if variant_type not in ("mini_parwa", "parwa", "high_parwa"):
        raise ValidationError(
            message=f"Invalid variant_type: {variant_type}",
            details={"allowed": ["mini_parwa", "parwa", "high_parwa"]},
        )

    target_company_id = body.get("company_id", company_id)

    retriever = RAGRetriever()
    result = await retriever.retrieve(
        query=query.strip(),
        company_id=target_company_id,
        variant_type=variant_type,
        top_k=body.get("top_k"),
        similarity_threshold=body.get("similarity_threshold"),
        filters=body.get("filters"),
    )

    return {"status": "ok", "data": result.to_dict()}


# ═══════════════════════════════════════════════════════════════════
# Document Management
# ═══════════════════════════════════════════════════════════════════


@router.post("/documents")
def add_document(
    body: dict,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Add a document with chunks to the knowledge base.

    Body:
      - document_id (required): Unique document identifier
      - chunks (required): List of dicts with 'content' and optional 'metadata'
      - company_id (required): Tenant identifier
      - metadata (optional): Document-level metadata
    """
    from shared.knowledge_base.vector_search import get_vector_store

    document_id = body.get("document_id")
    chunks = body.get("chunks")

    if not document_id:
        raise ValidationError(
            message="document_id is required",
            details={"required": ["document_id"]},
        )
    if not isinstance(chunks, list) or not chunks:
        raise ValidationError(
            message="chunks must be a non-empty list",
            details={"required": ["chunks"]},
        )

    target_company_id = body.get("company_id", company_id)
    store = get_vector_store()
    success = store.add_document(
        document_id=document_id,
        chunks=chunks,
        company_id=target_company_id,
        metadata=body.get("metadata"),
    )

    if not success:
        return {
            "status": "error",
            "data": {"message": "Failed to add document"},
        }

    return {
        "status": "ok",
        "data": {
            "document_id": document_id,
            "company_id": target_company_id,
            "chunk_count": len(chunks),
            "message": "Document added successfully",
        },
    }


@router.get("/documents/{company_id}/{document_id}")
def get_document(
    company_id: str,
    document_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Get a document with all its chunks from the knowledge base."""
    from shared.knowledge_base.vector_search import get_vector_store

    store = get_vector_store()
    doc = store.get_document(document_id, company_id)

    if doc is None:
        raise NotFoundError(
            message=f"Document '{document_id}' not found",
            details={"document_id": document_id, "company_id": company_id},
        )

    return {"status": "ok", "data": doc}


@router.delete("/documents/{company_id}/{document_id}")
def delete_document(
    company_id: str,
    document_id: str,
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Delete a document from the knowledge base."""
    from shared.knowledge_base.vector_search import get_vector_store

    store = get_vector_store()
    deleted = store.delete_document(document_id, company_id)

    return {
        "status": "ok",
        "data": {
            "document_id": document_id,
            "company_id": company_id,
            "deleted": deleted,
            "message": (
                "Document deleted successfully" if deleted else "Document not found"
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════
# Reindexing
# ═══════════════════════════════════════════════════════════════════


@router.post("/reindex")
async def trigger_reindex(
    body: dict,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Trigger reindexing for specific documents.

    Body:
      - company_id (required): Tenant identifier
      - document_ids (required): List of document IDs to reindex
    """
    from shared.knowledge_base.reindexing import ReindexingManager

    document_ids = body.get("document_ids")
    target_company_id = body.get("company_id", company_id)

    if not isinstance(document_ids, list) or not document_ids:
        raise ValidationError(
            message="document_ids must be a non-empty list",
            details={"required": ["document_ids"]},
        )

    manager = ReindexingManager()
    queued = await manager.mark_for_reindex(target_company_id, document_ids)

    return {
        "status": "ok",
        "data": {
            "company_id": target_company_id,
            "documents_queued": queued,
            "message": f"{queued} documents queued for reindexing",
        },
    }


@router.get("/reindex/status/{company_id}")
def get_reindex_status(
    company_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Get reindex queue status for a company."""
    from shared.knowledge_base.reindexing import ReindexingManager

    manager = ReindexingManager()
    status = manager.get_reindex_status(company_id)

    return {
        "status": "ok",
        "data": {
            "company_id": status.company_id,
            "pending": status.pending,
            "processing": status.processing,
            "completed": status.completed,
            "failed": status.failed,
            "total": status.total,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════


@router.get("/health")
def rag_health_check(
    user: User = Depends(get_current_user),
) -> dict:
    """Check RAG system health."""
    from shared.knowledge_base.vector_search import get_vector_store

    store = get_vector_store()
    is_healthy = store.health_check()

    return {
        "status": "ok" if is_healthy else "degraded",
        "data": {
            "vector_store_healthy": is_healthy,
            "store_type": type(store).__name__,
        },
    }
