"""
Week 60 - Builder 5: System Validator Module
System validation, dependency checking, and readiness validation
"""

import time
import threading
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """Check status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


class ReadinessCategory(Enum):
    """Readiness categories"""
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"


@dataclass
class SystemCheck:
    """System check result"""
    name: str
    category: str
    status: CheckStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Dependency:
    """Dependency information"""
    name: str
    current_version: str
    required_version: str = ""
    latest_version: str = ""
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReadinessCheck:
    """Readiness check item"""
    category: ReadinessCategory
    name: str
    description: str
    required: bool = True
    status: CheckStatus = CheckStatus.SKIP
    notes: str = ""


class SystemValidator:
    """
    System validator for checks, health, and compliance
    """

    def __init__(self):
        self.checks: List[SystemCheck] = []
        self.check_registry: Dict[str, callable] = {}
        self.results: Dict[str, List[SystemCheck]] = defaultdict(list)
        self.lock = threading.Lock()

    def register_check(self, name: str, category: str,
                       check_func: callable) -> None:
        """Register a system check"""
        with self.lock:
            self.check_registry[name] = {
                "func": check_func,
                "category": category
            }

    def run_check(self, name: str) -> Optional[SystemCheck]:
        """Run a single check"""
        check_info = self.check_registry.get(name)
        if not check_info:
            return None

        try:
            status, message, details = check_info["func"]()
            check = SystemCheck(
                name=name,
                category=check_info["category"],
                status=status,
                message=message,
                details=details
            )
        except Exception as e:
            check = SystemCheck(
                name=name,
                category=check_info["category"],
                status=CheckStatus.FAIL,
                message=str(e)
            )

        with self.lock:
            self.checks.append(check)
            self.results[name].append(check)

        return check

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered checks"""
        results = {
            "timestamp": time.time(),
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "skipped": 0,
            "checks": []
        }

        for name in self.check_registry.keys():
            check = self.run_check(name)
            if check:
                results["total"] += 1
                results["checks"].append({
                    "name": check.name,
                    "category": check.category,
                    "status": check.status.value,
                    "message": check.message
                })

                if check.status == CheckStatus.PASS:
                    results["passed"] += 1
                elif check.status == CheckStatus.FAIL:
                    results["failed"] += 1
                elif check.status == CheckStatus.WARNING:
                    results["warnings"] += 1
                else:
                    results["skipped"] += 1

        return results

    def get_results(self, name: str = None) -> List[SystemCheck]:
        """Get check results"""
        if name:
            return self.results.get(name, [])
        return self.checks

    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        summary = defaultdict(lambda: {"pass": 0, "fail": 0, "warning": 0, "skip": 0})

        for check in self.checks:
            summary[check.category][check.status.value] += 1

        return dict(summary)


class DependencyChecker:
    """
    Dependency checker for versions and vulnerabilities
    """

    def __init__(self):
        self.dependencies: Dict[str, Dependency] = {}
        self.vulnerability_db: Dict[str, List[Dict[str, Any]]] = {}
        self.lock = threading.Lock()

    def register_dependency(self, name: str, current_version: str,
                           required_version: str = "",
                           latest_version: str = "") -> Dependency:
        """Register a dependency"""
        dep = Dependency(
            name=name,
            current_version=current_version,
            required_version=required_version,
            latest_version=latest_version or current_version
        )

        with self.lock:
            self.dependencies[name] = dep

        return dep

    def check_versions(self) -> Dict[str, Any]:
        """Check for outdated dependencies"""
        results = {
            "total": len(self.dependencies),
            "outdated": 0,
            "up_to_date": 0,
            "dependencies": []
        }

        for name, dep in self.dependencies.items():
            is_outdated = False

            if dep.latest_version and dep.current_version != dep.latest_version:
                is_outdated = True

            if dep.required_version:
                if not self._version_satisfies(dep.current_version, dep.required_version):
                    is_outdated = True

            results["dependencies"].append({
                "name": name,
                "current": dep.current_version,
                "required": dep.required_version,
                "latest": dep.latest_version,
                "outdated": is_outdated
            })

            if is_outdated:
                results["outdated"] += 1
            else:
                results["up_to_date"] += 1

        return results

    def check_vulnerabilities(self) -> Dict[str, Any]:
        """Check for known vulnerabilities"""
        results = {
            "total_checked": len(self.dependencies),
            "vulnerable": 0,
            "secure": 0,
            "vulnerabilities": []
        }

        for name, dep in self.dependencies.items():
            vulns = self.vulnerability_db.get(f"{name}@{dep.current_version}", [])

            if vulns:
                results["vulnerable"] += 1
                results["vulnerabilities"].append({
                    "dependency": name,
                    "version": dep.current_version,
                    "vulnerabilities": vulns
                })
                dep.vulnerabilities = vulns
            else:
                results["secure"] += 1

        return results

    def add_vulnerability(self, package: str, version: str,
                          vuln_id: str, severity: str,
                          description: str = "") -> None:
        """Add vulnerability to database"""
        key = f"{package}@{version}"
        with self.lock:
            if key not in self.vulnerability_db:
                self.vulnerability_db[key] = []
            self.vulnerability_db[key].append({
                "id": vuln_id,
                "severity": severity,
                "description": description
            })

    def _version_satisfies(self, current: str, required: str) -> bool:
        """Check if version satisfies requirement"""
        # Simplified version check
        if required.startswith(">="):
            return current >= required[2:]
        elif required.startswith(">"):
            return current > required[1:]
        elif required.startswith("<="):
            return current <= required[2:]
        elif required.startswith("<"):
            return current < required[1:]
        return current == required

    def get_dependency(self, name: str) -> Optional[Dependency]:
        """Get dependency by name"""
        return self.dependencies.get(name)

    def list_dependencies(self) -> List[str]:
        """List all dependency names"""
        return list(self.dependencies.keys())


class ReadinessChecker:
    """
    Production readiness checker
    """

    def __init__(self):
        self.checklist: List[ReadinessCheck] = []
        self.results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def add_check(self, category: ReadinessCategory, name: str,
                  description: str, required: bool = True) -> None:
        """Add a readiness check"""
        check = ReadinessCheck(
            category=category,
            name=name,
            description=description,
            required=required
        )

        with self.lock:
            self.checklist.append(check)

    def run_checklist(self) -> Dict[str, Any]:
        """Run all readiness checks"""
        results = {
            "timestamp": time.time(),
            "ready": True,
            "categories": {},
            "checks": []
        }

        category_results = defaultdict(lambda: {"pass": 0, "fail": 0, "warning": 0, "required_fails": 0})

        for check in self.checklist:
            # Simulate check execution
            status = CheckStatus.PASS  # Default to pass for demo

            check.status = status
            check.notes = f"Checked at {time.time()}"

            results["checks"].append({
                "category": check.category.value,
                "name": check.name,
                "description": check.description,
                "required": check.required,
                "status": check.status.value
            })

            category_results[check.category.value][check.status.value] += 1
            if check.required and check.status == CheckStatus.FAIL:
                category_results[check.category.value]["required_fails"] += 1
                results["ready"] = False

        results["categories"] = dict(category_results)

        with self.lock:
            self.results[f"checklist-{int(time.time())}"] = results

        return results

    def get_results(self, run_id: str = None) -> Optional[Dict[str, Any]]:
        """Get readiness results"""
        if run_id:
            return self.results.get(run_id)
        if self.results:
            return list(self.results.values())[-1]
        return None

    def get_category_status(self, category: ReadinessCategory) -> Dict[str, Any]:
        """Get status for a specific category"""
        checks = [c for c in self.checklist if c.category == category]

        return {
            "category": category.value,
            "total": len(checks),
            "passed": sum(1 for c in checks if c.status == CheckStatus.PASS),
            "failed": sum(1 for c in checks if c.status == CheckStatus.FAIL)
        }

    def is_ready(self) -> bool:
        """Check if system is ready"""
        for check in self.checklist:
            if check.required and check.status == CheckStatus.FAIL:
                return False
        return True

    def clear_checklist(self) -> None:
        """Clear the checklist"""
        with self.lock:
            self.checklist.clear()
