"""
PARWA Knowledge Base Router (Week 6 — F-032, F-033)

Endpoints for knowledge base document management.

- POST   /api/kb/upload                    — Upload a document for processing
- GET    /api/kb/documents                 — List all knowledge documents
- GET    /api/kb/documents/{id}            — Get single document status
- DELETE /api/kb/documents/{id}            — Delete a knowledge document
- POST   /api/kb/documents/{id}/retry      — Retry a failed document
- POST   /api/kb/documents/{id}/reindex    — Re-index a completed document
- GET    /api/kb/stats                     — Get knowledge base statistics
- POST   /api/kb/retry-failed              — Retry all failed documents

F-032: KB Document Upload (drag-drop file upload, validation)
F-033: KB Processing + Indexing (chunking, vector embeddings via pgvector, Celery)

BC-001: All operations scoped to authenticated user's company_id.
GAP 2: Tenant isolation in document processing.
GAP 6: Failed document handling.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.services.file_storage_service import FileStorageService
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.exceptions import ValidationError
from app.services.onboarding_service import (
    retry_document_processing,
)
from database.base import get_db
from database.models.core import User
from database.models.onboarding import KnowledgeDocument

router = APIRouter(
    prefix="/api/kb",
    tags=["Knowledge Base"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)

logger = logging.getLogger("parwa.knowledge_base")


# ── Allowed File Types ─────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pd", ".docx", ".doc", ".txt", ".csv", ".md", ".json"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Request/Response Schemas ───────────────────────────────────────


class DocumentResponse(BaseModel):
    """Response with document details."""

    id: str
    filename: str
    file_type: str | None = None
    file_size: int | None = None
    status: str
    chunk_count: int | None = None
    error_message: str | None = None
    retry_count: int | None = None
    created_at: str | None = None


class UploadResponse(BaseModel):
    """Response after uploading a document."""

    id: str
    filename: str
    status: str
    message: str


class RetryResponse(BaseModel):
    """Response after retrying a failed document."""

    id: str
    status: str
    retry_count: int
    message: str


class KBStatsResponse(BaseModel):
    """Knowledge base statistics."""

    total_documents: int = 0
    total_chunks: int = 0
    completed: int = 0
    processing: int = 0
    failed: int = 0
    pending: int = 0


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# ── Endpoints ──────────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=201,
)
async def api_upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Upload a document for knowledge base processing.

    F-032: Accepts PDF, DOCX, DOC, TXT, CSV, MD, JSON files.
    Validates file type and size before accepting.
    Triggers async processing via Celery.

    GAP 2 FIX: Documents are scoped to company_id (tenant isolation).
    GAP 6 FIX: Failed documents can be retried.

    BC-001: Scoped to user's company_id.
    """
    # Validate file extension
    filename = file.filename or "unknown.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            message=f"File type '{ext}' not allowed. Allowed: {
                ', '.join(
                    sorted(ALLOWED_EXTENSIONS))}",
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise ValidationError(
            message=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
            details={"file_size": len(content), "max_size": MAX_FILE_SIZE},
        )

    # Create document record
    document = KnowledgeDocument(
        company_id=user.company_id,
        filename=filename,
        file_type=ext.lstrip("."),
        file_size=len(content),
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Store raw file to object storage for async processing
    storage_svc = FileStorageService()
    try:
        storage_result = storage_svc.upload_file(
            company_id=user.company_id,
            content=content,
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            uploaded_by=str(user.id),
            metadata={"document_id": str(document.id), "source": "knowledge_base"},
        )
        # Store file reference on document for Celery task to retrieve
        document.file_path = storage_result.get("file_path", storage_result.get("id"))
        document.storage_file_id = storage_result.get("id")
        db.flush()
    except Exception as e:
        logger.error(
            "kb_file_storage_failed", document_id=str(document.id), error=str(e)
        )
        # Continue processing even if storage fails - Celery task will handle
        # gracefully

    # Trigger async processing via Celery
    try:
        from app.tasks.knowledge_tasks import process_knowledge_document

        process_knowledge_document.delay(str(document.id), user.company_id)
    except Exception:
        # Celery not available — mark for sync processing
        document.status = "pending"

    return UploadResponse(
        id=str(document.id),
        filename=filename,
        status=document.status,
        message="Document uploaded successfully. Processing will begin shortly.",
    )


@router.get(
    "/documents",
    response_model=List[DocumentResponse],
)
def api_list_documents(
    status: str | None = Query(default=None, description="Filter by status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[DocumentResponse]:
    """List all knowledge documents for the company.

    F-032: Returns all uploaded documents with processing status.
    Optional status filter: pending, processing, completed, failed.

    BC-001: Scoped to user's company_id.
    """
    query = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.company_id == user.company_id,
    )

    if status:
        query = query.filter(KnowledgeDocument.status == status)

    documents = query.order_by(KnowledgeDocument.created_at.desc()).all()

    return [
        DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            chunk_count=doc.chunk_count,
            error_message=getattr(doc, "error_message", None),
            retry_count=getattr(doc, "retry_count", None),
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc in documents
    ]


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
)
def api_get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Get a single knowledge document status.

    BC-001: Scoped to user's company_id.
    """
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.company_id == user.company_id,
        )
        .first()
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=getattr(doc, "error_message", None),
        retry_count=getattr(doc, "retry_count", None),
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=MessageResponse,
)
def api_delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete a knowledge document and its chunks.

    GAP 6 FIX: Failed documents can be removed to allow onboarding to proceed.

    BC-001: Scoped to user's company_id.
    """
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.company_id == user.company_id,
        )
        .first()
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Delete associated chunks
    from database.models.onboarding import DocumentChunk

    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id,
        DocumentChunk.company_id == user.company_id,
    ).delete(synchronize_session="fetch")

    db.delete(doc)
    db.commit()

    return MessageResponse(message="Document deleted successfully.")


@router.post(
    "/documents/{document_id}/retry",
    response_model=RetryResponse,
)
def api_retry_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetryResponse:
    """Retry processing a failed document.

    GAP 6 FIX: Supports retrying failed documents with a max limit of 3.
    Resets status to processing and triggers Celery task.

    BC-001: Scoped to user's company_id.
    """
    result = retry_document_processing(
        db=db,
        document_id=document_id,
        company_id=user.company_id,
    )

    return RetryResponse(
        id=result["id"],
        status=result["status"],
        retry_count=result["retry_count"],
        message=result["message"],
    )


@router.post(
    "/documents/{document_id}/reindex",
    response_model=MessageResponse,
)
def api_reindex_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Re-index a completed document (delete chunks, re-chunk, re-embed).

    Uses KnowledgeBaseManager for full pipeline re-processing.

    BC-001: Scoped to user's company_id.
    """
    from app.shared.knowledge_base.manager import KnowledgeBaseManager

    manager = KnowledgeBaseManager(db, company_id=user.company_id)

    try:
        result = manager.reindex_document(document_id)
        return MessageResponse(
            message=f"Document re-indexed. {result.get('chunk_count', 0)} chunks created.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Re-indexing failed: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=KBStatsResponse,
)
def api_kb_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KBStatsResponse:
    """Get knowledge base statistics.

    Returns document counts by status and total chunk count.

    BC-001: Scoped to user's company_id.
    """
    from sqlalchemy import func
    from database.models.onboarding import DocumentChunk

    # Document counts by status
    docs = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.company_id == user.company_id,
        )
        .all()
    )

    total = len(docs)
    completed = sum(1 for d in docs if d.status == "completed")
    processing = sum(1 for d in docs if d.status == "processing")
    failed = sum(1 for d in docs if d.status == "failed")
    pending = sum(1 for d in docs if d.status == "pending")

    # Total chunks
    total_chunks = (
        db.query(func.count(DocumentChunk.id))
        .filter(
            DocumentChunk.company_id == user.company_id,
        )
        .scalar()
        or 0
    )

    return KBStatsResponse(
        total_documents=total,
        total_chunks=total_chunks,
        completed=completed,
        processing=processing,
        failed=failed,
        pending=pending,
    )


@router.post(
    "/retry-failed",
    response_model=MessageResponse,
)
def api_retry_all_failed(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Retry all failed documents for the company.

    GAP 6 FIX: Bulk retry mechanism.

    BC-001: Scoped to user's company_id.
    """
    failed_docs = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.company_id == user.company_id,
            KnowledgeDocument.status == "failed",
        )
        .all()
    )

    retried = 0
    for doc in failed_docs:
        retry_count = getattr(doc, "retry_count", 0) or 0
        if retry_count < 3:
            try:
                from app.tasks.knowledge_tasks import process_knowledge_document

                process_knowledge_document.delay(str(doc.id), user.company_id)
                doc.status = "processing"
                doc.retry_count = retry_count + 1  # type: ignore
                retried += 1
            except Exception:
                pass

    db.commit()

    return MessageResponse(
        message=f"Retrying {retried} failed document(s).",
    )
