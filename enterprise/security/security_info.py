"""
Enterprise Security - Security Information
Shared security information models
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class SecurityAlertType(str, Enum):
    THREAT_DETECTED = "threat_detected"
    VULNERABILITY_FOUND = "vulnerability_found"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    COMPLIANCE_VIOLATION = "compliance_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class SecurityAlert(BaseModel):
    """Security alert"""
    alert_id: str
    alert_type: SecurityAlertType
    severity: str
    title: str
    description: str
    client_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict()


class SecurityMetrics(BaseModel):
    """Security metrics"""
    client_id: str
    period_start: datetime
    period_end: datetime
    total_threats: int = 0
    blocked_ips: int = 0
    vulnerabilities_found: int = 0
    vulnerabilities_fixed: int = 0
    security_score: float = 100.0

    model_config = ConfigDict()
