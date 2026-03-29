"""
Week 59 - Builder 2: Quality Assurance Module
QA manager, code review, and defect tracking
"""

import time
import threading
import hashlib
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import re

logger = logging.getLogger(__name__)


class QACheckStatus(Enum):
    """QA check status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class DefectSeverity(Enum):
    """Defect severity levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    TRIVIAL = 5


class DefectStatus(Enum):
    """Defect lifecycle status"""
    NEW = "new"
    CONFIRMED = "confirmed"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    CLOSED = "closed"
    REOPENED = "reopened"


@dataclass
class QACheck:
    """QA check item"""
    id: str
    name: str
    category: str
    description: str = ""
    status: QACheckStatus = QACheckStatus.PENDING
    reviewer: str = ""
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Defect:
    """Defect record"""
    id: str
    title: str
    description: str
    severity: DefectSeverity
    status: DefectStatus = DefectStatus.NEW
    assignee: str = ""
    reporter: str = ""
    component: str = ""
    tags: List[str] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None


@dataclass
class CodeReview:
    """Code review record"""
    id: str
    file_path: str
    reviewer: str
    status: QACheckStatus = QACheckStatus.PENDING
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    score: int = 0
    created_at: float = field(default_factory=time.time)


class QAManager:
    """
    QA manager for workflows, checklists, and approvals
    """

    def __init__(self):
        self.checks: Dict[str, QACheck] = {}
        self.checklists: Dict[str, List[str]] = {}
        self.approvals: Dict[str, List[str]] = {}
        self.lock = threading.Lock()
        self.stats: Dict[str, int] = defaultdict(int)

    def create_check(self, name: str, category: str,
                     description: str = "") -> QACheck:
        """Create a QA check"""
        check_id = hashlib.md5(f"{name}:{time.time()}".encode()).hexdigest()[:8]
        check = QACheck(
            id=check_id,
            name=name,
            category=category,
            description=description
        )
        with self.lock:
            self.checks[check_id] = check
            self.stats["total_checks"] += 1
        return check

    def get_check(self, check_id: str) -> Optional[QACheck]:
        """Get a QA check"""
        return self.checks.get(check_id)

    def update_check_status(self, check_id: str, status: QACheckStatus,
                            reviewer: str = "", notes: str = "") -> bool:
        """Update check status"""
        check = self.checks.get(check_id)
        if not check:
            return False

        with self.lock:
            check.status = status
            check.reviewer = reviewer
            check.notes = notes
            check.updated_at = time.time()
            self.stats[status.value] += 1

        return True

    def create_checklist(self, name: str, check_ids: List[str]) -> None:
        """Create a QA checklist"""
        with self.lock:
            self.checklists[name] = check_ids

    def get_checklist(self, name: str) -> List[QACheck]:
        """Get checklist items"""
        check_ids = self.checklists.get(name, [])
        return [self.checks[cid] for cid in check_ids if cid in self.checks]

    def run_checklist(self, name: str) -> Dict[str, QACheckStatus]:
        """Run checklist and return statuses"""
        checks = self.get_checklist(name)
        return {check.id: check.status for check in checks}

    def request_approval(self, item_id: str, approvers: List[str]) -> None:
        """Request approval for an item"""
        with self.lock:
            self.approvals[item_id] = approvers

    def approve(self, item_id: str, approver: str) -> bool:
        """Record approval"""
        with self.lock:
            if item_id in self.approvals:
                if approver in self.approvals[item_id]:
                    self.approvals[item_id].remove(approver)
                    self.stats["approvals"] += 1
                    return True
        return False

    def is_approved(self, item_id: str) -> bool:
        """Check if item is fully approved"""
        approvers = self.approvals.get(item_id, [])
        return len(approvers) == 0

    def get_stats(self) -> Dict[str, int]:
        """Get QA statistics"""
        return dict(self.stats)


class CodeReviewer:
    """
    Code reviewer for analysis, suggestions, and standards
    """

    def __init__(self):
        self.reviews: Dict[str, CodeReview] = {}
        self.standards: Dict[str, List[str]] = {}
        self.lock = threading.Lock()

    def register_standard(self, name: str, rules: List[str]) -> None:
        """Register coding standards"""
        with self.lock:
            self.standards[name] = rules

    def create_review(self, file_path: str, reviewer: str) -> CodeReview:
        """Create a code review"""
        review_id = hashlib.md5(f"{file_path}:{time.time()}".encode()).hexdigest()[:8]
        review = CodeReview(
            id=review_id,
            file_path=file_path,
            reviewer=reviewer
        )
        with self.lock:
            self.reviews[review_id] = review
        return review

    def add_issue(self, review_id: str, line: int, message: str,
                  severity: str = "warning") -> bool:
        """Add an issue to a review"""
        review = self.reviews.get(review_id)
        if not review:
            return False

        with self.lock:
            review.issues.append({
                "line": line,
                "message": message,
                "severity": severity,
                "timestamp": time.time()
            })

        return True

    def add_suggestion(self, review_id: str, suggestion: str) -> bool:
        """Add a suggestion to a review"""
        review = self.reviews.get(review_id)
        if not review:
            return False

        with self.lock:
            review.suggestions.append(suggestion)

        return True

    def analyze_code(self, code: str, language: str = "python") -> List[Dict[str, Any]]:
        """Analyze code for issues"""
        issues = []

        # Simple static analysis
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for long lines
            if len(line) > 100:
                issues.append({
                    "line": i,
                    "message": "Line exceeds 100 characters",
                    "severity": "style"
                })

            # Check for TODO comments
            if "TODO" in line or "FIXME" in line:
                issues.append({
                    "line": i,
                    "message": "Unresolved TODO/FIXME comment",
                    "severity": "info"
                })

            # Python-specific checks
            if language == "python":
                # Check for bare except
                if re.search(r"except\s*:", line):
                    issues.append({
                        "line": i,
                        "message": "Bare except clause",
                        "severity": "warning"
                    })

                # Check for print statements
                if "print(" in line and "def " not in line:
                    issues.append({
                        "line": i,
                        "message": "Debug print statement",
                        "severity": "info"
                    })

        return issues

    def calculate_score(self, review_id: str) -> int:
        """Calculate review score (0-100)"""
        review = self.reviews.get(review_id)
        if not review:
            return 0

        score = 100
        for issue in review.issues:
            if issue["severity"] == "error":
                score -= 10
            elif issue["severity"] == "warning":
                score -= 5
            elif issue["severity"] == "style":
                score -= 2

        with self.lock:
            review.score = max(0, score)

        return review.score

    def get_review(self, review_id: str) -> Optional[CodeReview]:
        """Get a review by ID"""
        return self.reviews.get(review_id)


class DefectTracker:
    """
    Defect tracker for bug tracking, priorities, and lifecycle
    """

    def __init__(self):
        self.defects: Dict[str, Defect] = {}
        self.lock = threading.Lock()
        self.counters: Dict[str, int] = defaultdict(int)

    def create_defect(self, title: str, description: str,
                      severity: DefectSeverity,
                      component: str = "",
                      reporter: str = "",
                      tags: List[str] = None) -> Defect:
        """Create a new defect"""
        self.counters["defects"] += 1
        defect_id = f"DEF-{self.counters['defects']:04d}"

        defect = Defect(
            id=defect_id,
            title=title,
            description=description,
            severity=severity,
            component=component,
            reporter=reporter,
            tags=tags or []
        )

        with self.lock:
            self.defects[defect_id] = defect

        return defect

    def get_defect(self, defect_id: str) -> Optional[Defect]:
        """Get a defect by ID"""
        return self.defects.get(defect_id)

    def update_status(self, defect_id: str, status: DefectStatus,
                      assignee: str = None) -> bool:
        """Update defect status"""
        defect = self.defects.get(defect_id)
        if not defect:
            return False

        with self.lock:
            defect.status = status
            defect.updated_at = time.time()

            if assignee:
                defect.assignee = assignee

            if status == DefectStatus.RESOLVED:
                defect.resolved_at = time.time()

        return True

    def add_comment(self, defect_id: str, author: str,
                    comment: str) -> bool:
        """Add a comment to a defect"""
        defect = self.defects.get(defect_id)
        if not defect:
            return False

        with self.lock:
            defect.comments.append({
                "author": author,
                "text": comment,
                "timestamp": time.time()
            })
            defect.updated_at = time.time()

        return True

    def search_defects(self, status: DefectStatus = None,
                       severity: DefectSeverity = None,
                       component: str = None) -> List[Defect]:
        """Search defects by criteria"""
        results = []

        for defect in self.defects.values():
            match = True
            if status and defect.status != status:
                match = False
            if severity and defect.severity != severity:
                match = False
            if component and defect.component != component:
                match = False
            if match:
                results.append(defect)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get defect statistics"""
        status_counts = defaultdict(int)
        severity_counts = defaultdict(int)

        for defect in self.defects.values():
            status_counts[defect.status.value] += 1
            severity_counts[defect.severity.name] += 1

        return {
            "total": len(self.defects),
            "by_status": dict(status_counts),
            "by_severity": dict(severity_counts)
        }

    def resolve_defect(self, defect_id: str, resolution: str = "") -> bool:
        """Resolve a defect"""
        return self.update_status(defect_id, DefectStatus.RESOLVED)

    def close_defect(self, defect_id: str) -> bool:
        """Close a defect"""
        return self.update_status(defect_id, DefectStatus.CLOSED)

    def reopen_defect(self, defect_id: str, reason: str = "") -> bool:
        """Reopen a defect"""
        return self.update_status(defect_id, DefectStatus.REOPENED)
