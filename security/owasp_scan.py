"""
OWASP Top 10 Security Scanner.

Implements comprehensive OWASP Top 10 security checks:
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection
- A04: Insecure Design
- A05: Security Misconfiguration
- A06: Vulnerable and Outdated Components
- A07: Identification and Authentication Failures
- A08: Software and Data Integrity Failures
- A09: Security Logging and Monitoring Failures
- A10: Server-Side Request Forgery (SSRF)

CRITICAL: All 10 checks must pass.
"""
import re
import os
import ast
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class OWASPResult:
    """Result of an OWASP check."""
    code: str
    name: str
    passed: bool
    message: str
    details: List[str]
    severity: str  # critical, high, medium, low


class OWASPScanner:
    """OWASP Top 10 Security Scanner."""

    def __init__(self, project_root: str = "."):
        """Initialize scanner with project root."""
        self.project_root = Path(project_root)
        self.results: List[OWASPResult] = []

    def scan_all(self) -> Dict[str, Any]:
        """Run all OWASP Top 10 checks."""
        self.results = [
            self.check_a01_broken_access_control(),
            self.check_a02_cryptographic_failures(),
            self.check_a03_injection(),
            self.check_a04_insecure_design(),
            self.check_a05_security_misconfiguration(),
            self.check_a06_vulnerable_components(),
            self.check_a07_authentication_failures(),
            self.check_a08_software_integrity(),
            self.check_a09_security_logging(),
            self.check_a10_ssrf(),
        ]

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        return {
            "total_checks": len(self.results),
            "passed": passed,
            "failed": failed,
            "all_passed": failed == 0,
            "results": [{"code": r.code, "name": r.name, "passed": r.passed, "message": r.message} for r in self.results],
        }

    def check_a01_broken_access_control(self) -> OWASPResult:
        """A01: Check for broken access control vulnerabilities."""
        issues = []
        
        # Check for missing auth decorators
        api_files = list(self.project_root.glob("**/api/*.py"))
        for api_file in api_files:
            try:
                content = api_file.read_text()
                # Check if endpoints have auth checks
                if "@router" in content and "def " in content:
                    if "get_current_user" not in content and "require_auth" not in content:
                        if "public" not in api_file.name:
                            issues.append(f"{api_file}: Endpoint may lack authentication")
            except Exception:
                pass

        # Check for direct object references
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if re.search(r'\.get\(["\']?\w+_id["\']?\)', content):
                    if "owner_id" not in content and "user_id" not in content:
                        issues.append(f"{py_file}: Potential insecure direct object reference")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A01",
            name="Broken Access Control",
            passed=passed,
            message="All endpoints have proper access control" if passed else f"Found {len(issues)} access control issues",
            details=issues[:10],
            severity="critical" if not passed else "low",
        )

    def check_a02_cryptographic_failures(self) -> OWASPResult:
        """A02: Check for cryptographic failures."""
        issues = []
        
        # Check for weak hashing algorithms
        weak_algos = ["md5", "sha1"]
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                for algo in weak_algos:
                    if re.search(rf'hashlib\.{algo}\s*\(', content):
                        if "password" in content.lower() or "secret" in content.lower():
                            issues.append(f"{py_file}: Uses weak hash {algo} for sensitive data")
            except Exception:
                pass

        # Check for hardcoded secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+(["\'])',
            r'api_key\s*=\s*["\'][^"\']+(["\'])',
            r'secret\s*=\s*["\'][^"\']+(["\'])',
        ]
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                for pattern in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches and "test" not in str(py_file).lower():
                        issues.append(f"{py_file}: Potential hardcoded secret")
            except Exception:
                pass

        # Check for HTTPS usage
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "http://" in content and "localhost" not in content:
                    issues.append(f"{py_file}: Uses insecure HTTP")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A02",
            name="Cryptographic Failures",
            passed=passed,
            message="No cryptographic vulnerabilities found" if passed else f"Found {len(issues)} cryptographic issues",
            details=issues[:10],
            severity="critical" if not passed else "low",
        )

    def check_a03_injection(self) -> OWASPResult:
        """A03: Check for injection vulnerabilities."""
        issues = []
        
        # Check for SQL injection
        sql_patterns = [
            r'f["\'].*SELECT.*{',
            r'f["\'].*INSERT.*{',
            r'f["\'].*UPDATE.*{',
            r'f["\'].*DELETE.*{',
            r'\.execute\(["\'].*%s',
            r'\+.*SELECT',
        ]
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                for pattern in sql_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues.append(f"{py_file}: Potential SQL injection")
                        break
            except Exception:
                pass

        # Check for command injection
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if re.search(r'os\.system\s*\(', content):
                    issues.append(f"{py_file}: Uses os.system (command injection risk)")
                if re.search(r'subprocess\..*shell\s*=\s*True', content):
                    issues.append(f"{py_file}: Uses shell=True (command injection risk)")
            except Exception:
                pass

        # Check for NoSQL injection
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if re.search(r'\$where', content):
                    issues.append(f"{py_file}: Potential NoSQL injection ($where)")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A03",
            name="Injection",
            passed=passed,
            message="No injection vulnerabilities found" if passed else f"Found {len(issues)} injection issues",
            details=issues[:10],
            severity="critical" if not passed else "low",
        )

    def check_a04_insecure_design(self) -> OWASPResult:
        """A04: Check for insecure design patterns."""
        issues = []
        
        # Check for missing rate limiting
        api_files = list(self.project_root.glob("**/api/*.py"))
        for api_file in api_files:
            try:
                content = api_file.read_text()
                if "@router" in content:
                    if "rate_limit" not in content.lower() and "limiter" not in content.lower():
                        if "auth" in api_file.name or "login" in api_file.name:
                            issues.append(f"{api_file}: Auth endpoint may lack rate limiting")
            except Exception:
                pass

        # Check for missing input validation
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "request.json()" in content or "request.form" in content:
                    if "validate" not in content.lower() and "schema" not in content.lower():
                        issues.append(f"{py_file}: May lack input validation")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A04",
            name="Insecure Design",
            passed=passed,
            message="No insecure design patterns found" if passed else f"Found {len(issues)} design issues",
            details=issues[:10],
            severity="high" if not passed else "low",
        )

    def check_a05_security_misconfiguration(self) -> OWASPResult:
        """A05: Check for security misconfiguration."""
        issues = []
        
        # Check for debug mode
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if re.search(r'DEBUG\s*=\s*True', content):
                    if "test" not in str(py_file).lower():
                        issues.append(f"{py_file}: Debug mode enabled")
            except Exception:
                pass

        # Check for missing security headers
        for py_file in self.project_root.glob("**/middleware*.py"):
            try:
                content = py_file.read_text()
                required_headers = ["X-Content-Type-Options", "X-Frame-Options", "X-XSS-Protection"]
                for header in required_headers:
                    if header not in content:
                        issues.append(f"{py_file}: Missing security header {header}")
            except Exception:
                pass

        # Check for CORS misconfiguration
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if 'allow_origins=["*"]' in content or "allow_origins = ['*']" in content:
                    issues.append(f"{py_file}: CORS allows all origins")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A05",
            name="Security Misconfiguration",
            passed=passed,
            message="No security misconfigurations found" if passed else f"Found {len(issues)} misconfiguration issues",
            details=issues[:10],
            severity="high" if not passed else "low",
        )

    def check_a06_vulnerable_components(self) -> OWASPResult:
        """A06: Check for vulnerable components."""
        issues = []
        
        # Check requirements.txt for known vulnerable packages
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text()
                # Check for outdated packages (simplified check)
                if "pillow<9" in content or "pillow==8" in content:
                    issues.append("requirements.txt: Pillow version may be vulnerable")
                if "requests<2.31" in content:
                    issues.append("requirements.txt: Requests version may be vulnerable")
            except Exception:
                pass

        # Check package.json for vulnerable packages
        pkg_file = self.project_root / "frontend" / "package.json"
        if pkg_file.exists():
            try:
                content = pkg_file.read_text()
                # Check for known vulnerable packages
                if "lodash<4.17.21" in content:
                    issues.append("package.json: Lodash version may be vulnerable")
                if "axios<0.21.1" in content:
                    issues.append("package.json: Axios version may be vulnerable")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A06",
            name="Vulnerable and Outdated Components",
            passed=passed,
            message="No vulnerable components found" if passed else f"Found {len(issues)} vulnerable component issues",
            details=issues[:10],
            severity="critical" if not passed else "low",
        )

    def check_a07_authentication_failures(self) -> OWASPResult:
        """A07: Check for authentication failures."""
        issues = []
        
        # Check for weak password requirements
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "password" in content.lower():
                    if "min_length" not in content and "validate_password" not in content:
                        issues.append(f"{py_file}: May have weak password validation")
            except Exception:
                pass

        # Check for missing session management
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "session" in content.lower():
                    if "httponly" not in content.lower() and "secure" not in content.lower():
                        issues.append(f"{py_file}: Session may lack secure flags")
            except Exception:
                pass

        # Check for brute force protection
        auth_files = list(self.project_root.glob("**/auth*.py"))
        for auth_file in auth_files:
            try:
                content = auth_file.read_text()
                if "login" in content.lower():
                    if "lockout" not in content.lower() and "attempt" not in content.lower():
                        issues.append(f"{auth_file}: May lack brute force protection")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A07",
            name="Identification and Authentication Failures",
            passed=passed,
            message="No authentication vulnerabilities found" if passed else f"Found {len(issues)} authentication issues",
            details=issues[:10],
            severity="critical" if not passed else "low",
        )

    def check_a08_software_integrity(self) -> OWASPResult:
        """A08: Check for software and data integrity failures."""
        issues = []
        
        # Check for unsigned updates
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "download" in content.lower() and "verify" not in content.lower():
                    issues.append(f"{py_file}: Download without verification")
            except Exception:
                pass

        # Check for insecure deserialization
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "pickle.loads" in content or "yaml.load" in content:
                    if "safe_load" not in content:
                        issues.append(f"{py_file}: Insecure deserialization")
            except Exception:
                pass

        # Check for CI/CD security
        workflow_files = list(self.project_root.glob("**/.github/workflows/*.yml"))
        for wf in workflow_files:
            try:
                content = wf.read_text()
                if "pull_request_target" in content:
                    issues.append(f"{wf}: Uses pull_request_target (potential injection)")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A08",
            name="Software and Data Integrity Failures",
            passed=passed,
            message="No integrity vulnerabilities found" if passed else f"Found {len(issues)} integrity issues",
            details=issues[:10],
            severity="high" if not passed else "low",
        )

    def check_a09_security_logging(self) -> OWASPResult:
        """A09: Check for security logging and monitoring failures."""
        issues = []
        
        # Check for logging of security events
        auth_files = list(self.project_root.glob("**/auth*.py"))
        for auth_file in auth_files:
            try:
                content = auth_file.read_text()
                if "login" in content.lower() or "password" in content.lower():
                    if "logger" not in content.lower() and "log" not in content.lower():
                        issues.append(f"{auth_file}: Security events may not be logged")
            except Exception:
                pass

        # Check for logging sensitive data
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if re.search(r'log.*password', content, re.IGNORECASE):
                    issues.append(f"{py_file}: May log passwords")
                if re.search(r'log.*token', content, re.IGNORECASE):
                    issues.append(f"{py_file}: May log tokens")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A09",
            name="Security Logging and Monitoring Failures",
            passed=passed,
            message="Security logging is adequate" if passed else f"Found {len(issues)} logging issues",
            details=issues[:10],
            severity="medium" if not passed else "low",
        )

    def check_a10_ssrf(self) -> OWASPResult:
        """A10: Check for Server-Side Request Forgery."""
        issues = []
        
        # Check for user input in URLs
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if "requests.get" in content or "requests.post" in content:
                    if "request.args" in content or "request.json" in content:
                        if "allowlist" not in content.lower() and "whitelist" not in content.lower():
                            issues.append(f"{py_file}: Potential SSRF vulnerability")
            except Exception:
                pass

        # Check for URL fetching without validation
        for py_file in self.project_root.glob("**/*.py"):
            try:
                content = py_file.read_text()
                if re.search(r'urllib\.request\.urlopen\s*\(', content):
                    issues.append(f"{py_file}: Uses urllib without URL validation")
            except Exception:
                pass

        passed = len(issues) == 0
        return OWASPResult(
            code="A10",
            name="Server-Side Request Forgery (SSRF)",
            passed=passed,
            message="No SSRF vulnerabilities found" if passed else f"Found {len(issues)} SSRF issues",
            details=issues[:10],
            severity="critical" if not passed else "low",
        )

    def generate_report(self) -> str:
        """Generate a text report of all scan results."""
        report_lines = ["=" * 60, "OWASP Top 10 Security Scan Report", "=" * 60, ""]

        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            report_lines.append(f"{result.code}: {result.name}")
            report_lines.append(f"  Status: {status}")
            report_lines.append(f"  Message: {result.message}")
            if result.details:
                report_lines.append(f"  Details:")
                for detail in result.details[:5]:
                    report_lines.append(f"    - {detail}")
            report_lines.append("")

        passed = sum(1 for r in self.results if r.passed)
        report_lines.append(f"Summary: {passed}/{len(self.results)} checks passed")

        return "\n".join(report_lines)


def main():
    """Run OWASP scan from command line."""
    import sys
    
    scanner = OWASPScanner(".")
    results = scanner.scan_all()
    
    print(scanner.generate_report())
    
    if not results["all_passed"]:
        sys.exit(1)
    
    print("\n✅ All OWASP Top 10 checks passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
