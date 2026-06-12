"""Knowledge Base management routes (PHASE 16 — GAP 7).

Provides endpoints to:
  - Upload documents (PDF, DOCX, TXT, CSV, HTML, JSON)
  - List documents
  - Delete documents
  - Search knowledge base
  - Get document processing status
"""
import json
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, KBDocument, AuditLog, Notification
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge_base"])

# Upload directory
UPLOAD_DIR = "/home/z/my-project/upload/kb"

# Supported file formats
SUPPORTED_FORMATS = {
    ".pdf": {"max_size": 50 * 1024 * 1024, "processing": "PyPDF2 extraction → chunk → embed"},
    ".docx": {"max_size": 50 * 1024 * 1024, "processing": "python-docx extraction → chunk → embed"},
    ".txt": {"max_size": 10 * 1024 * 1024, "processing": "Direct chunk and embed"},
    ".md": {"max_size": 10 * 1024 * 1024, "processing": "Direct chunk and embed"},
    ".csv": {"max_size": 25 * 1024 * 1024, "processing": "Parse rows → embed as structured data"},
    ".html": {"max_size": 25 * 1024 * 1024, "processing": "Strip tags → chunk → embed"},
    ".htm": {"max_size": 25 * 1024 * 1024, "processing": "Strip tags → chunk → embed"},
    ".json": {"max_size": 25 * 1024 * 1024, "processing": "Flatten → embed as structured data"},
}


# --- Pydantic Models ---

class SearchKBRequest(BaseModel):
    query: str
    top_k: int = 5


# --- Routes ---

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a document to the knowledge base.

    Supported formats: PDF, DOCX, TXT, MD, CSV, HTML, JSON
    Max file size varies by format (see SUPPORTED_FORMATS).
    """
    # Validate file format
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: {', '.join(SUPPORTED_FORMATS.keys())}",
        )

    format_config = SUPPORTED_FORMATS[ext]

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size > format_config["max_size"]:
        max_mb = format_config["max_size"] // (1024 * 1024)
        actual_mb = file_size // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({actual_mb}MB, max {max_mb}MB for {ext} files)",
        )

    # Create upload directory if needed
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save file
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Create KB document record
    kb_doc = KBDocument(
        id=doc_id,
        tenant_id=current_user.tenant_id,
        filename=filename,
        file_type=ext,
        file_size=file_size,
        chunk_count=0,
        status="processing",
    )
    db.add(kb_doc)

    # Process the document (simulate chunking and embedding)
    try:
        chunk_count = _process_document(file_path, ext, content)
        kb_doc.chunk_count = chunk_count
        kb_doc.status = "ready"
    except Exception as e:
        kb_doc.status = "error"
        kb_doc.error_message = str(e)

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="kb.document_uploaded",
        actor=current_user.email,
        resource_type="kb_document",
        resource_id=doc_id,
        details=json.dumps({
            "filename": filename,
            "file_type": ext,
            "file_size": file_size,
            "chunk_count": kb_doc.chunk_count,
            "status": kb_doc.status,
        }),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "id": doc_id,
        "filename": filename,
        "file_type": ext,
        "file_size": file_size,
        "chunk_count": kb_doc.chunk_count,
        "status": kb_doc.status,
        "error_message": kb_doc.error_message,
    }


@router.get("/documents")
def list_documents(
    status_filter: str = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all documents in the tenant's knowledge base."""
    query = db.query(KBDocument).filter(
        KBDocument.tenant_id == current_user.tenant_id,
    )

    if status_filter:
        query = query.filter(KBDocument.status == status_filter)

    total = query.count()
    documents = query.order_by(KBDocument.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "chunk_count": d.chunk_count,
                "status": d.status,
                "error_message": d.error_message,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in documents
        ],
        "total": total,
    }


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document from the knowledge base. Removes all chunks and embeddings."""
    doc = db.query(KBDocument).filter(
        KBDocument.id == document_id,
        KBDocument.tenant_id == current_user.tenant_id,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file from disk
    file_path = os.path.join(UPLOAD_DIR, f"{doc.id}{doc.file_type}")
    if os.path.exists(file_path):
        os.remove(file_path)

    filename = doc.filename
    chunk_count = doc.chunk_count

    # Delete from database
    db.delete(doc)

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="kb.document_deleted",
        actor=current_user.email,
        resource_type="kb_document",
        resource_id=document_id,
        details=json.dumps({
            "filename": filename,
            "chunk_count": chunk_count,
        }),
        severity="warning",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Document '{filename}' deleted",
        "chunks_removed": chunk_count,
    }


@router.post("/search")
def search_knowledge_base(
    req: SearchKBRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search the knowledge base. Returns matching document chunks.

    In production, this would use vector similarity search (Pinecone/Weaviate).
    Current implementation: keyword-based search over document metadata.
    """
    # Get all ready documents for this tenant
    docs = db.query(KBDocument).filter(
        KBDocument.tenant_id == current_user.tenant_id,
        KBDocument.status == "ready",
    ).all()

    if not docs:
        return {
            "results": [],
            "total": 0,
            "query": req.query,
            "message": "No documents in knowledge base. Upload documents first.",
        }

    # Keyword-based search (simulated — in production this would be vector search)
    query_lower = req.query.lower()
    results = []

    for doc in docs:
        # Simple relevance: check if query terms appear in filename
        # In production, this would search actual chunk embeddings
        filename_lower = doc.filename.lower()
        score = 0.0
        query_terms = query_lower.split()
        for term in query_terms:
            if term in filename_lower:
                score += 0.3

        if score > 0 or len(results) < req.top_k:
            results.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "relevance_score": round(score, 2),
                "chunk_count": doc.chunk_count,
                "preview": f"Content from {doc.filename} (would show actual chunk text in production with vector search)",
            })

    # Sort by relevance
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = results[:req.top_k]

    # Log search
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="kb.search",
        actor=current_user.email,
        resource_type="kb_document",
        resource_id=None,
        details=json.dumps({"query": req.query, "results_count": len(results)}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "results": results,
        "total": len(results),
        "query": req.query,
    }


@router.get("/stats")
def get_kb_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get knowledge base statistics for the tenant."""
    docs = db.query(KBDocument).filter(
        KBDocument.tenant_id == current_user.tenant_id,
    ).all()

    total_chunks = sum(d.chunk_count for d in docs)
    total_size = sum(d.file_size or 0 for d in docs)

    return {
        "total_documents": len(docs),
        "ready_documents": sum(1 for d in docs if d.status == "ready"),
        "processing_documents": sum(1 for d in docs if d.status == "processing"),
        "error_documents": sum(1 for d in docs if d.status == "error"),
        "total_chunks": total_chunks,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "file_types": list(set(d.file_type for d in docs if d.file_type)),
    }


def _process_document(file_path: str, ext: str, content: bytes) -> int:
    """Process a document and return the number of chunks.

    In production, this would:
    1. Extract text (PyPDF2 for PDF, python-docx for DOCX, etc.)
    2. Chunk into ~500 token chunks with overlap
    3. Generate vector embeddings via OpenAI ada-002
    4. Store chunks + embeddings in vector DB

    Current implementation: Simulate chunking based on file size.
    """
    # Simple heuristic: ~500 tokens ≈ ~2000 bytes per chunk
    chunk_size = 2000
    chunk_count = max(1, len(content) // chunk_size)

    # Simulate processing delay
    # In production: actual text extraction, chunking, embedding
    return chunk_count
