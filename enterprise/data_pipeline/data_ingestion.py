"""Data Ingestion Module - Week 56, Builder 1"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import time

logger = logging.getLogger(__name__)


class IngestionSource(Enum):
    API = "api"
    DATABASE = "database"
    FILE = "file"
    STREAM = "stream"
    WEBHOOK = "webhook"


@dataclass
class IngestionConfig:
    source_type: IngestionSource
    connection_string: str = ""
    rate_limit: int = 100
    retry_count: int = 3
    timeout: int = 30
    batch_size: int = 1000


@dataclass
class IngestionResult:
    records_ingested: int
    records_failed: int
    duration_ms: float
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DataIngestion:
    def __init__(self, config: IngestionConfig):
        self.config = config
        self._sources: Dict[str, Callable] = {}
        self._stats = {"total_ingested": 0, "total_failed": 0}

    def register_source(self, name: str, handler: Callable) -> None:
        self._sources[name] = handler

    def ingest(self, source_name: str, data: Optional[Any] = None) -> IngestionResult:
        start_time = time.time()
        errors = []
        ingested = 0
        failed = 0

        handler = self._sources.get(source_name)
        if not handler:
            errors.append(f"Source not found: {source_name}")
            return IngestionResult(0, 0, 0, errors)

        for attempt in range(self.config.retry_count):
            try:
                if data:
                    result = handler(data)
                else:
                    result = handler()
                ingested = len(result) if isinstance(result, list) else 1
                break
            except Exception as e:
                errors.append(f"Attempt {attempt + 1}: {str(e)}")
                if attempt == self.config.retry_count - 1:
                    failed = 1

        duration = (time.time() - start_time) * 1000
        self._stats["total_ingested"] += ingested
        self._stats["total_failed"] += failed

        return IngestionResult(ingested, failed, duration, errors)

    def get_stats(self) -> Dict[str, int]:
        return self._stats.copy()


class StreamProcessor:
    def __init__(self, window_size: int = 60, max_batch: int = 100):
        self.window_size = window_size
        self.max_batch = max_batch
        self._buffer: List[Any] = []
        self._handlers: List[Callable] = []

    def add_handler(self, handler: Callable) -> None:
        self._handlers.append(handler)

    def process(self, event: Any) -> int:
        self._buffer.append(event)
        processed = 0

        if len(self._buffer) >= self.max_batch:
            processed = self._flush()

        return processed

    def _flush(self) -> int:
        batch = self._buffer.copy()
        self._buffer.clear()

        for handler in self._handlers:
            for event in batch:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Handler error: {e}")

        return len(batch)

    def get_buffer_size(self) -> int:
        return len(self._buffer)


class BatchProcessor:
    def __init__(self, batch_size: int = 100, parallelism: int = 4):
        self.batch_size = batch_size
        self.parallelism = parallelism
        self._jobs: Dict[str, Dict] = {}

    def process_batch(self, data: List[Any], handler: Callable) -> Dict[str, Any]:
        job_id = f"job_{len(self._jobs)}"
        self._jobs[job_id] = {"status": "running", "processed": 0, "total": len(data)}

        chunks = [data[i:i + self.batch_size] for i in range(0, len(data), self.batch_size)]
        processed = 0

        for chunk in chunks:
            try:
                handler(chunk)
                processed += len(chunk)
            except Exception as e:
                logger.error(f"Chunk error: {e}")

        self._jobs[job_id]["status"] = "completed"
        self._jobs[job_id]["processed"] = processed

        return {"job_id": job_id, "processed": processed, "total": len(data)}

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[str]:
        return list(self._jobs.keys())
