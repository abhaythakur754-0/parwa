"""run_with_timeout — endpoint-level timeouts (30s /transcribe, 120s /browse).

Runs inference on a small side pool; the caller gets a 504 on timeout.
Model LOADING is never timed (only inference), so a cold first request
may take as long as the load needs.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable

log = logging.getLogger("skills.timeout")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="skills-timeout")


class TimeoutError(RuntimeError):
    pass


def run_with_timeout(fn: Callable[..., Any], *args: Any,
                     timeout_s: float = 0, **kwargs: Any) -> Any:
    if not timeout_s or timeout_s <= 0:
        return fn(*args, **kwargs)
    future = _executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_s)
    except FuturesTimeoutError as exc:
        log.warning("inference timed out after %.1fs", timeout_s)
        raise TimeoutError(f"timed out after {timeout_s:.0f}s") from exc
