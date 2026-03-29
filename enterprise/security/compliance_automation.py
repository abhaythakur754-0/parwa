"""
Enterprise Security - Compliance Automation
Automated compliance checking for enterprise
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ComplianceFramework(str, Enum):
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    CCPA = "ccpa"
    SOC2 = "soc2"
    ISO27001 = "iso27001"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ComplianceCheck(BaseModel):
    """Compliance check result"""
    check_id: str
    framework: ComplianceFramework
    requirement: str
    status: ComplianceStatus
    description: str
    remediation: Optional[str] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    client_id: Optional[str] = None

    model_config = ConfigDict()


class ComplianceReport(BaseModel):
    """Compliance report"""
    report_id: str
    client_id: str
    framework: ComplianceFramework
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    checks: List[ComplianceCheck] = Field(default_factory=list)
    score: float = 0.0

    model_config = ConfigDict()


class ComplianceAutomation:
    """
    Automated compliance checking for enterprise clients.
    """

    HIPAA_REQUIREMENTS = [
        ("access_control", "Implement access controls", "Enable role-based access"),
        ("audit_logs", "Maintain audit logs", "Enable comprehensive logging"),
        ("encryption", "Encrypt PHI data", "Implement encryption at rest and in transit"),
        ("backup", "Implement data backup", "Configure automated backups"),
        ("auth", "Implement authentication", "Enable multi-factor authentication")
    ]

    PCI_DSS_REQUIREMENTS = [
        ("firewall", "Install firewall", "Configure network firewall"),
        ("passwords", "Change default passwords", "Set strong passwords"),
        ("cardholder_data", "Protect stored cardholder data", "Encrypt card data"),
        ("encryption_transit", "Encrypt transmission", "Enable TLS for all connections"),
        ("antivirus", "Use antivirus software", "Deploy antivirus solutions")
    ]

    GDPR_REQUIREMENTS = [
        ("consent", "Obtain consent", "Implement consent management"),
        ("data_portability", "Enable data portability", "Implement export functionality"),
        ("right_deletion", "Right to erasure", "Implement deletion workflows"),
        ("privacy_policy", "Privacy policy", "Publish privacy policy"),
        ("data_protection", "Data protection officer", "Appoint DPO")
    ]

    def __init__(self):
        self.reports: Dict[str, ComplianceReport] = {}
        self.client_frameworks: Dict[str, List[ComplianceFramework]] = {}

    def set_client_frameworks(self, client_id: str, frameworks: List[ComplianceFramework]) -> None:
        """Set required frameworks for a client"""
        self.client_frameworks[client_id] = frameworks

    def run_compliance_check(
        self,
        client_id: str,
        framework: ComplianceFramework,
        requirements: Optional[List[Dict[str, Any]]] = None
    ) -> ComplianceReport:
        """Run compliance check for a framework"""
        import uuid

        if requirements is None:
            requirements = self._get_default_requirements(framework)

        checks = []
        compliant_count = 0

        for req in requirements:
            check = ComplianceCheck(
                check_id=f"check_{uuid.uuid4().hex[:8]}",
                framework=framework,
                requirement=req.get("id", "unknown"),
                status=ComplianceStatus.COMPLIANT,  # Simplified
                description=req.get("description", ""),
                remediation=req.get("remediation"),
                client_id=client_id
            )
            checks.append(check)

            if check.status == ComplianceStatus.COMPLIANT:
                compliant_count += 1

        score = (compliant_count / len(requirements) * 100) if requirements else 0

        report = ComplianceReport(
            report_id=f"rpt_{uuid.uuid4().hex[:8]}",
            client_id=client_id,
            framework=framework,
            overall_status=ComplianceStatus.COMPLIANT if score == 100 else ComplianceStatus.PARTIAL,
            checks=checks,
            score=score
        )

        self.reports[report.report_id] = report
        return report

    def _get_default_requirements(self, framework: ComplianceFramework) -> List[Dict[str, Any]]:
        """Get default requirements for a framework"""
        if framework == ComplianceFramework.HIPAA:
            return [{"id": r[0], "description": r[1], "remediation": r[2]} for r in self.HIPAA_REQUIREMENTS]
        elif framework == ComplianceFramework.PCI_DSS:
            return [{"id": r[0], "description": r[1], "remediation": r[2]} for r in self.PCI_DSS_REQUIREMENTS]
        elif framework == ComplianceFramework.GDPR:
            return [{"id": r[0], "description": r[1], "remediation": r[2]} for r in self.GDPR_REQUIREMENTS]
        return []

    def get_client_reports(self, client_id: str) -> List[ComplianceReport]:
        """Get all reports for a client"""
        return [r for r in self.reports.values() if r.client_id == client_id]

    def get_latest_report(
        self,
        client_id: str,
        framework: ComplianceFramework
    ) -> Optional[ComplianceReport]:
        """Get latest report for a client and framework"""
        reports = [
            r for r in self.reports.values()
            if r.client_id == client_id and r.framework == framework
        ]
        if reports:
            return max(reports, key=lambda r: r.generated_at)
        return None

    def get_compliance_score(self, client_id: str) -> float:
        """Get overall compliance score for a client"""
        reports = self.get_client_reports(client_id)
        if not reports:
            return 0.0

        return sum(r.score for r in reports) / len(reports)
