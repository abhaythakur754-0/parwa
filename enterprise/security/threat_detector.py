"""
Enterprise Security - Threat Detector
Advanced threat detection for enterprise clients
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class ThreatLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ANOMALY = "anomaly"
    MALWARE = "malware"
    PHISHING = "phishing"


class ThreatEvent(BaseModel):
    """Detected threat event"""
    event_id: str = Field(default_factory=lambda: f"threat_{uuid.uuid4().hex[:8]}")
    client_id: str
    threat_type: ThreatType
    level: ThreatLevel
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class ThreatDetector:
    """
    Advanced threat detection for enterprise clients.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.events: Dict[str, ThreatEvent] = {}
        self.thresholds: Dict[str, int] = {
            "failed_logins_per_minute": 5,
            "api_calls_per_minute": 1000,
            "data_transfer_mb_per_minute": 100
        }

    def detect_brute_force(
        self,
        source_ip: str,
        failed_attempts: int,
        time_window_seconds: int = 60
    ) -> Optional[ThreatEvent]:
        """Detect brute force attack"""
        if failed_attempts >= self.thresholds["failed_logins_per_minute"]:
            event = ThreatEvent(
                client_id=self.client_id,
                threat_type=ThreatType.BRUTE_FORCE,
                level=ThreatLevel.HIGH,
                source_ip=source_ip,
                description=f"Brute force attack detected: {failed_attempts} failed attempts"
            )
            self.events[event.event_id] = event
            return event
        return None

    def detect_sql_injection(
        self,
        query: str,
        source_ip: str
    ) -> Optional[ThreatEvent]:
        """Detect SQL injection attempt"""
        sql_patterns = ["'", "OR 1=1", "UNION SELECT", "--", "; DROP"]
        for pattern in sql_patterns:
            if pattern.lower() in query.lower():
                event = ThreatEvent(
                    client_id=self.client_id,
                    threat_type=ThreatType.SQL_INJECTION,
                    level=ThreatLevel.CRITICAL,
                    source_ip=source_ip,
                    description=f"SQL injection attempt detected: pattern '{pattern}'"
                )
                self.events[event.event_id] = event
                return event
        return None

    def detect_xss(
        self,
        input_data: str,
        source_ip: str
    ) -> Optional[ThreatEvent]:
        """Detect XSS attempt"""
        xss_patterns = ["<script>", "javascript:", "onerror=", "onload="]
        for pattern in xss_patterns:
            if pattern.lower() in input_data.lower():
                event = ThreatEvent(
                    client_id=self.client_id,
                    threat_type=ThreatType.XSS,
                    level=ThreatLevel.HIGH,
                    source_ip=source_ip,
                    description=f"XSS attempt detected: pattern '{pattern}'"
                )
                self.events[event.event_id] = event
                return event
        return None

    def detect_anomaly(
        self,
        user_id: str,
        activity_score: float
    ) -> Optional[ThreatEvent]:
        """Detect anomalous behavior"""
        if activity_score > 0.9:  # High anomaly score
            event = ThreatEvent(
                client_id=self.client_id,
                threat_type=ThreatType.ANOMALY,
                level=ThreatLevel.MEDIUM,
                user_id=user_id,
                description=f"Anomalous behavior detected: score {activity_score}"
            )
            self.events[event.event_id] = event
            return event
        return None

    def detect_data_exfiltration(
        self,
        user_id: str,
        data_size_mb: float
    ) -> Optional[ThreatEvent]:
        """Detect potential data exfiltration"""
        if data_size_mb > self.thresholds["data_transfer_mb_per_minute"]:
            event = ThreatEvent(
                client_id=self.client_id,
                threat_type=ThreatType.DATA_EXFILTRATION,
                level=ThreatLevel.CRITICAL,
                user_id=user_id,
                description=f"Potential data exfiltration: {data_size_mb}MB transferred"
            )
            self.events[event.event_id] = event
            return event
        return None

    def get_threats(self, level: Optional[ThreatLevel] = None) -> List[ThreatEvent]:
        """Get all threats, optionally filtered by level"""
        events = list(self.events.values())
        if level:
            events = [e for e in events if e.level == level]
        return events

    def resolve_threat(self, event_id: str) -> bool:
        """Mark a threat as resolved"""
        if event_id in self.events:
            self.events[event_id].resolved = True
            self.events[event_id].resolved_at = datetime.utcnow()
            return True
        return False

    def get_threat_summary(self) -> Dict[str, int]:
        """Get threat summary by level"""
        summary = {level.value: 0 for level in ThreatLevel}
        for event in self.events.values():
            if not event.resolved:
                summary[event.level.value] += 1
        return summary
