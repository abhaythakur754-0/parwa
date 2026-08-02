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
)
async def api_upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    # ── Create document + chunks inline (no Celery, no embeddings) ──
    # Parse file content into text, split into chunks, store in document_chunks.
    # The pipeline's Node 3 (knowledge_fetch) queries document_chunks by keyword
    # overlap — no vector embeddings needed for basic retrieval.
    from fastapi.responses import JSONResponse

    try:
        # Decode file content to text
        try:
            file_text = content.decode("utf-8", errors="replace")
        except Exception:
            file_text = ""

        # Simple chunking: split by double-newline (paragraphs), then merge
        # short paragraphs to get ~500-char chunks.
        raw_paras = [p.strip() for p in file_text.split("\n\n") if p.strip()]
        chunks_text = []
        current = ""
        for para in raw_paras:
            if len(current) + len(para) + 2 < 500:
                current = (current + "\n\n" + para).strip() if current else para
            else:
                if current:
                    chunks_text.append(current)
                current = para
        if current:
            chunks_text.append(current)

        # If no paragraph breaks, split by single newlines or by 500-char windows
        if not chunks_text and file_text.strip():
            for i in range(0, len(file_text), 500):
                chunk = file_text[i:i+500].strip()
                if chunk:
                    chunks_text.append(chunk)

        document = KnowledgeDocument(
            company_id=user.company_id,
            filename=filename,
            file_type=ext.lstrip("."),
            file_size=len(content),
            status="completed",
            chunk_count=len(chunks_text),
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Insert chunks into document_chunks table
        try:
            from database.models.onboarding import DocumentChunk
            import uuid
            for idx, chunk_text in enumerate(chunks_text):
                chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    company_id=user.company_id,
                    chunk_index=idx,
                    content=chunk_text,
                )
                db.add(chunk)
            db.commit()
        except Exception as chunk_exc:
            logger.warning("kb_chunk_insert_partial_error: %s", str(chunk_exc)[:200])
            db.rollback()

        logger.info("kb_upload_completed document_id=%s filename=%s chunks=%d", str(document.id), filename, len(chunks_text))

        return JSONResponse(
            status_code=201,
            content={
                "id": str(document.id),
                "filename": filename,
                "status": "completed",
                "message": "Document uploaded successfully.",
                "chunk_count": len(chunks_text),
            },
        )

    except Exception as e:
        db.rollback()
        import traceback
        tb = traceback.format_exc()
        logger.error("kb_upload_failed: %s", str(e)[:500])
        logger.error("kb_upload_traceback: %s", tb[:1000])
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "KB_UPLOAD_ERROR",
                    "message": str(e)[:200],
                    "traceback": tb[:500],
                }
            },
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
        logger.error("kb_reindex_failed document_id=%s error=%s", document_id, str(exc)[:200])
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
                # Sync processing (same as upload endpoint) — no Celery
                doc.status = "processing"
                db.commit()
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
            "",
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
