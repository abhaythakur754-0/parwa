"""
PARWA Exception Classes (BC-012)

All exceptions inherit from ParwaBaseError and produce structured JSON
error responses. No stack traces are ever exposed to users.
"""

from typing import Any, Optional


class ParwaBaseError(Exception):
    """Base exception for all PARWA errors."""

    def __init__(
        self,
        message: str = "An error occurred",
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert to structured error dict for JSON response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundError(ParwaBaseError):
    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class ValidationError(ParwaBaseError):
    def __init__(
        self, message: str = "Validation failed",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="VALIDATION_ERROR",
            status_code=422, details=details,
        )


class AuthenticationError(ParwaBaseError):
    def __init__(
        self, message: str = "Authentication required",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="AUTHENTICATION_ERROR",
            status_code=401, details=details,
        )


class AuthorizationError(ParwaBaseError):
    def __init__(
        self, message: str = "Permission denied",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="AUTHORIZATION_ERROR",
            status_code=403, details=details,
        )


class RateLimitError(ParwaBaseError):
    def __init__(
        self, message: str = "Rate limit exceeded",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="RATE_LIMIT_EXCEEDED",
            status_code=429, details=details,
        )


class InternalError(ParwaBaseError):
    def __init__(
        self, message: str = "An internal error occurred",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="INTERNAL_ERROR",
            status_code=500, details=details,
        )


# ── Delivery Pipeline Errors (BC-015) ─────────────────────────────


class DeliveryError(ParwaBaseError):
    """Generic delivery failure — all channels exhausted, ticket undeliverable."""

    def __init__(
        self, message: str = "Delivery failed",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="DELIVERY_ERROR",
            status_code=502, details=details,
        )


class DeliveryCircuitOpenError(ParwaBaseError):
    """Circuit breaker is open for this channel — fast-fail without dispatch."""

    def __init__(
        self, message: str = "Delivery circuit breaker open",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="DELIVERY_CIRCUIT_OPEN",
            status_code=503, details=details,
        )


class DeliveryTimeoutError(ParwaBaseError):
    """Per-dispatch wall-clock timeout exceeded."""

    def __init__(
        self, message: str = "Delivery dispatch timed out",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="DELIVERY_TIMEOUT",
            status_code=504, details=details,
        )


# ── CRM Push-back Errors (BC-016) ──────────────────────────────────


class CRMPushError(ParwaBaseError):
    """CRM push-back failed after all retries.

    Customer already received the answer (phase 1 of Node 6.5 succeeded);
    this is a CRM-state-consistency error, not a delivery error.
    """

    def __init__(
        self, message: str = "CRM push-back failed",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message, error_code="CRM_PUSH_ERROR",
            status_code=502, details=details,
        )
