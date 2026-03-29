"""
PARWA Cold Start API Routes.

Provides endpoints for bootstrapping new clients with initial configuration.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.cold_start import ColdStartService, Industry
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/cold-start", tags=["Cold Start"])
logger = get_logger(__name__)

# Service instance
_cold_start_service = ColdStartService()


# --- Pydantic Schemas ---

class BootstrapRequest(BaseModel):
    """Request schema for client bootstrap."""
    client_name: str = Field(..., description="Name of the client")
    industry: Optional[str] = Field(None, description="Industry type (optional)")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="Custom configuration")


class BootstrapResponse(BaseModel):
    """Response schema for bootstrap."""
    client_id: str
    status: str
    industry: Optional[str] = None
    knowledge_base_ready: bool
    configuration_applied: bool
    errors: list = []


class StatusResponse(BaseModel):
    """Response schema for status check."""
    client_id: str
    status: str
    industry: Optional[str] = None
    knowledge_base_ready: bool
    configuration_applied: bool
    errors: list = []


class AnalyzeRequest(BaseModel):
    """Request schema for industry analysis."""
    client_name: str = Field(..., description="Client name for analysis")
    description: Optional[str] = Field(None, description="Client description")
    website: Optional[str] = Field(None, description="Client website")
    keywords: Optional[list] = Field(None, description="Keywords for analysis")


class AnalyzeResponse(BaseModel):
    """Response schema for industry analysis."""
    client_id: str
    detected_industry: str
    confidence_score: float
    keywords_found: list
    recommended_config: Dict[str, Any]


# --- API Endpoints ---

@router.post(
    "",
    response_model=BootstrapResponse,
    status_code=status.HTTP_200_OK,
    summary="Bootstrap new client",
    description="Bootstrap a new client with initial configuration and knowledge base setup."
)
async def bootstrap_client(
    request: BootstrapRequest
) -> BootstrapResponse:
    """
    Bootstrap a new client.

    Creates initial configuration and knowledge base for a new client.

    Args:
        request: Bootstrap request with client details.

    Returns:
        BootstrapResponse with bootstrap result.

    Raises:
        HTTPException: 500 if bootstrap fails.
    """
    try:
        result = await _cold_start_service.bootstrap({
            "client_name": request.client_name,
            "industry": request.industry,
            "custom_config": request.custom_config or {},
        })

        logger.info({
            "event": "bootstrap_endpoint_called",
            "client_id": result.client_id,
            "status": result.status.value,
        })

        return BootstrapResponse(
            client_id=result.client_id,
            status=result.status.value,
            industry=result.industry,
            knowledge_base_ready=result.knowledge_base_ready,
            configuration_applied=result.configuration_applied,
            errors=result.errors,
        )

    except Exception as e:
        logger.error({
            "event": "bootstrap_endpoint_error",
            "error": str(e),
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bootstrap failed: {str(e)}",
        )


@router.get(
    "/{client_id}/status",
    response_model=StatusResponse,
    summary="Get bootstrap status",
    description="Check the bootstrap status for a specific client."
)
async def get_bootstrap_status(
    client_id: str
) -> StatusResponse:
    """
    Get bootstrap status for a client.

    Args:
        client_id: Client identifier.

    Returns:
        StatusResponse with current bootstrap status.

    Raises:
        HTTPException: 404 if client not found.
    """
    status_result = await _cold_start_service.get_status(client_id)

    if not status_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )

    logger.info({
        "event": "status_endpoint_called",
        "client_id": client_id,
        "status": status_result["status"],
    })

    return StatusResponse(
        client_id=status_result["client_id"],
        status=status_result["status"],
        industry=status_result["industry"],
        knowledge_base_ready=status_result["knowledge_base_ready"],
        configuration_applied=status_result["configuration_applied"],
        errors=status_result["errors"],
    )


@router.post(
    "/{client_id}/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze client industry",
    description="Analyze client data to detect industry and recommend configuration."
)
async def analyze_client_industry(
    client_id: str,
    request: AnalyzeRequest
) -> AnalyzeResponse:
    """
    Analyze client to detect industry.

    Uses client information to determine the most appropriate industry
    and configuration recommendations.

    Args:
        client_id: Client identifier.
        request: Analysis request with client details.

    Returns:
        AnalyzeResponse with detected industry and recommendations.
    """
    analysis = await _cold_start_service.analyze_industry(
        client_id,
        {
            "client_name": request.client_name,
            "description": request.description,
            "website": request.website,
            "keywords": request.keywords,
        }
    )

    logger.info({
        "event": "analyze_endpoint_called",
        "client_id": client_id,
        "detected_industry": analysis.detected_industry,
        "confidence": analysis.confidence_score,
    })

    return AnalyzeResponse(
        client_id=analysis.client_id,
        detected_industry=analysis.detected_industry,
        confidence_score=analysis.confidence_score,
        keywords_found=analysis.keywords_found,
        recommended_config=analysis.recommended_config,
    )
