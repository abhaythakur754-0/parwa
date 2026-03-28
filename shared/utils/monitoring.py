import time
from typing import Optional, Callable, Any, Dict
from functools import wraps
import logging

# Make sentry_sdk optional
try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    sentry_sdk = None
    SENTRY_AVAILABLE = False

from prometheus_client import Counter, Histogram

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger("monitoring")

# Prometheus Metrics
APP_REQUEST_COUNT = Counter(
    "app_request_total", 
    "Total number of application operations", 
    ["operation_type", "operation_name"]
)

APP_OPERATION_LATENCY = Histogram(
    "app_operation_latency_seconds", 
    "Application operation latency in seconds", 
    ["operation_type", "operation_name"]
)

def init_monitoring() -> None:
    """
    Initializes performance monitoring and error tracking systems (Sentry).
    Should be called during application startup.
    """
    settings = get_settings()
    
    if not SENTRY_AVAILABLE:
        logger.warning("sentry_sdk not installed. Skipping Sentry initialization.")
        return
    
    if settings.sentry_dsn:
        try:
            sentry_sdk.init(
                dsn=str(settings.sentry_dsn),
                environment=settings.environment,
                traces_sample_rate=1.0 if settings.environment == "development" else 0.1,
            )
            logger.info("Sentry monitoring initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize Sentry", extra={"context": {"error": str(e)}})
    else:
        logger.warning("Sentry DSN not configured. Skipping Sentry initialization.")

def capture_exception(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Captures an exception and sends it to Sentry and the local logger.
    """
    logger.error("Exception captured", exc_info=error, extra={"context": context or {}})
    
    if not SENTRY_AVAILABLE:
        return
    
    if get_settings().sentry_dsn:
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_exception(error)

def track_performance(operation_type: str = "function", operation_name: str = "unknown"):
    """
    Decorator to track the execution time of a function/endpoint 
    using Prometheus metrics and the local logger.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            APP_REQUEST_COUNT.labels(operation_type=operation_type, operation_name=operation_name).inc()
            start_time = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                APP_OPERATION_LATENCY.labels(operation_type=operation_type, operation_name=operation_name).observe(duration)
                logger.info(f"Performance tracked: {operation_name}", extra={
                    "context": {
                        "operation_type": operation_type, 
                        "operation_name": operation_name, 
                        "duration_s": duration
                    }
                })
        return wrapper
    return decorator
