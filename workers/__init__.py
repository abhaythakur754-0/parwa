"""
PARWA Workers Module.

Background workers for processing tasks using ARQ.

Workers:
- RecallHandlerWorker: Handle action recalls
- ProactiveOutreachWorker: Send proactive outreach
- ReportGeneratorWorker: Generate reports
- KBIndexerWorker: Index knowledge base documents

CRITICAL: All 8 workers must register with ARQ without errors.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class WorkerRegistry:
    """
    Registry for tracking all workers.

    CRITICAL: All 8 workers must register here.
    """

    _workers: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, worker_class: Any) -> None:
        """Register a worker."""
        cls._workers[name] = worker_class

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all registered workers."""
        return cls._workers.copy()

    @classmethod
    def count(cls) -> int:
        """Count registered workers."""
        return len(cls._workers)


def get_worker_functions() -> List[str]:
    """
    Get all worker functions for ARQ registration.

    Returns:
        List of worker function names
    """
    return [
        "recall_action",
        "send_outreach",
        "generate_report",
        "index_document",
    ]


__all__ = [
    "WorkerRegistry",
    "get_worker_functions",
]
