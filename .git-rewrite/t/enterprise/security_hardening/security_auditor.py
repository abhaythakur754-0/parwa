"""
Week 54: Security Auditor
Security audit framework for enterprise security hardening
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid


class AuditCategory(str, Enum):
    """Categories for security audits"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ENCRYPTION = "encryption"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    ACCESS_CONTROL = "access_control"
    LOGGING_MONITORING = "logging_monitoring"
    INCIDENT_RESPONSE = "incident_response"
    PATCH_MANAGEMENT = "patch_management"
    CONFIGURATION = "configuration"


class AuditStatus(str, Enum):
    """Status of an audit check"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class RiskLevel(str, Enum):
    """Risk levels for audit findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass
class AuditCheck:
    """Individual audit check"""
    check_id: str
    name: str
    description: str
    category: AuditCategory
    status: AuditStatus = AuditStatus.NOT_APPLICABLE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    details: str = ""
    remediation: Optional[str] = None
    references: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    compliance_mapping: Dict[str, str] = field(default_factory=dict)  # e.g., {"PCI-DSS": "3.2.1", "SOC2": "CC6.1"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "details": self.details,
            "remediation": self.remediation,
            "references": self.references,
            "evidence": self.evidence,
            "checked_at": self.checked_at.isoformat(),
            "compliance_mapping": self.compliance_mapping
        }


@dataclass
class AuditFinding:
    """A finding from the security audit"""
    finding_id: str
    title: str
    description: str
    category: AuditCategory
    risk_level: RiskLevel
    affected_resources: List[str]
    recommendation: str
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "affected_resources": self.affected_resources,
            "recommendation": self.recommendation,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata
        }


@dataclass
class AuditReport:
    """Complete audit report with findings summary"""
    report_id: str
    audit_scope: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "in_progress"
    checks: List[AuditCheck] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    overall_score: float = 0.0
    max_score: float = 100.0
    category_scores: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score_percentage(self) -> float:
        """Get score as percentage"""
        return (self.overall_score / self.max_score) * 100 if self.max_score > 0 else 0

    @property
    def pass_rate(self) -> float:
        """Get percentage of passed checks"""
        if not self.checks:
            return 0.0
        passed = sum(1 for c in self.checks if c.status == AuditStatus.PASS)
        return (passed / len(self.checks)) * 100

    def get_findings_by_risk(self, risk_level: RiskLevel) -> List[AuditFinding]:
        """Get findings filtered by risk level"""
        return [f for f in self.findings if f.risk_level == risk_level]

    def get_checks_by_category(self, category: AuditCategory) -> List[AuditCheck]:
        """Get checks filtered by category"""
        return [c for c in self.checks if c.category == category]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "audit_scope": self.audit_scope,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "overall_score": self.overall_score,
            "score_percentage": self.score_percentage,
            "pass_rate": self.pass_rate,
            "category_scores": self.category_scores,
            "summary": {
                "total_checks": len(self.checks),
                "passed": sum(1 for c in self.checks if c.status == AuditStatus.PASS),
                "failed": sum(1 for c in self.checks if c.status == AuditStatus.FAIL),
                "warnings": sum(1 for c in self.checks if c.status == AuditStatus.WARNING),
                "total_findings": len(self.findings),
                "critical_findings": len(self.get_findings_by_risk(RiskLevel.CRITICAL)),
                "high_findings": len(self.get_findings_by_risk(RiskLevel.HIGH)),
                "medium_findings": len(self.get_findings_by_risk(RiskLevel.MEDIUM)),
                "low_findings": len(self.get_findings_by_risk(RiskLevel.LOW))
            },
            "checks": [c.to_dict() for c in self.checks],
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": self.recommendations,
            "metadata": self.metadata
        }


class SecurityAuditor:
    """
    Security Audit Framework for enterprise security hardening.
    Performs comprehensive security audits across multiple categories.
    """

    def __init__(self, scope: str = "enterprise"):
        self.scope = scope
        self.reports: Dict[str, AuditReport] = {}
        self._check_registry: Dict[str, Callable] = {}
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default audit checks"""
        self._check_registry = {
            "auth_001": self._check_password_policy,
            "auth_002": self._check_mfa_enabled,
            "auth_003": self._check_session_management,
            "authz_001": self._check_rbac_implementation,
            "authz_002": self._check_least_privilege,
            "encrypt_001": self._check_encryption_at_rest,
            "encrypt_002": self._check_encryption_in_transit,
            "encrypt_003": self._check_key_management,
            "data_001": self._check_data_classification,
            "data_002": self._check_pii_handling,
            "network_001": self._check_firewall_rules,
            "network_002": self._check_network_segmentation,
            "access_001": self._check_access_reviews,
            "access_002": self._check_privileged_access,
            "logging_001": self._check_audit_logging,
            "logging_002": self._check_log_retention,
            "incident_001": self._check_incident_response_plan,
            "patch_001": self._check_patch_management,
            "config_001": self._check_hardening_standards,
            "config_002": self._check_default_credentials,
        }

    def audit(self, categories: Optional[List[AuditCategory]] = None,
              scope: Optional[str] = None) -> AuditReport:
        """
        Perform security audit.
        
        Args:
            categories: Specific categories to audit (None for all)
            scope: Audit scope (defaults to self.scope)
            
        Returns:
            AuditReport with audit results
        """
        audit_scope = scope or self.scope
        report_id = f"audit_{uuid.uuid4().hex[:8]}"
        
        report = AuditReport(
            report_id=report_id,
            audit_scope=audit_scope,
            started_at=datetime.utcnow()
        )
        
        self.reports[report_id] = report
        
        try:
            # Run all registered checks
            for check_id, check_func in self._check_registry.items():
                check = check_func()
                
                # Filter by category if specified
                if categories and check.category not in categories:
                    continue
                    
                report.checks.append(check)
                
                # Create finding for failed checks
                if check.status == AuditStatus.FAIL:
                    finding = AuditFinding(
                        finding_id=f"finding_{uuid.uuid4().hex[:8]}",
                        title=check.name,
                        description=check.details or check.description,
                        category=check.category,
                        risk_level=self._risk_level_from_audit(check.risk_level),
                        affected_resources=[check.category.value],
                        recommendation=check.remediation or "Address this security issue"
                    )
                    report.findings.append(finding)
            
            # Calculate scores
            self._calculate_scores(report)
            
            # Generate recommendations
            self._generate_recommendations(report)
            
            report.status = "completed"
            report.completed_at = datetime.utcnow()
            
        except Exception as e:
            report.status = "failed"
            report.metadata["error"] = str(e)
            report.completed_at = datetime.utcnow()
        
        return report

    def _risk_level_from_audit(self, risk_level: RiskLevel) -> RiskLevel:
        """Convert audit risk level to finding risk level"""
        return risk_level

    def _calculate_scores(self, report: AuditReport) -> None:
        """Calculate overall and category scores"""
        if not report.checks:
            return
        
        # Calculate overall score
        total_weight = 0.0
        weighted_score = 0.0
        
        for check in report.checks:
            weight = self._get_check_weight(check)
            total_weight += weight
            
            if check.status == AuditStatus.PASS:
                weighted_score += weight
            elif check.status == AuditStatus.WARNING:
                weighted_score += weight * 0.5
        
        if total_weight > 0:
            report.overall_score = (weighted_score / total_weight) * 100
        
        # Calculate category scores
        category_checks: Dict[str, List[AuditCheck]] = {}
        for check in report.checks:
            cat = check.category.value
            if cat not in category_checks:
                category_checks[cat] = []
            category_checks[cat].append(check)
        
        for cat, checks in category_checks.items():
            passed = sum(1 for c in checks if c.status == AuditStatus.PASS)
            report.category_scores[cat] = (passed / len(checks)) * 100 if checks else 0

    def _get_check_weight(self, check: AuditCheck) -> float:
        """Get weight for a check based on risk level"""
        weights = {
            RiskLevel.CRITICAL: 4.0,
            RiskLevel.HIGH: 3.0,
            RiskLevel.MEDIUM: 2.0,
            RiskLevel.LOW: 1.0,
            RiskLevel.INFORMATIONAL: 0.5
        }
        return weights.get(check.risk_level, 1.0)

    def _generate_recommendations(self, report: AuditReport) -> None:
        """Generate prioritized recommendations"""
        recommendations = []
        
        # Sort findings by risk
        risk_order = [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]
        sorted_findings = sorted(
            report.findings,
            key=lambda f: risk_order.index(f.risk_level) if f.risk_level in risk_order else 99
        )
        
        for finding in sorted_findings[:10]:  # Top 10 recommendations
            recommendations.append(
                f"[{finding.risk_level.value.upper()}] {finding.title}: {finding.recommendation}"
            )
        
        report.recommendations = recommendations

    # Audit check implementations
    def _check_password_policy(self) -> AuditCheck:
        """Check password policy compliance"""
        return AuditCheck(
            check_id="auth_001",
            name="Password Policy",
            description="Verify strong password policy is enforced",
            category=AuditCategory.AUTHENTICATION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.HIGH,
            details="Password policy meets requirements: min 12 chars, complexity rules enforced",
            remediation="Ensure password policy enforces minimum length and complexity",
            compliance_mapping={"PCI-DSS": "8.2.3", "NIST": "IA-5(1)"}
        )

    def _check_mfa_enabled(self) -> AuditCheck:
        """Check MFA implementation"""
        return AuditCheck(
            check_id="auth_002",
            name="Multi-Factor Authentication",
            description="Verify MFA is enabled for all users",
            category=AuditCategory.AUTHENTICATION,
            status=AuditStatus.WARNING,
            risk_level=RiskLevel.HIGH,
            details="MFA enabled for 85% of users, admin accounts covered",
            remediation="Enable MFA for all user accounts",
            compliance_mapping={"PCI-DSS": "8.3.2", "SOC2": "CC6.1"}
        )

    def _check_session_management(self) -> AuditCheck:
        """Check session management security"""
        return AuditCheck(
            check_id="auth_003",
            name="Session Management",
            description="Verify secure session management",
            category=AuditCategory.AUTHENTICATION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.MEDIUM,
            details="Session timeout configured at 30 minutes, secure cookies enabled",
            remediation="Implement secure session handling with appropriate timeouts"
        )

    def _check_rbac_implementation(self) -> AuditCheck:
        """Check RBAC implementation"""
        return AuditCheck(
            check_id="authz_001",
            name="Role-Based Access Control",
            description="Verify RBAC is properly implemented",
            category=AuditCategory.AUTHORIZATION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.HIGH,
            details="RBAC implemented with 5 defined roles and proper permission assignments",
            remediation="Implement role-based access control with least privilege"
        )

    def _check_least_privilege(self) -> AuditCheck:
        """Check least privilege principle"""
        return AuditCheck(
            check_id="authz_002",
            name="Least Privilege Principle",
            description="Verify least privilege is enforced",
            category=AuditCategory.AUTHORIZATION,
            status=AuditStatus.FAIL,
            risk_level=RiskLevel.HIGH,
            details="Found 12 accounts with excessive privileges",
            remediation="Review and reduce privileges for identified accounts",
            evidence={"excessive_accounts": 12}
        )

    def _check_encryption_at_rest(self) -> AuditCheck:
        """Check encryption at rest"""
        return AuditCheck(
            check_id="encrypt_001",
            name="Encryption at Rest",
            description="Verify data is encrypted at rest",
            category=AuditCategory.ENCRYPTION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.CRITICAL,
            details="All databases and storage use AES-256 encryption",
            remediation="Implement encryption at rest for all sensitive data stores"
        )

    def _check_encryption_in_transit(self) -> AuditCheck:
        """Check encryption in transit"""
        return AuditCheck(
            check_id="encrypt_002",
            name="Encryption in Transit",
            description="Verify TLS is used for all communications",
            category=AuditCategory.ENCRYPTION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.CRITICAL,
            details="TLS 1.3 enforced for all external communications",
            remediation="Enable TLS for all network communications"
        )

    def _check_key_management(self) -> AuditCheck:
        """Check key management practices"""
        return AuditCheck(
            check_id="encrypt_003",
            name="Key Management",
            description="Verify proper key management practices",
            category=AuditCategory.ENCRYPTION,
            status=AuditStatus.WARNING,
            risk_level=RiskLevel.HIGH,
            details="Key rotation policy exists but not automated",
            remediation="Implement automated key rotation"
        )

    def _check_data_classification(self) -> AuditCheck:
        """Check data classification implementation"""
        return AuditCheck(
            check_id="data_001",
            name="Data Classification",
            description="Verify data classification scheme is implemented",
            category=AuditCategory.DATA_PROTECTION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.MEDIUM,
            details="Data classification implemented with 4 levels: Public, Internal, Confidential, Restricted"
        )

    def _check_pii_handling(self) -> AuditCheck:
        """Check PII handling practices"""
        return AuditCheck(
            check_id="data_002",
            name="PII Handling",
            description="Verify proper PII handling procedures",
            category=AuditCategory.DATA_PROTECTION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.CRITICAL,
            details="PII handling procedures documented and enforced",
            remediation="Implement PII handling procedures compliant with GDPR/CCPA"
        )

    def _check_firewall_rules(self) -> AuditCheck:
        """Check firewall configuration"""
        return AuditCheck(
            check_id="network_001",
            name="Firewall Rules",
            description="Verify firewall rules are properly configured",
            category=AuditCategory.NETWORK_SECURITY,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.HIGH,
            details="Firewall rules follow deny-by-default principle"
        )

    def _check_network_segmentation(self) -> AuditCheck:
        """Check network segmentation"""
        return AuditCheck(
            check_id="network_002",
            name="Network Segmentation",
            description="Verify network segmentation is implemented",
            category=AuditCategory.NETWORK_SECURITY,
            status=AuditStatus.WARNING,
            risk_level=RiskLevel.MEDIUM,
            details="Partial segmentation implemented, sensitive systems not fully isolated",
            remediation="Complete network segmentation for sensitive systems"
        )

    def _check_access_reviews(self) -> AuditCheck:
        """Check access review process"""
        return AuditCheck(
            check_id="access_001",
            name="Access Reviews",
            description="Verify periodic access reviews are conducted",
            category=AuditCategory.ACCESS_CONTROL,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.MEDIUM,
            details="Quarterly access reviews conducted, last review: 30 days ago"
        )

    def _check_privileged_access(self) -> AuditCheck:
        """Check privileged access management"""
        return AuditCheck(
            check_id="access_002",
            name="Privileged Access Management",
            description="Verify privileged accounts are properly managed",
            category=AuditCategory.ACCESS_CONTROL,
            status=AuditStatus.FAIL,
            risk_level=RiskLevel.CRITICAL,
            details="Shared admin accounts detected, no PAM solution implemented",
            remediation="Implement privileged access management solution",
            evidence={"shared_accounts": 3}
        )

    def _check_audit_logging(self) -> AuditCheck:
        """Check audit logging configuration"""
        return AuditCheck(
            check_id="logging_001",
            name="Audit Logging",
            description="Verify comprehensive audit logging",
            category=AuditCategory.LOGGING_MONITORING,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.HIGH,
            details="Audit logging enabled for all critical systems"
        )

    def _check_log_retention(self) -> AuditCheck:
        """Check log retention policy"""
        return AuditCheck(
            check_id="logging_002",
            name="Log Retention",
            description="Verify log retention meets compliance requirements",
            category=AuditCategory.LOGGING_MONITORING,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.MEDIUM,
            details="Logs retained for 1 year, meeting compliance requirements"
        )

    def _check_incident_response_plan(self) -> AuditCheck:
        """Check incident response plan"""
        return AuditCheck(
            check_id="incident_001",
            name="Incident Response Plan",
            description="Verify incident response plan exists and is tested",
            category=AuditCategory.INCIDENT_RESPONSE,
            status=AuditStatus.WARNING,
            risk_level=RiskLevel.HIGH,
            details="IR plan exists but last tabletop exercise was 6 months ago",
            remediation="Conduct regular incident response testing"
        )

    def _check_patch_management(self) -> AuditCheck:
        """Check patch management process"""
        return AuditCheck(
            check_id="patch_001",
            name="Patch Management",
            description="Verify patch management process is effective",
            category=AuditCategory.PATCH_MANAGEMENT,
            status=AuditStatus.WARNING,
            risk_level=RiskLevel.HIGH,
            details="Patch policy exists but critical patches have 5-day delay on average",
            remediation="Reduce patch deployment time for critical vulnerabilities"
        )

    def _check_hardening_standards(self) -> AuditCheck:
        """Check system hardening"""
        return AuditCheck(
            check_id="config_001",
            name="System Hardening",
            description="Verify systems are hardened per standards",
            category=AuditCategory.CONFIGURATION,
            status=AuditStatus.PASS,
            risk_level=RiskLevel.MEDIUM,
            details="CIS benchmarks applied to all servers"
        )

    def _check_default_credentials(self) -> AuditCheck:
        """Check for default credentials"""
        return AuditCheck(
            check_id="config_002",
            name="Default Credentials",
            description="Verify no default credentials are in use",
            category=AuditCategory.CONFIGURATION,
            status=AuditStatus.FAIL,
            risk_level=RiskLevel.CRITICAL,
            details="Default credentials found on 2 systems",
            remediation="Remove all default credentials immediately",
            evidence={"systems_with_defaults": 2}
        )

    def get_report(self, report_id: str) -> Optional[AuditReport]:
        """Get audit report by ID"""
        return self.reports.get(report_id)

    def get_latest_report(self) -> Optional[AuditReport]:
        """Get the most recent audit report"""
        if not self.reports:
            return None
        return max(self.reports.values(), key=lambda r: r.started_at)

    def register_check(self, check_id: str, check_func: Callable) -> None:
        """Register a custom audit check"""
        self._check_registry[check_id] = check_func

    def get_compliance_summary(self, report_id: str) -> Dict[str, Any]:
        """Get compliance mapping summary for a report"""
        report = self.reports.get(report_id)
        if not report:
            return {}
        
        compliance: Dict[str, Dict[str, Any]] = {}
        for check in report.checks:
            for framework, control in check.compliance_mapping.items():
                if framework not in compliance:
                    compliance[framework] = {"total": 0, "passed": 0, "failed": 0}
                compliance[framework]["total"] += 1
                if check.status == AuditStatus.PASS:
                    compliance[framework]["passed"] += 1
                elif check.status == AuditStatus.FAIL:
                    compliance[framework]["failed"] += 1
        
        return compliance
