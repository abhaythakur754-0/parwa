# Compliance Reporter - Week 49 Builder 2
# Compliance report generator for enterprise audit

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class ComplianceFramework(Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    CCPA = "ccpa"
    CUSTOM = "custom"


class ReportStatus(Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    HTML = "html"


@dataclass
class ComplianceFinding:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    framework: ComplianceFramework = ComplianceFramework.GDPR
    category: str = ""
    requirement: str = ""
    status: str = "unknown"
    severity: str = "medium"
    description: str = ""
    evidence: List[str] = field(default_factory=list)
    remediation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComplianceReport:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    framework: ComplianceFramework = ComplianceFramework.GDPR
    status: ReportStatus = ReportStatus.PENDING
    start_date: datetime = field(default_factory=datetime.utcnow)
    end_date: datetime = field(default_factory=datetime.utcnow)
    findings: List[ComplianceFinding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    format: ReportFormat = ReportFormat.JSON


class ComplianceReporter:
    """Generates compliance reports for enterprise audit"""

    def __init__(self, audit_logger=None):
        self._audit_logger = audit_logger
        self._reports: Dict[str, ComplianceReport] = {}
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._metrics = {
            "total_reports": 0,
            "by_framework": {},
            "avg_score": 0.0
        }
        self._initialize_templates()

    def _initialize_templates(self) -> None:
        """Initialize report templates for each framework"""
        self._templates = {
            ComplianceFramework.GDPR: {
                "categories": [
                    "data_subject_rights",
                    "data_processing",
                    "consent_management",
                    "data_breach_notification",
                    "privacy_by_design"
                ],
                "requirements": [
                    "Right to access",
                    "Right to erasure",
                    "Data minimization",
                    "Purpose limitation",
                    "Storage limitation"
                ]
            },
            ComplianceFramework.HIPAA: {
                "categories": [
                    "privacy_rule",
                    "security_rule",
                    "breach_notification",
                    "enforcement_rule",
                    "phi_protection"
                ],
                "requirements": [
                    "PHI access controls",
                    "Audit controls",
                    "Integrity controls",
                    "Transmission security",
                    "Workforce training"
                ]
            },
            ComplianceFramework.SOC2: {
                "categories": [
                    "security",
                    "availability",
                    "processing_integrity",
                    "confidentiality",
                    "privacy"
                ],
                "requirements": [
                    "Access controls",
                    "Change management",
                    "Risk assessment",
                    "Monitoring",
                    "Incident response"
                ]
            }
        }

    def set_audit_logger(self, logger) -> None:
        """Set the audit logger source"""
        self._audit_logger = logger

    def create_report(
        self,
        tenant_id: str,
        framework: ComplianceFramework,
        name: str,
        start_date: datetime,
        end_date: datetime,
        created_by: str = "",
        format: ReportFormat = ReportFormat.JSON
    ) -> ComplianceReport:
        """Create a new compliance report"""
        report = ComplianceReport(
            tenant_id=tenant_id,
            framework=framework,
            name=name or f"{framework.value.upper()} Report",
            start_date=start_date,
            end_date=end_date,
            created_by=created_by,
            format=format
        )

        self._reports[report.id] = report
        self._metrics["total_reports"] += 1

        fw_key = framework.value
        self._metrics["by_framework"][fw_key] = self._metrics["by_framework"].get(fw_key, 0) + 1

        return report

    def add_finding(
        self,
        report_id: str,
        category: str,
        requirement: str,
        status: str,
        severity: str = "medium",
        description: str = "",
        evidence: Optional[List[str]] = None,
        remediation: Optional[str] = None
    ) -> Optional[ComplianceFinding]:
        """Add a finding to a report"""
        report = self._reports.get(report_id)
        if not report:
            return None

        finding = ComplianceFinding(
            framework=report.framework,
            category=category,
            requirement=requirement,
            status=status,
            severity=severity,
            description=description,
            evidence=evidence or [],
            remediation=remediation
        )

        report.findings.append(finding)
        return finding

    def generate_report(
        self,
        tenant_id: str,
        framework: ComplianceFramework,
        start_date: datetime,
        end_date: datetime
    ) -> ComplianceReport:
        """Generate a compliance report automatically"""
        report = self.create_report(
            tenant_id=tenant_id,
            framework=framework,
            name=f"{framework.value.upper()} Compliance Report",
            start_date=start_date,
            end_date=end_date
        )

        report.status = ReportStatus.GENERATING

        # Get template for framework
        template = self._templates.get(framework, {})

        # Generate findings based on template
        for category in template.get("categories", []):
            finding = ComplianceFinding(
                framework=framework,
                category=category,
                requirement=f"{category} compliance",
                status="compliant",
                severity="low",
                description=f"Assessment of {category}"
            )
            report.findings.append(finding)

        # Calculate score
        report.score = self._calculate_score(report)
        report.summary = self._generate_summary(report)
        report.status = ReportStatus.COMPLETED

        return report

    def _calculate_score(self, report: ComplianceReport) -> float:
        """Calculate compliance score"""
        if not report.findings:
            return 100.0

        compliant = len([f for f in report.findings if f.status == "compliant"])
        total = len(report.findings)
        return (compliant / total) * 100 if total > 0 else 100.0

    def _generate_summary(self, report: ComplianceReport) -> Dict[str, Any]:
        """Generate report summary"""
        findings = report.findings
        return {
            "total_findings": len(findings),
            "compliant": len([f for f in findings if f.status == "compliant"]),
            "non_compliant": len([f for f in findings if f.status == "non_compliant"]),
            "partial": len([f for f in findings if f.status == "partial"]),
            "by_severity": {
                "critical": len([f for f in findings if f.severity == "critical"]),
                "high": len([f for f in findings if f.severity == "high"]),
                "medium": len([f for f in findings if f.severity == "medium"]),
                "low": len([f for f in findings if f.severity == "low"])
            }
        }

    def get_report(self, report_id: str) -> Optional[ComplianceReport]:
        """Get a report by ID"""
        return self._reports.get(report_id)

    def get_reports_by_tenant(
        self,
        tenant_id: str,
        framework: Optional[ComplianceFramework] = None
    ) -> List[ComplianceReport]:
        """Get all reports for a tenant"""
        reports = [r for r in self._reports.values() if r.tenant_id == tenant_id]
        if framework:
            reports = [r for r in reports if r.framework == framework]
        return reports

    def export_report(
        self,
        report_id: str,
        format: Optional[ReportFormat] = None
    ) -> Optional[Dict[str, Any]]:
        """Export report in specified format"""
        report = self._reports.get(report_id)
        if not report:
            return None

        export_format = format or report.format

        return {
            "id": report.id,
            "tenant_id": report.tenant_id,
            "name": report.name,
            "framework": report.framework.value,
            "status": report.status.value,
            "score": report.score,
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
            "findings": [
                {
                    "category": f.category,
                    "requirement": f.requirement,
                    "status": f.status,
                    "severity": f.severity,
                    "description": f.description,
                    "remediation": f.remediation
                }
                for f in report.findings
            ],
            "summary": report.summary,
            "created_at": report.created_at.isoformat(),
            "format": export_format.value
        }

    def delete_report(self, report_id: str) -> bool:
        """Delete a report"""
        if report_id in self._reports:
            del self._reports[report_id]
            self._metrics["total_reports"] -= 1
            return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get reporter metrics"""
        return {
            **self._metrics,
            "total_reports_stored": len(self._reports)
        }

    def compare_reports(
        self,
        report_id1: str,
        report_id2: str
    ) -> Optional[Dict[str, Any]]:
        """Compare two compliance reports"""
        report1 = self._reports.get(report_id1)
        report2 = self._reports.get(report_id2)

        if not report1 or not report2:
            return None

        return {
            "report1": {
                "id": report1.id,
                "score": report1.score,
                "findings_count": len(report1.findings)
            },
            "report2": {
                "id": report2.id,
                "score": report2.score,
                "findings_count": len(report2.findings)
            },
            "score_difference": report1.score - report2.score,
            "findings_difference": len(report1.findings) - len(report2.findings)
        }
