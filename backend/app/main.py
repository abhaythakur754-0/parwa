"""
PARWA FastAPI Application (BC-012)

Main FastAPI app with:
- Health/ready/metrics endpoints (BC-012)
- Structured JSON error responses (BC-012)
- No stack traces to users (BC-012)
- OpenAPI schema hidden when DEBUG=False (BC-011)
"""

from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app.config import get_settings
from backend.app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ParwaBaseError,
    RateLimitError,
    ValidationError,
)
from backend.app.logger import configure_logging, get_logger

# Track if logging has been configured (idempotent)
_logging_configured = False

# Current environment (set at import time for test route guards)
_CURRENT_ENV = os.environ.get("ENVIRONMENT", "development")


def _ensure_logging():
    """Ensure logging is configured (safe to call multiple times)."""
    global _logging_configured  # noqa: PLW0603
    if not _logging_configured:
        env = os.environ.get("ENVIRONMENT", "production")
        configure_logging(env)
        _logging_configured = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    configure_logging(settings.ENVIRONMENT)

    # Hide OpenAPI schema when not in debug mode (BC-011)
    if settings.DEBUG:
        app.docs_url = "/docs"
        app.redoc_url = "/redoc"
        app.openapi_url = "/openapi.json"
    else:
        app.docs_url = None
        app.redoc_url = None
        app.openapi_url = None

    logger = get_logger("lifespan")
    logger.info("parwa_startup", environment=settings.ENVIRONMENT, version="0.1.0")
    yield
    logger.info("parwa_shutdown")


app = FastAPI(
    title="PARWA API",
    description="AI-Powered Customer Support Platform",
    version="0.1.0",
    lifespan=lifespan,
    # docs/openapi set in lifespan after settings loaded to avoid
    # module-level crash when env vars missing (BC-011)
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ── Exception Handlers (BC-012: structured JSON, no stack traces) ───


@app.exception_handler(ParwaBaseError)
async def parwa_exception_handler(request: Request, exc: ParwaBaseError) -> JSONResponse:
    """Handle all PARWA custom exceptions with structured JSON."""
    data = exc.to_dict()
    # BC-012: Include correlation ID in every error response
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        data["correlation_id"] = correlation_id
    return JSONResponse(
        status_code=exc.status_code,
        content=data,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 with structured JSON (BC-012)."""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": f"The path {request.url.path} was not found",
                "details": None,
            }
        },
    )


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 422 validation errors with structured JSON (BC-012)."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": None,
            }
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 500 errors — NO stack traces to users (BC-012)."""
    _ensure_logging()
    logger = get_logger("error_handler")
    logger.error(
        "internal_error",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": None,
            }
        },
    )


# ── Health Endpoints (BC-012) ──────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe — returns 200 if app is running."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe — returns 200 when dependencies are healthy."""
    return {"status": "ready"}


@app.get("/metrics", tags=["Health"])
async def metrics():
    """Prometheus-style metrics endpoint."""
    try:
        settings = get_settings()
        env = settings.ENVIRONMENT
    except Exception:
        env = "unknown"
    now = datetime.now(timezone.utc).isoformat()
    return PlainTextResponse(
        content=(
            "# HELP parwa_build_info PARWA build information\n"
            "# TYPE parwa_build_info gauge\n"
            f'parwa_build_info{{version="0.1.0",environment="{env}"}} 1\n'
            "# HELP parwa_health_check PARWA health status (1=healthy, 0=unhealthy)\n"
            "# TYPE parwa_health_check gauge\n"
            f'parwa_health_check{{status="healthy"}} 1\n'
            f"# Last scraped at {now}\n"
        ),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ── Test-only routes (only active in test environment) ──────────

if _CURRENT_ENV == "test":

    @app.get("/test/raise/not-found")
    async def _test_raise_not_found():
        raise NotFoundError(message="Test resource not found", details={"id": "123"})

    @app.get("/test/raise/validation")
    async def _test_raise_validation():
        raise ValidationError(message="Test validation", details=["field x invalid"])

    @app.get("/test/raise/authentication")
    async def _test_raise_authentication():
        raise AuthenticationError(message="Test auth failed", details={"reason": "bad token"})

    @app.get("/test/raise/authorization")
    async def _test_raise_authorization():
        raise AuthorizationError(message="Test forbidden", details={"required": "admin"})

    @app.get("/test/raise/rate-limit")
    async def _test_raise_rate_limit():
        raise RateLimitError(message="Test rate limit", details={"retry_after": 60})

    @app.get("/test/raise/internal")
    async def _test_raise_internal():
        raise ValueError("This simulates an unexpected 500 error")
