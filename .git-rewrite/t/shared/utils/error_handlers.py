import logging
from typing import Any, Dict, Optional, Type
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.core_functions.logger import get_logger

logger = get_logger("error_handlers")

class ParwaError(Exception):
    """Base exception for all PARWA custom errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class NotFoundError(ParwaError):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)

class ValidationError(ParwaError):
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=422, details=details)

class AuthError(ParwaError):
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED, details=details)

class RateLimitError(ParwaError):
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, details=details)

async def parwa_exception_handler(request: Request, exc: ParwaError) -> JSONResponse:
    logger.error(
        f"{exc.__class__.__name__}: {exc.message}",
        extra={
            "context": {"url": str(request.url), "method": request.method, "details": exc.details},
            "request_id": getattr(request.state, "request_id", None)
        },
        exc_info=True
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_type": exc.__class__.__name__, "extra": exc.details}
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        f"HTTPException: {exc.detail}",
        extra={
            "context": {"url": str(request.url), "method": request.method, "status_code": exc.status_code},
            "request_id": getattr(request.state, "request_id", None)
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_type": "HTTPException"}
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning(
        "RequestValidationError",
        extra={
            "context": {"url": str(request.url), "method": request.method, "errors": exc.errors()},
            "request_id": getattr(request.state, "request_id", None)
        }
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Input validation failed", "error_type": "RequestValidationError", "errors": exc.errors()}
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "context": {"url": str(request.url), "method": request.method},
            "request_id": getattr(request.state, "request_id", None)
        },
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error_type": "InternalServerError"}
    )

def setup_error_handlers(app: FastAPI) -> None:
    """Registers global error handlers on the given FastAPI app instance."""
    app.add_exception_handler(ParwaError, parwa_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
