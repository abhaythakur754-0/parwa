"""
Week 54: Patch Manager
Patch management system for enterprise security hardening
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid


class PatchStatus(str, Enum):
    """Status of a patch"""
    AVAILABLE = "AVAILABLE"
    DOWNLOADED = "DOWNLOADED"
    INSTALLED = "INSTALLED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    SCHEDULED = "SCHEDULED"
    DEFERRED = "DEFERRED"


class PatchSeverity(str, Enum):
    """Severity level of a patch"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    OPTIONAL = "OPTIONAL"


class PatchType(str, Enum):
    """Type of patch"""
    SECURITY = "security"
    BUGFIX = "bugfix"
    FEATURE = "feature"
    CUMULATIVE = "cumulative"
    HOTFIX = "hotfix"


@dataclass
class Patch:
    """Represents a software patch"""
    patch_id: str
    name: str
    version: str
    severity: PatchSeverity
    description: str
    patch_type: PatchType
    affected_components: List[str]
    release_date: datetime
    cve_ids: List[str] = field(default_factory=list)
    kb_article: Optional[str] = None
    download_url: Optional[str] = None
    file_size_mb: float = 0.0
    reboot_required: bool = False
    dependencies: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "name": self.name,
            "version": self.version,
            "severity": self.severity.value,
            "description": self.description,
            "patch_type": self.patch_type.value,
            "affected_components": self.affected_components,
            "release_date": self.release_date.isoformat(),
            "cve_ids": self.cve_ids,
            "kb_article": self.kb_article,
            "download_url": self.download_url,
            "file_size_mb": self.file_size_mb,
            "reboot_required": self.reboot_required,
            "dependencies": self.dependencies,
            "superseded_by": self.superseded_by,
            "metadata": self.metadata
        }


@dataclass
class PatchInstallation:
    """Record of a patch installation attempt"""
    installation_id: str
    patch_id: str
    system_id: str
    status: PatchStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    installed_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "installation_id": self.installation_id,
            "patch_id": self.patch_id,
            "system_id": self.system_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "installed_by": self.installed_by,
            "metadata": self.metadata
        }


@dataclass
class PatchSchedule:
    """Schedule for patch deployment"""
    schedule_id: str
    name: str
    patch_ids: List[str]
    target_systems: List[str]
    scheduled_time: datetime
    maintenance_window: timedelta
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    approval_required: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "patch_ids": self.patch_ids,
            "target_systems": self.target_systems,
            "scheduled_time": self.scheduled_time.isoformat(),
            "maintenance_window_minutes": self.maintenance_window.total_seconds() / 60,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None
        }


class PatchManager:
    """
    Patch Management System for enterprise security hardening.
    Manages patch lifecycle including discovery, scheduling, deployment, and rollback.
    """

    def __init__(self, system_id: str = "default"):
        self.system_id = system_id
        self.patches: Dict[str, Patch] = {}
        self.installations: Dict[str, PatchInstallation] = {}
        self.schedules: Dict[str, PatchSchedule] = {}
        self._installation_history: List[PatchInstallation] = []
        self._initialize_sample_patches()

    def _initialize_sample_patches(self) -> None:
        """Initialize with sample patches for testing"""
        sample_patches = [
            Patch(
                patch_id="patch_001",
                name="Security Update for Log4j",
                version="2.17.1",
                severity=PatchSeverity.CRITICAL,
                description="Addresses CVE-2021-44228 (Log4Shell) vulnerability",
                patch_type=PatchType.SECURITY,
                affected_components=["log4j-core", "log4j-api"],
                release_date=datetime(2021, 12, 17),
                cve_ids=["CVE-2021-44228"],
                kb_article="KB500001",
                reboot_required=False,
                file_size_mb=15.2
            ),
            Patch(
                patch_id="patch_002",
                name="Spring Framework Security Fix",
                version="5.3.18",
                severity=PatchSeverity.CRITICAL,
                description="Addresses Spring4Shell vulnerability",
                patch_type=PatchType.SECURITY,
                affected_components=["spring-core", "spring-web"],
                release_date=datetime(2022, 3, 31),
                cve_ids=["CVE-2022-22965"],
                kb_article="KB500002",
                reboot_required=False,
                file_size_mb=45.5
            ),
            Patch(
                patch_id="patch_003",
                name="OpenSSL Security Update",
                version="3.0.3",
                severity=PatchSeverity.HIGH,
                description="Fixes multiple security vulnerabilities in OpenSSL",
                patch_type=PatchType.SECURITY,
                affected_components=["openssl", "libssl"],
                release_date=datetime(2022, 5, 3),
                cve_ids=["CVE-2022-0778", "CVE-2022-1292"],
                kb_article="KB500003",
                reboot_required=True,
                file_size_mb=8.7
            ),
            Patch(
                patch_id="patch_004",
                name="Kernel Security Update",
                version="5.15.45",
                severity=PatchSeverity.HIGH,
                description="Kernel security and bug fixes",
                patch_type=PatchType.SECURITY,
                affected_components=["linux-kernel"],
                release_date=datetime(2022, 6, 15),
                cve_ids=["CVE-2022-1011", "CVE-2022-1419"],
                kb_article="KB500004",
                reboot_required=True,
                file_size_mb=120.5
            ),
            Patch(
                patch_id="patch_005",
                name="Application Bug Fix Bundle",
                version="2.1.5",
                severity=PatchSeverity.MEDIUM,
                description="Collection of bug fixes for application stability",
                patch_type=PatchType.BUGFIX,
                affected_components=["app-core", "app-ui"],
                release_date=datetime(2022, 7, 1),
                cve_ids=[],
                kb_article="KB500005",
                reboot_required=False,
                file_size_mb=25.0
            ),
        ]
        for patch in sample_patches:
            self.patches[patch.patch_id] = patch

    def check_updates(self, component: Optional[str] = None) -> List[Patch]:
        """
        Check for available patches/updates.
        
        Args:
            component: Optional specific component to check
            
        Returns:
            List of available patches
        """
        available = []
        for patch in self.patches.values():
            # Skip already installed patches
            installed = any(
                inst.patch_id == patch.patch_id and inst.status == PatchStatus.INSTALLED
                for inst in self.installations.values()
            )
            if installed:
                continue
                
            if component:
                if component in patch.affected_components:
                    available.append(patch)
            else:
                available.append(patch)
        
        # Sort by severity
        severity_order = [PatchSeverity.CRITICAL, PatchSeverity.HIGH, 
                         PatchSeverity.MEDIUM, PatchSeverity.LOW]
        available.sort(key=lambda p: severity_order.index(p.severity) 
                      if p.severity in severity_order else 99)
        
        return available

    def apply_patch(self, patch_id: str, system_id: Optional[str] = None,
                   scheduled: bool = False) -> PatchInstallation:
        """
        Apply a patch to a system.
        
        Args:
            patch_id: ID of the patch to apply
            system_id: Target system (defaults to self.system_id)
            scheduled: Whether this is a scheduled installation
            
        Returns:
            PatchInstallation record
        """
        target_system = system_id or self.system_id
        
        if patch_id not in self.patches:
            raise ValueError(f"Patch {patch_id} not found")
        
        patch = self.patches[patch_id]
        
        # Check dependencies
        for dep_id in patch.dependencies:
            if dep_id not in self.patches:
                continue
            dep_installed = any(
                inst.patch_id == dep_id and inst.status == PatchStatus.INSTALLED
                for inst in self.installations.values()
            )
            if not dep_installed:
                raise ValueError(f"Dependency {dep_id} not installed")
        
        installation_id = f"inst_{uuid.uuid4().hex[:8]}"
        installation = PatchInstallation(
            installation_id=installation_id,
            patch_id=patch_id,
            system_id=target_system,
            status=PatchStatus.AVAILABLE,
            started_at=datetime.utcnow()
        )
        
        self.installations[installation_id] = installation
        
        try:
            # Simulate patch installation
            installation.status = PatchStatus.DOWNLOADED
            
            # Simulate installation process
            if self._simulate_installation(patch):
                installation.status = PatchStatus.INSTALLED
                installation.completed_at = datetime.utcnow()
                installation.installed_by = "patch_manager"
            else:
                installation.status = PatchStatus.FAILED
                installation.error_message = "Installation failed - unknown error"
                installation.completed_at = datetime.utcnow()
                
        except Exception as e:
            installation.status = PatchStatus.FAILED
            installation.error_message = str(e)
            installation.completed_at = datetime.utcnow()
        
        self._installation_history.append(installation)
        return installation

    def _simulate_installation(self, patch: Patch) -> bool:
        """Simulate patch installation (returns success for most cases)"""
        # Simulate success for most patches, failure for some edge cases
        return True

    def rollback_patch(self, installation_id: str) -> PatchInstallation:
        """
        Rollback a previously installed patch.
        
        Args:
            installation_id: ID of the installation to rollback
            
        Returns:
            Updated PatchInstallation record
        """
        if installation_id not in self.installations:
            raise ValueError(f"Installation {installation_id} not found")
        
        installation = self.installations[installation_id]
        
        if installation.status != PatchStatus.INSTALLED:
            raise ValueError(f"Cannot rollback patch with status {installation.status}")
        
        try:
            # Simulate rollback
            installation.status = PatchStatus.ROLLED_BACK
            installation.completed_at = datetime.utcnow()
            installation.metadata["rollback_time"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            installation.status = PatchStatus.FAILED
            installation.error_message = f"Rollback failed: {str(e)}"
        
        return installation

    def schedule_patch(self, patch_ids: List[str], target_systems: List[str],
                      scheduled_time: datetime, maintenance_window_minutes: int = 60,
                      name: Optional[str] = None) -> PatchSchedule:
        """
        Schedule patches for deployment.
        
        Args:
            patch_ids: List of patch IDs to deploy
            target_systems: List of target system IDs
            scheduled_time: When to deploy
            maintenance_window_minutes: Duration of maintenance window
            name: Schedule name
            
        Returns:
            PatchSchedule record
        """
        # Validate patches exist
        for patch_id in patch_ids:
            if patch_id not in self.patches:
                raise ValueError(f"Patch {patch_id} not found")
        
        schedule_id = f"schedule_{uuid.uuid4().hex[:8]}"
        schedule = PatchSchedule(
            schedule_id=schedule_id,
            name=name or f"Scheduled Patch Deployment {schedule_id}",
            patch_ids=patch_ids,
            target_systems=target_systems,
            scheduled_time=scheduled_time,
            maintenance_window=timedelta(minutes=maintenance_window_minutes)
        )
        
        self.schedules[schedule_id] = schedule
        return schedule

    def approve_schedule(self, schedule_id: str, approver: str) -> PatchSchedule:
        """Approve a scheduled patch deployment"""
        if schedule_id not in self.schedules:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        schedule = self.schedules[schedule_id]
        schedule.approved_by = approver
        schedule.approved_at = datetime.utcnow()
        schedule.status = "approved"
        
        return schedule

    def execute_schedule(self, schedule_id: str) -> List[PatchInstallation]:
        """Execute a scheduled patch deployment"""
        if schedule_id not in self.schedules:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        schedule = self.schedules[schedule_id]
        
        if schedule.approval_required and not schedule.approved_by:
            raise ValueError("Schedule requires approval before execution")
        
        installations = []
        for system_id in schedule.target_systems:
            for patch_id in schedule.patch_ids:
                try:
                    inst = self.apply_patch(patch_id, system_id, scheduled=True)
                    installations.append(inst)
                except Exception as e:
                    inst = PatchInstallation(
                        installation_id=f"inst_{uuid.uuid4().hex[:8]}",
                        patch_id=patch_id,
                        system_id=system_id,
                        status=PatchStatus.FAILED,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        error_message=str(e)
                    )
                    installations.append(inst)
        
        schedule.status = "completed"
        return installations

    def get_patch_history(self, system_id: Optional[str] = None,
                         patch_id: Optional[str] = None) -> List[PatchInstallation]:
        """
        Get patch installation history.
        
        Args:
            system_id: Filter by system
            patch_id: Filter by patch
            
        Returns:
            List of installation records
        """
        history = self._installation_history
        
        if system_id:
            history = [h for h in history if h.system_id == system_id]
        if patch_id:
            history = [h for h in history if h.patch_id == patch_id]
        
        return sorted(history, key=lambda h: h.started_at, reverse=True)

    def get_pending_patches(self) -> List[Patch]:
        """Get patches pending installation"""
        return self.check_updates()

    def get_installed_patches(self) -> List[Patch]:
        """Get successfully installed patches"""
        installed_ids = {
            inst.patch_id for inst in self.installations.values()
            if inst.status == PatchStatus.INSTALLED
        }
        return [self.patches[pid] for pid in installed_ids if pid in self.patches]

    def get_failed_installations(self) -> List[PatchInstallation]:
        """Get failed installation attempts"""
        return [i for i in self.installations.values() if i.status == PatchStatus.FAILED]

    def get_rolled_back_patches(self) -> List[PatchInstallation]:
        """Get rolled back installations"""
        return [i for i in self.installations.values() if i.status == PatchStatus.ROLLED_BACK]

    def get_scheduled_deployments(self) -> List[PatchSchedule]:
        """Get pending scheduled deployments"""
        return [s for s in self.schedules.values() if s.status == "pending"]

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get patch compliance status"""
        total_patches = len(self.patches)
        installed_count = len(self.get_installed_patches())
        pending_critical = len([p for p in self.get_pending_patches() 
                               if p.severity == PatchSeverity.CRITICAL])
        pending_high = len([p for p in self.get_pending_patches() 
                           if p.severity == PatchSeverity.HIGH])
        
        compliance_score = (installed_count / total_patches * 100) if total_patches > 0 else 100
        
        return {
            "compliance_score": compliance_score,
            "total_patches": total_patches,
            "installed_patches": installed_count,
            "pending_patches": total_patches - installed_count,
            "pending_critical": pending_critical,
            "pending_high": pending_high,
            "failed_installations": len(self.get_failed_installations()),
            "rolled_back": len(self.get_rolled_back_patches()),
            "status": "compliant" if compliance_score >= 90 else "non-compliant"
        }

    def get_patch_by_cve(self, cve_id: str) -> List[Patch]:
        """Find patches that address a specific CVE"""
        return [p for p in self.patches.values() if cve_id in p.cve_ids]

    def get_system_patch_status(self, system_id: str) -> Dict[str, Any]:
        """Get patch status for a specific system"""
        system_installations = [
            i for i in self.installations.values() if i.system_id == system_id
        ]
        
        installed = [i for i in system_installations if i.status == PatchStatus.INSTALLED]
        failed = [i for i in system_installations if i.status == PatchStatus.FAILED]
        rolled_back = [i for i in system_installations if i.status == PatchStatus.ROLLED_BACK]
        
        return {
            "system_id": system_id,
            "installed_count": len(installed),
            "failed_count": len(failed),
            "rolled_back_count": len(rolled_back),
            "last_installation": max([i.started_at for i in system_installations]) if system_installations else None,
            "installations": [i.to_dict() for i in system_installations]
        }

    def add_patch(self, patch: Patch) -> None:
        """Add a new patch to the repository"""
        self.patches[patch.patch_id] = patch

    def remove_patch(self, patch_id: str) -> bool:
        """Remove a patch from the repository"""
        if patch_id in self.patches:
            del self.patches[patch_id]
            return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Get overall patch management summary"""
        return {
            "total_patches": len(self.patches),
            "installed": len(self.get_installed_patches()),
            "pending": len(self.get_pending_patches()),
            "failed": len(self.get_failed_installations()),
            "rolled_back": len(self.get_rolled_back_patches()),
            "scheduled_deployments": len(self.get_scheduled_deployments()),
            "compliance": self.get_compliance_status()
        }
