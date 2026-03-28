"""
Week 58 - Builder 4: Data Sync Module
Bidirectional data synchronization with conflict resolution
"""

import time
import threading
import hashlib
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Sync direction"""
    SOURCE_TO_TARGET = "source_to_target"
    TARGET_TO_SOURCE = "target_to_source"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(Enum):
    """Sync status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class ConflictStrategy(Enum):
    """Conflict resolution strategy"""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    LATEST_WINS = "latest_wins"
    MANUAL = "manual"


@dataclass
class SyncRecord:
    """Synchronization record"""
    id: str
    source_id: str
    target_id: str
    entity_type: str
    source_data: Dict[str, Any]
    target_data: Dict[str, Any]
    source_timestamp: float
    target_timestamp: float
    checksum: str
    synced_at: Optional[float] = None


@dataclass
class SyncConfig:
    """Sync configuration"""
    name: str
    source: str
    target: str
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_strategy: ConflictStrategy = ConflictStrategy.LATEST_WINS
    batch_size: int = 100
    sync_interval: int = 60


@dataclass
class SyncResult:
    """Sync operation result"""
    sync_id: str
    status: SyncStatus
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    conflicts: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class SyncEngine:
    """
    Bidirectional sync engine with conflict resolution
    """

    def __init__(self):
        self.configs: Dict[str, SyncConfig] = {}
        self.records: Dict[str, SyncRecord] = {}
        self.results: Dict[str, SyncResult] = {}
        self.status: Dict[str, SyncStatus] = {}
        self.lock = threading.Lock()
        self.stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"syncs": 0, "records": 0, "conflicts": 0, "errors": 0}
        )

    def register_sync(self, config: SyncConfig) -> None:
        """Register a sync configuration"""
        with self.lock:
            self.configs[config.name] = config
            self.status[config.name] = SyncStatus.PENDING

    def unregister_sync(self, name: str) -> bool:
        """Unregister a sync configuration"""
        with self.lock:
            if name in self.configs:
                del self.configs[name]
                if name in self.status:
                    del self.status[name]
                return True
        return False

    def _compute_checksum(self, data: Dict[str, Any]) -> str:
        """Compute data checksum"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def _detect_conflict(self, record: SyncRecord) -> bool:
        """Detect if there's a sync conflict"""
        if record.source_data == record.target_data:
            return False
        source_checksum = self._compute_checksum(record.source_data)
        target_checksum = self._compute_checksum(record.target_data)
        return source_checksum != target_checksum

    def _resolve_conflict(self, record: SyncRecord,
                          strategy: ConflictStrategy) -> Dict[str, Any]:
        """Resolve sync conflict"""
        if strategy == ConflictStrategy.SOURCE_WINS:
            return record.source_data
        elif strategy == ConflictStrategy.TARGET_WINS:
            return record.target_data
        elif strategy == ConflictStrategy.LATEST_WINS:
            if record.source_timestamp > record.target_timestamp:
                return record.source_data
            return record.target_data
        else:
            # Manual - return both for external resolution
            return {
                "conflict": True,
                "source": record.source_data,
                "target": record.target_data
            }

    def sync_record(self, sync_name: str, record: SyncRecord) -> SyncResult:
        """Sync a single record"""
        sync_id = hashlib.md5(
            f"{sync_name}:{record.id}:{time.time()}".encode()
        ).hexdigest()[:16]

        result = SyncResult(sync_id=sync_id, status=SyncStatus.RUNNING)
        config = self.configs.get(sync_name)

        if not config:
            result.status = SyncStatus.FAILED
            result.errors.append(f"Sync config not found: {sync_name}")
            return result

        # Detect conflict
        if self._detect_conflict(record):
            result.conflicts += 1
            resolved = self._resolve_conflict(record, config.conflict_strategy)
            record.source_data = resolved
            record.target_data = resolved

        record.synced_at = time.time()
        record.checksum = self._compute_checksum(record.source_data)

        result.records_processed = 1
        result.records_updated = 1
        result.status = SyncStatus.COMPLETED
        result.completed_at = time.time()

        with self.lock:
            self.records[record.id] = record
            self.results[sync_id] = result
            self.stats[sync_name]["syncs"] += 1
            self.stats[sync_name]["records"] += 1
            if result.conflicts > 0:
                self.stats[sync_name]["conflicts"] += 1

        return result

    def sync_batch(self, sync_name: str,
                   records: List[SyncRecord]) -> SyncResult:
        """Sync a batch of records"""
        sync_id = hashlib.md5(
            f"{sync_name}:batch:{time.time()}".encode()
        ).hexdigest()[:16]

        result = SyncResult(sync_id=sync_id, status=SyncStatus.RUNNING)
        config = self.configs.get(sync_name)

        if not config:
            result.status = SyncStatus.FAILED
            result.errors.append(f"Sync config not found: {sync_name}")
            return result

        for record in records:
            try:
                if self._detect_conflict(record):
                    result.conflicts += 1
                    resolved = self._resolve_conflict(
                        record, config.conflict_strategy
                    )
                    record.source_data = resolved
                    record.target_data = resolved
                    result.records_updated += 1
                else:
                    result.records_skipped += 1

                record.synced_at = time.time()
                record.checksum = self._compute_checksum(record.source_data)

                with self.lock:
                    self.records[record.id] = record

                result.records_processed += 1

            except Exception as e:
                result.errors.append(str(e))

        result.status = SyncStatus.COMPLETED if not result.errors else SyncStatus.FAILED
        result.completed_at = time.time()

        with self.lock:
            self.results[sync_id] = result
            self.stats[sync_name]["syncs"] += 1
            self.stats[sync_name]["records"] += result.records_processed
            self.stats[sync_name]["conflicts"] += result.conflicts

        return result

    def get_sync_status(self, name: str) -> Optional[SyncStatus]:
        """Get sync status"""
        return self.status.get(name)

    def get_result(self, sync_id: str) -> Optional[SyncResult]:
        """Get sync result by ID"""
        return self.results.get(sync_id)

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get sync statistics"""
        return dict(self.stats)


class SyncScheduler:
    """
    Scheduler for automated sync operations
    """

    def __init__(self, engine: SyncEngine):
        self.engine = engine
        self.schedules: Dict[str, Dict[str, Any]] = {}
        self.running: Dict[str, bool] = {}
        self.lock = threading.Lock()

    def schedule_sync(self, name: str, interval: int,
                      callback: Callable = None) -> None:
        """Schedule a sync to run at intervals"""
        with self.lock:
            self.schedules[name] = {
                "interval": interval,
                "callback": callback,
                "last_run": None,
                "next_run": time.time() + interval
            }

    def unschedule_sync(self, name: str) -> bool:
        """Remove a scheduled sync"""
        with self.lock:
            if name in self.schedules:
                del self.schedules[name]
                return True
        return False

    def run_sync(self, name: str, records: List[SyncRecord] = None) -> Optional[SyncResult]:
        """Run a scheduled sync"""
        schedule = self.schedules.get(name)
        if not schedule:
            return None

        config = self.engine.configs.get(name)
        if not config:
            return None

        # Run sync (with mock records if none provided)
        if records is None:
            records = []

        result = self.engine.sync_batch(name, records)

        with self.lock:
            schedule["last_run"] = time.time()
            schedule["next_run"] = time.time() + schedule["interval"]

        if schedule["callback"]:
            schedule["callback"](result)

        return result

    def get_next_run(self, name: str) -> Optional[float]:
        """Get next scheduled run time"""
        schedule = self.schedules.get(name)
        return schedule["next_run"] if schedule else None

    def get_schedule(self, name: str) -> Optional[Dict[str, Any]]:
        """Get schedule info"""
        return self.schedules.get(name)

    def list_schedules(self) -> List[str]:
        """List all scheduled syncs"""
        return list(self.schedules.keys())


class SyncMonitor:
    """
    Monitor for sync operations and health
    """

    def __init__(self, engine: SyncEngine, scheduler: SyncScheduler):
        self.engine = engine
        self.scheduler = scheduler
        self.alerts: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def get_sync_health(self, name: str) -> Dict[str, Any]:
        """Get health status of a sync"""
        config = self.engine.configs.get(name)
        if not config:
            return {"status": "not_found"}

        status = self.engine.status.get(name, SyncStatus.PENDING)
        stats = self.engine.stats.get(name, {})

        return {
            "name": name,
            "status": status.value,
            "total_syncs": stats.get("syncs", 0),
            "total_records": stats.get("records", 0),
            "total_conflicts": stats.get("conflicts", 0),
            "total_errors": stats.get("errors", 0)
        }

    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all syncs"""
        return {
            name: self.get_sync_health(name)
            for name in self.engine.configs.keys()
        }

    def record_alert(self, sync_name: str, message: str,
                     severity: str = "warning") -> None:
        """Record a sync alert"""
        with self.lock:
            self.alerts.append({
                "sync": sync_name,
                "message": message,
                "severity": severity,
                "timestamp": time.time()
            })

    def get_alerts(self, sync_name: str = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Get alerts, optionally filtered by sync"""
        alerts = self.alerts
        if sync_name:
            alerts = [a for a in alerts if a["sync"] == sync_name]
        return alerts[-limit:]

    def clear_alerts(self, sync_name: str = None) -> int:
        """Clear alerts"""
        with self.lock:
            if sync_name:
                original = len(self.alerts)
                self.alerts = [a for a in self.alerts if a["sync"] != sync_name]
                return original - len(self.alerts)
            else:
                count = len(self.alerts)
                self.alerts.clear()
                return count

    def get_recovery_suggestions(self, sync_name: str) -> List[str]:
        """Get recovery suggestions for a sync"""
        health = self.get_sync_health(sync_name)
        suggestions = []

        if health.get("status") == "failed":
            suggestions.append("Check source and target connections")
            suggestions.append("Verify credentials and permissions")

        if health.get("total_conflicts", 0) > 10:
            suggestions.append("Review conflict resolution strategy")
            suggestions.append("Consider manual conflict resolution")

        if health.get("total_errors", 0) > 5:
            suggestions.append("Check error logs for patterns")
            suggestions.append("Verify data format compatibility")

        return suggestions
