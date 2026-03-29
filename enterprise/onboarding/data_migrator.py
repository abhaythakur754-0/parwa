"""
Enterprise Onboarding - Data Migrator
Migrates client data during onboarding
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class MigrationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MigrationJob(BaseModel):
    """Migration job definition"""
    job_id: str
    source: str
    destination: str
    data_types: List[str] = Field(default_factory=list)
    status: MigrationStatus = MigrationStatus.PENDING
    records_migrated: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict()


class DataMigrator:
    """
    Handles data migration for enterprise client onboarding.
    """

    def __init__(self):
        self.jobs: Dict[str, MigrationJob] = {}

    def create_migration_job(
        self,
        job_id: str,
        source: str,
        destination: str,
        data_types: List[str]
    ) -> MigrationJob:
        """Create a new migration job"""
        job = MigrationJob(
            job_id=job_id,
            source=source,
            destination=destination,
            data_types=data_types
        )
        self.jobs[job_id] = job
        return job

    def run_migration(self, job_id: str) -> MigrationJob:
        """Run a migration job"""
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")

        job = self.jobs[job_id]
        job.status = MigrationStatus.RUNNING
        job.started_at = datetime.utcnow()

        try:
            # Simulate migration
            for data_type in job.data_types:
                job.records_migrated += self._migrate_data_type(data_type)

            job.status = MigrationStatus.COMPLETED
            job.completed_at = datetime.utcnow()
        except Exception as e:
            job.status = MigrationStatus.FAILED
            job.errors.append(str(e))

        return job

    def _migrate_data_type(self, data_type: str) -> int:
        """Migrate a specific data type"""
        # Return simulated record count
        return 100

    def get_job_status(self, job_id: str) -> Optional[MigrationStatus]:
        """Get job status"""
        if job_id in self.jobs:
            return self.jobs[job_id].status
        return None

    def list_jobs(self) -> List[str]:
        """List all jobs"""
        return list(self.jobs.keys())
