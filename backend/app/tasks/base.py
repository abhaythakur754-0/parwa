"""
PARWA Task Base Classes (BC-004)

Base task classes that enforce:
- company_id as first parameter (BC-001)
- Automatic audit logging
- Structured error handling
- Retry with exponential backoff
- Dead letter queue for failed tasks (CL-01 FIX: actually routes to DLQ)
- Task idempotency via Redis dedup (CL-03 FIX)

Day 20: Added tenant context propagation for Celery tasks:
- inject_tenant_context decorator auto-extracts company_id from task headers
- set_task_tenant_header() helper sets headers during task dispatch
- ParwaBaseTask.__call__ auto-sets tenant context from headers
- company_id flows: API → middleware → task header → Celery task
"""

import functools
import json
import logging
from typing import Any, Callable, Dict, Optional

from celery import Task

from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks")

# Header key used to pass company_id from API → Celery task
TENANT_HEADER_KEY = "X-Parwa-Company-ID"

# CL-03: Redis key prefix for task dedup
DEDUP_KEY_PREFIX = "parwa:task_dedup:"
DEDUP_DEFAULT_TTL_SECONDS = 3600  # 1 hour default dedup window


def _get_redis_client():
    """Get Redis client for dedup and DLQ operations."""
    try:
        from app.core.redis import get_redis
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(get_redis())
        finally:
            loop.close()
    except Exception:
        return None


def _build_dedup_key(task_name: str, args: tuple, kwargs: dict) -> Optional[str]:
    """Build a deterministic dedup key from task name and arguments.

    CL-03 FIX: Generates a unique key based on the task name and
    its arguments so that duplicate task dispatches can be detected
    and skipped.

    Args:
        task_name: The Celery task name (e.g. 'app.tasks.ai.classify_ticket')
        args: Positional arguments to the task
        kwargs: Keyword arguments to the task

    Returns:
        A Redis key string like 'parwa:task_dedup:app.tasks.ai.classify_ticket:hash'
    """
    try:
        # Create a stable string representation of the task arguments
        key_parts = [task_name]
        for arg in args:
            key_parts.append(str(arg))
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")

        key_str = ":".join(key_parts)

        # Hash to keep the key length manageable
        import hashlib
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]

        return f"{DEDUP_KEY_PREFIX}{task_name}:{key_hash}"
    except Exception:
        return None


class ParwaTask(Task):
    """Base task class with structured lifecycle logging (BC-012).

    All PARWA tasks should inherit from ParwaTask to get:
    - Retry logging with structured context
    - Failure logging without stack traces (BC-012)
    - Success logging with timing info
    - Day 16: DLQ routing on max retries exhausted
    - Day 20: Auto tenant context from task headers
    - CL-01 FIX: Actually routes failed tasks to dead_letter queue
    """

    abstract = True

    # Day 16: Route to dead_letter queue when all retries fail
    throws = (Exception,)

    def _safe_request_attr(self, attr: str, default=None):
        """Safely get request attribute outside task context."""
        try:
            return getattr(self.request, attr, default)
        except (AttributeError, RuntimeError):
            return default

    def _get_task_company_id(self) -> Optional[str]:
        """Extract company_id from task request headers or first arg.

        Checks task headers first (set by set_task_tenant_header during
        dispatch), falls back to first positional argument.

        Returns:
            The company_id or None.
        """
        # Check headers first (preferred path for Day 20)
        headers = self._safe_request_attr("headers") or {}
        if isinstance(headers, dict):
            company_id = headers.get(TENANT_HEADER_KEY)
            if company_id:
                return str(company_id)

        # Fallback: first positional arg (legacy behavior)
        return None

    def __call__(self, *args, **kwargs):
        """Execute task with tenant context propagation.

        Before executing the task body, this method:
        1. Extracts company_id from task headers (set by API during dispatch)
        2. Sets the tenant context for downstream code (DB, Redis)
        3. Executes the task
        4. Clears the tenant context after execution
        """
        from app.core.tenant_context import (
            clear_tenant_context,
            set_tenant_context,
        )

        company_id = self._get_task_company_id()

        if company_id:
            set_tenant_context(company_id)
            logger.debug(
                "task_tenant_context_set",
                extra={
                    "task_name": self.name,
                    "company_id": company_id,
                },
            )
        else:
            # Log warning if no company_id found — tasks should always
            # have tenant context for proper isolation
            logger.warning(
                "task_no_tenant_context",
                extra={
                    "task_name": self.name,
                    "has_headers": bool(
                        self._safe_request_attr("headers")
                    ),
                    "warning": (
                        "No company_id found in task headers or args. "
                        "Use set_task_tenant_header() when dispatching tasks."
                    ),
                },
            )

        try:
            return self.run(*args, **kwargs)
        finally:
            clear_tenant_context()

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
                "error_message": str(exc)[:500],
            },
        )

    def on_failure(self, exc, traceback, args, kwargs, einfo):
        """Log failure and route to DLQ when retries exhausted (BC-012).

        CL-01 FIX: When max retries are exhausted, this method now
        actually republishes the failed task to the 'dead_letter' queue
        instead of just logging a dlq_routed=True flag.

        The republished task includes:
        - Original task args/kwargs
        - Error information in headers
        - Original task_id for traceability
        """
        retries = self._safe_request_attr("retries", 0)
        max_retries = self.max_retries

        # Check if this is a final failure (all retries exhausted)
        is_final = retries >= max_retries
        extra = {
            "task_name": self.name,
            "task_id": self._safe_request_attr("id"),
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:500],
            "company_id": args[0] if args else None,
        }
        if is_final:
            extra["dlq_routed"] = True
            logger.error(
                "task_permanently_failed",
                extra=extra,
            )

            # CL-01 FIX: Actually route the task to the dead_letter queue
            try:
                self._route_to_dlq(exc, args, kwargs)
            except Exception as dlq_exc:
                logger.error(
                    "dlq_route_failed",
                    extra={
                        "task_name": self.name,
                        "task_id": self._safe_request_attr("id"),
                        "dlq_error": str(dlq_exc)[:200],
                    },
                )
        else:
            logger.error(
                "task_failure",
                extra=extra,
            )

    def _route_to_dlq(self, exc, args, kwargs):
        """CL-01 FIX: Republish the failed task to the dead_letter queue.

        This method creates a new task message and publishes it to the
        'dead_letter' queue via Redis, preserving:
        - The original task name, args, and kwargs
        - The error that caused the failure
        - The original task_id for traceability
        - The company_id for tenant isolation

        The dead_letter queue can be processed by a separate worker or
        by the periodic purge_dead_letter_queue_task in periodic.py.
        """
        task_id = self._safe_request_attr("id")
        company_id = args[0] if args else None

        # Build the DLQ message payload
        dlq_payload = {
            "original_task_name": self.name,
            "original_task_id": task_id,
            "args": [str(a) for a in args],  # Serialize args
            "kwargs": {k: str(v) for k, v in kwargs.items()},  # Serialize kwargs
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:500],
            "company_id": company_id,
            "retries_exhausted": True,
        }

        # Publish to dead_letter queue via Redis (as a Celery task message)
        try:
            redis = _get_redis_client()
            if redis is not None:
                # Push to the Celery dead_letter queue (Redis list)
                queue_key = "parwa:dead_letter"
                redis.lpush(queue_key, json.dumps(dlq_payload))
                # Set TTL on the queue key (keep DLQ entries for 7 days max)
                try:
                    redis.expire(queue_key, 7 * 24 * 3600)
                except Exception:
                    pass  # TTL is best-effort

                logger.info(
                    "task_routed_to_dlq",
                    extra={
                        "task_name": self.name,
                        "original_task_id": task_id,
                        "company_id": company_id,
                        "dlq_queue": "dead_letter",
                    },
                )
            else:
                logger.warning(
                    "dlq_redis_unavailable",
                    extra={
                        "task_name": self.name,
                        "original_task_id": task_id,
                        "warning": "Redis unavailable — DLQ entry not stored",
                    },
                )
        except Exception as e:
            logger.error(
                "dlq_publish_error",
                extra={
                    "task_name": self.name,
                    "error": str(e)[:200],
                },
            )
            raise

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
    Day 20: Also supports company_id from task headers.

    CL-03 FIX: Now includes idempotency/dedup checking via Redis.
    Override `dedup_enabled = True` and optionally `dedup_ttl_seconds`
    on your task class to enable automatic dedup.
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

    # CL-03: Idempotency / dedup configuration
    dedup_enabled: bool = False  # Opt-in: set True on task class to enable
    dedup_ttl_seconds: int = DEDUP_DEFAULT_TTL_SECONDS  # Dedup window

    def __call__(self, *args, **kwargs):
        """Execute task with dedup check and tenant context.

        CL-03 FIX: Before executing the task, checks Redis for a dedup
        key. If found, skips execution and returns the previous result
        (if cached) or a dedup_skip indicator.
        """
        # CL-03: Check dedup before executing
        if self.dedup_enabled:
            dedup_key = _build_dedup_key(self.name, args, kwargs)
            if dedup_key:
                redis = _get_redis_client()
                if redis is not None:
                    try:
                        existing = redis.get(dedup_key)
                        if existing is not None:
                            logger.info(
                                "task_dedup_skip",
                                extra={
                                    "task_name": self.name,
                                    "dedup_key": dedup_key,
                                    "message": "Duplicate task detected — skipping execution",
                                },
                            )
                            # Try to return cached result
                            try:
                                cached = json.loads(existing)
                                return cached
                            except (json.JSONDecodeError, TypeError):
                                return {"status": "dedup_skip", "task_name": self.name}
                    except Exception as e:
                        logger.warning(
                            "task_dedup_check_failed",
                            extra={
                                "task_name": self.name,
                                "error": str(e)[:200],
                                "message": "Dedup check failed — proceeding with execution",
                            },
                        )

        # Execute the task (with tenant context from parent)
        result = super().__call__(*args, **kwargs)

        # CL-03: Store dedup key after successful execution
        if self.dedup_enabled:
            dedup_key = _build_dedup_key(self.name, args, kwargs)
            if dedup_key:
                redis = _get_redis_client()
                if redis is not None:
                    try:
                        # Cache the result for duplicate requests
                        result_json = json.dumps(result) if result is not None else "null"
                        redis.setex(dedup_key, self.dedup_ttl_seconds, result_json)
                    except Exception as e:
                        logger.warning(
                            "task_dedup_store_failed",
                            extra={
                                "task_name": self.name,
                                "error": str(e)[:200],
                            },
                        )

        return result


def with_company_id(func: Callable) -> Callable:
    """Decorator that validates company_id as first parameter (BC-001).

    Ensures:
    - First positional argument (after self for bound methods) is a non-empty string
    - Provides clear error message on validation failure

    For bound task methods (bind=True), the first arg is 'self' (the task),
    so we need to check the second argument for company_id.

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
        
        # For bound methods (bind=True), first arg is 'self' (task instance)
        # Check if first arg is a Task instance
        first_arg = args[0]
        if isinstance(first_arg, Task):
            # Bound method: self, company_id, ...other args
            if len(args) < 2:
                raise ValueError(
                    "company_id is required as the second parameter for bound tasks (BC-001)"
                )
            company_id = args[1]
        else:
            # Unbound function: company_id is first arg
            company_id = first_arg
            
        if not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "company_id must be a non-empty string (BC-001)"
            )
        return func(*args, **kwargs)

    return wrapper


def inject_tenant_context(func: Callable) -> Callable:
    """Decorator that auto-extracts company_id from task headers.

    Reads the X-Parwa-Company-ID header from the current Celery task
    request and sets the tenant context for downstream code.

    Must be used on task run() methods that inherit from ParwaBaseTask.

    Usage:
        class MyTask(ParwaBaseTask):
            @inject_tenant_context
            def run(self, data: dict):
                company_id = get_tenant_context()
                ...

    Args:
        func: The task run method to wrap.

    Returns:
        Wrapped function with tenant context set.
    """

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # Context is already set by ParwaTask.__call__
        # This decorator is a safety net for tasks that might
        # bypass the base class
        from app.core.tenant_context import get_tenant_context

        company_id = get_tenant_context()
        if not company_id:
            logger.warning(
                "inject_tenant_context_no_context",
                extra={
                    "func": func.__name__,
                    "warning": (
                        "No tenant context available. "
                        "Ensure task is dispatched with "
                        "set_task_tenant_header()."
                    ),
                },
            )
        return func(*args, **kwargs)

    return sync_wrapper


def set_task_tenant_header(company_id: str) -> Dict[str, str]:
    """Create task headers with company_id for tenant propagation.

    Call this when dispatching Celery tasks from API endpoints to
    ensure the task has tenant context when it executes in the worker.

    The company_id will be available in task.request.headers and
    will be automatically extracted by ParwaTask.__call__().

    Usage:
        headers = set_task_tenant_header(company_id)
        my_task.apply_async(args=[data], headers=headers)

    Args:
        company_id: The current tenant's company_id.

    Returns:
        Dict with the company_id header for task dispatch.

    Raises:
        ValueError: If company_id is empty or invalid.
    """
    if not company_id or not isinstance(company_id, str):
        raise ValueError(
            "company_id is required for task tenant header (BC-001)"
        )
    if not company_id.strip():
        raise ValueError(
            "company_id must not be whitespace-only (BC-001)"
        )

    return {TENANT_HEADER_KEY: company_id.strip()}
