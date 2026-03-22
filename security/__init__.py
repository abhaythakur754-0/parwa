"""
Security Module for PARWA.

Provides security scanning and vulnerability detection capabilities:
- OWASP Top 10 scanning
- CVE vulnerability scanning
- Dependency vulnerability checking
"""
from .owasp_scan import OWASPScanner, OWASPResult
from .cve_scan import CVEScanner, CVEScanResult
from .dependency_check import DependencyChecker, DependencyCheckResult

__all__ = [
    "OWASPScanner",
    "OWASPResult",
    "CVEScanner",
    "CVEScanResult",
    "DependencyChecker",
    "DependencyCheckResult",
]
