"""
PARWA Error Handler Middleware (BC-012)

Provides:
1. Correlation ID generation and propagation for every request
2. Structured JSON error responses — no stack traces to users
3. Request-level error logging with full context

The correlation ID flow:
- Check for incoming X-Correlation-ID header (from upstream/previous request)
- If missing, generate a new UUID v4
- Store in request.state for downstream access
- Include in all error responses

BC-012 Requirements:
- Error responses always have {error: {code, message, details}}
- Stack traces NEVER exposed to users (logged internally only)
- Correlation ID in every error response for debugging
"""

import uuid

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.exceptions import ParwaBaseError
from app.logger import get_logger

# Header names
CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"

logger = get_logger("error_handler")


def get_correlation_id(request: Request) -> str:
    """Extract or generate correlation ID for a request.

    Checks the X-Correlation-ID header first. If missing,
    generates a new UUID v4.

    Args:
        request: Incoming HTTP request.

    Returns:
        Correlation ID string.
    """
    correlation_id = request.headers.get(CORRELATION_ID_HEADER)
    if correlation_id and len(correlation_id) <= 64:
        # Sanitize: only allow alphanumeric, hyphens, underscores
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )
        if all(c in safe_chars for c in correlation_id):
            return correlation_id

    return str(uuid.uuid4())


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware: error handling + correlation ID.

    - Generates/propagates correlation ID for every request
    - Catches unhandled exceptions and returns
      structured JSON (BC-012)
    - Logs all errors with full context (but never
      returns stack traces to users)
    - Sets correlation ID in response header
    """

    async def dispatch(self, request: Request, call_next):
        # Generate/extract correlation ID
        correlation_id = get_correlation_id(request)
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
            # Set correlation ID on all successful responses
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        except ParwaBaseError as exc:
            # Handle known PARWA errors — structured JSON, no stack trace
            return self._handle_parwa_error(request, exc, correlation_id)
        except StarletteHTTPException as exc:
            # Handle Starlette HTTPException (404, 422, etc.)
            return self._handle_http_exception(request, exc, correlation_id)
        except Exception as exc:
            # Handle unexpected errors — log, return generic msg
            return self._handle_unexpected_error(
                request,
                exc,
                correlation_id,
            )

    def _handle_parwa_error(
        self, request: Request, exc: ParwaBaseError, correlation_id: str
    ) -> JSONResponse:
        """Handle known PARWA exceptions with structured JSON."""
        error_dict = exc.to_dict()

        # Add correlation ID to error response
        error_dict["correlation_id"] = correlation_id

        # Log the error with full context (internal only)
        logger.error(
            "parwa_error",
            correlation_id=correlation_id,
            error_code=exc.error_code,
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            message=exc.message,
        )

        response = JSONResponse(
            status_code=exc.status_code,
            content=error_dict,
        )
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response

    def _handle_http_exception(
        self,
        request: Request,
        exc: StarletteHTTPException,
        correlation_id: str,
    ) -> JSONResponse:
        """Handle Starlette HTTPException with structured JSON.

        Converts Starlette's HTTPException to PARWA structured format
        while preserving the original status code.
        """
        logger.warning(
            "http_exception",
            correlation_id=correlation_id,
            status_code=exc.status_code,
            detail=str(exc.detail),
            path=request.url.path,
            method=request.method,
        )

        error_response = {
            "error": {
                "code": _status_to_error_code(exc.status_code),
                "message": str(exc.detail),
                "details": None,
            },
            "correlation_id": correlation_id,
        }

        response = JSONResponse(
            status_code=exc.status_code,
            content=error_response,
        )
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response

    def _handle_unexpected_error(
        self, request: Request, exc: Exception, correlation_id: str
    ) -> JSONResponse:
        """Handle unexpected exceptions.

        Log stack trace internally, return generic message.

        BC-012: Stack traces are NEVER sent to users.
        They are only logged internally for debugging.
        """
        # Log full error with stack trace (internal only)
        logger.exception(
            "unexpected_error",
            correlation_id=correlation_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
            path=request.url.path,
            method=request.method,
        )

        # Return generic error to user — no stack trace, no internal details
        error_response = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": None,
            },
            "correlation_id": correlation_id,
        }

        response = JSONResponse(status_code=500, content=error_response)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response


def build_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details=None,
    correlation_id: str = None,
) -> JSONResponse:
    """Build a structured error response (BC-012 format).

    Utility function for building error responses in route handlers.
    All errors follow the format: {error: {code, message, details}}.

    Args:
        status_code: HTTP status code.
        error_code: Machine-readable error code.
        message: Human-readable error message.
        details: Optional additional details.
        correlation_id: Optional correlation ID.

    Returns:
        JSONResponse with structured error body.
    """
    content = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details,
        }
    }
    if correlation_id:
        content["correlation_id"] = correlation_id

    return JSONResponse(status_code=status_code, content=content)


def _status_to_error_code(status_code: int) -> str:
    """Convert HTTP status code to PARWA error code string.

    Maps common status codes to PARWA error codes for consistency.
    Unknown codes default to HTTP_ERROR.
    """
    _mapping = {
        400: "BAD_REQUEST",
        401: "AUTHENTICATION_ERROR",
        403: "AUTHORIZATION_ERROR",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
    }
    return _mapping.get(status_code, "HTTP_ERROR")
