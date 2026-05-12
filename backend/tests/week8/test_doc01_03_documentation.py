"""
Week 8 Tests: DOC-01/03 — Documentation Validation

Validates:
- Production Runbook exists and covers key sections
- Architecture document exists and covers key sections
- Documentation files are substantial (>500 lines each)
"""

import os
import pytest


PRODUCTION_RUNBOOK = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "docs", "PRODUCTION_RUNBOOK.md"
)
ARCHITECTURE_DOC = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "docs", "ARCHITECTURE.md"
)


def _count_lines(path):
    """Count lines in a file."""
    with open(path, "r") as f:
        return len(f.readlines())


def _read(path):
    with open(path, "r") as f:
        return f.read()


class TestProductionRunbook:
    """Validate Production Runbook documentation."""

    def test_runbook_exists(self):
        """PRODUCTION_RUNBOOK.md must exist."""
        assert os.path.exists(PRODUCTION_RUNBOOK)

    def test_runbook_substantial(self):
        """Runbook must be substantial (>= 500 lines)."""
        lines = _count_lines(PRODUCTION_RUNBOOK)
        assert lines >= 500, f"Runbook too short: {lines} lines (expected >= 500)"

    def test_runbook_has_environment_setup(self):
        """Must cover environment setup."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert any(kw in content for kw in [
            "environment", "prerequisite", "setup", "env var"
        ]), "Missing environment setup section"

    def test_runbook_has_deployment(self):
        """Must cover deployment procedures."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert "deploy" in content, "Missing deployment section"

    def test_runbook_has_ssl_section(self):
        """Must cover SSL/TLS configuration."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert "ssl" in content or "tls" in content, "Missing SSL/TLS section"

    def test_runbook_has_monitoring(self):
        """Must cover monitoring and alerting."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert "monitor" in content or "grafana" in content or "alert" in content, \
            "Missing monitoring section"

    def test_runbook_has_rollback(self):
        """Must cover rollback procedures."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert "rollback" in content, "Missing rollback section"

    def test_runbook_has_troubleshooting(self):
        """Must cover troubleshooting."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert "troubleshoot" in content, "Missing troubleshooting section"

    def test_runbook_has_database_backup(self):
        """Must cover database backup verification."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert any(kw in content for kw in ["backup", "restore", "pg_dump"]), \
            "Missing backup section"

    def test_runbook_has_security_checklist(self):
        """Must cover security checklist."""
        content = _read(PRODUCTION_RUNBOOK).lower()
        assert "security" in content and ("checklist" in content or "check" in content), \
            "Missing security checklist"


class TestArchitectureDocument:
    """Validate Architecture documentation."""

    def test_architecture_exists(self):
        """ARCHITECTURE.md must exist."""
        assert os.path.exists(ARCHITECTURE_DOC)

    def test_architecture_substantial(self):
        """Architecture doc must be substantial (>= 400 lines)."""
        lines = _count_lines(ARCHITECTURE_DOC)
        assert lines >= 400, f"Architecture doc too short: {lines} lines"

    def test_architecture_has_tech_stack(self):
        """Must document technology stack."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert any(kw in content for kw in ["fastapi", "next.js", "postgresql", "redis"]), \
            "Missing technology stack documentation"

    def test_architecture_has_ai_pipeline(self):
        """Must document AI pipeline architecture."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert any(kw in content for kw in [
            "langgraph", "maker", "clara", "fake", "llm_gateway"
        ]), "Missing AI pipeline documentation"

    def test_architecture_has_variants(self):
        """Must document product variants."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert "variant" in content, "Missing variant documentation"

    def test_architecture_has_security(self):
        """Must document security architecture."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert "security" in content or "jwt" in content or "rbac" in content, \
            "Missing security architecture"

    def test_architecture_has_multi_tenant(self):
        """Must document multi-tenant architecture."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert "tenant" in content or "multi-tenant" in content or "rls" in content, \
            "Missing multi-tenant documentation"

    def test_architecture_mentions_llm_gateway(self):
        """Must mention llm_gateway or LLM integration (real LLM calls, not regex)."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert any(kw in content for kw in [
            "llm_gateway", "llm gateway", "llm integration", "real llm"
        ]), "Must mention LLM gateway/integration"

    def test_architecture_has_infrastructure(self):
        """Must document infrastructure (Docker, monitoring)."""
        content = _read(ARCHITECTURE_DOC).lower()
        assert any(kw in content for kw in ["docker", "nginx", "prometheus", "grafana"]), \
            "Missing infrastructure documentation"


class TestExistingDocumentation:
    """Validate existing documentation files haven't been broken."""

    def test_docs_directory_exists(self):
        """docs/ directory must exist."""
        assert os.path.isdir(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "docs"
        ))

    def test_documents_directory_exists(self):
        """documents/ directory must exist."""
        assert os.path.isdir(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "documents"
        ))

    def test_jarvis_spec_exists(self):
        """JARVIS_SPECIFICATION.md must exist."""
        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "docs", "JARVIS_SPECIFICATION.md"
        ))

    def test_ai_technique_framework_exists(self):
        """PARWA_AI_Technique_Framework.md must exist."""
        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "documents", "PARWA_AI_Technique_Framework.md"
        ))

    def test_context_bible_exists(self):
        """PARWA_Context_Bible.md must exist."""
        assert os.path.exists(os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "documents", "PARWA_Context_Bible.md"
        ))
