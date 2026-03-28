"""
Compliance Checking Framework for Week 54 Advanced Security Hardening.

This module provides a comprehensive compliance checking framework that supports
multiple regulatory frameworks including GDPR, HIPAA, SOC2, PCI-DSS, and ISO27001.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime
import json


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    GDPR = "GDPR"
    HIPAA = "HIPAA"
    SOC2 = "SOC2"
    PCI_DSS = "PCI_DSS"
    ISO27001 = "ISO27001"


class ComplianceStatus(Enum):
    """Status of compliance check results."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIAL = "PARTIAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class Severity(Enum):
    """Severity levels for compliance findings."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class ComplianceRule:
    """
    Represents a single compliance rule to be checked.
    
    Attributes:
        rule_id: Unique identifier for the rule
        requirement: The compliance requirement text
        framework: The compliance framework this rule belongs to
        severity: Severity level of the rule
        check_function: Callable that performs the actual compliance check
        description: Detailed description of the rule
        remediation: Suggested remediation steps if non-compliant
    """
    rule_id: str
    requirement: str
    framework: ComplianceFramework
    severity: Severity
    check_function: Callable[[Dict[str, Any]], bool]
    description: str = ""
    remediation: str = ""
    
    def check(self, context: Dict[str, Any]) -> bool:
        """Execute the compliance check."""
        try:
            return self.check_function(context)
        except Exception as e:
            return False


@dataclass
class Finding:
    """
    Represents a compliance finding from a rule check.
    
    Attributes:
        rule_id: ID of the rule that was checked
        status: Compliance status of the finding
        message: Human-readable message about the finding
        severity: Severity level of the finding
        timestamp: When the finding was recorded
        details: Additional details about the finding
    """
    rule_id: str
    status: ComplianceStatus
    message: str
    severity: Severity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceResult:
    """
    Represents the result of a compliance check for a framework.
    
    Attributes:
        framework: The compliance framework that was checked
        status: Overall compliance status
        score: Compliance score (0-100)
        findings: List of individual findings
        checked_at: Timestamp when the check was performed
        summary: Summary of the compliance check
    """
    framework: ComplianceFramework
    status: ComplianceStatus
    score: float
    findings: List[Finding] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    summary: str = ""
    
    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the result."""
        self.findings.append(finding)
        
    def get_critical_findings(self) -> List[Finding]:
        """Get all critical severity findings."""
        return [f for f in self.findings if f.severity == Severity.CRITICAL]
    
    def get_non_compliant_findings(self) -> List[Finding]:
        """Get all non-compliant findings."""
        return [f for f in self.findings if f.status == ComplianceStatus.NON_COMPLIANT]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "framework": self.framework.value,
            "status": self.status.value,
            "score": self.score,
            "findings_count": len(self.findings),
            "critical_count": len(self.get_critical_findings()),
            "non_compliant_count": len(self.get_non_compliant_findings()),
            "checked_at": self.checked_at.isoformat(),
            "summary": self.summary
        }


class ComplianceChecker:
    """
    Main compliance checking framework that orchestrates compliance checks
    across multiple regulatory frameworks.
    
    Attributes:
        rules: Dictionary mapping frameworks to their rules
        results: Dictionary storing the latest results per framework
    """
    
    def __init__(self):
        """Initialize the compliance checker."""
        self.rules: Dict[ComplianceFramework, List[ComplianceRule]] = {
            framework: [] for framework in ComplianceFramework
        }
        self.results: Dict[ComplianceFramework, ComplianceResult] = {}
        self._initialize_default_rules()
    
    def _initialize_default_rules(self) -> None:
        """Initialize default compliance rules for each framework."""
        # GDPR Rules
        self.add_rule(ComplianceRule(
            rule_id="GDPR-001",
            requirement="Data encryption at rest",
            framework=ComplianceFramework.GDPR,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("encryption_at_rest", False),
            description="Personal data must be encrypted at rest",
            remediation="Enable encryption for all data storage systems"
        ))
        self.add_rule(ComplianceRule(
            rule_id="GDPR-002",
            requirement="Data encryption in transit",
            framework=ComplianceFramework.GDPR,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("encryption_in_transit", False),
            description="Personal data must be encrypted during transmission",
            remediation="Enable TLS for all data transmissions"
        ))
        self.add_rule(ComplianceRule(
            rule_id="GDPR-003",
            requirement="Data subject consent tracking",
            framework=ComplianceFramework.GDPR,
            severity=Severity.CRITICAL,
            check_function=lambda ctx: ctx.get("consent_tracking", False),
            description="Must track consent for data processing",
            remediation="Implement consent management system"
        ))
        self.add_rule(ComplianceRule(
            rule_id="GDPR-004",
            requirement="Data retention policy",
            framework=ComplianceFramework.GDPR,
            severity=Severity.MEDIUM,
            check_function=lambda ctx: ctx.get("retention_policy", False),
            description="Must have data retention policies in place",
            remediation="Define and implement data retention policies"
        ))
        self.add_rule(ComplianceRule(
            rule_id="GDPR-005",
            requirement="Right to erasure",
            framework=ComplianceFramework.GDPR,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("right_to_erasure", False),
            description="Must support data subject's right to erasure",
            remediation="Implement data deletion procedures"
        ))
        
        # HIPAA Rules
        self.add_rule(ComplianceRule(
            rule_id="HIPAA-001",
            requirement="PHI access controls",
            framework=ComplianceFramework.HIPAA,
            severity=Severity.CRITICAL,
            check_function=lambda ctx: ctx.get("phi_access_controls", False),
            description="Protected Health Information must have access controls",
            remediation="Implement role-based access control for PHI"
        ))
        self.add_rule(ComplianceRule(
            rule_id="HIPAA-002",
            requirement="PHI audit logging",
            framework=ComplianceFramework.HIPAA,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("phi_audit_logging", False),
            description="All PHI access must be logged",
            remediation="Enable comprehensive audit logging"
        ))
        self.add_rule(ComplianceRule(
            rule_id="HIPAA-003",
            requirement="PHI encryption",
            framework=ComplianceFramework.HIPAA,
            severity=Severity.CRITICAL,
            check_function=lambda ctx: ctx.get("phi_encryption", False),
            description="PHI must be encrypted at rest and in transit",
            remediation="Implement encryption for all PHI storage and transmission"
        ))
        self.add_rule(ComplianceRule(
            rule_id="HIPAA-004",
            requirement="Breach notification",
            framework=ComplianceFramework.HIPAA,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("breach_notification", False),
            description="Must have breach notification procedures",
            remediation="Implement breach notification system"
        ))
        
        # SOC2 Rules
        self.add_rule(ComplianceRule(
            rule_id="SOC2-001",
            requirement="Access control policies",
            framework=ComplianceFramework.SOC2,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("access_control_policies", False),
            description="Must have documented access control policies",
            remediation="Document and implement access control policies"
        ))
        self.add_rule(ComplianceRule(
            rule_id="SOC2-002",
            requirement="Change management",
            framework=ComplianceFramework.SOC2,
            severity=Severity.MEDIUM,
            check_function=lambda ctx: ctx.get("change_management", False),
            description="Must have change management procedures",
            remediation="Implement change management process"
        ))
        self.add_rule(ComplianceRule(
            rule_id="SOC2-003",
            requirement="Incident response",
            framework=ComplianceFramework.SOC2,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("incident_response", False),
            description="Must have incident response procedures",
            remediation="Develop incident response plan"
        ))
        self.add_rule(ComplianceRule(
            rule_id="SOC2-004",
            requirement="Vulnerability management",
            framework=ComplianceFramework.SOC2,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("vulnerability_management", False),
            description="Must have vulnerability management program",
            remediation="Implement vulnerability scanning and remediation"
        ))
        
        # PCI-DSS Rules
        self.add_rule(ComplianceRule(
            rule_id="PCI-001",
            requirement="Cardholder data protection",
            framework=ComplianceFramework.PCI_DSS,
            severity=Severity.CRITICAL,
            check_function=lambda ctx: ctx.get("cardholder_data_protection", False),
            description="Cardholder data must be protected",
            remediation="Implement cardholder data protection measures"
        ))
        self.add_rule(ComplianceRule(
            rule_id="PCI-002",
            requirement="Network segmentation",
            framework=ComplianceFramework.PCI_DSS,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("network_segmentation", False),
            description="Cardholder data environment must be segmented",
            remediation="Implement network segmentation"
        ))
        self.add_rule(ComplianceRule(
            rule_id="PCI-003",
            requirement="Regular security testing",
            framework=ComplianceFramework.PCI_DSS,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("security_testing", False),
            description="Must perform regular security testing",
            remediation="Schedule regular penetration tests and vulnerability scans"
        ))
        self.add_rule(ComplianceRule(
            rule_id="PCI-004",
            requirement="PCI-DSS compliance monitoring",
            framework=ComplianceFramework.PCI_DSS,
            severity=Severity.MEDIUM,
            check_function=lambda ctx: ctx.get("pci_compliance_monitoring", False),
            description="Must monitor PCI-DSS compliance continuously",
            remediation="Implement continuous compliance monitoring"
        ))
        
        # ISO27001 Rules
        self.add_rule(ComplianceRule(
            rule_id="ISO-001",
            requirement="Information security policy",
            framework=ComplianceFramework.ISO27001,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("infosec_policy", False),
            description="Must have documented information security policy",
            remediation="Develop and document information security policy"
        ))
        self.add_rule(ComplianceRule(
            rule_id="ISO-002",
            requirement="Risk assessment",
            framework=ComplianceFramework.ISO27001,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("risk_assessment", False),
            description="Must perform regular risk assessments",
            remediation="Implement risk assessment process"
        ))
        self.add_rule(ComplianceRule(
            rule_id="ISO-003",
            requirement="Security awareness training",
            framework=ComplianceFramework.ISO27001,
            severity=Severity.MEDIUM,
            check_function=lambda ctx: ctx.get("security_training", False),
            description="Must provide security awareness training",
            remediation="Implement security awareness training program"
        ))
        self.add_rule(ComplianceRule(
            rule_id="ISO-004",
            requirement="Business continuity",
            framework=ComplianceFramework.ISO27001,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("business_continuity", False),
            description="Must have business continuity plan",
            remediation="Develop business continuity plan"
        ))
        self.add_rule(ComplianceRule(
            rule_id="ISO-005",
            requirement="Supplier relationships security",
            framework=ComplianceFramework.ISO27001,
            severity=Severity.MEDIUM,
            check_function=lambda ctx: ctx.get("supplier_security", False),
            description="Must manage security in supplier relationships",
            remediation="Implement supplier security management"
        ))
    
    def add_rule(self, rule: ComplianceRule) -> None:
        """Add a compliance rule to the checker."""
        self.rules[rule.framework].append(rule)
    
    def check_compliance(
        self,
        framework: ComplianceFramework,
        context: Dict[str, Any]
    ) -> ComplianceResult:
        """
        Check compliance for a specific framework.
        
        Args:
            framework: The compliance framework to check
            context: Context dictionary with compliance data
            
        Returns:
            ComplianceResult with the check results
        """
        rules = self.rules.get(framework, [])
        findings: List[Finding] = []
        compliant_count = 0
        total_rules = len(rules)
        
        for rule in rules:
            is_compliant = rule.check(context)
            
            status = ComplianceStatus.COMPLIANT if is_compliant else ComplianceStatus.NON_COMPLIANT
            message = f"Rule {rule.rule_id}: {rule.requirement} - {'Passed' if is_compliant else 'Failed'}"
            
            finding = Finding(
                rule_id=rule.rule_id,
                status=status,
                message=message,
                severity=rule.severity,
                details={
                    "requirement": rule.requirement,
                    "remediation": rule.remediation if not is_compliant else None
                }
            )
            findings.append(finding)
            
            if is_compliant:
                compliant_count += 1
        
        # Calculate score
        score = (compliant_count / total_rules * 100) if total_rules > 0 else 0.0
        
        # Determine overall status
        if score == 100:
            status = ComplianceStatus.COMPLIANT
        elif score >= 80:
            status = ComplianceStatus.PARTIAL
        else:
            status = ComplianceStatus.NON_COMPLIANT
        
        result = ComplianceResult(
            framework=framework,
            status=status,
            score=score,
            findings=findings,
            summary=f"Compliance score: {score:.1f}%. {compliant_count}/{total_rules} rules passed."
        )
        
        self.results[framework] = result
        return result
    
    def check_all_frameworks(
        self,
        context: Dict[str, Any]
    ) -> Dict[ComplianceFramework, ComplianceResult]:
        """
        Check compliance for all frameworks.
        
        Args:
            context: Context dictionary with compliance data
            
        Returns:
            Dictionary mapping frameworks to their results
        """
        results = {}
        for framework in ComplianceFramework:
            results[framework] = self.check_compliance(framework, context)
        return results
    
    def get_result(self, framework: ComplianceFramework) -> Optional[ComplianceResult]:
        """Get the latest result for a framework."""
        return self.results.get(framework)
    
    def get_overall_score(self) -> float:
        """Calculate overall compliance score across all checked frameworks."""
        if not self.results:
            return 0.0
        
        total_score = sum(result.score for result in self.results.values())
        return total_score / len(self.results)
    
    def get_all_critical_findings(self) -> List[Finding]:
        """Get all critical findings across all frameworks."""
        findings = []
        for result in self.results.values():
            findings.extend(result.get_critical_findings())
        return findings
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive compliance report."""
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "overall_score": self.get_overall_score(),
            "frameworks": {
                framework.value: result.to_dict()
                for framework, result in self.results.items()
            },
            "critical_findings_count": len(self.get_all_critical_findings()),
            "summary": self._generate_summary()
        }
    
    def _generate_summary(self) -> str:
        """Generate a summary of compliance status."""
        if not self.results:
            return "No compliance checks have been performed."
        
        compliant = sum(1 for r in self.results.values() if r.status == ComplianceStatus.COMPLIANT)
        partial = sum(1 for r in self.results.values() if r.status == ComplianceStatus.PARTIAL)
        non_compliant = sum(1 for r in self.results.values() if r.status == ComplianceStatus.NON_COMPLIANT)
        
        return (
            f"Compliance Summary: {compliant} compliant, "
            f"{partial} partial, {non_compliant} non-compliant frameworks. "
            f"Overall score: {self.get_overall_score():.1f}%"
        )
    
    def clear_results(self) -> None:
        """Clear all stored results."""
        self.results.clear()
    
    def get_rules_by_framework(self, framework: ComplianceFramework) -> List[ComplianceRule]:
        """Get all rules for a specific framework."""
        return self.rules.get(framework, [])
    
    def get_rules_by_severity(self, severity: Severity) -> List[ComplianceRule]:
        """Get all rules with a specific severity across all frameworks."""
        rules = []
        for framework_rules in self.rules.values():
            rules.extend(r for r in framework_rules if r.severity == severity)
        return rules
