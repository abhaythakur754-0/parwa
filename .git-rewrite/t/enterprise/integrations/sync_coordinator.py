"""
Synchronization Coordinator
Enterprise Integration Hub - Week 43 Builder 5
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class SyncTask:
    """A single sync task"""
    id: str
    name: str
    source_id: str
    target_id: str
    entity_type: str
    batch_size: int = 100
    transform_fn: Optional[Callable] = None
    filter_fn: Optional[Callable] = None
    status: str = "pending"
    progress: float = 0.0
    records_total: int = 0
    records_processed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "entity_type": self.entity_type,
            "status": self.status,
            "progress": self.progress,
            "records_total": self.records_total,
            "records_processed": self.records_processed,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


@dataclass
class ConflictResolution:
    """Strategy for resolving sync conflicts"""
    strategy: str  # source_wins, target_wins, latest_wins, merge
    merge_rules: Optional[Dict[str, str]] = None
    
    def resolve(
        self,
        source_record: Dict[str, Any],
        target_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve conflict between source and target records"""
        if self.strategy == "source_wins":
            return source_record
        elif self.strategy == "target_wins":
            return target_record
        elif self.strategy == "latest_wins":
            source_time = source_record.get("updated_at") or source_record.get("last_modified")
            target_time = target_record.get("updated_at") or target_record.get("last_modified")
            
            if source_time and target_time:
                if source_time > target_time:
                    return source_record
                else:
                    return target_record
            return source_record
        elif self.strategy == "merge":
            return self._merge_records(source_record, target_record)
        
        return source_record
    
    def _merge_records(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two records based on merge rules"""
        result = target.copy()
        
        if self.merge_rules:
            for field_name, rule in self.merge_rules.items():
                if rule == "source":
                    result[field_name] = source.get(field_name)
                elif rule == "target":
                    pass  # Keep target value
                elif rule == "concat":
                    result[field_name] = f"{source.get(field_name, '')} {target.get(field_name, '')}"
        else:
            # Default merge: source overwrites non-null values
            for key, value in source.items():
                if value is not None:
                    result[key] = value
        
        return result


class SyncCoordinator:
    """Coordinates synchronization between integrations"""
    
    def __init__(
        self,
        integration_hub: Any,
        conflict_resolution: Optional[ConflictResolution] = None
    ):
        self.hub = integration_hub
        self.conflict_resolution = conflict_resolution or ConflictResolution(strategy="source_wins")
        self._active_tasks: Dict[str, SyncTask] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._concurrency_limit = 5
    
    async def start(self) -> None:
        """Start the sync coordinator"""
        self._running = True
        logger.info("Sync coordinator started")
        
        # Start worker tasks
        workers = [
            asyncio.create_task(self._worker())
            for _ in range(self._concurrency_limit)
        ]
        
        await asyncio.gather(*workers)
    
    def stop(self) -> None:
        """Stop the sync coordinator"""
        self._running = False
        logger.info("Sync coordinator stopped")
    
    async def _worker(self) -> None:
        """Worker coroutine for processing sync tasks"""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                await self._process_task(task)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    async def _process_task(self, task: SyncTask) -> None:
        """Process a single sync task"""
        task.status = "running"
        task.started_at = datetime.utcnow()
        self._active_tasks[task.id] = task
        
        try:
            # Get source and target
            source = self.hub.get_integration(task.source_id)
            target = self.hub.get_integration(task.target_id)
            
            if not source or not target:
                task.status = "failed"
                task.error = "Source or target not found"
                task.completed_at = datetime.utcnow()
                return
            
            # Fetch from source
            records = await self._fetch_records(source, task)
            task.records_total = len(records)
            
            # Process in batches
            for i in range(0, len(records), task.batch_size):
                batch = records[i:i + task.batch_size]
                
                # Apply transformation if provided
                if task.transform_fn:
                    batch = [task.transform_fn(r) for r in batch]
                
                # Apply filter if provided
                if task.filter_fn:
                    batch = [r for r in batch if task.filter_fn(r)]
                
                # Push to target
                await self._push_records(target, task.entity_type, batch)
                
                task.records_processed += len(batch)
                task.progress = (task.records_processed / task.records_total) * 100 if task.records_total > 0 else 100
            
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            logger.error(f"Task processing error: {e}")
        
        finally:
            del self._active_tasks[task.id]
    
    async def _fetch_records(
        self,
        source: Any,
        task: SyncTask
    ) -> List[Dict[str, Any]]:
        """Fetch records from source integration"""
        # This would call the appropriate fetch method on the connector
        return []
    
    async def _push_records(
        self,
        target: Any,
        entity_type: str,
        records: List[Dict[str, Any]]
    ) -> int:
        """Push records to target integration"""
        # This would call the appropriate push method on the connector
        return len(records)
    
    async def queue_sync(
        self,
        name: str,
        source_id: str,
        target_id: str,
        entity_type: str,
        batch_size: int = 100,
        transform_fn: Optional[Callable] = None,
        filter_fn: Optional[Callable] = None
    ) -> SyncTask:
        """Queue a sync task"""
        import uuid
        
        task = SyncTask(
            id=str(uuid.uuid4()),
            name=name,
            source_id=source_id,
            target_id=target_id,
            entity_type=entity_type,
            batch_size=batch_size,
            transform_fn=transform_fn,
            filter_fn=filter_fn
        )
        
        await self._task_queue.put(task)
        return task
    
    def get_task_status(self, task_id: str) -> Optional[SyncTask]:
        """Get status of a sync task"""
        return self._active_tasks.get(task_id)
    
    def get_active_tasks(self) -> List[SyncTask]:
        """Get all active sync tasks"""
        return list(self._active_tasks.values())
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout: float = 300.0
    ) -> Optional[SyncTask]:
        """Wait for a task to complete"""
        start_time = datetime.utcnow()
        
        while True:
            if task_id not in self._active_tasks:
                # Task is complete - check history
                # In a real implementation, we'd check a completed tasks store
                return None
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed >= timeout:
                return self._active_tasks.get(task_id)
            
            await asyncio.sleep(0.5)
    
    def get_queue_size(self) -> int:
        """Get the size of the task queue"""
        return self._task_queue.qsize()
    
    def set_concurrency(self, limit: int) -> None:
        """Set the concurrency limit"""
        self._concurrency_limit = max(1, min(limit, 20))
        logger.info(f"Set concurrency limit to {self._concurrency_limit}")


class BidirectionalSync:
    """Manages bidirectional synchronization between two systems"""
    
    def __init__(
        self,
        hub: Any,
        coordinator: SyncCoordinator,
        left_integration: str,
        right_integration: str,
        entity_type: str
    ):
        self.hub = hub
        self.coordinator = coordinator
        self.left_id = left_integration
        self.right_id = right_integration
        self.entity_type = entity_type
        self._last_sync_left: Optional[datetime] = None
        self._last_sync_right: Optional[datetime] = None
    
    async def sync(self) -> Dict[str, Any]:
        """Perform bidirectional sync"""
        results = {
            "left_to_right": None,
            "right_to_left": None,
            "conflicts": []
        }
        
        # Sync left to right
        task_lr = await self.coordinator.queue_sync(
            name=f"sync_{self.left_id}_to_{self.right_id}",
            source_id=self.left_id,
            target_id=self.right_id,
            entity_type=self.entity_type
        )
        
        # Sync right to left
        task_rl = await self.coordinator.queue_sync(
            name=f"sync_{self.right_id}_to_{self.left_id}",
            source_id=self.right_id,
            target_id=self.left_id,
            entity_type=self.entity_type
        )
        
        # Wait for both to complete
        await self.coordinator.wait_for_task(task_lr.id)
        await self.coordinator.wait_for_task(task_rl.id)
        
        results["left_to_right"] = task_lr.to_dict()
        results["right_to_left"] = task_rl.to_dict()
        
        return results
    
    def get_last_sync(self) -> Dict[str, Optional[datetime]]:
        """Get last sync times"""
        return {
            "left_to_right": self._last_sync_left,
            "right_to_left": self._last_sync_right
        }
