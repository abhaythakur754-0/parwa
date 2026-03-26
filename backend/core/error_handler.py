"""
PARWA Error Handling Module
Comprehensive error handling for AI Workforce Customer Care System
"""

from typing import Optional, Dict, Any, Callable, Type
from functools import wraps
from enum import Enum
import logging
import traceback
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels for logging and alerting"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    EXTERNAL_API = "external_api"
    DATABASE = "database"
    WEBHOOK = "webhook"
    COMPLIANCE = "compliance"
    CONFIGURATION = "configuration"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"


class PARWAError(Exception):
    """Base exception class for PARWA system"""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        category: ErrorCategory = ErrorCategory.VALIDATION,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
        company_id: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.retryable = retryable
        self.company_id = company_id
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }


# ============================================================================
# Webhook Errors
# ============================================================================

class WebhookError(PARWAError):
    """Base webhook error"""
    def __init__(self, message: str, error_code: str = "WEBHOOK_ERROR", **kwargs):
        kwargs.setdefault("category", ErrorCategory.WEBHOOK)
        super().__init__(message, error_code, **kwargs)


class WebhookSignatureError(WebhookError):
    """Invalid webhook signature"""
    def __init__(self, message: str = "Invalid webhook signature", source: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="WEBHOOK_SIGNATURE_INVALID",
            severity=ErrorSeverity.HIGH,
            details={"source": source}
        )


class WebhookTimestampError(WebhookError):
    """Webhook timestamp expired or invalid"""
    def __init__(self, message: str = "Webhook timestamp expired", timestamp_diff: Optional[float] = None):
        super().__init__(
            message=message,
            error_code="WEBHOOK_TIMESTAMP_EXPIRED",
            severity=ErrorSeverity.MEDIUM,
            details={"timestamp_diff_seconds": timestamp_diff}
        )


class WebhookPayloadError(WebhookError):
    """Invalid webhook payload"""
    def __init__(self, message: str = "Invalid webhook payload", validation_errors: Optional[list] = None):
        super().__init__(
            message=message,
            error_code="WEBHOOK_PAYLOAD_INVALID",
            severity=ErrorSeverity.MEDIUM,
            details={"validation_errors": validation_errors or []}
        )


class WebhookProcessingError(WebhookError):
    """Error processing webhook"""
    def __init__(self, message: str = "Error processing webhook", event_type: Optional[str] = None, retryable: bool = True):
        super().__init__(
            message=message,
            error_code="WEBHOOK_PROCESSING_ERROR",
            severity=ErrorSeverity.HIGH,
            retryable=retryable,
            details={"event_type": event_type}
        )


# ============================================================================
# Authentication & Authorization Errors
# ============================================================================

class AuthenticationError(PARWAError):
    """Authentication failed"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTH_FAILED",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.MEDIUM
        )


class AuthorizationError(PARWAError):
    """Authorization failed - insufficient permissions"""
    def __init__(self, message: str = "Insufficient permissions", required_role: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="AUTH_FORBIDDEN",
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.MEDIUM,
            details={"required_role": required_role}
        )


class APIKeyError(PARWAError):
    """Invalid or missing API key"""
    def __init__(self, message: str = "Invalid API key", provider: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="API_KEY_INVALID",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            details={"provider": provider}
        )


# ============================================================================
# External API Errors
# ============================================================================

class ExternalAPIError(PARWAError):
    """External API error"""
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        retryable: bool = True,
        **kwargs
    ):
        kwargs.setdefault("category", ErrorCategory.EXTERNAL_API)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("retryable", retryable)
        kwargs["details"] = kwargs.get("details", {})
        kwargs["details"]["provider"] = provider
        kwargs["details"]["status_code"] = status_code
        super().__init__(message, "EXTERNAL_API_ERROR", **kwargs)


class GoogleAIError(ExternalAPIError):
    """Google AI API error"""
    def __init__(self, message: str = "Google AI API error", **kwargs):
        super().__init__(message, provider="google_ai", **kwargs)


class CerebrasError(ExternalAPIError):
    """Cerebras API error"""
    def __init__(self, message: str = "Cerebras API error", **kwargs):
        super().__init__(message, provider="cerebras", **kwargs)


class GroqError(ExternalAPIError):
    """Groq API error"""
    def __init__(self, message: str = "Groq API error", **kwargs):
        super().__init__(message, provider="groq", **kwargs)


class BrevoError(ExternalAPIError):
    """Brevo (Sendinblue) API error"""
    def __init__(self, message: str = "Brevo API error", **kwargs):
        super().__init__(message, provider="brevo", **kwargs)


class ShopifyAPIError(ExternalAPIError):
    """Shopify API error"""
    def __init__(self, message: str = "Shopify API error", **kwargs):
        super().__init__(message, provider="shopify", **kwargs)


class StripeAPIError(ExternalAPIError):
    """Stripe API error"""
    def __init__(self, message: str = "Stripe API error", **kwargs):
        super().__init__(message, provider="stripe", **kwargs)


# ============================================================================
# Database Errors
# ============================================================================

class DatabaseError(PARWAError):
    """Database operation error"""
    def __init__(self, message: str = "Database error", operation: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.DATABASE)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("retryable", True)
        kwargs["details"] = kwargs.get("details", {})
        kwargs["details"]["operation"] = operation
        super().__init__(message, "DATABASE_ERROR", **kwargs)


class RecordNotFoundError(DatabaseError):
    """Record not found in database"""
    def __init__(self, message: str = "Record not found", model: Optional[str] = None, record_id: Optional[str] = None):
        super().__init__(
            message=message,
            operation="read",
            severity=ErrorSeverity.LOW,
            retryable=False
        )
        self.details["model"] = model
        self.details["record_id"] = record_id


class DuplicateRecordError(DatabaseError):
    """Duplicate record in database"""
    def __init__(self, message: str = "Record already exists", field: Optional[str] = None):
        super().__init__(
            message=message,
            operation="create",
            severity=ErrorSeverity.LOW,
            retryable=False
        )
        self.details["field"] = field


# ============================================================================
# Compliance Errors
# ============================================================================

class ComplianceError(PARWAError):
    """Compliance-related error"""
    def __init__(self, message: str, error_code: str = "COMPLIANCE_ERROR", **kwargs):
        kwargs.setdefault("category", ErrorCategory.COMPLIANCE)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        super().__init__(message, error_code, **kwargs)


class GDPRComplianceError(ComplianceError):
    """GDPR compliance error"""
    def __init__(self, message: str = "GDPR compliance violation", request_type: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="GDPR_VIOLATION",
            details={"request_type": request_type}
        )


class TCPAComplianceError(ComplianceError):
    """TCPA compliance error"""
    def __init__(self, message: str = "TCPA compliance violation", phone_number: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="TCPA_VIOLATION",
            severity=ErrorSeverity.CRITICAL,
            details={"phone_number": phone_number[:6] + "****" if phone_number else None}
        )


class SLABreachError(ComplianceError):
    """SLA breach error"""
    def __init__(self, message: str = "SLA breach detected", sla_hours: Optional[int] = None):
        super().__init__(
            message=message,
            error_code="SLA_BREACH",
            severity=ErrorSeverity.CRITICAL,
            details={"sla_hours": sla_hours}
        )


# ============================================================================
# Rate Limiting Errors
# ============================================================================

class RateLimitError(PARWAError):
    """Rate limit exceeded"""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[int] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            details={
                "limit": limit,
                "window_seconds": window,
                "retry_after_seconds": retry_after
            }
        )


# ============================================================================
# Configuration Errors
# ============================================================================

class ConfigurationError(PARWAError):
    """Configuration error"""
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.CONFIGURATION)
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)
        kwargs["details"] = kwargs.get("details", {})
        kwargs["details"]["config_key"] = config_key
        super().__init__(message, "CONFIG_ERROR", **kwargs)


class MissingConfigError(ConfigurationError):
    """Required configuration missing"""
    def __init__(self, config_key: str):
        super().__init__(
            message=f"Required configuration missing: {config_key}",
            config_key=config_key
        )


class InvalidConfigError(ConfigurationError):
    """Invalid configuration value"""
    def __init__(self, config_key: str, reason: str):
        super().__init__(
            message=f"Invalid configuration for {config_key}: {reason}",
            config_key=config_key
        )


# ============================================================================
# Error Handler Decorators
# ============================================================================

def handle_errors(
    default_message: str = "An error occurred",
    reraise: bool = False,
    log_errors: bool = True,
    return_error_dict: bool = False
):
    """
    Decorator for handling errors in functions.
    
    Args:
        default_message: Default error message if not a PARWAError
        reraise: Whether to reraise the exception
        log_errors: Whether to log errors
        return_error_dict: Return error as dict instead of raising
    """
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except PARWAError as e:
                if log_errors:
                    _log_error(e)
                if reraise:
                    raise
                if return_error_dict:
                    return e.to_dict()
                raise
            except Exception as e:
                error = PARWAError(
                    message=str(e) or default_message,
                    error_code="INTERNAL_ERROR",
                    severity=ErrorSeverity.HIGH,
                    details={"original_exception": type(e).__name__}
                )
                if log_errors:
                    _log_error(error)
                    logger.error(f"Unexpected error: {traceback.format_exc()}")
                if reraise:
                    raise error from e
                if return_error_dict:
                    return error.to_dict()
                raise error from e

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except PARWAError as e:
                if log_errors:
                    _log_error(e)
                if reraise:
                    raise
                if return_error_dict:
                    return e.to_dict()
                raise
            except Exception as e:
                error = PARWAError(
                    message=str(e) or default_message,
                    error_code="INTERNAL_ERROR",
                    severity=ErrorSeverity.HIGH,
                    details={"original_exception": type(e).__name__}
                )
                if log_errors:
                    _log_error(error)
                    logger.error(f"Unexpected error: {traceback.format_exc()}")
                if reraise:
                    raise error from e
                if return_error_dict:
                    return error.to_dict()
                raise error from e

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def _log_error(error: PARWAError):
    """Log error based on severity"""
    log_data = error.to_dict()
    # Rename 'message' key to avoid conflict with LogRecord's built-in attribute
    if "message" in log_data:
        log_data["error_message"] = log_data.pop("message")
    
    if error.severity == ErrorSeverity.CRITICAL:
        logger.critical(f"CRITICAL ERROR [{error.error_code}]: {error.message}", extra=log_data)
    elif error.severity == ErrorSeverity.HIGH:
        logger.error(f"HIGH ERROR [{error.error_code}]: {error.message}", extra=log_data)
    elif error.severity == ErrorSeverity.MEDIUM:
        logger.warning(f"MEDIUM ERROR [{error.error_code}]: {error.message}", extra=log_data)
    else:
        logger.info(f"LOW ERROR [{error.error_code}]: {error.message}", extra=log_data)


# ============================================================================
# Retry Logic
# ============================================================================

class RetryConfig:
    """Configuration for retry logic"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_exceptions: tuple = (ExternalAPIError, RateLimitError, DatabaseError)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for retrying failed operations with exponential backoff.
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt == config.max_retries:
                        raise
                    
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} after {delay:.2f}s: {e.message}"
                    )
                    import time
                    time.sleep(delay)
                except Exception:
                    raise
            
            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt == config.max_retries:
                        raise
                    
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} after {delay:.2f}s: {e.message}"
                    )
                    await asyncio.sleep(delay)
                except Exception:
                    raise
            
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# ============================================================================
# Error Response Builder
# ============================================================================

class ErrorResponseBuilder:
    """Build standardized error responses for API endpoints"""
    
    @staticmethod
    def build(
        error: Exception,
        include_trace: bool = False,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build error response from exception.
        
        Args:
            error: The exception that occurred
            include_trace: Whether to include stack trace (development only)
            company_id: Company ID for multi-tenant context
        
        Returns:
            Standardized error response dictionary
        """
        if isinstance(error, PARWAError):
            response = error.to_dict()
        else:
            response = {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": str(error),
                "category": ErrorCategory.VALIDATION.value,
                "severity": ErrorSeverity.MEDIUM.value,
                "retryable": False,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"exception_type": type(error).__name__}
            }
        
        if company_id:
            response["company_id"] = company_id
        
        if include_trace:
            response["trace"] = traceback.format_exc()
        
        return response
    
    @staticmethod
    def validation_error(
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Build validation error response"""
        return {
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": message,
            "category": ErrorCategory.VALIDATION.value,
            "severity": ErrorSeverity.LOW.value,
            "retryable": False,
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "field": field,
                "provided_value": str(value) if value is not None else None
            }
        }
    
    @staticmethod
    def not_found_error(
        resource: str,
        resource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build not found error response"""
        return {
            "error": True,
            "error_code": "NOT_FOUND",
            "message": f"{resource} not found",
            "category": ErrorCategory.DATABASE.value,
            "severity": ErrorSeverity.LOW.value,
            "retryable": False,
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "resource": resource,
                "resource_id": resource_id
            }
        }
