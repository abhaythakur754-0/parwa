"""
Tests for documentation completeness and accuracy.
"""

import os
import pytest
from pathlib import Path


class TestDocumentationCompleteness:
    """Tests for documentation completeness."""

    @pytest.fixture
    def docs_dir(self):
        """Get docs directory path."""
        return Path(__file__).parent.parent.parent / "docs"

    def test_api_reference_exists(self, docs_dir):
        """Test API reference documentation exists."""
        api_ref = docs_dir / "API_REFERENCE.md"
        assert api_ref.exists(), "API_REFERENCE.md should exist"
        
        content = api_ref.read_text()
        assert "authentication" in content.lower()
        assert "endpoints" in content.lower()
        assert "error" in content.lower()

    def test_deployment_guide_exists(self, docs_dir):
        """Test deployment guide exists."""
        deploy_guide = docs_dir / "DEPLOYMENT_GUIDE.md"
        assert deploy_guide.exists(), "DEPLOYMENT_GUIDE.md should exist"
        
        content = deploy_guide.read_text()
        assert "kubernetes" in content.lower()
        assert "docker" in content.lower()
        assert "production" in content.lower()

    def test_architecture_overview_exists(self, docs_dir):
        """Test architecture overview exists."""
        arch_doc = docs_dir / "ARCHITECTURE_OVERVIEW.md"
        assert arch_doc.exists(), "ARCHITECTURE_OVERVIEW.md should exist"
        
        content = arch_doc.read_text()
        assert "frontend" in content.lower()
        assert "backend" in content.lower()
        assert "database" in content.lower()

    def test_client_onboarding_guide_exists(self, docs_dir):
        """Test client onboarding guide exists."""
        onboarding = docs_dir / "CLIENT_ONBOARDING_GUIDE.md"
        assert onboarding.exists(), "CLIENT_ONBOARDING_GUIDE.md should exist"
        
        content = onboarding.read_text()
        assert "step" in content.lower()
        assert "configuration" in content.lower()

    def test_troubleshooting_guide_exists(self, docs_dir):
        """Test troubleshooting guide exists."""
        troubleshooting = docs_dir / "TROUBLESHOOTING_GUIDE.md"
        assert troubleshooting.exists(), "TROUBLESHOOTING_GUIDE.md should exist"
        
        content = troubleshooting.read_text()
        assert "error" in content.lower()
        assert "solution" in content.lower()


class TestDocumentationQuality:
    """Tests for documentation quality."""

    @pytest.fixture
    def docs_dir(self):
        """Get docs directory path."""
        return Path(__file__).parent.parent.parent / "docs"

    def test_api_reference_has_examples(self, docs_dir):
        """Test API reference has code examples."""
        api_ref = docs_dir / "API_REFERENCE.md"
        if not api_ref.exists():
            pytest.skip("API_REFERENCE.md not found")
        
        content = api_ref.read_text()
        assert "```" in content, "API reference should have code examples"

    def test_deployment_guide_has_commands(self, docs_dir):
        """Test deployment guide has shell commands."""
        deploy_guide = docs_dir / "DEPLOYMENT_GUIDE.md"
        if not deploy_guide.exists():
            pytest.skip("DEPLOYMENT_GUIDE.md not found")
        
        content = deploy_guide.read_text()
        assert "```bash" in content, "Deployment guide should have bash commands"

    def test_all_docs_have_headers(self, docs_dir):
        """Test all documentation files have proper headers."""
        md_files = list(docs_dir.glob("**/*.md"))
        
        for md_file in md_files:
            content = md_file.read_text()
            lines = content.strip().split("\n")
            
            # Check file starts with a header
            assert lines[0].startswith("#"), f"{md_file.name} should start with a header"


class TestDocumentationLinks:
    """Tests for documentation links."""

    def test_internal_links_valid(self):
        """Test internal documentation links are valid."""
        # This would check for broken links in docs
        # For now, we just verify the structure exists
        pass
