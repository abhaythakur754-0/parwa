# Event Replay - Week 47 Builder 4
# Event replay capabilities for webhooks

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid


class ReplayStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReplayJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    status: ReplayStatus = ReplayStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_types: List[str] = field(default_factory=list)
    webhook_ids: List[str] = field(default_factory=list)
    total_events: int = 0
    processed_events: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class ReplayCheckpoint:
    job_id: str
    last_event_id: str
    last_event_time: datetime
    events_processed: int
    created_at: datetime = field(default_factory=datetime.utcnow)


class EventReplay:
    """Event replay system for re-processing historical events"""

    def __init__(self, event_store=None):
        self._event_store = event_store
        self._jobs: Dict[str, ReplayJob] = {}
        self._checkpoints: Dict[str, ReplayCheckpoint] = {}
        self._handlers: List[Callable] = []
        self._metrics = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "total_events_replayed": 0
        }

    def set_event_store(self, store) -> None:
        """Set the event store"""
        self._event_store = store

    def register_handler(self, handler: Callable) -> None:
        """Register a replay handler"""
        self._handlers.append(handler)

    def create_job(
        self,
        tenant_id: str,
        name: str,
        start_time: datetime,
        end_time: datetime,
        event_types: Optional[List[str]] = None,
        webhook_ids: Optional[List[str]] = None
    ) -> ReplayJob:
        """Create a new replay job"""
        job = ReplayJob(
            tenant_id=tenant_id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            event_types=event_types or [],
            webhook_ids=webhook_ids or []
        )
        self._jobs[job.id] = job
        self._metrics["total_jobs"] += 1
        return job

    async def start_replay(
        self,
        job_id: str,
        batch_size: int = 100
    ) -> ReplayJob:
        """Start executing a replay job"""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = ReplayStatus.RUNNING

        try:
            # Get events from store
            events = await self._fetch_events(job)

            for event in events:
                # Skip cancelled jobs
                if job.status == ReplayStatus.CANCELLED:
                    break

                job.processed_events += 1

                # Deliver to handlers
                success = await self._deliver_event(event, job)
                if success:
                    job.successful_deliveries += 1
                else:
                    job.failed_deliveries += 1

                # Create checkpoint every batch
                if job.processed_events % batch_size == 0:
                    self._create_checkpoint(job, event)

                self._metrics["total_events_replayed"] += 1

            if job.status == ReplayStatus.RUNNING:
                job.status = ReplayStatus.COMPLETED
                self._metrics["completed_jobs"] += 1

        except Exception as e:
            job.status = ReplayStatus.FAILED
            self._metrics["failed_jobs"] += 1

        job.completed_at = datetime.utcnow()
        return job

    async def _fetch_events(self, job: ReplayJob) -> List[Any]:
        """Fetch events for replay from the event store"""
        if not self._event_store:
            return []

        # This would typically query the event store
        # Placeholder for actual implementation
        events = await self._event_store.get_events_by_time_range(
            start_time=job.start_time,
            end_time=job.end_time,
            tenant_id=job.tenant_id,
            event_types=job.event_types
        )
        job.total_events = len(events)
        return events

    async def _deliver_event(self, event: Any, job: ReplayJob) -> bool:
        """Deliver an event to registered handlers"""
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, job)
                else:
                    handler(event, job)
            except Exception:
                return False
        return True

    def _create_checkpoint(self, job: ReplayJob, event: Any) -> None:
        """Create a checkpoint for the replay job"""
        checkpoint = ReplayCheckpoint(
            job_id=job.id,
            last_event_id=getattr(event, 'id', str(uuid.uuid4())),
            last_event_time=getattr(event, 'created_at', datetime.utcnow()),
            events_processed=job.processed_events
        )
        self._checkpoints[job.id] = checkpoint

    def get_checkpoint(self, job_id: str) -> Optional[ReplayCheckpoint]:
        """Get checkpoint for a job"""
        return self._checkpoints.get(job_id)

    async def resume_from_checkpoint(
        self,
        job_id: str,
        batch_size: int = 100
    ) -> ReplayJob:
        """Resume a job from its last checkpoint"""
        checkpoint = self._checkpoints.get(job_id)
        job = self._jobs.get(job_id)

        if not job or not checkpoint:
            raise ValueError("Job or checkpoint not found")

        # Update job with checkpoint state
        job.processed_events = checkpoint.events_processed
        job.status = ReplayStatus.RUNNING

        # Continue from checkpoint
        return await self.start_replay(job_id, batch_size)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running replay job"""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status not in [ReplayStatus.PENDING, ReplayStatus.RUNNING]:
            return False
        job.status = ReplayStatus.CANCELLED
        return True

    def get_job(self, job_id: str) -> Optional[ReplayJob]:
        """Get a replay job by ID"""
        return self._jobs.get(job_id)

    def get_jobs_by_tenant(self, tenant_id: str) -> List[ReplayJob]:
        """Get all jobs for a tenant"""
        return [j for j in self._jobs.values() if j.tenant_id == tenant_id]

    def get_running_jobs(self) -> List[ReplayJob]:
        """Get all running jobs"""
        return [j for j in self._jobs.values() if j.status == ReplayStatus.RUNNING]

    def get_job_progress(self, job_id: str) -> Dict[str, Any]:
        """Get progress for a job"""
        job = self._jobs.get(job_id)
        if not job:
            return {}

        progress = 0
        if job.total_events > 0:
            progress = (job.processed_events / job.total_events) * 100

        return {
            "job_id": job.id,
            "status": job.status.value,
            "progress_percent": round(progress, 2),
            "total_events": job.total_events,
            "processed_events": job.processed_events,
            "successful_deliveries": job.successful_deliveries,
            "failed_deliveries": job.failed_deliveries
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get replay system metrics"""
        return {
            **self._metrics,
            "active_jobs": len([j for j in self._jobs.values() 
                              if j.status == ReplayStatus.RUNNING])
        }

    def clear_completed_jobs(self, older_than: Optional[datetime] = None) -> int:
        """Clear completed jobs"""
        to_remove = []
        for job_id, job in self._jobs.items():
            if job.status in [ReplayStatus.COMPLETED, ReplayStatus.FAILED, ReplayStatus.CANCELLED]:
                if older_than is None or job.created_at < older_than:
                    to_remove.append(job_id)

        for job_id in to_remove:
            del self._jobs[job_id]
            if job_id in self._checkpoints:
                del self._checkpoints[job_id]

        return len(to_remove)
