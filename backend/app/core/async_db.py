"""
Async DB Helper (S-08 fix)

Provides utilities to run synchronous SQLAlchemy operations in a thread pool,
preventing event loop blocking in async FastAPI endpoints.

Problem: `with SessionLocal() as db:` inside `async def` blocks the event loop
on every DB query because SQLAlchemy's synchronous sessions perform I/O
that halts the asyncio event loop.

Solution: `run_sync_db()` runs the entire DB operation (including session
lifecycle) in a separate thread via `asyncio.to_thread()`, keeping the
event loop free to serve other requests.

Usage:
    async def my_async_method(self, company_id: str):
        def _db_work():
            with SessionLocal() as db:
                result = db.query(Company).filter(...).first()
                return result

        return await run_sync_db(_db_work)
"""

import asyncio
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger("parwa.core.async_db")

T = TypeVar("T")


async def run_sync_db(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a synchronous DB function in a thread pool.

    Moves the entire DB operation (including SessionLocal() creation,
    queries, commits, and session close) off the event loop thread.
    This prevents the FastAPI async event loop from being blocked
    during synchronous SQLAlchemy I/O operations.

    Args:
        func: A synchronous callable that performs DB operations.
        *args: Positional arguments forwarded to ``func``.
        **kwargs: Keyword arguments forwarded to ``func``.

    Returns:
        Whatever ``func`` returns.

    Raises:
        Any exception raised by ``func`` is re-raised in the calling
        async context.
    """
    return await asyncio.to_thread(func, *args, **kwargs)
