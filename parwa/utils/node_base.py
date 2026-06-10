"""Base utilities for PARWA LangGraph nodes.

Provides error handling, logging, state validation, and the
safe_node decorator that wraps every node with production-grade resilience.

Every node in PARWA should use @safe_node to get:
- try/except with graceful fallback (never crash the pipeline)
- Structured logging with node name, ticket_id, and timing
- State validation before and after each node
- Error tracking in state for debugging
- Full async support — async nodes get async safe_node automatically
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
import traceback
from typing import Any, Callable, TypeVar

from parwa.state import TicketState

logger = logging.getLogger("parwa.node")

F = TypeVar("F", bound=Callable[[dict[str, Any]], dict[str, Any]])


def _validate_state_dict(state: dict[str, Any]) -> list[str]:
    """Validate a state dict against the TicketState schema.

    Returns a list of validation issues (empty = valid).
    """
    issues: list[str] = []

    # Check required input fields
    raw_message = state.get("raw_message", "")
    if not isinstance(raw_message, str):
        issues.append(f"raw_message must be str, got {type(raw_message).__name__}")

    # Check variant is valid
    variant = state.get("variant", "parwa")
    if variant not in ("mini", "parwa", "high"):
        issues.append(f"variant must be mini/parwa/high, got '{variant}'")

    # Check channel is valid
    channel = state.get("channel", "email")
    if channel not in ("email", "chat", "social", "voice"):
        issues.append(f"channel must be email/chat/social/voice, got '{channel}'")

    # Check numeric fields are numbers
    for field in ("intent_confidence", "sentiment_urgency", "quality_score", "loop_count"):
        val = state.get(field)
        if val is not None and not isinstance(val, (int, float)):
            issues.append(f"{field} must be numeric, got {type(val).__name__}")

    # Check boolean fields
    for field in ("should_escalate", "should_loop_back", "pii_detected", "verification_passed"):
        val = state.get(field)
        if val is not None and not isinstance(val, bool):
            issues.append(f"{field} must be bool, got {type(val).__name__}")

    # Check list fields
    for field in ("active_frameworks", "reasoning_chain", "strategy_plan",
                  "action_plans", "execution_results", "audit_log",
                  "proactive_insights", "predictions", "kb_results",
                  "context_history", "quality_issues", "reasoning_paths"):
        val = state.get(field)
        if val is not None and not isinstance(val, list):
            issues.append(f"{field} must be list, got {type(val).__name__}")

    return issues


def _build_error_result(
    node_name: str,
    exc: Exception,
    fallback: dict[str, Any] | None,
    state: dict[str, Any],
    elapsed: float,
) -> dict[str, Any]:
    """Build a safe error result dict when a node fails.

    This is shared between sync and async wrappers so both
    produce identical error tracking behavior.

    Protected by its own try/except to ensure it never raises,
    even if state is corrupted or fallback is invalid.
    """
    try:
        tb = traceback.format_exc()

        # Safely extract ticket_id from state
        try:
            ticket_id = state.get("ticket_id", "UNKNOWN") if isinstance(state, dict) else "UNKNOWN"
        except Exception:
            ticket_id = "UNKNOWN"

        logger.error(
            "node=%s ticket=%s status=FAILED elapsed=%.3fs "
            "error_type=%s error=%s\n%s",
            node_name, ticket_id, elapsed,
            type(exc).__name__, str(exc), tb,
        )

        # Build error-safe result — use deep copy of fallback to avoid mutation
        try:
            import copy
            error_result = copy.deepcopy(fallback) if fallback else {}
        except Exception:
            error_result = {}

        error_result["node_error"] = {
            "node": node_name,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": tb,
            "elapsed_seconds": elapsed,
        }

        # Track errors in state for debugging
        # The graph's merge reducer now concatenates lists, so we only
        # return the NEW error — the reducer handles accumulation.
        error_result["pipeline_errors"] = [
            {
                "node": node_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
        ]

        return error_result

    except Exception as inner_exc:
        # Last resort — if _build_error_result itself fails, return a minimal safe dict
        logger.critical(
            "node=%s _build_error_result FAILED: %s — returning minimal error result",
            node_name, inner_exc,
        )
        return {
            "node_error": {
                "node": node_name,
                "error_type": "ErrorBuilderFailed",
                "error_message": f"Original: {exc}; Builder: {inner_exc}",
                "traceback": "",
                "elapsed_seconds": elapsed,
            },
            "pipeline_errors": [
                {
                    "node": node_name,
                    "error": f"Original: {exc}; Builder: {inner_exc}",
                    "error_type": "ErrorBuilderFailed",
                }
            ],
        }


def safe_node(
    node_name: str,
    *,
    fallback: dict[str, Any] | None = None,
    validate_input: bool = True,
    validate_output: bool = True,
    log_level: int = logging.DEBUG,
) -> Callable[[F], F]:
    """Decorator that wraps a PARWA node with production-grade error handling.

    Guarantees:
    1. Node NEVER raises an exception — returns partial state on failure
    2. Errors are logged with full context (node, ticket_id, traceback)
    3. Errors are tracked in state['_errors'] for debugging
    4. Node execution time is logged
    5. State is validated before and after the node runs
    6. Supports BOTH sync and async node functions automatically

    Args:
        node_name: Human-readable node name (e.g. "INTENT_CLASSIFIER").
        fallback: Default return dict if node fails completely.
        validate_input: Whether to validate state before the node runs.
        validate_output: Whether to validate state after the node runs.
        log_level: Logging level for normal execution.

    Example:
        @safe_node("INTENT_CLASSIFIER")
        async def intent_classifier(state: dict[str, Any]) -> dict[str, Any]:
            ...
    """
    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):
            # ─── Async wrapper ─────────────────────────────────────────
            @functools.wraps(func)
            async def async_wrapper(state: dict[str, Any]) -> dict[str, Any]:
                ticket_id = state.get("ticket_id", "UNKNOWN")
                start_time = time.monotonic()

                # Pre-validation
                if validate_input:
                    issues = _validate_state_dict(state)
                    if issues:
                        logger.warning(
                            "node=%s ticket=%s input_validation_issues=%s",
                            node_name, ticket_id, issues,
                        )

                # Execute node with error handling
                try:
                    logger.log(
                        log_level,
                        "node=%s ticket=%s status=started (async)",
                        node_name, ticket_id,
                    )

                    result = await func(state)

                    # Ensure result is a dict
                    if not isinstance(result, dict):
                        logger.error(
                            "node=%s ticket=%s error=non_dict_return type=%s",
                            node_name, ticket_id, type(result).__name__,
                        )
                        result = fallback or {}

                    # Post-validation
                    if validate_output:
                        output_issues = _validate_state_dict({**state, **result})
                        if output_issues:
                            logger.warning(
                                "node=%s ticket=%s output_validation_issues=%s",
                                node_name, ticket_id, output_issues,
                            )

                    elapsed = time.monotonic() - start_time
                    logger.log(
                        log_level,
                        "node=%s ticket=%s status=completed elapsed=%.3fs keys=%s (async)",
                        node_name, ticket_id, elapsed, list(result.keys()),
                    )

                    return result

                except Exception as exc:
                    elapsed = time.monotonic() - start_time
                    return _build_error_result(
                        node_name, exc, fallback, state, elapsed,
                    )

            return async_wrapper  # type: ignore[return-value]

        else:
            # ─── Sync wrapper ─────────────────────────────────────────
            @functools.wraps(func)
            def wrapper(state: dict[str, Any]) -> dict[str, Any]:
                ticket_id = state.get("ticket_id", "UNKNOWN")
                start_time = time.monotonic()

                # Pre-validation
                if validate_input:
                    issues = _validate_state_dict(state)
                    if issues:
                        logger.warning(
                            "node=%s ticket=%s input_validation_issues=%s",
                            node_name, ticket_id, issues,
                        )

                # Execute node with error handling
                try:
                    logger.log(
                        log_level,
                        "node=%s ticket=%s status=started",
                        node_name, ticket_id,
                    )

                    result = func(state)

                    # Ensure result is a dict
                    if not isinstance(result, dict):
                        logger.error(
                            "node=%s ticket=%s error=non_dict_return type=%s",
                            node_name, ticket_id, type(result).__name__,
                        )
                        result = fallback or {}

                    # Post-validation
                    if validate_output:
                        output_issues = _validate_state_dict({**state, **result})
                        if output_issues:
                            logger.warning(
                                "node=%s ticket=%s output_validation_issues=%s",
                                node_name, ticket_id, output_issues,
                            )

                    elapsed = time.monotonic() - start_time
                    logger.log(
                        log_level,
                        "node=%s ticket=%s status=completed elapsed=%.3fs keys=%s",
                        node_name, ticket_id, elapsed, list(result.keys()),
                    )

                    return result

                except Exception as exc:
                    elapsed = time.monotonic() - start_time
                    return _build_error_result(
                        node_name, exc, fallback, state, elapsed,
                    )

            return wrapper  # type: ignore[return-value]

    return decorator


def get_node_logger(node_name: str) -> logging.Logger:
    """Get a logger specific to a node.

    Args:
        node_name: The node name for log context.

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(f"parwa.node.{node_name}")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure PARWA logging with a standard format.

    Args:
        level: Logging level (default INFO).
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
