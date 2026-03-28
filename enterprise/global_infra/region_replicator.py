# Region Replicator - Week 51 Builder 4
# Cross-region replication

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class ReplicationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReplicationMode(Enum):
    SYNC = "sync"
    ASYNC = "async"
    EVENTUAL = "eventual"


@dataclass
class ReplicationJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_region: str = ""
    target_regions: List[str] = field(default_factory=list)
    data_type: str = ""
    data_id: str = ""
    mode: ReplicationMode = ReplicationMode.ASYNC
    status: ReplicationStatus = ReplicationStatus.PENDING
    progress: int = 0
    bytes_replicated: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReplicationLag:
    source_region: str = ""
    target_region: str = ""
    lag_ms: int = 0
    last_replicated_at: Optional[datetime] = None
    items_pending: int = 0


class RegionReplicator:
    """Manages cross-region data replication"""

    def __init__(self):
        self._jobs: Dict[str, ReplicationJob] = {}
        self._lags: Dict[str, ReplicationLag] = {}
        self._config: Dict[str, ReplicationMode] = {}
        self._metrics = {
            "total_jobs": 0,
            "completed": 0,
            "failed": 0,
            "bytes_replicated": 0,
            "avg_lag_ms": 0
        }

    def configure_replication(
        self,
        source_region: str,
        target_region: str,
        mode: ReplicationMode = ReplicationMode.ASYNC
    ) -> None:
        """Configure replication between regions"""
        key = f"{source_region}->{target_region}"
        self._config[key] = mode
        self._lags[key] = ReplicationLag(
            source_region=source_region,
            target_region=target_region
        )

    def create_job(
        self,
        source_region: str,
        target_regions: List[str],
        data_type: str,
        data_id: str,
        mode: ReplicationMode = ReplicationMode.ASYNC
    ) -> ReplicationJob:
        """Create a replication job"""
        job = ReplicationJob(
            source_region=source_region,
            target_regions=target_regions,
            data_type=data_type,
            data_id=data_id,
            mode=mode
        )
        self._jobs[job.id] = job
        self._metrics["total_jobs"] += 1
        return job

    def start_job(self, job_id: str) -> bool:
        """Start a replication job"""
        job = self._jobs.get(job_id)
        if not job or job.status != ReplicationStatus.PENDING:
            return False

        job.status = ReplicationStatus.IN_PROGRESS
        job.started_at = datetime.utcnow()
        return True

    def update_progress(
        self,
        job_id: str,
        progress: int,
        bytes_replicated: int
    ) -> bool:
        """Update job progress"""
        job = self._jobs.get(job_id)
        if not job or job.status != ReplicationStatus.IN_PROGRESS:
            return False

        job.progress = min(100, progress)
        job.bytes_replicated = bytes_replicated
        return True

    def complete_job(self, job_id: str) -> bool:
        """Complete a replication job"""
        job = self._jobs.get(job_id)
        if not job:
            return False

        job.status = ReplicationStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.utcnow()

        self._metrics["completed"] += 1
        self._metrics["bytes_replicated"] += job.bytes_replicated

        # Update lag info
        for target in job.target_regions:
            key = f"{job.source_region}->{target}"
            if key in self._lags:
                self._lags[key].last_replicated_at = datetime.utcnow()
                self._lags[key].items_pending = max(0, self._lags[key].items_pending - 1)

        return True

    def fail_job(self, job_id: str, error: str = "") -> bool:
        """Mark job as failed"""
        job = self._jobs.get(job_id)
        if not job:
            return False

        job.status = ReplicationStatus.FAILED
        job.completed_at = datetime.utcnow()
        self._metrics["failed"] += 1
        return True

    def get_job(self, job_id: str) -> Optional[ReplicationJob]:
        """Get job by ID"""
        return self._jobs.get(job_id)

    def get_jobs_by_source(self, region: str) -> List[ReplicationJob]:
        """Get all jobs from a source region"""
        return [j for j in self._jobs.values() if j.source_region == region]

    def get_jobs_by_status(self, status: ReplicationStatus) -> List[ReplicationJob]:
        """Get all jobs with a status"""
        return [j for j in self._jobs.values() if j.status == status]

    def get_active_jobs(self) -> List[ReplicationJob]:
        """Get all active jobs"""
        return self.get_jobs_by_status(ReplicationStatus.IN_PROGRESS)

    def update_lag(
        self,
        source_region: str,
        target_region: str,
        lag_ms: int,
        items_pending: int = 0
    ) -> bool:
        """Update replication lag"""
        key = f"{source_region}->{target_region}"
        if key not in self._lags:
            return False

        self._lags[key].lag_ms = lag_ms
        self._lags[key].items_pending = items_pending
        return True

    def get_lag(
        self,
        source_region: str,
        target_region: str
    ) -> Optional[ReplicationLag]:
        """Get replication lag between regions"""
        key = f"{source_region}->{target_region}"
        return self._lags.get(key)

    def get_all_lags(self) -> List[ReplicationLag]:
        """Get all replication lags"""
        return list(self._lags.values())

    def get_replication_config(
        self,
        source_region: str,
        target_region: str
    ) -> Optional[ReplicationMode]:
        """Get replication mode between regions"""
        key = f"{source_region}->{target_region}"
        return self._config.get(key)

    def get_metrics(self) -> Dict[str, Any]:
        """Get replicator metrics"""
        lags = [l.lag_ms for l in self._lags.values() if l.lag_ms > 0]
        avg_lag = sum(lags) / len(lags) if lags else 0

        return {
            **self._metrics,
            "avg_lag_ms": avg_lag,
            "active_jobs": len(self.get_active_jobs())
        }
