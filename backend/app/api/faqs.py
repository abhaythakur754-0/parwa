"""
FAQ API Endpoints (Mini Parwa Feature)

REST API for managing Frequently Asked Questions.
These FAQs are used by the AI pipeline for quick answers.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.auth import get_current_user
from app.services.faq_service import get_faq_service, FAQService


router = APIRouter(prefix="/api/v1/faqs", tags=["FAQs"])


# ── Schemas ────────────────────────────────────────────────────────────────

class FAQCreate(BaseModel):
    """Request to create a new FAQ."""
    question: str = Field(..., min_length=5, max_length=500)
    answer: str = Field(..., min_length=10, max_length=2000)
    category: str = Field(default="General", max_length=50)
    keywords: List[str] = Field(default_factory=list)


class FAQUpdate(BaseModel):
    """Request to update an existing FAQ."""
    question: Optional[str] = Field(None, min_length=5, max_length=500)
    answer: Optional[str] = Field(None, min_length=10, max_length=2000)
    category: Optional[str] = Field(None, max_length=50)
    keywords: Optional[List[str]] = None


class FAQResponse(BaseModel):
    """FAQ response schema."""
    id: str
    question: str
    answer: str
    category: str
    keywords: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FAQListResponse(BaseModel):
    """List of FAQs with metadata."""
    faqs: List[FAQResponse]
    total: int
    categories: List[str]


class FAQImportRequest(BaseModel):
    """Request to import FAQs."""
    faqs: List[FAQCreate]
    merge: bool = Field(default=True, description="Merge with existing or replace")


class FAQImportResponse(BaseModel):
    """Response for FAQ import."""
    imported: int
    message: str


# ── Dependencies ────────────────────────────────────────────────────────────

def get_faq_service_dep(current_user = Depends(get_current_user)) -> FAQService:
    """Get FAQ service with company context from current user."""
    company_id = str(current_user.company_id) if hasattr(current_user, 'company_id') else None
    return get_faq_service(company_id=company_id)


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=FAQListResponse)
async def list_faqs(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in questions and answers"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    service: FAQService = Depends(get_faq_service_dep),
):
    """List all FAQs with optional filtering.
    
    Mini Parwa: Basic FAQ management included.
    """
    faqs = service.list_faqs(category=category, search=search, limit=limit)
    categories = service.get_categories()
    
    return FAQListResponse(
        faqs=[FAQResponse(**faq) for faq in faqs],
        total=len(faqs),
        categories=categories,
    )


@router.get("/categories")
async def list_categories(
    service: FAQService = Depends(get_faq_service_dep),
):
    """List all FAQ categories."""
    return {"categories": service.get_categories()}


@router.get("/{faq_id}", response_model=FAQResponse)
async def get_faq(
    faq_id: str,
    service: FAQService = Depends(get_faq_service_dep),
):
    """Get a specific FAQ by ID."""
    faq = service.get_faq(faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    return FAQResponse(**faq)


@router.post("", response_model=FAQResponse, status_code=201)
async def create_faq(
    request: FAQCreate,
    service: FAQService = Depends(get_faq_service_dep),
):
    """Create a new FAQ.
    
    Mini Parwa: Create FAQs for AI reference.
    """
    faq = service.create_faq(
        question=request.question,
        answer=request.answer,
        category=request.category,
        keywords=request.keywords,
    )
    
    return FAQResponse(**faq)


@router.put("/{faq_id}", response_model=FAQResponse)
async def update_faq(
    faq_id: str,
    request: FAQUpdate,
    service: FAQService = Depends(get_faq_service_dep),
):
    """Update an existing FAQ."""
    faq = service.update_faq(
        faq_id=faq_id,
        question=request.question,
        answer=request.answer,
        category=request.category,
        keywords=request.keywords,
    )
    
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    return FAQResponse(**faq)


@router.delete("/{faq_id}")
async def delete_faq(
    faq_id: str,
    service: FAQService = Depends(get_faq_service_dep),
):
    """Delete an FAQ."""
    deleted = service.delete_faq(faq_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    return {"status": "deleted", "id": faq_id}


@router.get("/ai/search")
async def search_for_ai(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(5, ge=1, le=10, description="Max results"),
    service: FAQService = Depends(get_faq_service_dep),
):
    """Search FAQs for AI reference.
    
    This endpoint is used by the AI pipeline to find relevant FAQs
    when generating responses.
    """
    results = service.get_faqs_for_ai(query=query, limit=limit)
    
    return {
        "query": query,
        "results": results,
        "total": len(results),
    }


@router.post("/import", response_model=FAQImportResponse)
async def import_faqs(
    request: FAQImportRequest,
    service: FAQService = Depends(get_faq_service_dep),
):
    """Import multiple FAQs.
    
    Mini Parwa: Bulk import FAQs for quick setup.
    """
    imported = 0
    
    for faq in request.faqs:
        try:
            service.create_faq(
                question=faq.question,
                answer=faq.answer,
                category=faq.category,
                keywords=faq.keywords,
            )
            imported += 1
        except Exception as e:
            # Skip invalid FAQs
            continue
    
    return FAQImportResponse(
        imported=imported,
        message=f"Successfully imported {imported} FAQs",
    )


@router.get("/export")
async def export_faqs(
    service: FAQService = Depends(get_faq_service_dep),
):
    """Export all FAQs as JSON."""
    faqs_json = service.export_faqs()
    
    return {
        "format": "json",
        "data": faqs_json,
    }
