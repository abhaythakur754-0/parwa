"""
Quick Rollback for Agent Lightning

Implements instant rollback mechanism:
1. One-command rollback
2. Version history
3. Instant traffic switch
4. Rollback verification

CRITICAL: Rollback must be fast and reliable.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


logger = logging.getLogger(__name__)


class RollbackStatus(Enum):
    """Rollback status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class RollbackReason(Enum):
    """Reasons for rollback."""
    ERROR_RATE_EXCEEDED = "error_rate_exceeded"
    LATENCY_EXCEEDED = "latency_exceeded"
    MANUAL = "manual"
    HEALTH_CHECK_FAILED = "health_check_failed"
    SAFETY_VIOLATION = "safety_violation"
    ACCURACY_DEGRADATION = "accuracy_degradation"


@dataclass
class ModelVersion:
    """Model version information."""
    version: str
    deployed_at: datetime
    traffic_percent: float
    accuracy: float
    error_rate: float
    is_active: bool
    deployment_id: str
    previous_version: Optional[str] = None


@dataclass
class RollbackRecord:
    """Record of a rollback operation."""
    rollback_id: str
    from_version: str
    to_version: str
    reason: RollbackReason
    status: RollbackStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    verified: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class VersionHistory:
    """Manages model version history."""
    
    def __init__(self, max_versions: int = 10):
        self.max_versions = max_versions
        self.versions: List[ModelVersion] = []
    
    def add_version(self, version: ModelVersion):
        """Add a new version to history."""
        self.versions.append(version)
        
        # Keep only max_versions
        if len(self.versions) > self.max_versions:
            self.versions = self.versions[-self.max_versions:]
    
    def get_previous_version(self, current_version: str) -> Optional[ModelVersion]:
        """Get the previous version."""
        for i, v in enumerate(self.versions):
            if v.version == current_version and i > 0:
                return self.versions[i - 1]
        return None
    
    def get_version(self, version: str) -> Optional[ModelVersion]:
        """Get a specific version."""
        for v in self.versions:
            if v.version == version:
                return v
        return None
    
    def get_active_version(self) -> Optional[ModelVersion]:
        """Get the currently active version."""
        for v in self.versions:
            if v.is_active:
                return v
        return None
    
    def get_rollback_candidates(self) -> List[ModelVersion]:
        """Get versions that can be rolled back to."""
        active = self.get_active_version()
        if not active:
            return []
        
        return [v for v in self.versions if v.version != active.version]


class TrafficSwitcher:
    """Handles instant traffic switching."""
    
    def __init__(self):
        self.current_split: Dict[str, float] = {}
        self.switch_history: List[Dict[str, Any]] = []
    
    async def switch_traffic(self, from_version: str, to_version: str, percent: float = 100.0) -> bool:
        """Switch traffic from one version to another."""
        start_time = time.time()
        
        logger.info(f"Switching traffic: {from_version} -> {to_version} ({percent}%)")
        
        # Simulate instant traffic switch
        self.current_split = {
            from_version: 100 - percent,
            to_version: percent
        }
        
        # Record switch
        self.switch_history.append({
            "from": from_version,
            "to": to_version,
            "percent": percent,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": int((time.time() - start_time) * 1000)
        })
        
        return True
    
    def get_current_split(self) -> Dict[str, float]:
        """Get current traffic split."""
        return self.current_split.copy()


class HealthVerifier:
    """Verifies system health after rollback."""
    
    def __init__(self):
        self.checks_performed = 0
    
    async def verify_health(self, version: str) -> Dict[str, Any]:
        """Verify health of a version."""
        self.checks_performed += 1
        await asyncio.sleep(0.05)  # Simulate health check
        
        return {
            "version": version,
            "healthy": True,
            "error_rate": 0.005,
            "latency_ms": 120,
            "accuracy": 0.82,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def verify_rollback_success(self, from_version: str, to_version: str) -> bool:
        """Verify rollback was successful."""
        health = await self.verify_health(to_version)
        return health.get("healthy", False)


class QuickRollbackManager:
    """Manages quick rollback operations."""
    
    def __init__(
        self,
        version_history: VersionHistory,
        traffic_switcher: TrafficSwitcher,
        health_verifier: HealthVerifier,
        rollback_timeout_ms: int = 5000
    ):
        self.version_history = version_history
        self.traffic_switcher = traffic_switcher
        self.health_verifier = health_verifier
        self.rollback_timeout_ms = rollback_timeout_ms
        
        self.rollback_records: List[RollbackRecord] = []
        self._in_progress = False
    
    async def rollback(
        self,
        target_version: Optional[str] = None,
        reason: RollbackReason = RollbackReason.MANUAL
    ) -> RollbackRecord:
        """Execute rollback to target version (or previous if not specified)."""
        
        if self._in_progress:
            raise RuntimeError("Rollback already in progress")
        
        self._in_progress = True
        start_time = time.time()
        
        rollback_id = f"rb-{int(start_time)}"
        
        # Get current version
        current = self.version_history.get_active_version()
        if not current:
            self._in_progress = False
            return RollbackRecord(
                rollback_id=rollback_id,
                from_version="unknown",
                to_version="unknown",
                reason=reason,
                status=RollbackStatus.FAILED,
                started_at=datetime.utcnow(),
                details={"error": "No active version found"}
            )
        
        # Determine target version
        if target_version:
            target = self.version_history.get_version(target_version)
        else:
            target = self.version_history.get_previous_version(current.version)
        
        if not target:
            self._in_progress = False
            return RollbackRecord(
                rollback_id=rollback_id,
                from_version=current.version,
                to_version=target_version or "none",
                reason=reason,
                status=RollbackStatus.FAILED,
                started_at=datetime.utcnow(),
                details={"error": "Target version not found"}
            )
        
        # Create rollback record
        record = RollbackRecord(
            rollback_id=rollback_id,
            from_version=current.version,
            to_version=target.version,
            reason=reason,
            status=RollbackStatus.IN_PROGRESS,
            started_at=datetime.utcnow()
        )
        
        logger.warning(f"Starting rollback: {current.version} -> {target.version}")
        
        try:
            # Step 1: Switch traffic
            switch_success = await asyncio.wait_for(
                self.traffic_switcher.switch_traffic(
                    current.version,
                    target.version,
                    100.0
                ),
                timeout=self.rollback_timeout_ms / 1000
            )
            
            if not switch_success:
                raise RuntimeError("Traffic switch failed")
            
            # Step 2: Update version status
            current.is_active = False
            target.is_active = True
            
            # Step 3: Verify rollback
            verify_success = await self.health_verifier.verify_rollback_success(
                current.version,
                target.version
            )
            
            if verify_success:
                record.status = RollbackStatus.VERIFIED
                record.verified = True
            else:
                record.status = RollbackStatus.COMPLETED
                record.verified = False
            
            record.completed_at = datetime.utcnow()
            record.duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Rollback completed in {record.duration_ms}ms")
            
        except asyncio.TimeoutError:
            record.status = RollbackStatus.FAILED
            record.completed_at = datetime.utcnow()
            record.duration_ms = self.rollback_timeout_ms
            record.details["error"] = "Rollback timed out"
            logger.error("Rollback timed out")
            
        except Exception as e:
            record.status = RollbackStatus.FAILED
            record.completed_at = datetime.utcnow()
            record.duration_ms = int((time.time() - start_time) * 1000)
            record.details["error"] = str(e)
            logger.error(f"Rollback failed: {e}")
        
        finally:
            self._in_progress = False
            self.rollback_records.append(record)
        
        return record
    
    def get_rollback_history(self, limit: int = 10) -> List[RollbackRecord]:
        """Get recent rollback history."""
        return self.rollback_records[-limit:]
    
    def get_last_rollback(self) -> Optional[RollbackRecord]:
        """Get the most recent rollback."""
        return self.rollback_records[-1] if self.rollback_records else None


class TestQuickRollback:
    """Tests for quick rollback functionality."""
    
    @pytest.fixture
    def version_history(self):
        history = VersionHistory()
        history.add_version(ModelVersion(
            version="v1.0.0",
            deployed_at=datetime.utcnow() - timedelta(days=7),
            traffic_percent=0,
            accuracy=0.75,
            error_rate=0.01,
            is_active=False,
            deployment_id="d1"
        ))
        history.add_version(ModelVersion(
            version="v1.5.0",
            deployed_at=datetime.utcnow() - timedelta(days=3),
            traffic_percent=0,
            accuracy=0.78,
            error_rate=0.008,
            is_active=False,
            deployment_id="d2"
        ))
        history.add_version(ModelVersion(
            version="v2.0.0",
            deployed_at=datetime.utcnow() - timedelta(hours=1),
            traffic_percent=100,
            accuracy=0.82,
            error_rate=0.005,
            is_active=True,
            deployment_id="d3",
            previous_version="v1.5.0"
        ))
        return history
    
    @pytest.fixture
    def traffic_switcher(self):
        return TrafficSwitcher()
    
    @pytest.fixture
    def health_verifier(self):
        return HealthVerifier()
    
    @pytest.fixture
    def rollback_manager(self, version_history, traffic_switcher, health_verifier):
        return QuickRollbackManager(
            version_history,
            traffic_switcher,
            health_verifier,
            rollback_timeout_ms=5000
        )
    
    @pytest.mark.asyncio
    async def test_rollback_to_previous_version(self, rollback_manager):
        """Test rollback to previous version."""
        record = await rollback_manager.rollback(reason=RollbackReason.MANUAL)
        
        assert record.status in [RollbackStatus.COMPLETED, RollbackStatus.VERIFIED]
        assert record.from_version == "v2.0.0"
        assert record.to_version == "v1.5.0"
    
    @pytest.mark.asyncio
    async def test_rollback_to_specific_version(self, rollback_manager):
        """Test rollback to specific version."""
        record = await rollback_manager.rollback(
            target_version="v1.0.0",
            reason=RollbackReason.MANUAL
        )
        
        assert record.status in [RollbackStatus.COMPLETED, RollbackStatus.VERIFIED]
        assert record.to_version == "v1.0.0"
    
    @pytest.mark.asyncio
    async def test_rollback_is_fast(self, rollback_manager):
        """Test rollback completes quickly."""
        start = time.time()
        record = await rollback_manager.rollback()
        elapsed_ms = (time.time() - start) * 1000
        
        assert elapsed_ms < 1000  # Should complete in under 1 second
        assert record.duration_ms < 1000
    
    @pytest.mark.asyncio
    async def test_traffic_switched(self, rollback_manager, traffic_switcher):
        """Test traffic is switched after rollback."""
        await rollback_manager.rollback()
        
        split = traffic_switcher.get_current_split()
        assert "v1.5.0" in split
        assert split.get("v1.5.0", 0) == 100.0
    
    @pytest.mark.asyncio
    async def test_version_status_updated(self, rollback_manager, version_history):
        """Test version status is updated after rollback."""
        await rollback_manager.rollback()
        
        # v2.0.0 should no longer be active
        v2 = version_history.get_version("v2.0.0")
        assert v2.is_active is False
        
        # v1.5.0 should now be active
        v15 = version_history.get_version("v1.5.0")
        assert v15.is_active is True
    
    @pytest.mark.asyncio
    async def test_rollback_is_verified(self, rollback_manager, health_verifier):
        """Test rollback health is verified."""
        record = await rollback_manager.rollback()
        
        # Health verifier should have been called
        assert health_verifier.checks_performed >= 1
        
        # Record should show verification status
        if record.status == RollbackStatus.VERIFIED:
            assert record.verified is True
    
    @pytest.mark.asyncio
    async def test_rollback_history_recorded(self, rollback_manager):
        """Test rollback is recorded in history."""
        await rollback_manager.rollback()
        
        history = rollback_manager.get_rollback_history()
        assert len(history) >= 1
        
        last = rollback_manager.get_last_rollback()
        assert last is not None
        assert last.rollback_id is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_rollback_blocked(self, rollback_manager):
        """Test concurrent rollback is blocked."""
        # Start first rollback
        task1 = asyncio.create_task(rollback_manager.rollback())
        
        # Try second rollback immediately
        await asyncio.sleep(0.01)
        
        with pytest.raises(RuntimeError, match="already in progress"):
            await rollback_manager.rollback()
        
        # Wait for first to complete
        await task1
    
    @pytest.mark.asyncio
    async def test_rollback_to_nonexistent_version_fails(self, rollback_manager):
        """Test rollback to nonexistent version fails."""
        record = await rollback_manager.rollback(
            target_version="v99.0.0",
            reason=RollbackReason.MANUAL
        )
        
        assert record.status == RollbackStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_rollback_reason_recorded(self, rollback_manager):
        """Test rollback reason is recorded."""
        record = await rollback_manager.rollback(reason=RollbackReason.ERROR_RATE_EXCEEDED)
        
        assert record.reason == RollbackReason.ERROR_RATE_EXCEEDED
    
    @pytest.mark.asyncio
    async def test_one_command_rollback(self, rollback_manager):
        """Test single command triggers complete rollback."""
        # This should complete the entire rollback in one call
        record = await rollback_manager.rollback()
        
        # Should be complete
        assert record.status in [RollbackStatus.COMPLETED, RollbackStatus.VERIFIED]
        assert record.completed_at is not None
        assert record.duration_ms > 0


# CLI interface
async def cli_rollback(target_version: Optional[str] = None, reason: str = "manual"):
    """CLI command for quick rollback."""
    # Initialize components
    version_history = VersionHistory()
    version_history.add_version(ModelVersion(
        version="v1.0.0",
        deployed_at=datetime.utcnow() - timedelta(days=7),
        traffic_percent=0,
        accuracy=0.75,
        error_rate=0.01,
        is_active=False,
        deployment_id="d1"
    ))
    version_history.add_version(ModelVersion(
        version="v2.0.0",
        deployed_at=datetime.utcnow() - timedelta(hours=1),
        traffic_percent=100,
        accuracy=0.82,
        error_rate=0.005,
        is_active=True,
        deployment_id="d2",
        previous_version="v1.0.0"
    ))
    
    traffic_switcher = TrafficSwitcher()
    health_verifier = HealthVerifier()
    rollback_manager = QuickRollbackManager(
        version_history,
        traffic_switcher,
        health_verifier
    )
    
    # Execute rollback
    reason_enum = RollbackReason.MANUAL if reason == "manual" else RollbackReason[reason.upper()]
    
    print(f"\n{'='*60}")
    print("QUICK ROLLBACK")
    print(f"{'='*60}")
    
    record = await rollback_manager.rollback(target_version, reason_enum)
    
    print(f"\nRollback ID: {record.rollback_id}")
    print(f"From: {record.from_version}")
    print(f"To: {record.to_version}")
    print(f"Reason: {record.reason.value}")
    print(f"Status: {record.status.value}")
    print(f"Duration: {record.duration_ms}ms")
    print(f"Verified: {record.verified}")
    
    if record.details:
        print(f"Details: {record.details}")
    
    print(f"{'='*60}\n")
    
    return record


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--target":
            target = sys.argv[2] if len(sys.argv) > 2 else None
            reason = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--reason" else "manual"
            asyncio.run(cli_rollback(target, reason))
        elif sys.argv[1] == "test":
            pytest.main([__file__, "-v", "--tb=short"])
    else:
        asyncio.run(cli_rollback())
