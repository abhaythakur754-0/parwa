"""
Week 60 - Builder 3: Release Manager Module
Release management, versioning, and validation
"""

import time
import re
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ReleaseStatus(Enum):
    """Release status"""
    DRAFT = "draft"
    CANDIDATE = "candidate"
    RELEASED = "released"
    WITHDRAWN = "withdrawn"


class VersionBump(Enum):
    """Version bump types"""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass
class Release:
    """Release record"""
    version: str
    status: ReleaseStatus = ReleaseStatus.DRAFT
    changelog: List[str] = field(default_factory=list)
    release_notes: str = ""
    created_at: float = field(default_factory=time.time)
    released_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionInfo:
    """Version information"""
    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build: str = ""

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version


class ReleaseManager:
    """
    Release manager for releases, versioning, and notes
    """

    def __init__(self):
        self.releases: Dict[str, Release] = {}
        self.current_version: str = "0.0.0"
        self.lock = threading.Lock()

    def create_release(self, version: str,
                       changelog: List[str] = None,
                       notes: str = "") -> Release:
        """Create a new release"""
        release = Release(
            version=version,
            changelog=changelog or [],
            release_notes=notes
        )

        with self.lock:
            self.releases[version] = release

        return release

    def promote_release(self, version: str,
                        status: ReleaseStatus) -> bool:
        """Promote release to a new status"""
        release = self.releases.get(version)
        if not release:
            return False

        with self.lock:
            release.status = status
            if status == ReleaseStatus.RELEASED:
                release.released_at = time.time()
                self.current_version = version

        return True

    def withdraw_release(self, version: str, reason: str = "") -> bool:
        """Withdraw a release"""
        release = self.releases.get(version)
        if not release:
            return False

        with self.lock:
            release.status = ReleaseStatus.WITHDRAWN
            if reason:
                release.metadata["withdrawal_reason"] = reason

        return True

    def get_release(self, version: str) -> Optional[Release]:
        """Get release by version"""
        return self.releases.get(version)

    def get_current_version(self) -> str:
        """Get current released version"""
        return self.current_version

    def list_releases(self, status: ReleaseStatus = None) -> List[Release]:
        """List releases, optionally filtered by status"""
        releases = list(self.releases.values())
        if status:
            releases = [r for r in releases if r.status == status]
        return sorted(releases, key=lambda r: r.created_at, reverse=True)

    def add_changelog_entry(self, version: str, entry: str) -> bool:
        """Add changelog entry to release"""
        release = self.releases.get(version)
        if not release:
            return False

        with self.lock:
            release.changelog.append(entry)

        return True


class VersionManager:
    """
    Version manager for semantic versioning
    """

    def __init__(self):
        self.versions: Dict[str, VersionInfo] = {}
        self.tags: Dict[str, str] = {}  # tag -> version
        self.lock = threading.Lock()

    def parse_version(self, version_str: str) -> Optional[VersionInfo]:
        """Parse version string into VersionInfo"""
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9]+))?(?:\+([a-zA-Z0-9]+))?$"
        match = re.match(pattern, version_str)

        if not match:
            return None

        return VersionInfo(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build=match.group(5) or ""
        )

    def bump_version(self, current: str, bump_type: VersionBump) -> str:
        """Bump version according to type"""
        version = self.parse_version(current)
        if not version:
            return current

        if bump_type == VersionBump.MAJOR:
            version.major += 1
            version.minor = 0
            version.patch = 0
        elif bump_type == VersionBump.MINOR:
            version.minor += 1
            version.patch = 0
        else:  # PATCH
            version.patch += 1

        version.prerelease = ""
        version.build = ""

        return str(version)

    def compare_versions(self, v1: str, v2: str) -> int:
        """Compare two versions. Returns -1, 0, or 1"""
        ver1 = self.parse_version(v1)
        ver2 = self.parse_version(v2)

        if not ver1 or not ver2:
            return 0

        if ver1.major != ver2.major:
            return -1 if ver1.major < ver2.major else 1
        if ver1.minor != ver2.minor:
            return -1 if ver1.minor < ver2.minor else 1
        if ver1.patch != ver2.patch:
            return -1 if ver1.patch < ver2.patch else 1

        return 0

    def register_version(self, version: str) -> bool:
        """Register a version"""
        version_info = self.parse_version(version)
        if not version_info:
            return False

        with self.lock:
            self.versions[version] = version_info

        return True

    def create_tag(self, tag: str, version: str) -> bool:
        """Create a tag for a version"""
        if version not in self.versions:
            return False

        with self.lock:
            self.tags[tag] = version

        return True

    def get_version(self, version: str) -> Optional[VersionInfo]:
        """Get version info"""
        return self.versions.get(version)

    def get_tag_version(self, tag: str) -> Optional[str]:
        """Get version for a tag"""
        return self.tags.get(tag)

    def list_versions(self) -> List[str]:
        """List all registered versions"""
        return list(self.versions.keys())


class ReleaseValidator:
    """
    Release validator for checks and sign-offs
    """

    def __init__(self):
        self.checks: List[Dict[str, Any]] = []
        self.signoffs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def register_check(self, name: str, check_func: callable,
                       required: bool = True) -> None:
        """Register a release check"""
        with self.lock:
            self.checks.append({
                "name": name,
                "func": check_func,
                "required": required
            })

    def run_checks(self, version: str) -> Dict[str, Any]:
        """Run all release checks"""
        results = {
            "version": version,
            "timestamp": time.time(),
            "passed": True,
            "checks": []
        }

        for check in self.checks:
            try:
                passed = check["func"](version)
                results["checks"].append({
                    "name": check["name"],
                    "passed": passed,
                    "required": check["required"]
                })
                if not passed and check["required"]:
                    results["passed"] = False
            except Exception as e:
                results["checks"].append({
                    "name": check["name"],
                    "passed": False,
                    "error": str(e),
                    "required": check["required"]
                })
                if check["required"]:
                    results["passed"] = False

        with self.lock:
            self.results[f"checks-{version}"] = results

        return results

    def request_signoff(self, version: str, approver: str) -> None:
        """Request a sign-off"""
        with self.lock:
            self.signoffs[version].append({
                "approver": approver,
                "status": "pending",
                "requested_at": time.time()
            })

    def provide_signoff(self, version: str, approver: str,
                        approved: bool, notes: str = "") -> bool:
        """Provide a sign-off"""
        with self.lock:
            for signoff in self.signoffs.get(version, []):
                if signoff["approver"] == approver:
                    signoff["status"] = "approved" if approved else "rejected"
                    signoff["notes"] = notes
                    signoff["signed_at"] = time.time()
                    return True
        return False

    def get_signoffs(self, version: str) -> List[Dict[str, Any]]:
        """Get sign-offs for a version"""
        return self.signoffs.get(version, [])

    def is_approved(self, version: str) -> bool:
        """Check if all sign-offs are approved"""
        signoffs = self.signoffs.get(version, [])
        if not signoffs:
            return True  # No sign-offs required

        return all(s["status"] == "approved" for s in signoffs)

    def get_result(self, version: str) -> Optional[Dict[str, Any]]:
        """Get validation result"""
        return self.results.get(f"checks-{version}")
