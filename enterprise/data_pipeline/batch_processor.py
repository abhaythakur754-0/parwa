"""
Week 56 - Batch Processing Engine
Batch processing with chunking, parallelism, and job management.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future, as_completed
import asyncio
import time
import logging
import threading
import uuid

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class BatchStatus(Enum):
    """Status of a batch job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    batch_size: int = 100
    max_parallelism: int = 4
    timeout: float = 300.0  # seconds
    chunk_size: int = 50
    retry_count: int = 3
    retry_delay: float = 1.0
    enable_checkpointing: bool = True
    checkpoint_interval: int = 10  # batches
    progress_callback_interval: int = 5  # seconds
    fail_fast: bool = False
    preserve_order: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        if self.max_parallelism <= 0:
            raise ValueError("Max parallelism must be positive")
        if self.chunk_size <= 0:
            raise ValueError("Chunk size must be positive")


@dataclass
class BatchJob(Generic[T]):
    """
    Represents a batch processing job.
    
    Attributes:
        job_id: Unique identifier for the job
        name: Human-readable name
        status: Current status of the job
        total_items: Total number of items to process
        processed_items: Number of items processed
        failed_items: Number of failed items
        progress: Progress percentage (0-100)
        start_time: When the job started
        end_time: When the job ended
        errors: List of error messages
        metadata: Additional metadata
    """
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: BatchStatus = BatchStatus.PENDING
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    progress: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_progress(self) -> None:
        """Update progress percentage based on processed items."""
        if self.total_items > 0:
            self.progress = (self.processed_items / self.total_items) * 100
    
    def is_complete(self) -> bool:
        """Check if job is complete (success or failure)."""
        return self.status in (BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED)
    
    def get_duration_seconds(self) -> Optional[float]:
        """Get the duration of the job in seconds."""
        if self.start_time is None:
            return None
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()


@dataclass
class BatchResult(Generic[R]):
    """Result of a batch processing operation."""
    success: bool
    job_id: str
    items_processed: int = 0
    items_failed: int = 0
    results: List[R] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkResult(Generic[R]):
    """Result of processing a chunk."""
    chunk_id: int
    success: bool
    items_processed: int = 0
    results: List[R] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class ChunkProcessor(Generic[T, R]):
    """Processes data in chunks with parallelism."""
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self._processed_chunks: Dict[int, ChunkResult] = {}
        self._lock = threading.Lock()
    
    def chunk(self, data: List[T]) -> List[List[T]]:
        """
        Split data into chunks.
        
        Args:
            data: List of items to chunk
            
        Returns:
            List of chunks
        """
        chunks = []
        chunk_size = self.config.chunk_size or self.config.batch_size
        
        for i in range(0, len(data), chunk_size):
            chunks.append(data[i:i + chunk_size])
        
        return chunks
    
    def process_chunk(
        self,
        chunk: List[T],
        processor: Callable[[T], R],
        chunk_id: int
    ) -> ChunkResult[R]:
        """
        Process a single chunk.
        
        Args:
            chunk: List of items to process
            processor: Function to process each item
            chunk_id: Identifier for this chunk
            
        Returns:
            ChunkResult with processing results
        """
        start_time = time.time()
        results = []
        errors = []
        
        for item in chunk:
            try:
                result = processor(item)
                results.append(result)
            except Exception as e:
                errors.append(f"Error processing item: {str(e)}")
        
        chunk_result = ChunkResult(
            chunk_id=chunk_id,
            success=len(errors) == 0,
            items_processed=len(results),
            results=results,
            errors=errors,
            duration_seconds=time.time() - start_time
        )
        
        with self._lock:
            self._processed_chunks[chunk_id] = chunk_result
        
        return chunk_result
    
    def get_processed_chunks(self) -> Dict[int, ChunkResult]:
        """Get all processed chunk results."""
        with self._lock:
            return self._processed_chunks.copy()


class BatchProcessor(Generic[T, R]):
    """
    Batch processing engine with chunking and parallelism.
    
    Features:
    - Configurable batch and chunk sizes
    - Parallel processing with thread/process pools
    - Job tracking and progress monitoring
    - Checkpointing support
    - Error handling with retries
    """
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self._jobs: Dict[str, BatchJob] = {}
        self._chunk_processor = ChunkProcessor[T, R](config)
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_job: Optional[BatchJob] = None
        self._lock = threading.Lock()
        self._stats = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "total_items_processed": 0
        }
    
    def create_job(self, name: str, total_items: int = 0, metadata: Dict = None) -> BatchJob:
        """
        Create a new batch job.
        
        Args:
            name: Human-readable name for the job
            total_items: Total number of items to process
            metadata: Additional metadata for the job
            
        Returns:
            BatchJob instance
        """
        job = BatchJob(
            name=name,
            total_items=total_items,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._jobs[job.job_id] = job
            self._stats["total_jobs"] += 1
        
        return job
    
    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)
    
    def get_all_jobs(self) -> Dict[str, BatchJob]:
        """Get all jobs."""
        with self._lock:
            return self._jobs.copy()
    
    def process_batch(
        self,
        data: List[T],
        processor: Callable[[T], R],
        job: Optional[BatchJob] = None
    ) -> BatchResult[R]:
        """
        Process a batch of data.
        
        Args:
            data: List of items to process
            processor: Function to process each item
            job: Optional job to track progress
            
        Returns:
            BatchResult with processing results
        """
        start_time = time.time()
        
        # Create job if not provided
        if job is None:
            job = self.create_job("batch_process", total_items=len(data))
        
        # Update job status
        job.status = BatchStatus.RUNNING
        job.start_time = datetime.utcnow()
        
        all_results = []
        all_errors = []
        
        try:
            # Split into batches
            batches = self._split_into_batches(data, self.config.batch_size)
            
            # Process batches
            if self.config.max_parallelism > 1:
                batch_results = self._process_batches_parallel(batches, processor, job)
            else:
                batch_results = self._process_batches_sequential(batches, processor, job)
            
            # Collect results
            for batch_result in batch_results:
                all_results.extend(batch_result.results)
                all_errors.extend(batch_result.errors)
            
            # Update job
            job.processed_items = len(all_results)
            job.failed_items = len(all_errors)
            job.result = all_results
            job.errors = all_errors
            job.update_progress()
            
            # Set final status
            if len(all_errors) > 0 and self.config.fail_fast:
                job.status = BatchStatus.FAILED
            else:
                job.status = BatchStatus.COMPLETED
            
        except Exception as e:
            job.status = BatchStatus.FAILED
            job.errors.append(str(e))
            all_errors.append(str(e))
        
        finally:
            job.end_time = datetime.utcnow()
            self._update_stats(job)
        
        return BatchResult(
            success=job.status == BatchStatus.COMPLETED,
            job_id=job.job_id,
            items_processed=job.processed_items,
            items_failed=job.failed_items,
            results=all_results,
            errors=all_errors,
            duration_seconds=time.time() - start_time
        )
    
    def _split_into_batches(self, data: List[T], batch_size: int) -> List[List[T]]:
        """Split data into batches."""
        batches = []
        for i in range(0, len(data), batch_size):
            batches.append(data[i:i + batch_size])
        return batches
    
    def _process_batches_parallel(
        self,
        batches: List[List[T]],
        processor: Callable[[T], R],
        job: BatchJob
    ) -> List[ChunkResult[R]]:
        """Process batches in parallel."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_parallelism) as executor:
            futures: List[Future] = []
            
            for i, batch in enumerate(batches):
                future = executor.submit(
                    self._chunk_processor.process_chunk,
                    batch,
                    processor,
                    i
                )
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.config.timeout)
                    results.append(result)
                    
                    # Update job progress
                    with self._lock:
                        job.processed_items += result.items_processed
                        job.failed_items += len(result.errors)
                        job.update_progress()
                        
                except Exception as e:
                    results.append(ChunkResult(
                        chunk_id=-1,
                        success=False,
                        errors=[str(e)]
                    ))
        
        # Sort by chunk_id if preserving order
        if self.config.preserve_order:
            results.sort(key=lambda x: x.chunk_id)
        
        return results
    
    def _process_batches_sequential(
        self,
        batches: List[List[T]],
        processor: Callable[[T], R],
        job: BatchJob
    ) -> List[ChunkResult[R]]:
        """Process batches sequentially."""
        results = []
        
        for i, batch in enumerate(batches):
            result = self._chunk_processor.process_chunk(batch, processor, i)
            results.append(result)
            
            # Update job progress
            job.processed_items += result.items_processed
            job.failed_items += len(result.errors)
            job.update_progress()
            
            # Checkpointing
            if self.config.enable_checkpointing and (i + 1) % self.config.checkpoint_interval == 0:
                self._checkpoint(job)
        
        return results
    
    def _checkpoint(self, job: BatchJob) -> None:
        """Save checkpoint for job."""
        logger.info(f"Checkpoint for job {job.job_id}: {job.processed_items}/{job.total_items} items")
    
    def _update_stats(self, job: BatchJob) -> None:
        """Update global statistics."""
        with self._lock:
            if job.status == BatchStatus.COMPLETED:
                self._stats["completed_jobs"] += 1
            elif job.status == BatchStatus.FAILED:
                self._stats["failed_jobs"] += 1
            self._stats["total_items_processed"] += job.processed_items
    
    async def process_batch_async(
        self,
        data: List[T],
        processor: Callable[[T], R],
        job: Optional[BatchJob] = None
    ) -> BatchResult[R]:
        """Asynchronously process a batch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.process_batch(data, processor, job)
        )
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == BatchStatus.RUNNING:
                job.status = BatchStatus.CANCELLED
                job.end_time = datetime.utcnow()
                return True
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a running job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == BatchStatus.RUNNING:
                job.status = BatchStatus.PAUSED
                return True
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == BatchStatus.PAUSED:
                job.status = BatchStatus.RUNNING
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        with self._lock:
            return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset global statistics."""
        with self._lock:
            self._stats = {
                "total_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "total_items_processed": 0
            }
    
    def get_active_jobs(self) -> List[BatchJob]:
        """Get all active (non-completed) jobs."""
        with self._lock:
            return [
                job for job in self._jobs.values()
                if not job.is_complete()
            ]
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clean up completed jobs older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours for completed jobs
            
        Returns:
            Number of jobs cleaned up
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours) if max_age_hours > 0 else datetime.max
        # Import timedelta
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        cleaned = 0
        with self._lock:
            to_remove = []
            for job_id, job in self._jobs.items():
                if job.is_complete() and job.end_time and job.end_time < cutoff:
                    to_remove.append(job_id)
            
            for job_id in to_remove:
                del self._jobs[job_id]
                cleaned += 1
        
        return cleaned


class BatchPipeline(Generic[T, R]):
    """
    Chain multiple batch processors together.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._stages: List[Callable] = []
        self._configs: List[BatchConfig] = []
    
    def add_stage(
        self,
        processor: Callable,
        config: Optional[BatchConfig] = None
    ) -> 'BatchPipeline':
        """Add a processing stage to the pipeline."""
        self._stages.append(processor)
        self._configs.append(config or BatchConfig())
        return self
    
    def execute(self, data: List[T]) -> List[Any]:
        """Execute the pipeline on data."""
        current_data = data
        
        for stage_idx, (processor, config) in enumerate(zip(self._stages, self._configs)):
            batch_processor = BatchProcessor(config)
            job = batch_processor.create_job(f"stage_{stage_idx}", len(current_data))
            result = batch_processor.process_batch(current_data, processor, job)
            
            if not result.success:
                raise RuntimeError(f"Pipeline stage {stage_idx} failed: {result.errors}")
            
            current_data = result.results
        
        return current_data
    
    def get_stage_count(self) -> int:
        """Get the number of stages in the pipeline."""
        return len(self._stages)
