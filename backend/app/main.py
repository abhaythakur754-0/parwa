"""
PARWA FastAPI Application (BC-012)

Main FastAPI app with:
- Health/ready/metrics endpoints (BC-012)
- Structured JSON error responses (BC-012)
- No stack traces to users (BC-012)
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app.config import get_settings
from backend.app.exceptions import ParwaBaseError
from backend.app.logger import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    configure_logging(settings.ENVIRONMENT)
    logger = get_logger("lifespan")
    logger.info("parwa_startup", environment=settings.ENVIRONMENT, version="0.1.0")
    yield
    logger.info("parwa_shutdown")


app = FastAPI(
    title="PARWA API",
    description="AI-Powered Customer Support Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().DEBUG else None,
    redoc_url="/redoc" if get_settings().DEBUG else None,
)


# ── Exception Handlers (BC-012: structured JSON, no stack traces) ───


@app.exception_handler(ParwaBaseError)
async def parwa_exception_handler(request: Request, exc: ParwaBaseError) -> JSONResponse:
    """Handle all PARWA custom exceptions with structured JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
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
    now = datetime.now(timezone.utc).isoformat()
    return PlainTextResponse(
        content=(
            "# HELP parwa_build_info PARWA build information\n"
            "# TYPE parwa_build_info gauge\n"
            f'parwa_build_info{{version="0.1.0",environment="{get_settings().ENVIRONMENT}"}} 1\n'
            "# HELP parwa_health_check PARWA health status (1=healthy, 0=unhealthy)\n"
            "# TYPE parwa_health_check gauge\n"
            f'parwa_health_check{{status="healthy"}} 1\n'
            f"# Last scraped at {now}\n"
        ),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
