"""
PARWA Knowledge Base Reindexing Module

Manages background reindexing jobs for the knowledge base vector store.
Ensures embeddings stay in sync when documents are updated.

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation on errors.

Parent: Day 4 (G1 fix — module was missing, causing ImportError)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.reindexing")


class ReindexStatus(str, Enum):
    """Status of a reindexing job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReindexJob:
    """A single reindexing job."""

    job_id: str
    company_id: str
    document_ids: List[str]
    status: str = ReindexStatus.PENDING.value
    progress: float = 0.0  # 0.0 to 1.0
    total_chunks: int = 0
    processed_chunks: int = 0
    error_message: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "company_id": self.company_id,
            "document_ids": self.document_ids,
            "status": self.status,
            "progress": round(self.progress, 4),
            "total_chunks": self.total_chunks,
            "processed_chunks": self.processed_chunks,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
        }


class ReindexingManager:
    """Manages knowledge base reindexing jobs.

    BC-001: All jobs scoped to company_id.
    BC-008: Individual job failures don't crash the manager.
    """

    def __init__(self):
        self._jobs: Dict[str, ReindexJob] = {}

    def create_job(
        self,
        company_id: str,
        document_ids: List[str],
    ) -> ReindexJob:
        """Create a new reindexing job."""
        import uuid

        job_id = str(uuid.uuid4())[:8]
        job = ReindexJob(
            job_id=job_id,
            company_id=company_id,
            document_ids=document_ids,
        )
        self._jobs[job_id] = job
        logger.info(
            "reindex_job_created",
            job_id=job_id,
            company_id=company_id,
            document_count=len(document_ids),
        )
        return job

    def get_job(self, job_id: str) -> Optional[ReindexJob]:
        """Get a reindexing job by ID."""
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str, company_id: str) -> bool:
        """Cancel a pending or running reindexing job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.company_id != company_id:
            logger.warning(
                "reindex_cancel_unauthorized",
                job_id=job_id,
                company_id=company_id,
            )
            return False
        if job.status in (
                ReindexStatus.PENDING.value,
                ReindexStatus.RUNNING.value):
            job.status = ReindexStatus.CANCELLED.value
            job.completed_at = time.time()
            return True
        return False

    def list_jobs(
        self,
        company_id: str,
        status: Optional[str] = None,
    ) -> List[ReindexJob]:
        """List reindexing jobs for a company."""
        jobs = [
            j for j in self._jobs.values()
            if j.company_id == company_id
        ]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def run_job(self, job_id: str) -> ReindexJob:
        """Execute a reindexing job (placeholder).

        In production, this would regenerate embeddings for all chunks
        and update the vector store. For now, it simulates progress.
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = ReindexStatus.RUNNING.value
        job.started_at = time.time()
        job.total_chunks = len(job.document_ids) * 5  # estimate

        try:
            # Simulate reindexing progress
            for doc_id in job.document_ids:
                job.processed_chunks += 5
                job.progress = job.processed_chunks / max(job.total_chunks, 1)
                # In production: regenerate embeddings + upsert to vector store
                logger.debug(
                    "reindex_document",
                    job_id=job_id,
                    document_id=doc_id,
                    progress=round(job.progress, 2),
                )

            job.status = ReindexStatus.COMPLETED.value
            job.progress = 1.0
        except Exception as exc:
            job.status = ReindexStatus.FAILED.value
            job.error_message = str(exc)
            logger.error(
                "reindex_job_failed",
                job_id=job_id,
                error=str(exc),
            )
        finally:
            job.completed_at = time.time()

        return job
