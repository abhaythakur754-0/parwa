"""Threat Detector Module - Week 54, Builder 2"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ThreatType(Enum):
    MALWARE = "malware"
    PHISHING = "phishing"
    DDOS = "ddos"
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    PATH_TRAVERSAL = "path_traversal"


class ThreatSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Threat:
    threat_type: ThreatType
    severity: ThreatSeverity
    source: str
    description: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False


@dataclass
class ThreatSignature:
    name: str
    pattern: str
    threat_type: ThreatType
    severity: ThreatSeverity


class ThreatDetector:
    def __init__(self):
        self.threats: Dict[str, Threat] = {}
        self.signatures: List[ThreatSignature] = []
        self._load_default_signatures()

    def _load_default_signatures(self):
        self.signatures = [
            ThreatSignature("sql_injection", "'", ThreatType.SQL_INJECTION, ThreatSeverity.HIGH),
            ThreatSignature("xss", "<script", ThreatType.XSS, ThreatSeverity.HIGH),
            ThreatSignature("path_traversal", "../", ThreatType.PATH_TRAVERSAL, ThreatSeverity.MEDIUM),
        ]

    def detect(self, data: str, source: str = "unknown") -> List[Threat]:
        detected = []
        data_lower = data.lower()
        for sig in self.signatures:
            if sig.pattern.lower() in data_lower:
                threat = Threat(
                    threat_type=sig.threat_type,
                    severity=sig.severity,
                    source=source,
                    description=f"Detected {sig.name}",
                    indicators={"pattern": sig.pattern},
                )
                self.threats[str(len(self.threats))] = threat
                detected.append(threat)
        return detected

    def add_signature(self, signature: ThreatSignature) -> None:
        self.signatures.append(signature)

    def get_threats(self, resolved: Optional[bool] = None) -> List[Threat]:
        if resolved is None:
            return list(self.threats.values())
        return [t for t in self.threats.values() if t.resolved == resolved]

    def resolve_threat(self, threat_id: str) -> bool:
        if threat_id in self.threats:
            self.threats[threat_id].resolved = True
            return True
        return False
