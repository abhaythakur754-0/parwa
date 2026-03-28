"""
Enterprise Security Hardening - Threat Detector
Advanced threat detection engine with real-time capabilities
"""
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import re
import hashlib
import threading
from collections import defaultdict


class ThreatType(str, Enum):
    """Types of security threats"""
    MALWARE = "malware"
    PHISHING = "phishing"
    DDOS = "ddos"
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    ZERO_DAY = "zero_day"
    INSIDER_THREAT = "insider_threat"
    API_ABUSE = "api_abuse"
    CREDENTIAL_STUFFING = "credential_stuffing"


class ThreatSeverity(str, Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatStatus(str, Enum):
    """Threat status"""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


@dataclass
class ThreatIndicator:
    """Threat indicator data"""
    indicator_type: str
    value: str
    confidence: float = 0.0
    source: str = "internal"
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Threat:
    """Detected threat data"""
    threat_id: str = field(default_factory=lambda: f"threat_{uuid.uuid4().hex[:12]}")
    threat_type: ThreatType = ThreatType.MALWARE
    severity: ThreatSeverity = ThreatSeverity.MEDIUM
    status: ThreatStatus = ThreatStatus.DETECTED
    source: str = ""
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    target_resource: Optional[str] = None
    description: str = ""
    indicators: List[ThreatIndicator] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    mitigated_at: Optional[datetime] = None
    confidence_score: float = 0.0
    false_positive_probability: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_indicator(self, indicator: ThreatIndicator) -> None:
        """Add an indicator to the threat"""
        self.indicators.append(indicator)

    def to_dict(self) -> Dict[str, Any]:
        """Convert threat to dictionary"""
        return {
            "threat_id": self.threat_id,
            "threat_type": self.threat_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "source": self.source,
            "source_ip": self.source_ip,
            "user_id": self.user_id,
            "target_resource": self.target_resource,
            "description": self.description,
            "indicators_count": len(self.indicators),
            "timestamp": self.timestamp.isoformat(),
            "confidence_score": self.confidence_score,
            "metadata": self.metadata
        }


@dataclass
class ThreatSignature:
    """Threat signature for pattern matching"""
    signature_id: str
    name: str
    threat_type: ThreatType
    severity: ThreatSeverity
    pattern: str
    pattern_type: str = "regex"  # regex, exact, contains, hash
    description: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def match(self, data: str) -> bool:
        """Check if data matches the signature pattern"""
        if not self.enabled:
            return False
        
        if self.pattern_type == "regex":
            try:
                return bool(re.search(self.pattern, data, re.IGNORECASE))
            except re.error:
                return False
        elif self.pattern_type == "exact":
            return data == self.pattern
        elif self.pattern_type == "contains":
            return self.pattern.lower() in data.lower()
        elif self.pattern_type == "hash":
            data_hash = hashlib.sha256(data.encode()).hexdigest()
            return data_hash == self.pattern
        return False


class ThreatDetector:
    """
    Advanced threat detection engine with real-time capabilities.
    Supports signature-based detection, behavioral analysis, and real-time monitoring.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.threats: Dict[str, Threat] = {}
        self.signatures: Dict[str, ThreatSignature] = {}
        self.indicators_db: Dict[str, List[ThreatIndicator]] = defaultdict(list)
        self._lock = threading.RLock()
        self._detection_stats = defaultdict(int)
        self._recent_detections: List[Threat] = []
        self._max_recent = 1000
        
        # Initialize default signatures
        self._init_default_signatures()

    def _init_default_signatures(self) -> None:
        """Initialize built-in threat signatures"""
        default_signatures = [
            # SQL Injection patterns
            ThreatSignature(
                signature_id="sig_sql_001",
                name="SQL Injection - UNION SELECT",
                threat_type=ThreatType.SQL_INJECTION,
                severity=ThreatSeverity.HIGH,
                pattern=r"union\s+select",
                pattern_type="regex",
                description="Detects UNION SELECT SQL injection attempts"
            ),
            ThreatSignature(
                signature_id="sig_sql_002",
                name="SQL Injection - OR 1=1",
                threat_type=ThreatType.SQL_INJECTION,
                severity=ThreatSeverity.HIGH,
                pattern=r"or\s+1\s*=\s*1",
                pattern_type="regex",
                description="Detects OR 1=1 SQL injection attempts"
            ),
            ThreatSignature(
                signature_id="sig_sql_003",
                name="SQL Injection - DROP TABLE",
                threat_type=ThreatType.SQL_INJECTION,
                severity=ThreatSeverity.CRITICAL,
                pattern=r"drop\s+table",
                pattern_type="regex",
                description="Detects DROP TABLE SQL injection attempts"
            ),
            # XSS patterns
            ThreatSignature(
                signature_id="sig_xss_001",
                name="XSS - Script Tag",
                threat_type=ThreatType.XSS,
                severity=ThreatSeverity.HIGH,
                pattern=r"<\s*script",
                pattern_type="regex",
                description="Detects script tag XSS attempts"
            ),
            ThreatSignature(
                signature_id="sig_xss_002",
                name="XSS - JavaScript Protocol",
                threat_type=ThreatType.XSS,
                severity=ThreatSeverity.HIGH,
                pattern=r"javascript\s*:",
                pattern_type="regex",
                description="Detects javascript: protocol XSS attempts"
            ),
            ThreatSignature(
                signature_id="sig_xss_003",
                name="XSS - Event Handler",
                threat_type=ThreatType.XSS,
                severity=ThreatSeverity.MEDIUM,
                pattern=r"on(error|load|click|mouse)\s*=",
                pattern_type="regex",
                description="Detects event handler XSS attempts"
            ),
            # Path Traversal
            ThreatSignature(
                signature_id="sig_path_001",
                name="Path Traversal - Directory",
                threat_type=ThreatType.PATH_TRAVERSAL,
                severity=ThreatSeverity.HIGH,
                pattern=r"\.\.[\\/]",
                pattern_type="regex",
                description="Detects directory traversal attempts"
            ),
            # Command Injection
            ThreatSignature(
                signature_id="sig_cmd_001",
                name="Command Injection - Pipe",
                threat_type=ThreatType.COMMAND_INJECTION,
                severity=ThreatSeverity.CRITICAL,
                pattern=r"\|\s*(cat|ls|id|whoami|pwd)",
                pattern_type="regex",
                description="Detects command injection via pipe"
            ),
            ThreatSignature(
                signature_id="sig_cmd_002",
                name="Command Injection - Semicolon",
                threat_type=ThreatType.COMMAND_INJECTION,
                severity=ThreatSeverity.CRITICAL,
                pattern=r";\s*(cat|ls|id|whoami|rm|wget)",
                pattern_type="regex",
                description="Detects command injection via semicolon"
            ),
            # Phishing patterns
            ThreatSignature(
                signature_id="sig_phish_001",
                name="Phishing - Credential Harvest",
                threat_type=ThreatType.PHISHING,
                severity=ThreatSeverity.HIGH,
                pattern=r"(password|login|credential).*(form|input|submit)",
                pattern_type="regex",
                description="Detects potential credential harvesting forms"
            ),
        ]
        
        for sig in default_signatures:
            self.signatures[sig.signature_id] = sig

    def add_signature(self, signature: ThreatSignature) -> None:
        """Add a custom threat signature"""
        with self._lock:
            self.signatures[signature.signature_id] = signature

    def remove_signature(self, signature_id: str) -> bool:
        """Remove a threat signature"""
        with self._lock:
            if signature_id in self.signatures:
                del self.signatures[signature_id]
                return True
        return False

    def detect(
        self,
        data: str,
        source: str = "",
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Threat]:
        """
        Detect threats in the provided data.
        Uses signature matching and behavioral analysis.
        """
        detected_threats = []
        
        with self._lock:
            for sig_id, signature in self.signatures.items():
                if signature.match(data):
                    threat = Threat(
                        threat_type=signature.threat_type,
                        severity=signature.severity,
                        status=ThreatStatus.DETECTED,
                        source=source,
                        source_ip=source_ip,
                        user_id=user_id,
                        description=f"Matched signature: {signature.name}",
                        confidence_score=0.8,
                        metadata=metadata or {}
                    )
                    threat.add_indicator(ThreatIndicator(
                        indicator_type="signature_match",
                        value=sig_id,
                        confidence=0.8,
                        source="threat_detector"
                    ))
                    
                    self.threats[threat.threat_id] = threat
                    detected_threats.append(threat)
                    self._detection_stats[signature.threat_type.value] += 1
                    
                    # Track recent detections
                    self._recent_detections.append(threat)
                    if len(self._recent_detections) > self._max_recent:
                        self._recent_detections.pop(0)
        
        return detected_threats

    def detect_batch(
        self,
        data_list: List[Dict[str, Any]]
    ) -> List[Threat]:
        """Detect threats in a batch of data items"""
        all_threats = []
        for item in data_list:
            data = item.get("data", "")
            source = item.get("source", "")
            source_ip = item.get("source_ip")
            user_id = item.get("user_id")
            metadata = item.get("metadata", {})
            
            threats = self.detect(data, source, source_ip, user_id, metadata)
            all_threats.extend(threats)
        
        return all_threats

    def detect_brute_force(
        self,
        source_ip: str,
        failed_attempts: int,
        threshold: int = 5,
        time_window_seconds: int = 60
    ) -> Optional[Threat]:
        """Detect brute force attack based on failed attempts"""
        if failed_attempts >= threshold:
            threat = Threat(
                threat_type=ThreatType.BRUTE_FORCE,
                severity=ThreatSeverity.HIGH,
                source="brute_force_detector",
                source_ip=source_ip,
                description=f"Brute force attack detected: {failed_attempts} failed attempts",
                confidence_score=min(1.0, failed_attempts / (threshold * 2))
            )
            threat.add_indicator(ThreatIndicator(
                indicator_type="failed_attempts",
                value=str(failed_attempts),
                confidence=0.9,
                source="auth_system"
            ))
            
            with self._lock:
                self.threats[threat.threat_id] = threat
                self._detection_stats["brute_force"] += 1
                self._recent_detections.append(threat)
            
            return threat
        return None

    def detect_ddos(
        self,
        source_ip: str,
        request_count: int,
        threshold: int = 1000,
        time_window_seconds: int = 60
    ) -> Optional[Threat]:
        """Detect DDoS attack based on request volume"""
        if request_count >= threshold:
            severity = ThreatSeverity.CRITICAL if request_count >= threshold * 5 else ThreatSeverity.HIGH
            threat = Threat(
                threat_type=ThreatType.DDOS,
                severity=severity,
                source="ddos_detector",
                source_ip=source_ip,
                description=f"DDoS attack detected: {request_count} requests in {time_window_seconds}s",
                confidence_score=min(1.0, request_count / (threshold * 2))
            )
            threat.add_indicator(ThreatIndicator(
                indicator_type="request_volume",
                value=str(request_count),
                confidence=0.95,
                source="traffic_monitor"
            ))
            
            with self._lock:
                self.threats[threat.threat_id] = threat
                self._detection_stats["ddos"] += 1
                self._recent_detections.append(threat)
            
            return threat
        return None

    def detect_data_exfiltration(
        self,
        user_id: str,
        data_volume_mb: float,
        threshold_mb: float = 100.0
    ) -> Optional[Threat]:
        """Detect potential data exfiltration"""
        if data_volume_mb >= threshold_mb:
            severity = ThreatSeverity.CRITICAL if data_volume_mb >= threshold_mb * 5 else ThreatSeverity.HIGH
            threat = Threat(
                threat_type=ThreatType.DATA_EXFILTRATION,
                severity=severity,
                source="data_monitor",
                user_id=user_id,
                description=f"Data exfiltration suspected: {data_volume_mb}MB transferred",
                confidence_score=min(1.0, data_volume_mb / (threshold_mb * 2))
            )
            threat.add_indicator(ThreatIndicator(
                indicator_type="data_volume",
                value=f"{data_volume_mb}MB",
                confidence=0.85,
                source="data_transfer_monitor"
            ))
            
            with self._lock:
                self.threats[threat.threat_id] = threat
                self._detection_stats["data_exfiltration"] += 1
                self._recent_detections.append(threat)
            
            return threat
        return None

    def detect_privilege_escalation(
        self,
        user_id: str,
        original_role: str,
        new_role: str,
        authorized: bool = False
    ) -> Optional[Threat]:
        """Detect privilege escalation attempts"""
        if not authorized:
            threat = Threat(
                threat_type=ThreatType.PRIVILEGE_ESCALATION,
                severity=ThreatSeverity.CRITICAL,
                source="auth_monitor",
                user_id=user_id,
                description=f"Unauthorized privilege escalation: {original_role} -> {new_role}",
                confidence_score=0.95
            )
            threat.add_indicator(ThreatIndicator(
                indicator_type="role_change",
                value=f"{original_role}->{new_role}",
                confidence=1.0,
                source="role_manager"
            ))
            
            with self._lock:
                self.threats[threat.threat_id] = threat
                self._detection_stats["privilege_escalation"] += 1
                self._recent_detections.append(threat)
            
            return threat
        return None

    def add_indicator(
        self,
        indicator_type: str,
        value: str,
        confidence: float = 0.0,
        source: str = "external"
    ) -> ThreatIndicator:
        """Add a threat indicator to the database"""
        indicator = ThreatIndicator(
            indicator_type=indicator_type,
            value=value,
            confidence=confidence,
            source=source
        )
        
        with self._lock:
            self.indicators_db[indicator_type].append(indicator)
        
        return indicator

    def check_indicator(
        self,
        indicator_type: str,
        value: str
    ) -> Optional[ThreatIndicator]:
        """Check if an indicator exists in the database"""
        with self._lock:
            for indicator in self.indicators_db.get(indicator_type, []):
                if indicator.value == value:
                    return indicator
        return None

    def get_threat(self, threat_id: str) -> Optional[Threat]:
        """Get a threat by ID"""
        return self.threats.get(threat_id)

    def get_threats(
        self,
        threat_type: Optional[ThreatType] = None,
        severity: Optional[ThreatSeverity] = None,
        status: Optional[ThreatStatus] = None,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Threat]:
        """Get threats with optional filters"""
        results = list(self.threats.values())
        
        if threat_type:
            results = [t for t in results if t.threat_type == threat_type]
        if severity:
            results = [t for t in results if t.severity == severity]
        if status:
            results = [t for t in results if t.status == status]
        if source_ip:
            results = [t for t in results if t.source_ip == source_ip]
        if user_id:
            results = [t for t in results if t.user_id == user_id]
        
        return sorted(results, key=lambda t: t.timestamp, reverse=True)[:limit]

    def resolve_threat(self, threat_id: str, status: ThreatStatus = ThreatStatus.RESOLVED) -> bool:
        """Mark a threat as resolved"""
        with self._lock:
            if threat_id in self.threats:
                self.threats[threat_id].status = status
                self.threats[threat_id].resolved_at = datetime.utcnow()
                return True
        return False

    def mitigate_threat(self, threat_id: str) -> bool:
        """Mark a threat as mitigated"""
        with self._lock:
            if threat_id in self.threats:
                self.threats[threat_id].status = ThreatStatus.MITIGATED
                self.threats[threat_id].mitigated_at = datetime.utcnow()
                return True
        return False

    def get_recent_detections(self, limit: int = 100) -> List[Threat]:
        """Get recent threat detections"""
        return self._recent_detections[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            "total_threats": len(self.threats),
            "by_type": dict(self._detection_stats),
            "by_severity": {
                "critical": len([t for t in self.threats.values() if t.severity == ThreatSeverity.CRITICAL]),
                "high": len([t for t in self.threats.values() if t.severity == ThreatSeverity.HIGH]),
                "medium": len([t for t in self.threats.values() if t.severity == ThreatSeverity.MEDIUM]),
                "low": len([t for t in self.threats.values() if t.severity == ThreatSeverity.LOW])
            },
            "by_status": {
                "detected": len([t for t in self.threats.values() if t.status == ThreatStatus.DETECTED]),
                "investigating": len([t for t in self.threats.values() if t.status == ThreatStatus.INVESTIGATING]),
                "mitigated": len([t for t in self.threats.values() if t.status == ThreatStatus.MITIGATED]),
                "resolved": len([t for t in self.threats.values() if t.status == ThreatStatus.RESOLVED]),
                "false_positive": len([t for t in self.threats.values() if t.status == ThreatStatus.FALSE_POSITIVE])
            },
            "signatures_count": len(self.signatures),
            "indicators_count": sum(len(v) for v in self.indicators_db.values())
        }

    def clear_old_threats(self, days: int = 30) -> int:
        """Clear threats older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0
        
        with self._lock:
            to_remove = [
                tid for tid, t in self.threats.items()
                if t.timestamp < cutoff and t.status in [ThreatStatus.RESOLVED, ThreatStatus.FALSE_POSITIVE]
            ]
            for tid in to_remove:
                del self.threats[tid]
                removed += 1
        
        return removed

    def export_threats(self, format: str = "dict") -> Any:
        """Export threats for reporting"""
        if format == "dict":
            return [t.to_dict() for t in self.threats.values()]
        return list(self.threats.values())
