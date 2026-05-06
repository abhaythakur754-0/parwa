"""
Secrets Scanner.

Scans for accidentally committed secrets:
- API keys
- Passwords
- Tokens
- Private keys
- AWS credentials
- Database connection strings
"""
import re
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class SecretFinding:
    """Result of a secrets scan."""
    file_path: str
    line_number: int
    secret_type: str
    matched_pattern: str
    severity: str
    context: str


class SecretsScanner:
    """Scanner for accidentally committed secrets."""

    # Patterns for detecting secrets
    SECRET_PATTERNS = [
        # AWS Access Key
        {
            "name": "AWS Access Key",
            "pattern": r'AKIA[0-9A-Z]{16}',
            "severity": "critical",
        },
        # AWS Secret Key
        {
            "name": "AWS Secret Key",
            "pattern": r'aws_secret_access_key\s*=\s*["\']?[A-Za-z0-9/+=]{40}["\']?',
            "severity": "critical",
        },
        # Generic API Key
        {
            "name": "Generic API Key",
            "pattern": r'api[_-]?key\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']',
            "severity": "high",
        },
        # Generic Secret
        {
            "name": "Generic Secret",
            "pattern": r'secret[_-]?key\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']',
            "severity": "high",
        },
        # Password in config
        {
            "name": "Password",
            "pattern": r'password\s*=\s*["\'][^"\']{8,}["\']',
            "severity": "high",
        },
        # Database connection string
        {
            "name": "Database Connection String",
            "pattern": r'(postgres|mysql|mongodb)://[^:]+:[^@]+@[^/]+',
            "severity": "critical",
        },
        # JWT Secret
        {
            "name": "JWT Secret",
            "pattern": r'jwt[_-]?secret\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']',
            "severity": "critical",
        },
        # Private Key
        {
            "name": "Private Key",
            "pattern": r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
            "severity": "critical",
        },
        # Stripe API Key
        {
            "name": "Stripe API Key",
            "pattern": r'sk_(live|test)_[0-9a-zA-Z]{24}',
            "severity": "critical",
        },
        # GitHub Token
        {
            "name": "GitHub Token",
            "pattern": r'ghp_[0-9a-zA-Z]{36}',
            "severity": "critical",
        },
        # Slack Token
        {
            "name": "Slack Token",
            "pattern": r'xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24}',
            "severity": "high",
        },
        # Twilio Auth Token
        {
            "name": "Twilio Auth Token",
            "pattern": r'TWILIO_AUTH_TOKEN\s*=\s*["\'][a-f0-9]{32}["\']',
            "severity": "high",
        },
    ]

    # Files to skip
    SKIP_PATTERNS = [
        r'\.git/',
        r'__pycache__/',
        r'node_modules/',
        r'\.pyc$',
        r'\.min\.js$',
        r'venv/',
        r'\.venv/',
        r'test.*\.py$',
        r'.*_test\.py$',
    ]

    def __init__(self, project_root: str = "."):
        """Initialize scanner with project root."""
        self.project_root = Path(project_root)
        self.findings: List[SecretFinding] = []

    def scan_all(self) -> Dict[str, Any]:
        """Scan all files for secrets."""
        self.findings = []

        # Scan all text files
        for file_path in self._get_scanable_files():
            self._scan_file(file_path)

        # Categorize by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for finding in self.findings:
            sev = finding.severity.lower()
            if sev in by_severity:
                by_severity[sev].append(finding)

        return {
            "total_findings": len(self.findings),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "has_secrets": len(self.findings) > 0,
            "critical_count": len(by_severity["critical"]),
            "findings": [{"file": f.file_path, "type": f.secret_type, "severity": f.severity} for f in self.findings[:20]],
        }

    def _get_scanable_files(self) -> List[Path]:
        """Get list of files to scan."""
        files = []
        
        # Extensions to scan
        scan_extensions = [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
            ".env", ".cfg", ".ini", ".conf", ".sh", ".bash", ".zsh",
            ".md", ".txt", ".sql", ".toml",
        ]

        for ext in scan_extensions:
            for file_path in self.project_root.glob(f"**/*{ext}"):
                # Check if file should be skipped
                skip = False
                for pattern in self.SKIP_PATTERNS:
                    if re.search(pattern, str(file_path)):
                        skip = True
                        break
                if not skip:
                    files.append(file_path)

        # Also check for files without extensions
        for file_path in self.project_root.glob("*"):
            if file_path.is_file() and file_path.suffix == "":
                if file_path.name.startswith(".env"):
                    files.append(file_path)

        return files

    def _scan_file(self, file_path: Path) -> None:
        """Scan a single file for secrets."""
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                for pattern_info in self.SECRET_PATTERNS:
                    match = re.search(pattern_info["pattern"], line, re.IGNORECASE)
                    if match:
                        # Check for false positives
                        if self._is_false_positive(line, pattern_info["name"]):
                            continue

                        self.findings.append(SecretFinding(
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_number=i,
                            secret_type=pattern_info["name"],
                            matched_pattern=match.group()[:50] + "...",  # Truncate for safety
                            severity=pattern_info["severity"],
                            context=line.strip()[:100],
                        ))
        except Exception:
            pass

    def _is_false_positive(self, line: str, secret_type: str) -> bool:
        """Check if a match is a false positive."""
        line_lower = line.lower()
        
        # Skip placeholder/example values
        placeholders = [
            "your_", "example", "placeholder", "xxx", "test_", "mock_",
            "fake_", "dummy_", "sample_", "<", ">", "${", "os.environ",
            "getenv", "settings.", "config.", "env[", "process.env",
        ]
        
        for placeholder in placeholders:
            if placeholder in line_lower:
                return True

        # Skip comments explaining the field
        if line.strip().startswith("#") or line.strip().startswith("//"):
            if "example" in line_lower or "format" in line_lower:
                return True

        return False

    def generate_report(self) -> str:
        """Generate a text report of secrets scan results."""
        report_lines = ["=" * 60, "Secrets Scan Report", "=" * 60, ""]

        if not self.findings:
            report_lines.append("✅ No secrets detected in codebase!")
            return "\n".join(report_lines)

        # Group by severity
        critical = [f for f in self.findings if f.severity == "critical"]
        high = [f for f in self.findings if f.severity == "high"]

        if critical:
            report_lines.append("🔴 CRITICAL SECRETS DETECTED:")
            for finding in critical:
                report_lines.append(f"  {finding.file_path}:{finding.line_number}")
                report_lines.append(f"    Type: {finding.secret_type}")
                report_lines.append(f"    Context: {finding.context[:80]}")
                report_lines.append("")

        if high:
            report_lines.append("🟠 HIGH SEVERITY FINDINGS:")
            for finding in high:
                report_lines.append(f"  {finding.file_path}:{finding.line_number}")
                report_lines.append(f"    Type: {finding.secret_type}")
                report_lines.append("")

        report_lines.append(f"Total findings: {len(self.findings)}")
        report_lines.append(f"Critical: {len(critical)}, High: {len(high)}")

        return "\n".join(report_lines)


def main():
    """Run secrets scan from command line."""
    import sys
    
    scanner = SecretsScanner(".")
    results = scanner.scan_all()
    
    print(scanner.generate_report())
    
    if results["has_secrets"]:
        print(f"\n❌ Found {results['total_findings']} potential secrets!")
        print("Please review and remove any accidentally committed secrets.")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
