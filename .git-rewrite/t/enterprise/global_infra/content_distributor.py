# Content Distributor - Week 51 Builder 2
# Content distribution across edge locations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class DistributionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ContentType(Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    STREAMING = "streaming"
    API = "api"


@dataclass
class DistributionTarget:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    region: str = ""
    endpoint: str = ""
    priority: int = 1
    enabled: bool = True
    last_sync: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DistributionJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_type: ContentType = ContentType.STATIC
    source_path: str = ""
    targets: List[str] = field(default_factory=list)
    status: DistributionStatus = DistributionStatus.PENDING
    progress_percent: int = 0
    total_files: int = 0
    distributed_files: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


class ContentDistributor:
    """Distributes content across edge locations"""

    def __init__(self):
        self._targets: Dict[str, DistributionTarget] = {}
        self._jobs: Dict[str, DistributionJob] = {}
        self._metrics = {
            "total_jobs": 0,
            "total_distributed": 0,
            "by_region": {},
            "by_status": {}
        }

    def add_target(
        self,
        region: str,
        endpoint: str,
        priority: int = 1
    ) -> DistributionTarget:
        """Add a distribution target"""
        target = DistributionTarget(
            region=region,
            endpoint=endpoint,
            priority=priority
        )
        self._targets[target.id] = target
        return target

    def remove_target(self, target_id: str) -> bool:
        """Remove a distribution target"""
        if target_id in self._targets:
            del self._targets[target_id]
            return True
        return False

    def create_job(
        self,
        content_type: ContentType,
        source_path: str,
        target_regions: Optional[List[str]] = None
    ) -> DistributionJob:
        """Create a distribution job"""
        # Get target IDs for regions
        targets = []
        if target_regions:
            for target in self._targets.values():
                if target.region in target_regions and target.enabled:
                    targets.append(target.id)
        else:
            # Use all enabled targets
            targets = [t.id for t in self._targets.values() if t.enabled]

        job = DistributionJob(
            content_type=content_type,
            source_path=source_path,
            targets=targets
        )
        self._jobs[job.id] = job
        self._metrics["total_jobs"] += 1

        status_key = job.status.value
        self._metrics["by_status"][status_key] = \
            self._metrics["by_status"].get(status_key, 0) + 1

        return job

    def start_job(self, job_id: str) -> bool:
        """Start a distribution job"""
        job = self._jobs.get(job_id)
        if not job or job.status != DistributionStatus.PENDING:
            return False

        job.status = DistributionStatus.IN_PROGRESS
        job.started_at = datetime.utcnow()
        return True

    def update_progress(
        self,
        job_id: str,
        distributed_files: int,
        total_files: int
    ) -> bool:
        """Update job progress"""
        job = self._jobs.get(job_id)
        if not job or job.status != DistributionStatus.IN_PROGRESS:
            return False

        job.distributed_files = distributed_files
        job.total_files = total_files
        job.progress_percent = int((distributed_files / total_files * 100) if total_files > 0 else 0)
        return True

    def complete_job(self, job_id: str) -> bool:
        """Complete a distribution job"""
        job = self._jobs.get(job_id)
        if not job:
            return False

        job.status = DistributionStatus.COMPLETED
        job.progress_percent = 100
        job.completed_at = datetime.utcnow()

        # Update target last_sync
        for target_id in job.targets:
            target = self._targets.get(target_id)
            if target:
                target.last_sync = datetime.utcnow()
                self._metrics["by_region"][target.region] = \
                    self._metrics["by_region"].get(target.region, 0) + 1

        self._metrics["total_distributed"] += job.distributed_files
        return True

    def fail_job(self, job_id: str, error_message: str = "") -> bool:
        """Mark job as failed"""
        job = self._jobs.get(job_id)
        if not job:
            return False

        job.status = DistributionStatus.FAILED
        job.completed_at = datetime.utcnow()
        job.error_message = error_message
        return True

    def get_job(self, job_id: str) -> Optional[DistributionJob]:
        """Get job by ID"""
        return self._jobs.get(job_id)

    def get_jobs_by_status(self, status: DistributionStatus) -> List[DistributionJob]:
        """Get all jobs with a status"""
        return [j for j in self._jobs.values() if j.status == status]

    def get_target(self, target_id: str) -> Optional[DistributionTarget]:
        """Get target by ID"""
        return self._targets.get(target_id)

    def get_targets_by_region(self, region: str) -> List[DistributionTarget]:
        """Get all targets in a region"""
        return [t for t in self._targets.values() if t.region == region]

    def get_enabled_targets(self) -> List[DistributionTarget]:
        """Get all enabled targets"""
        return [t for t in self._targets.values() if t.enabled]

    def enable_target(self, target_id: str) -> bool:
        """Enable a target"""
        target = self._targets.get(target_id)
        if not target:
            return False
        target.enabled = True
        return True

    def disable_target(self, target_id: str) -> bool:
        """Disable a target"""
        target = self._targets.get(target_id)
        if not target:
            return False
        target.enabled = False
        return True

    def get_active_jobs(self) -> List[DistributionJob]:
        """Get all active jobs"""
        return [
            j for j in self._jobs.values()
            if j.status in [DistributionStatus.PENDING, DistributionStatus.IN_PROGRESS]
        ]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job"""
        job = self._jobs.get(job_id)
        if not job or job.status not in [DistributionStatus.PENDING, DistributionStatus.IN_PROGRESS]:
            return False

        job.status = DistributionStatus.FAILED
        job.error_message = "Cancelled by user"
        job.completed_at = datetime.utcnow()
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get distribution metrics"""
        return self._metrics.copy()
