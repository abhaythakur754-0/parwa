"""Error Tracker for PARWA - Week 19 Builder 3"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from pathlib import Path
import threading


@dataclass
class ErrorRecord:
    """Single error record"""
    error_id: str
    error_type: str
    message: str
    timestamp: str
    client_id: str
    severity: str  # low, medium, high, critical
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_notes: Optional[str] = None


class ErrorTracker:
    """Tracks and categorizes errors for PARWA"""

    SEVERITY_LEVELS = ["low", "medium", "high", "critical"]
    ERROR_CATEGORIES = {
        "timeout": "Performance",
        "rate_limit": "Rate Limiting",
        "invalid_input": "Validation",
        "not_found": "Resource",
        "permission": "Authorization",
        "database": "Database",
        "api": "External API",
        "internal": "Internal",
    }

    def __init__(self, client_id: str = "system"):
        self.client_id = client_id
        self._lock = threading.Lock()
        self._errors: List[ErrorRecord] = []
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._category_counts: Dict[str, int] = defaultdict(int)
        self._severity_counts: Dict[str, int] = defaultdict(int)
        self._alert_callbacks: List[callable] = []

    def record_error(
        self,
        error_type: str,
        message: str,
        severity: str = "medium",
        context: Optional[Dict] = None
    ) -> ErrorRecord:
        """Record an error"""
        if severity not in self.SEVERITY_LEVELS:
            severity = "medium"

        error_id = f"err_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._errors)}"
        
        record = ErrorRecord(
            error_id=error_id,
            error_type=error_type,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            client_id=self.client_id,
            severity=severity,
            context=context or {}
        )

        with self._lock:
            self._errors.append(record)
            self._error_counts[error_type] += 1
            self._category_counts[self.ERROR_CATEGORIES.get(error_type, "Internal")] += 1
            self._severity_counts[severity] += 1

        # Alert on critical errors
        if severity == "critical":
            self._trigger_alert(record)

        return record

    def get_error_frequency(self, error_type: Optional[str] = None) -> Dict[str, int]:
        """Get error frequency by type"""
        with self._lock:
            if error_type:
                return {error_type: self._error_counts.get(error_type, 0)}
            return dict(self._error_counts)

    def get_errors_by_severity(self, severity: str) -> List[ErrorRecord]:
        """Get errors filtered by severity"""
        with self._lock:
            return [e for e in self._errors if e.severity == severity]

    def get_error_trends(self, hours: int = 24) -> Dict[str, List[Dict]]:
        """Get error trends over time"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        trends = defaultdict(list)
        with self._lock:
            for error in self._errors:
                if error.timestamp >= cutoff_str:
                    trends[error.error_type].append({
                        "timestamp": error.timestamp,
                        "severity": error.severity
                    })

        return dict(trends)

    def get_summary(self) -> Dict[str, Any]:
        """Get error summary"""
        with self._lock:
            return {
                "total_errors": len(self._errors),
                "by_type": dict(self._error_counts),
                "by_category": dict(self._category_counts),
                "by_severity": dict(self._severity_counts),
                "unresolved": sum(1 for e in self._errors if not e.resolved),
                "critical_unresolved": sum(1 for e in self._errors if e.severity == "critical" and not e.resolved)
            }

    def resolve_error(self, error_id: str, notes: Optional[str] = None) -> bool:
        """Mark an error as resolved"""
        with self._lock:
            for error in self._errors:
                if error.error_id == error_id:
                    error.resolved = True
                    error.resolution_notes = notes
                    return True
        return False

    def add_alert_callback(self, callback: callable):
        """Add callback for critical error alerts"""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, error: ErrorRecord):
        """Trigger alert callbacks for critical errors"""
        alert = {
            "error_id": error.error_id,
            "type": error.error_type,
            "message": error.message,
            "client_id": error.client_id,
            "timestamp": error.timestamp
        }
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def export_to_file(self, filepath: str) -> bool:
        """Export errors to JSON file"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            data = {
                "client_id": self.client_id,
                "exported_at": datetime.utcnow().isoformat(),
                "summary": self.get_summary(),
                "errors": [asdict(e) for e in self._errors]
            }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        return True

    def clear_resolved(self, older_than_days: int = 30) -> int:
        """Clear resolved errors older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        cutoff_str = cutoff.isoformat()

        with self._lock:
            original_count = len(self._errors)
            self._errors = [
                e for e in self._errors
                if not e.resolved or e.timestamp >= cutoff_str
            ]
            return original_count - len(self._errors)


# Singleton instance
_tracker: Optional[ErrorTracker] = None


def get_error_tracker(client_id: str = "system") -> ErrorTracker:
    """Get or create error tracker instance"""
    global _tracker
    if _tracker is None or _tracker.client_id != client_id:
        _tracker = ErrorTracker(client_id)
    return _tracker
