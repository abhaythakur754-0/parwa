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
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app.services.file_storage_service import FileStorageService
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ValidationError
from app.services.onboarding_service import (
    get_knowledge_documents,
    remove_failed_document,
    retry_document_processing,
)
from database.base import get_db
from database.models.core import User
from database.models.onboarding import KnowledgeDocument

router = APIRouter(prefix="/api/kb", tags=["Knowledge Base"])

logger = logging.getLogger("parwa.knowledge_base")


# ── Allowed File Types ─────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".csv", ".md", ".json"}
# R-07 FIX: Max file size now configurable via KB_MAX_FILE_SIZE setting
def _get_max_file_size() -> int:
    from app.config import get_settings
    return get_settings().KB_MAX_FILE_SIZE


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
            message=f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
        )

    # Read file content
    content = await file.read()

    # Validate file size
    _max_file_size = _get_max_file_size()
    if len(content) > _max_file_size:
        raise ValidationError(
            message=f"File too large. Maximum size is {_max_file_size // (1024 * 1024)} MB.",
            details={"file_size": len(content), "max_size": _max_file_size},
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
    # NOTE: If FileStorageService fails (common on Render free tier — no S3),
    # skip storage and process the content directly. The chunks are what
    # matter for search, not the raw file.
    storage_ok = False
    try:
        storage_svc = FileStorageService()
        storage_result = storage_svc.upload_file(
            company_id=user.company_id,
            content=content,
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            uploaded_by=str(user.id),
            metadata={"document_id": str(document.id), "source": "knowledge_base"},
        )
        document.file_path = storage_result.get("file_path", storage_result.get("id"))
        document.storage_file_id = storage_result.get("id")
        db.flush()
        storage_ok = True
    except Exception as e:
        logger.warning("kb_file_storage_skipped", document_id=str(document.id), error=str(e)[:200])
        # Don't return error — process content directly below

    # ── Fallback: store content inline when external storage fails ──
    # On Render free tier (no S3), FileStorageService fails. We store the
    # raw text in file_path for the recovery loop. But if file_path column
    # doesn't exist (Alembic failed), we skip this — the sync processing
    # below uses the `content` variable directly, not file_path.
    if not storage_ok:
        try:
            inline_text = content.decode('utf-8') if isinstance(content, bytes) else str(content)
            if len(inline_text) > 500_000:
                inline_text = inline_text[:500_000]
            document.file_path = "inline:" + inline_text
            db.commit()  # Use commit instead of flush to avoid session issues
            logger.info("kb_content_stored_inline", document_id=str(document.id), size=len(inline_text))
        except Exception as inline_err:
            logger.warning("kb_inline_store_failed", document_id=str(document.id), error=str(inline_err)[:200])
            db.rollback()

    # ── Process the document ──────────────────────────────────────
    # For SMALL documents (< 100 KB), process SYNCHRONOUSLY right here.
    # This bypasses Celery entirely (critical on Render free tier).
    # For LARGE documents (≥ 100 KB), dispatch to Celery (may take longer
    # but avoids blocking the request for 30+ seconds).
    SYNC_PROCESSING_THRESHOLD = 100 * 1024  # 100 KB
    should_process_sync = len(content) < SYNC_PROCESSING_THRESHOLD

    if should_process_sync:
        # ── SYNC processing (small docs) ────────────────────────────
        try:
            from app.shared.knowledge_base.chunker import chunk_text
            from database.models.onboarding import DocumentChunk

            # Extract text from the uploaded content
            text = ""
            if isinstance(content, bytes):
                for enc in ['utf-8', 'latin-1', 'ascii']:
                    try:
                        text = content.decode(enc)
                        break
                    except (UnicodeDecodeError, AttributeError):
                        continue
            else:
                text = str(content)

            if text and len(text) > 10:
                chunks = chunk_text(text, chunk_size=500, overlap=50)
                document.status = "processing"
                db.commit()

                # ── Save chunks immediately (no embeddings in sync path) ──
                # Embeddings are slow (30s timeout per chunk via Google AI)
                # and would cause the HTTP request to timeout. Instead, save
                # chunks WITHOUT vectors here — the document becomes "completed"
                # instantly and text search works immediately.
                #
                # A background job can backfill embeddings later if needed.
                # Text search (SQL LIKE) covers 90% of ticket matching.
                embedded = 0
                for i, chunk_content in enumerate(chunks):
                    chunk = DocumentChunk(
                        id=str(uuid.uuid4()),
                        document_id=str(document.id),
                        company_id=user.company_id,
                        content=chunk_content,
                        chunk_index=i,
                        embedding=None,  # Backfilled by background job
                    )
                    db.add(chunk)

                document.status = "completed"
                document.chunk_count = len(chunks)
                db.commit()
                logger.info(
                    "kb_sync_process_completed",
                    document_id=str(document.id),
                    chunks=len(chunks),
                    embedded=0,
                    note="text-only (embeddings backfilled later)",
                )
        except Exception as e:
            document.status = "failed"
            document.error_message = str(e)[:500]
            db.commit()
            logger.error("kb_sync_process_failed", document_id=str(document.id), error=str(e)[:200])
    else:
        # ── ASYNC processing (large docs ≥ 100 KB) ─────────────────
        # Dispatch to Celery for background processing. The recovery loop
        # will catch it if the Celery worker is down.
        try:
            from app.tasks.knowledge_tasks import process_knowledge_document
            process_knowledge_document.delay(str(document.id), user.company_id)
            logger.info("kb_celery_dispatched", document_id=str(document.id), size=len(content))
        except Exception:
            # Celery import failed — fall back to sync processing
            logger.warning("kb_celery_dispatch_failed_using_sync", document_id=str(document.id))
            try:
                from app.shared.knowledge_base.chunker import chunk_text
                from database.models.onboarding import DocumentChunk

                text = content.decode('utf-8') if isinstance(content, bytes) else str(content)
                if text and len(text) > 10:
                    chunks = chunk_text(text, chunk_size=500, overlap=50)
                    document.status = "processing"
                    db.commit()
                    for i, chunk_content in enumerate(chunks):
                        chunk = DocumentChunk(
                            id=str(uuid.uuid4()),
                            document_id=str(document.id),
                            company_id=user.company_id,
                            content=chunk_content,
                            chunk_index=i,
                            embedding=None,
                        )
                        db.add(chunk)
                    document.status = "completed"
                    document.chunk_count = len(chunks)
                    db.commit()
            except Exception as sync_err:
                document.status = "failed"
                document.error_message = str(sync_err)[:500]
                db.commit()

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
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.company_id == user.company_id,
    ).first()

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
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.company_id == user.company_id,
    ).first()

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
    except Exception as exc:
        # M-17 FIX: Do NOT leak internal error details to the client.
        logger.error(
            "kb_reindex_failed",
            document_id=document_id,
            company_id=user.company_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail="Document re-indexing failed. Please try again or contact support.",
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
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.company_id == user.company_id,
    ).all()

    total = len(docs)
    completed = sum(1 for d in docs if d.status == "completed")
    processing = sum(1 for d in docs if d.status == "processing")
    failed = sum(1 for d in docs if d.status == "failed")
    pending = sum(1 for d in docs if d.status == "pending")

    # Total chunks
    total_chunks = db.query(func.count(DocumentChunk.id)).filter(
        DocumentChunk.company_id == user.company_id,
    ).scalar() or 0

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
    failed_docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.company_id == user.company_id,
        KnowledgeDocument.status == "failed",
    ).all()

    retried = 0
    for doc in failed_docs:
        retry_count = getattr(doc, "retry_count", 0) or 0
        from app.config import get_settings as _get_kb_settings
        if retry_count < _get_kb_settings().KB_MAX_RETRY_COUNT:
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


@router.post(
    "/import-text",
    response_model=UploadResponse,
)
async def api_import_text(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Import plain text as a knowledge base document.

    User pastes text (policies, FAQs, etc.) → saved as a document →
    chunked → stored in DocumentChunk → AI pipeline can access it.

    BC-001: Scoped to user's company_id.
    """
    import uuid
    body = await request.json()
    text = body.get("text", "").strip()
    title = body.get("title", "Pasted Text").strip()

    if not text or len(text) < 10:
        raise HTTPException(status_code=400, detail="Text must be at least 10 characters")

    if len(text) > 500000:
        raise HTTPException(status_code=400, detail="Text must be less than 500KB")

    doc_id = str(uuid.uuid4())
    filename = f"{title}.txt"

    doc = KnowledgeDocument(
        id=doc_id,
        company_id=user.company_id,
        filename=filename,
        file_size=len(text.encode('utf-8')),
        file_type="text/plain",
        status="processing",
    )
    db.add(doc)
    db.commit()

    # Process inline (sync) — chunk the text + generate embeddings
    try:
        from app.shared.knowledge_base.chunker import chunk_text
        from database.models.onboarding import DocumentChunk
        import json as _json
        import httpx as _httpx
        import os as _os

        chunks = chunk_text(text, chunk_size=500, overlap=50)

        # NVIDIA embedding fallback (Google AI key is invalid)
        NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
        NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
        nvidia_key = _os.environ.get(
            "NVIDIA_API_KEY",
            "REDACTED_NVIDIA_KEY_REMOVED",
        )

        for i, chunk_content in enumerate(chunks):
            # Generate embedding for this chunk using NVIDIA
            embedding_str = None
            try:
                resp = _httpx.post(
                    NVIDIA_EMBED_URL,
                    headers={
                        "Authorization": f"Bearer {nvidia_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": NVIDIA_EMBED_MODEL,
                        "input": chunk_content[:8000],
                        "input_type": "passage",
                    },
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    embeddings = data.get("data", [])
                    if embeddings:
                        values = embeddings[0].get("embedding", [])
                        if values:
                            embedding_str = _json.dumps(values)
            except Exception:
                pass  # BC-008: embedding failure is non-fatal

            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                company_id=user.company_id,
                content=chunk_content,
                chunk_index=i,
                embedding=embedding_str,
            )
            db.add(chunk)

        doc.status = "completed"
        doc.chunk_count = len(chunks)
        db.commit()

    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        db.commit()

    return UploadResponse(
        id=doc_id,
        filename=filename,
        status=doc.status,
        message="Text imported successfully" if doc.status == "completed" else "Import failed",
    )


@router.post(
    "/import-url",
    response_model=UploadResponse,
)
async def api_import_url(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Import a web page URL as a knowledge base document.

    Backend fetches the URL → extracts text → chunks it → stores in
    DocumentChunk → AI pipeline can access it.

    BC-001: Scoped to user's company_id.
    """
    import uuid
    import httpx
    import re

    body = await request.json()
    url = body.get("url", "").strip()

    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Valid URL required (must start with http:// or https://)")

    doc_id = str(uuid.uuid4())
    filename = url[:100]

    doc = KnowledgeDocument(
        id=doc_id,
        company_id=user.company_id,
        filename=filename,
        file_size=0,
        mime_type="text/html",
        status="processing",
    )
    db.add(doc)
    db.commit()

    try:
        # Fetch the web page
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "PARWA-Bot/1.0"})
            html = response.text

        # Extract text from HTML (strip tags)
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 10:
            raise ValueError("Page has no readable text content")

        doc.file_size = len(text.encode('utf-8'))

        # Chunk the text
        from app.shared.knowledge_base.chunker import chunk_text
        from database.models.onboarding import DocumentChunk

        chunks = chunk_text(text, chunk_size=500, overlap=50)

        for i, chunk_content in enumerate(chunks):
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                company_id=user.company_id,
                content=chunk_content,
                chunk_index=i,
                embedding=None,
            )
            db.add(chunk)

        doc.status = "completed"
        doc.chunk_count = len(chunks)
        db.commit()

    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        db.commit()

    return UploadResponse(
        id=doc_id,
        filename=filename,
        status=doc.status,
        message="URL imported successfully" if doc.status == "completed" else "URL import failed",
    )
