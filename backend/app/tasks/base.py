"""
PARWA Task Base Classes (BC-004)

Base task classes that enforce:
- company_id as first parameter (BC-001)
- Automatic audit logging
- Structured error handling
- Retry with exponential backoff
- Dead letter queue for failed tasks
"""

import functools
import logging
from typing import Callable

from celery import Task

from backend.app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks")


class ParwaTask(Task):
    """Base task class with structured lifecycle logging (BC-012).

    All PARWA tasks should inherit from ParwaTask to get:
    - Retry logging with structured context
    - Failure logging without stack traces (BC-012)
    - Success logging with timing info
    """

    abstract = True

    def _safe_request_attr(self, attr: str, default=None):
        """Safely get request attribute outside task context."""
        try:
            return getattr(self.request, attr, default)
        except (AttributeError, RuntimeError):
            return default

    def on_retry(self, exc, traceback, eta):
        """Log retry event with structured context (BC-012)."""
        logger.warning(
            "task_retry",
            extra={
                "task_name": self.name,
                "task_id": self._safe_request_attr("id"),
                "retry_count": self._safe_request_attr("retries", 0),
                "max_retries": self.max_retries,
                "eta": str(eta) if eta else None,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

    def on_failure(self, exc, traceback, args, kwargs, einfo):
        """Log failure without stack traces (BC-012)."""
        logger.error(
            "task_failure",
            extra={
                "task_name": self.name,
                "task_id": self._safe_request_attr("id"),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "company_id": args[0] if args else None,
            },
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Log successful completion with structured context."""
        logger.info(
            "task_success",
            extra={
                "task_name": self.name,
                "task_id": task_id,
                "company_id": args[0] if args else None,
            },
        )


class ParwaBaseTask(ParwaTask):
    """Concrete base task with retry defaults (BC-004).

    All PARWA tasks should inherit from this class to get:
    - Automatic retry on any exception
    - Exponential backoff (2s, 4s, 8s...)
    - Max 3 retries
    - Default queue: "default"

    BC-001: Every task's first parameter must be company_id.
    """

    abstract = True
    _app = app

    # Retry configuration (BC-004)
    autoretry_for = (Exception,)
    retry_backoff = True
    max_retries = 3
    retry_backoff_max = 300  # 5 minutes
    retry_jitter = True
    queue = "default"


def with_company_id(func: Callable) -> Callable:
    """Decorator that validates company_id as first parameter (BC-001).

    Ensures:
    - First positional argument is a non-empty string
    - Provides clear error message on validation failure

    Raises:
        ValueError: If company_id is missing or empty.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check positional args
        if not args:
            raise ValueError(
                "company_id is required as the first parameter (BC-001)"
            )
        company_id = args[0]
        if not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "company_id must be a non-empty string (BC-001)"
            )
        return func(*args, **kwargs)

    return wrapper
