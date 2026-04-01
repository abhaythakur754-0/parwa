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
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None) -> None:
        super().__init__(message=message, error_code="NOT_FOUND", status_code=404, details=details)


class ValidationError(ParwaBaseError):
    def __init__(self, message: str = "Validation failed", details: Optional[Any] = None) -> None:
        super().__init__(message=message, error_code="VALIDATION_ERROR", status_code=422, details=details)


class AuthenticationError(ParwaBaseError):
    def __init__(self, message: str = "Authentication required", details: Optional[Any] = None) -> None:
        super().__init__(message=message, error_code="AUTHENTICATION_ERROR", status_code=401, details=details)


class AuthorizationError(ParwaBaseError):
    def __init__(self, message: str = "Permission denied", details: Optional[Any] = None) -> None:
        super().__init__(message=message, error_code="AUTHORIZATION_ERROR", status_code=403, details=details)


class RateLimitError(ParwaBaseError):
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Any] = None) -> None:
        super().__init__(message=message, error_code="RATE_LIMIT_EXCEEDED", status_code=429, details=details)


class InternalError(ParwaBaseError):
    def __init__(self, message: str = "An internal error occurred", details: Optional[Any] = None) -> None:
        super().__init__(message=message, error_code="INTERNAL_ERROR", status_code=500, details=details)
