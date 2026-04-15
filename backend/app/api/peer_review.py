"""
Peer Review API — F-108 Junior-to-Senior Escalation

Provides endpoints for:
- POST /api/peer-review/escalate — Create an escalation
- POST /api/peer-review/auto-escalate — Auto escalate if needed
- GET /api/peer-review/queue — Get senior agent's review queue
- GET /api/peer-review/escalations/{escalation_id} — Get escalation details
- POST /api/peer-review/escalations/{escalation_id}/submit — Submit review
- GET /api/peer-review/analytics — Get escalation analytics
- GET /api/peer-review/workload — Get senior workload distribution
- GET /api/peer-review/learning/{agent_id} — Get learning progress
- POST /api/training/pipeline-test — Run full pipeline integration test

BC-001: All endpoints scoped to company_id (via middleware).
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request, Path, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("parwa.peer_review_api")

router = APIRouter(prefix="/api/v1", tags=["Peer Review"])


def _get_db(request: Request):
    """Get DB session from request state."""
    from database.session import get_db_session
    return get_db_session()


def _get_company_id(request: Request) -> Optional[str]:
    """Get company_id from request state (injected by middleware)."""
    return getattr(request.state, "company_id", None)


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────

class EscalationRequest(BaseModel):
    """Request to create an escalation."""
    junior_agent_id: str = Field(..., description="Junior agent requesting review")
    ticket_id: str = Field(..., description="Related ticket ID")
    reason: str = Field(
        ...,
        description="Reason: low_confidence, complex_query, policy_violation_risk, customer_escalation, uncertainty, knowledge_gap"
    )
    original_response: Optional[str] = Field(None, description="Draft response for review")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Junior's confidence score")
    context: Optional[dict] = Field(None, description="Additional context")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")


class AutoEscalateRequest(BaseModel):
    """Request for auto-escalation check."""
    agent_id: str = Field(..., description="Agent ID")
    ticket_id: str = Field(..., description="Ticket ID")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence score")
    response_draft: str = Field(..., description="Draft response")
    context: Optional[dict] = Field(None, description="Additional context")


class ReviewSubmitRequest(BaseModel):
    """Request to submit a senior review."""
    senior_agent_id: str = Field(..., description="Senior agent ID")
    reviewed_response: str = Field(..., description="Reviewed/corrected response")
    feedback: Optional[str] = Field(None, description="Feedback for junior")
    corrections: Optional[list] = Field(None, description="List of corrections")
    approved: bool = Field(True, description="Whether original was approved")
    use_for_training: bool = Field(True, description="Use for training data")


# ─────────────────────────────────────────────────────────────────────────────
# Escalation Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/peer-review/escalate",
    summary="Create an escalation (F-108)",
)
async def create_escalation(
    request: Request,
    body: EscalationRequest,
):
    """Create a junior-to-senior escalation for review."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        result = service.create_escalation(
            company_id=company_id,
            junior_agent_id=body.junior_agent_id,
            ticket_id=body.ticket_id,
            reason=body.reason,
            original_response=body.original_response,
            confidence_score=body.confidence_score,
            context=body.context,
            priority=body.priority,
        )

        if result.get("status") == "error":
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "ESCALATION_ERROR", "message": result.get("error")}},
            )

        return result

    except Exception as exc:
        logger.error(
            "create_escalation_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to create escalation"}},
        )


@router.post(
    "/peer-review/auto-escalate",
    summary="Auto escalate if needed (F-108)",
)
async def auto_escalate(
    request: Request,
    body: AutoEscalateRequest,
):
    """Automatically escalate if confidence is below threshold."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        result = service.auto_escalate_if_needed(
            company_id=company_id,
            agent_id=body.agent_id,
            ticket_id=body.ticket_id,
            confidence_score=body.confidence_score,
            response_draft=body.response_draft,
            context=body.context,
        )

        return result

    except Exception as exc:
        logger.error(
            "auto_escalate_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to auto-escalate"}},
        )


@router.get(
    "/peer-review/queue",
    summary="Get review queue (F-108)",
)
async def get_review_queue(
    request: Request,
    senior_agent_id: str = Query(..., description="Senior agent ID"),
    status: Optional[str] = Query("pending", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get the review queue for a senior agent."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        return service.get_review_queue(
            company_id=company_id,
            senior_agent_id=senior_agent_id,
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
        )

    except Exception as exc:
        logger.error(
            "get_review_queue_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get review queue"}},
        )


@router.get(
    "/peer-review/escalations/{escalation_id}",
    summary="Get escalation details (F-108)",
)
async def get_escalation_details(
    request: Request,
    escalation_id: str = Path(..., description="Escalation ID"),
):
    """Get details of a specific escalation."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        result = service.get_escalation_details(company_id, escalation_id)

        if not result:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": f"Escalation {escalation_id} not found"}},
            )

        return result

    except Exception as exc:
        logger.error(
            "get_escalation_details_error",
            extra={"company_id": company_id, "escalation_id": escalation_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get escalation details"}},
        )


@router.post(
    "/peer-review/escalations/{escalation_id}/submit",
    summary="Submit review (F-108)",
)
async def submit_review(
    request: Request,
    escalation_id: str = Path(..., description="Escalation ID"),
    body: ReviewSubmitRequest = None,
):
    """Submit a senior agent's review."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        result = service.submit_review(
            company_id=company_id,
            escalation_id=escalation_id,
            senior_agent_id=body.senior_agent_id,
            reviewed_response=body.reviewed_response,
            feedback=body.feedback,
            corrections=body.corrections,
            approved=body.approved,
            use_for_training=body.use_for_training,
        )

        if result.get("status") == "error":
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "REVIEW_ERROR", "message": result.get("error")}},
            )

        return result

    except Exception as exc:
        logger.error(
            "submit_review_error",
            extra={"company_id": company_id, "escalation_id": escalation_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to submit review"}},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/peer-review/analytics",
    summary="Get escalation analytics (F-108)",
)
async def get_escalation_analytics(
    request: Request,
    days: int = Query(30, ge=1, le=90, description="Days to analyze"),
):
    """Get escalation analytics for the company."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        return service.get_escalation_analytics(company_id, days)

    except Exception as exc:
        logger.error(
            "get_escalation_analytics_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get analytics"}},
        )


@router.get(
    "/peer-review/workload",
    summary="Get senior workload distribution (F-108)",
)
async def get_senior_workload(request: Request):
    """Get workload distribution among senior agents."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        workload = service.get_senior_workload(company_id)

        return {
            "company_id": company_id,
            "senior_agents": workload,
            "total": len(workload),
        }

    except Exception as exc:
        logger.error(
            "get_senior_workload_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get workload"}},
        )


@router.get(
    "/peer-review/learning/{agent_id}",
    summary="Get learning progress (F-108)",
)
async def get_learning_progress(
    request: Request,
    agent_id: str = Path(..., description="Junior agent ID"),
    days: int = Query(30, ge=1, le=90, description="Days to analyze"),
):
    """Get learning progress for a junior agent from reviews."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import PeerReviewService

        service = PeerReviewService(db)
        return service.get_learning_progress(company_id, agent_id, days)

    except Exception as exc:
        logger.error(
            "get_learning_progress_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get learning progress"}},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Training Pipeline Test Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/training/pipeline-test",
    summary="Run full pipeline integration test (F-108)",
)
async def run_pipeline_test(request: Request):
    """Run the full training pipeline integration test."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.peer_review_service import run_full_training_pipeline_test

        result = run_full_training_pipeline_test(company_id, db)

        if result.get("success"):
            return result
        else:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "TEST_FAILED", "message": "Pipeline test failed", "details": result}},
            )

    except Exception as exc:
        logger.error(
            "run_pipeline_test_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to run pipeline test"}},
        )
