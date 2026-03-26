"""
PARWA Service Error Decorators
Error handling decorators and utilities for service layer
"""

import logging
from typing import Optional, Dict, Any, Callable, TypeVar, ParamSpec
from functools import wraps
from datetime import datetime
import traceback

from backend.core.error_handler import (
    PARWAError,
    DatabaseError,
    RecordNotFoundError,
    DuplicateRecordError,
    ExternalAPIError,
    ConfigurationError,
    handle_errors,
    with_retry,
    RetryConfig,
    ErrorSeverity,
    ErrorCategory,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


# ============================================================================
# Service Context
# ============================================================================

class ServiceContext:
    """Context for service operations"""
    
    def __init__(
        self,
        service_name: str,
        operation: str,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        self.service_name = service_name
        self.operation = operation
        self.company_id = company_id
        self.user_id = user_id
        self.request_id = request_id
        self.start_time = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service_name,
            "operation": self.operation,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "start_time": self.start_time.isoformat()
        }


# ============================================================================
# Service Decorators
# ============================================================================

def service_error_handler(
    service_name: str,
    operation: str,
    reraise: bool = True,
    log_performance: bool = True
):
    """
    Decorator for service layer error handling.
    
    Args:
        service_name: Name of the service
        operation: Name of the operation
        reraise: Whether to reraise exceptions
        log_performance: Whether to log performance metrics
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            context = ServiceContext(service_name, operation)
            start_time = datetime.utcnow()
            
            try:
                result = func(*args, **kwargs)
                
                if log_performance:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    logger.debug(
                        f"[{service_name}] {operation} completed in {duration:.3f}s"
                    )
                
                return result
                
            except PARWAError:
                raise
            except Exception as e:
                error = _wrap_service_error(e, service_name, operation)
                logger.error(
                    f"[{service_name}] {operation} failed: {error.message}",
                    extra={"context": context.to_dict(), "error": error.to_dict()}
                )
                if reraise:
                    raise error from e
                return None

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            context = ServiceContext(service_name, operation)
            start_time = datetime.utcnow()
            
            try:
                result = await func(*args, **kwargs)
                
                if log_performance:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    logger.debug(
                        f"[{service_name}] {operation} completed in {duration:.3f}s"
                    )
                
                return result
                
            except PARWAError:
                raise
            except Exception as e:
                error = _wrap_service_error(e, service_name, operation)
                logger.error(
                    f"[{service_name}] {operation} failed: {error.message}",
                    extra={"context": context.to_dict(), "error": error.to_dict()}
                )
                if reraise:
                    raise error from e
                return None

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def _wrap_service_error(
    error: Exception,
    service_name: str,
    operation: str
) -> PARWAError:
    """Wrap generic exception in appropriate PARWA error"""
    
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    
    # Database errors
    if any(x in error_str for x in ["not found", "does not exist", "no result"]):
        return RecordNotFoundError(
            message=str(error),
            model=service_name
        )
    
    if any(x in error_str for x in ["duplicate", "already exists", "unique constraint"]):
        return DuplicateRecordError(message=str(error))
    
    if any(x in error_str for x in ["connection", "timeout", "database"]):
        return DatabaseError(
            message=str(error),
            operation=operation,
            retryable=True
        )
    
    # Configuration errors
    if any(x in error_str for x in ["config", "environment", "missing key", "not set"]):
        return ConfigurationError(
            message=str(error),
            config_key=f"{service_name}.{operation}"
        )
    
    # Generic database error for unknown DB issues
    if "sql" in error_str or "query" in error_str or error_type in ["integrityerror", "dataerror"]:
        return DatabaseError(
            message=str(error),
            operation=operation,
            retryable=True
        )
    
    # Default to generic PARWA error
    return PARWAError(
        message=str(error),
        error_code="SERVICE_ERROR",
        category=ErrorCategory.DATABASE,
        severity=ErrorSeverity.HIGH,
        details={
            "service": service_name,
            "operation": operation,
            "original_type": type(error).__name__
        }
    )


# ============================================================================
# Validation Decorators
# ============================================================================

def validate_input(validator: Callable[[Dict[str, Any]], bool]):
    """
    Decorator to validate input parameters.
    
    Args:
        validator: Function that validates input, returns True or raises ValidationError
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Combine args and kwargs for validation
            input_data = kwargs.copy()
            if args and len(args) > 1:
                # Assume first arg after self is the input
                if isinstance(args[1], dict):
                    input_data.update(args[1])
            
            validator(input_data)
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            input_data = kwargs.copy()
            if args and len(args) > 1:
                if isinstance(args[1], dict):
                    input_data.update(args[1])
            
            validator(input_data)
            return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def require_company_id(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to ensure company_id is provided.
    
    Raises AuthorizationError if company_id is missing.
    """
    from backend.core.error_handler import AuthorizationError
    
    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        company_id = kwargs.get("company_id")
        if not company_id and len(args) > 1:
            # Check if second arg might be company_id
            if isinstance(args[1], str) and args[1].startswith("comp_"):
                company_id = args[1]
        
        if not company_id:
            raise AuthorizationError(
                message="company_id is required for this operation"
            )
        return func(*args, **kwargs)

    @wraps(func)
    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        company_id = kwargs.get("company_id")
        if not company_id and len(args) > 1:
            if isinstance(args[1], str) and args[1].startswith("comp_"):
                company_id = args[1]
        
        if not company_id:
            raise AuthorizationError(
                message="company_id is required for this operation"
            )
        return await func(*args, **kwargs)

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# ============================================================================
# Transaction Decorators
# ============================================================================

def atomic_transaction(session_getter: Callable):
    """
    Decorator to wrap function in a database transaction.
    
    Args:
        session_getter: Function that returns a database session
    
    Usage:
        @atomic_transaction(get_db_session)
        def my_function(db, data):
            # Operations are atomic
            pass
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            session = session_getter()
            try:
                result = func(*args, session=session, **kwargs)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                logger.warning(f"Transaction rolled back: {str(e)}")
                raise
            finally:
                session.close()

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            session = session_getter()
            try:
                result = await func(*args, session=session, **kwargs)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                logger.warning(f"Transaction rolled back: {str(e)}")
                raise
            finally:
                session.close()

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============================================================================
# Audit Logging Decorator
# ============================================================================

def audit_log(action: str, resource_type: str):
    """
    Decorator to log audit trail for service operations.
    
    Args:
        action: Action being performed (create, update, delete, read)
        resource_type: Type of resource being operated on
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            user_id = kwargs.get("user_id", "system")
            company_id = kwargs.get("company_id", "unknown")
            
            logger.info(
                f"AUDIT: {action} {resource_type}",
                extra={
                    "action": action,
                    "resource_type": resource_type,
                    "user_id": user_id,
                    "company_id": company_id,
                    "function": func.__name__
                }
            )
            
            try:
                result = func(*args, **kwargs)
                logger.info(
                    f"AUDIT: {action} {resource_type} - SUCCESS",
                    extra={
                        "action": action,
                        "resource_type": resource_type,
                        "user_id": user_id,
                        "company_id": company_id
                    }
                )
                return result
            except Exception as e:
                logger.warning(
                    f"AUDIT: {action} {resource_type} - FAILED: {str(e)}",
                    extra={
                        "action": action,
                        "resource_type": resource_type,
                        "user_id": user_id,
                        "company_id": company_id,
                        "error": str(e)
                    }
                )
                raise

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            user_id = kwargs.get("user_id", "system")
            company_id = kwargs.get("company_id", "unknown")
            
            logger.info(
                f"AUDIT: {action} {resource_type}",
                extra={
                    "action": action,
                    "resource_type": resource_type,
                    "user_id": user_id,
                    "company_id": company_id,
                    "function": func.__name__
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.info(
                    f"AUDIT: {action} {resource_type} - SUCCESS",
                    extra={
                        "action": action,
                        "resource_type": resource_type,
                        "user_id": user_id,
                        "company_id": company_id
                    }
                )
                return result
            except Exception as e:
                logger.warning(
                    f"AUDIT: {action} {resource_type} - FAILED: {str(e)}",
                    extra={
                        "action": action,
                        "resource_type": resource_type,
                        "user_id": user_id,
                        "company_id": company_id,
                        "error": str(e)
                    }
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============================================================================
# Circuit Breaker
# ============================================================================

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Failures exceeded threshold, calls fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"
    
    def can_execute(self) -> bool:
        """Check if call can proceed"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit breaker [{self.name}] entering HALF_OPEN state")
                    return True
            return False
        
        # HALF_OPEN - allow one test call
        return True
    
    def record_success(self):
        """Record successful call"""
        if self.state == "HALF_OPEN":
            logger.info(f"Circuit breaker [{self.name}] recovered, closing circuit")
        self.failures = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """Record failed call"""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            logger.warning(f"Circuit breaker [{self.name}] test failed, reopening circuit")
        elif self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker [{self.name}] opened after {self.failures} failures"
            )


def circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to apply circuit breaker pattern.
    
    Args:
        breaker: CircuitBreaker instance
    """
    from backend.core.error_handler import ExternalAPIError
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not breaker.can_execute():
                raise ExternalAPIError(
                    message=f"Circuit breaker [{breaker.name}] is open",
                    provider=breaker.name,
                    retryable=True
                )
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not breaker.can_execute():
                raise ExternalAPIError(
                    message=f"Circuit breaker [{breaker.name}] is open",
                    provider=breaker.name,
                    retryable=True
                )
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
