"""
PARWA AI Entitlement Middleware (Week 8, SG-05 / BC-011)

Intercepts requests to /api/ai/ paths and checks variant-level
feature entitlements before allowing the request through.

- Only intercepts requests to /api/ai/ paths
- Extracts company_id from request.state (set by TenantMiddleware)
- For POST/PUT/DELETE to /api/ai/ endpoints, calls enforce_entitlement()
  to check feature access
- Skips health/status endpoints
- On 403, returns JSON error response matching PARWA error format

Building Codes:
- BC-001: Multi-Tenant Isolation (company_id on every check)
- BC-007: AI Model Interaction (feature gating per variant tier)
- BC-011: Authentication & Security
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("parwa.middleware.ai_entitlement")

# ── Path Configuration ────────────────────────────────────────────────

# Only intercept paths starting with this prefix
AI_PATH_PREFIX = "/api/ai/"

# Status/health endpoints that skip entitlement checks
SKIP_PATHS = {
    "/api/ai/router/status",
    "/api/ai/cold-start/status",
    "/api/ai/failover/status",
}

# Skip prefixes (any path starting with these)
SKIP_PREFIXES = (
    "/api/ai/router/status",
    "/api/ai/cold-start/status",
    "/api/ai/failover/status",
)

# Path segment → feature_id mapping for entitlement checks
PATH_FEATURE_MAP = {
    "router": "ai_routing",
    "classify": "ticket_classification",
    "respond": "response_generation",
    "sentiment": "sentiment_analysis",
    "guardrail": "prompt_injection_detection",
    "summarize": "conversation_summarization",
    "knowledge": "knowledge_base_search",
    "router/rebalance": "auto_rebalancing",
    "cold-start/warmup": "cold_start_warmup",
    "failover": "automatic_failover",
}

# Default variant_type if none can be determined from DB
DEFAULT_VARIANT_TYPE = "mini_parwa"

# HTTP methods that require entitlement checks
MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _extract_feature_id(path: str) -> str | None:
    """
    Extract feature_id from the request path.

    Examples:
        /api/ai/router/classify → router
        /api/ai/guardrail/check  → guardrail
        /api/ai/respond           → respond
    """
    # Strip the prefix
    if not path.startswith(AI_PATH_PREFIX):
        return None

    remainder = path[len(AI_PATH_PREFIX):]
    # Remove leading slash
    remainder = remainder.lstrip("/")

    # Get the first segment
    segment = remainder.split("/")[0] if remainder else ""

    # Check two-segment paths first (e.g., "router/rebalance")
    if "/" in remainder:
        two_seg = "/".join(remainder.split("/")[:2])
        if two_seg in PATH_FEATURE_MAP:
            return PATH_FEATURE_MAP[two_seg]

    return PATH_FEATURE_MAP.get(segment)


def _should_skip(path: str) -> bool:
    """Check if the path should skip entitlement checks."""
    if path in SKIP_PATHS:
        return True
    for prefix in SKIP_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _get_company_variant_type(db, company_id: str) -> str:
    """
    Get the company's highest active variant type.

    Queries variant_instances for the company and returns the
    highest variant type found. Falls back to DEFAULT_VARIANT_TYPE.
    """
    try:
        from database.models.variant_engine import VariantInstance

        instances = db.query(VariantInstance).filter_by(
            company_id=company_id,
            status="active",
        ).all()

        if not instances:
            return DEFAULT_VARIANT_TYPE

        # Return the highest variant type
        priority = {
            "mini_parwa": 1,
            "parwa": 2,
            "parwa_high": 3,
        }
        sorted_instances = sorted(
            instances,
            key=lambda i: priority.get(i.variant_type, 0),
            reverse=True,
        )
        return sorted_instances[0].variant_type

    except Exception:
        logger.warning(
            "ai_entitlement_variant_lookup_failed",
            extra={
                "company_id": company_id,
                "warning": (
                    "Failed to look up variant type, "
                    f"using default: {DEFAULT_VARIANT_TYPE}"
                ),
            },
        )
        return DEFAULT_VARIANT_TYPE


class AIEntitlementMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces AI feature entitlements.

    - Only intercepts /api/ai/ paths
    - Checks entitlement for POST/PUT/DELETE/PATCH requests
    - Skips GET requests and health/status endpoints
    - On 403, returns PARWA-formatted JSON error response

    Must be added AFTER TenantMiddleware (so company_id is available
    on request.state) but BEFORE CORS.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ── Skip non-AI paths entirely ──
        if not path.startswith(AI_PATH_PREFIX):
            return await call_next(request)

        # ── Skip health/status endpoints ──
        if _should_skip(path):
            return await call_next(request)

        # ── GET/HEAD/OPTIONS: skip entitlement check ──
        if request.method.upper() not in MUTATING_METHODS:
            return await call_next(request)

        # ── Extract company_id from request.state ──
        company_id = getattr(request.state, "company_id", None)
        if not company_id or not company_id.strip():
            # No company_id — TenantMiddleware would have already
            # returned 403, but handle defensively
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "AUTHORIZATION_ERROR",
                        "message": (
                            "Tenant identification required "
                            "for AI feature access"
                        ),
                        "details": None,
                    }
                },
            )

        # ── Extract feature_id from path ──
        feature_id = _extract_feature_id(path)
        if not feature_id:
            # Unknown AI path — allow through (will 404 if
            # route doesn't exist)
            return await call_next(request)

        # ── Check entitlement ──
        try:
            from database.base import SessionLocal
            from backend.app.services.entitlement_middleware import (
                enforce_entitlement,
            )

            db = SessionLocal()
            try:
                variant_type = _get_company_variant_type(
                    db, company_id,
                )
                enforce_entitlement(
                    db, company_id, feature_id, variant_type,
                )

                logger.info(
                    "ai_entitlement_granted",
                    extra={
                        "company_id": company_id,
                        "feature_id": feature_id,
                        "variant_type": variant_type,
                        "method": request.method,
                        "path": path,
                    },
                )
            finally:
                db.close()

        except Exception as exc:
            error_code = getattr(exc, "error_code", None)
            status_code = getattr(exc, "status_code", 403)
            message = str(getattr(exc, "message", str(exc)))
            details = getattr(exc, "details", None)

            # Build PARWA error response (BC-012 format)
            error_response = {
                "error": {
                    "code": error_code or "FEATURE_NOT_ENTITLED",
                    "message": message,
                    "details": details,
                }
            }

            # Include correlation ID if available
            correlation_id = getattr(
                request.state, "correlation_id", None,
            )
            if correlation_id:
                error_response["correlation_id"] = correlation_id

            logger.warning(
                "ai_entitlement_denied",
                extra={
                    "company_id": company_id,
                    "feature_id": feature_id,
                    "error_code": error_code,
                    "status_code": status_code,
                    "method": request.method,
                    "path": path,
                },
            )

            return JSONResponse(
                status_code=status_code,
                content=error_response,
            )

        # ── Entitlement check passed — continue ──
        return await call_next(request)
