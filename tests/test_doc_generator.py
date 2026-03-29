"""
Week 60 - Builder 1 Tests: Documentation Generator Module
Unit tests for Doc Generator, API Documenter, and Doc Validator
"""

import pytest
from parwa_final_release.doc_generator import (
    DocGenerator, DocSection, DocType, DocFormat, GeneratedDoc,
    APIDocumenter, APIEndpoint,
    DocValidator
)


class TestDocGenerator:
    """Tests for DocGenerator class"""

    @pytest.fixture
    def generator(self):
        """Create doc generator"""
        return DocGenerator()

    def test_generate_readme(self, generator):
        """Test README generation"""
        doc = generator.generate_readme(
            title="MyProject",
            description="A test project"
        )

        assert doc.doc_type == DocType.README
        assert "# MyProject" in doc.content
        assert "A test project" in doc.content

    def test_generate_readme_with_sections(self, generator):
        """Test README with sections"""
        sections = [
            DocSection(title="Installation", content="Install with pip"),
            DocSection(title="Usage", content="How to use")
        ]

        doc = generator.generate_readme("Project", "Desc", sections)

        assert "Installation" in doc.content
        assert "Usage" in doc.content

    def test_generate_changelog(self, generator):
        """Test changelog generation"""
        changes = [
            {"type": "added", "description": "New feature"},
            {"type": "fixed", "description": "Bug fix"}
        ]

        doc = generator.generate_changelog(changes, version="1.0.0")

        assert doc.doc_type == DocType.CHANGELOG
        assert "1.0.0" in doc.content
        assert "New feature" in doc.content

    def test_generate_guide(self, generator):
        """Test guide generation"""
        doc = generator.generate_guide(
            title="Getting Started",
            steps=["Step 1", "Step 2", "Step 3"],
            prerequisites=["Python 3.8+", "pip"]
        )

        assert doc.doc_type == DocType.GUIDE
        assert "Getting Started" in doc.content
        assert "Prerequisites" in doc.content

    def test_register_template(self, generator):
        """Test template registration"""
        generator.register_template("api", "# API Reference\n\n{content}")

        assert "api" in generator.templates

    def test_get_document(self, generator):
        """Test get document"""
        doc = generator.generate_readme("Test", "Desc")
        doc_id = list(generator.documents.keys())[0]

        retrieved = generator.get_document(doc_id)
        assert retrieved.doc_type == DocType.README

    def test_list_documents(self, generator):
        """Test list documents"""
        generator.generate_readme("Doc1", "Desc")
        generator.generate_changelog([])

        docs = generator.list_documents()
        assert len(docs) >= 2


class TestAPIDocumenter:
    """Tests for APIDocumenter class"""

    @pytest.fixture
    def documenter(self):
        """Create API documenter"""
        return APIDocumenter()

    def test_register_endpoint(self, documenter):
        """Test endpoint registration"""
        endpoint = APIEndpoint(
            path="/api/users",
            method="GET",
            description="List users"
        )

        documenter.register_endpoint(endpoint)

        assert "GET:/api/users" in documenter.endpoints

    def test_register_schema(self, documenter):
        """Test schema registration"""
        schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
        documenter.register_schema("User", schema)

        assert "User" in documenter.schemas

    def test_generate_openapi(self, documenter):
        """Test OpenAPI generation"""
        documenter.register_endpoint(APIEndpoint(
            path="/api/users",
            method="GET",
            description="List users"
        ))

        spec = documenter.generate_openapi(
            title="Test API",
            version="1.0.0"
        )

        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Test API"
        assert "/api/users" in spec["paths"]

    def test_generate_markdown_docs(self, documenter):
        """Test markdown documentation"""
        documenter.register_endpoint(APIEndpoint(
            path="/api/users",
            method="GET",
            description="List users",
            parameters=[{"name": "limit", "description": "Max results"}]
        ))

        markdown = documenter.generate_markdown_docs()

        assert "# API Documentation" in markdown
        assert "GET /api/users" in markdown
        assert "limit" in markdown

    def test_get_endpoint(self, documenter):
        """Test get endpoint"""
        documenter.register_endpoint(APIEndpoint(
            path="/api/test",
            method="POST",
            description="Test endpoint"
        ))

        endpoint = documenter.get_endpoint("POST", "/api/test")
        assert endpoint.description == "Test endpoint"

    def test_list_endpoints(self, documenter):
        """Test list endpoints"""
        documenter.register_endpoint(APIEndpoint(path="/a", method="GET"))
        documenter.register_endpoint(APIEndpoint(path="/b", method="POST"))

        endpoints = documenter.list_endpoints()
        assert len(endpoints) == 2


class TestDocValidator:
    """Tests for DocValidator class"""

    @pytest.fixture
    def validator(self):
        """Create doc validator"""
        return DocValidator()

    @pytest.fixture
    def sample_doc(self):
        """Create sample document"""
        return GeneratedDoc(
            doc_type=DocType.README,
            format=DocFormat.MARKDOWN,
            content="# Title\n\nSee [link](https://example.com)\n\n```python\nprint('hello')\n```"
        )

    def test_validate_coverage(self, validator):
        """Test coverage validation"""
        result = validator.validate_coverage(
            code_elements=["func1", "func2", "func3"],
            documented=["func1", "func2"]
        )

        assert result["total_elements"] == 3
        assert result["documented"] == 2
        assert result["coverage_percentage"] == pytest.approx(66.67, rel=0.1)

    def test_validate_links(self, validator, sample_doc):
        """Test link validation"""
        result = validator.validate_links(sample_doc.content)

        assert result["total_links"] == 1
        assert result["valid_links"] == 1

    def test_validate_examples(self, validator, sample_doc):
        """Test example validation"""
        result = validator.validate_examples(sample_doc)

        assert result["total_examples"] == 1
        assert result["examples"][0]["language"] == "python"

    def test_validate_doc(self, validator, sample_doc):
        """Test full document validation"""
        result = validator.validate_doc("test-doc", sample_doc)

        assert result["doc_id"] == "test-doc"
        assert "links" in result
        assert "examples" in result

    def test_get_result(self, validator, sample_doc):
        """Test get validation result"""
        validator.validate_doc("test-doc", sample_doc)
        result = validator.get_result("test-doc")

        assert result is not None
        assert result["doc_id"] == "test-doc"
