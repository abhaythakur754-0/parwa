# Tests for Builder 5 - System Documentation
# Week 50: doc_generator.py, api_documenter.py, runbook_manager.py

import pytest
from datetime import datetime, timedelta

from enterprise.ops.doc_generator import (
    DocGenerator, Document, DocSection, DocType, DocFormat
)
from enterprise.ops.api_documenter import (
    ApiDocumenter, ApiDocument, ApiEndpoint, ApiParameter, ApiResponse,
    HttpMethod, ParameterLocation
)
from enterprise.ops.runbook_manager import (
    RunbookManager, Runbook, RunbookStep, RunbookExecution,
    RunbookStatus, RunbookPriority
)


# =============================================================================
# DOC GENERATOR TESTS
# =============================================================================

class TestDocGenerator:
    """Tests for DocGenerator class"""

    def test_init(self):
        """Test generator initialization"""
        generator = DocGenerator()
        assert generator is not None
        metrics = generator.get_metrics()
        assert metrics["total_documents"] == 0

    def test_create_document(self):
        """Test creating a document"""
        generator = DocGenerator()
        doc = generator.create_document(
            title="API Documentation",
            doc_type=DocType.API,
            version="1.0.0"
        )
        assert doc.title == "API Documentation"
        assert doc.doc_type == DocType.API
        assert doc.version == "1.0.0"

    def test_add_section(self):
        """Test adding a section"""
        generator = DocGenerator()
        doc = generator.create_document("Test Doc", DocType.GUIDE)
        section = generator.add_section(
            document_id=doc.id,
            title="Introduction",
            content="This is the introduction."
        )
        assert section is not None
        assert section.title == "Introduction"
        assert section.content == "This is the introduction."
        assert len(doc.sections) == 1

    def test_add_section_invalid_document(self):
        """Test adding section to invalid document"""
        generator = DocGenerator()
        section = generator.add_section("invalid_id", "Title", "Content")
        assert section is None

    def test_get_section(self):
        """Test getting section by ID"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        section = generator.add_section(doc.id, "Title", "Content")
        retrieved = generator.get_section(section.id)
        assert retrieved is not None
        assert retrieved.id == section.id

    def test_update_section(self):
        """Test updating section content"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        section = generator.add_section(doc.id, "Title", "Content")
        result = generator.update_section(section.id, "New content")
        assert result is True
        assert section.content == "New content"

    def test_remove_section(self):
        """Test removing a section"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        section = generator.add_section(doc.id, "Title", "Content")
        result = generator.remove_section(doc.id, section.id)
        assert result is True
        assert len(doc.sections) == 0

    def test_generate_document(self):
        """Test generating document content"""
        generator = DocGenerator()
        doc = generator.create_document("Test Doc", DocType.GUIDE)
        generator.add_section(doc.id, "Section 1", "Content 1")
        generator.add_section(doc.id, "Section 2", "Content 2")
        content = generator.generate_document(doc.id)
        assert "# Test Doc" in content
        assert "## Section 1" in content
        assert "Content 1" in content

    def test_set_and_get_template(self):
        """Test setting and getting templates"""
        generator = DocGenerator()
        generator.set_template("api", "# {{title}}\n\n{{content}}")
        template = generator.get_template("api")
        assert template == "# {{title}}\n\n{{content}}"

    def test_apply_template(self):
        """Test applying template"""
        generator = DocGenerator()
        generator.set_template("readme", "# {{name}}\n\n{{description}}")
        doc = generator.create_document("Test", DocType.README)
        result = generator.apply_template(
            doc.id, "readme",
            {"name": "My Project", "description": "A test project"}
        )
        assert result is True
        assert len(doc.sections) == 1

    def test_get_documents_by_type(self):
        """Test getting documents by type"""
        generator = DocGenerator()
        generator.create_document("API Doc", DocType.API)
        generator.create_document("Guide", DocType.GUIDE)
        generator.create_document("API Doc 2", DocType.API)

        api_docs = generator.get_documents_by_type(DocType.API)
        assert len(api_docs) == 2

    def test_search_sections(self):
        """Test searching sections"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        generator.add_section(doc.id, "API Reference", "API documentation")
        generator.add_section(doc.id, "Installation", "How to install")

        results = generator.search_sections("API")
        assert len(results) == 1  # Found in "API Reference" section

        results = generator.search_sections("install")
        assert len(results) == 1  # Found in "Installation" section

    def test_export_markdown(self):
        """Test exporting to markdown"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        generator.add_section(doc.id, "Section", "Content")
        exported = generator.export_document(doc.id, DocFormat.MARKDOWN)
        assert "# Test" in exported

    def test_export_html(self):
        """Test exporting to HTML"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        generator.add_section(doc.id, "Section", "Content")
        exported = generator.export_document(doc.id, DocFormat.HTML)
        assert "<html>" in exported

    def test_export_json(self):
        """Test exporting to JSON"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        generator.add_section(doc.id, "Section", "Content")
        exported = generator.export_document(doc.id, DocFormat.JSON)
        assert '"title": "Test"' in exported

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        generator = DocGenerator()
        doc = generator.create_document("Test", DocType.GUIDE)
        generator.add_section(doc.id, "Section 1", "Content")
        generator.add_section(doc.id, "Section 2", "Content")

        metrics = generator.get_metrics()
        assert metrics["total_documents"] == 1
        assert metrics["total_sections"] == 2


# =============================================================================
# API DOCUMENTER TESTS
# =============================================================================

class TestApiDocumenter:
    """Tests for ApiDocumenter class"""

    def test_init(self):
        """Test documenter initialization"""
        documenter = ApiDocumenter()
        assert documenter is not None
        metrics = documenter.get_metrics()
        assert metrics["total_documents"] == 0

    def test_create_document(self):
        """Test creating API document"""
        documenter = ApiDocumenter()
        doc = documenter.create_document(
            title="My API",
            version="2.0.0",
            base_url="https://api.example.com"
        )
        assert doc.title == "My API"
        assert doc.version == "2.0.0"
        assert doc.base_url == "https://api.example.com"

    def test_add_endpoint(self):
        """Test adding an endpoint"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("My API")
        endpoint = documenter.add_endpoint(
            document_id=doc.id,
            path="/users",
            method=HttpMethod.GET,
            summary="Get all users",
            tags=["Users"]
        )
        assert endpoint is not None
        assert endpoint.path == "/users"
        assert endpoint.method == HttpMethod.GET

    def test_add_parameter(self):
        """Test adding parameter to endpoint"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        endpoint = documenter.add_endpoint(doc.id, "/users/{id}", HttpMethod.GET)
        result = documenter.add_parameter(
            endpoint_id=endpoint.id,
            name="id",
            location=ParameterLocation.PATH,
            data_type="string",
            required=True,
            description="User ID"
        )
        assert result is True
        assert len(endpoint.parameters) == 1

    def test_add_response(self):
        """Test adding response to endpoint"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        endpoint = documenter.add_endpoint(doc.id, "/users", HttpMethod.GET)
        result = documenter.add_response(
            endpoint_id=endpoint.id,
            status_code=200,
            description="Success",
            schema={"type": "array"}
        )
        assert result is True
        assert len(endpoint.responses) == 1

    def test_get_endpoints_by_tag(self):
        """Test getting endpoints by tag"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        documenter.add_endpoint(doc.id, "/users", HttpMethod.GET, tags=["Users"])
        documenter.add_endpoint(doc.id, "/orders", HttpMethod.GET, tags=["Orders"])
        documenter.add_endpoint(doc.id, "/users/{id}", HttpMethod.GET, tags=["Users"])

        users_endpoints = documenter.get_endpoints_by_tag("Users")
        assert len(users_endpoints) == 2

    def test_get_endpoints_by_method(self):
        """Test getting endpoints by method"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        documenter.add_endpoint(doc.id, "/users", HttpMethod.GET)
        documenter.add_endpoint(doc.id, "/users", HttpMethod.POST)
        documenter.add_endpoint(doc.id, "/orders", HttpMethod.GET)

        get_endpoints = documenter.get_endpoints_by_method(HttpMethod.GET)
        assert len(get_endpoints) == 2

    def test_deprecate_endpoint(self):
        """Test deprecating endpoint"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        endpoint = documenter.add_endpoint(doc.id, "/old-endpoint", HttpMethod.GET)
        result = documenter.deprecate_endpoint(endpoint.id)
        assert result is True
        assert endpoint.deprecated is True

    def test_generate_openapi_spec(self):
        """Test generating OpenAPI spec"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("My API", "1.0.0", "https://api.example.com")
        endpoint = documenter.add_endpoint(doc.id, "/users", HttpMethod.GET, "Get users")
        documenter.add_parameter(endpoint.id, "limit", ParameterLocation.QUERY, "integer")
        documenter.add_response(endpoint.id, 200, "Success")

        spec = documenter.generate_openapi_spec(doc.id)
        assert spec is not None
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "My API"
        assert "/users" in spec["paths"]

    def test_generate_markdown_docs(self):
        """Test generating markdown docs"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("My API", base_url="https://api.example.com")
        documenter.add_endpoint(doc.id, "/users", HttpMethod.GET, "Get all users")

        md = documenter.generate_markdown_docs(doc.id)
        assert "# My API" in md
        assert "GET /users" in md
        assert "Get all users" in md

    def test_search_endpoints(self):
        """Test searching endpoints"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        documenter.add_endpoint(doc.id, "/users", HttpMethod.GET, "Get users")
        documenter.add_endpoint(doc.id, "/orders", HttpMethod.GET, "Get orders")

        results = documenter.search_endpoints("users")
        assert len(results) == 1

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        documenter = ApiDocumenter()
        doc = documenter.create_document("API")
        documenter.add_endpoint(doc.id, "/users", HttpMethod.GET)
        documenter.add_endpoint(doc.id, "/users", HttpMethod.POST)
        documenter.add_endpoint(doc.id, "/orders", HttpMethod.GET)

        metrics = documenter.get_metrics()
        assert metrics["total_documents"] == 1
        assert metrics["total_endpoints"] == 3
        assert metrics["by_method"]["GET"] == 2
        assert metrics["by_method"]["POST"] == 1


# =============================================================================
# RUNBOOK MANAGER TESTS
# =============================================================================

class TestRunbookManager:
    """Tests for RunbookManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = RunbookManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_runbooks"] == 0

    def test_create_runbook(self):
        """Test creating a runbook"""
        manager = RunbookManager()
        runbook = manager.create_runbook(
            title="Database Backup",
            description="How to backup the database",
            category="Database",
            priority=RunbookPriority.HIGH,
            author="ops-team"
        )
        assert runbook.title == "Database Backup"
        assert runbook.status == RunbookStatus.DRAFT
        assert runbook.priority == RunbookPriority.HIGH

    def test_add_step(self):
        """Test adding a step"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test Runbook")
        step = manager.add_step(
            runbook_id=runbook.id,
            title="Step 1",
            description="Do something",
            command="echo 'hello'"
        )
        assert step is not None
        assert step.title == "Step 1"
        assert step.command == "echo 'hello'"
        assert len(runbook.steps) == 1

    def test_add_step_invalid_runbook(self):
        """Test adding step to invalid runbook"""
        manager = RunbookManager()
        step = manager.add_step("invalid_id", "Step", "Description")
        assert step is None

    def test_update_step(self):
        """Test updating a step"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        step = manager.add_step(runbook.id, "Step", "Description")
        result = manager.update_step(step.id, title="Updated Step")
        assert result is True
        assert step.title == "Updated Step"

    def test_remove_step(self):
        """Test removing a step"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        step = manager.add_step(runbook.id, "Step", "Description")
        result = manager.remove_step(runbook.id, step.id)
        assert result is True
        assert len(runbook.steps) == 0

    def test_publish_runbook(self):
        """Test publishing a runbook"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        result = manager.publish_runbook(runbook.id)
        assert result is True
        assert runbook.status == RunbookStatus.PUBLISHED

    def test_publish_non_draft_runbook(self):
        """Test publishing non-draft runbook"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        manager.publish_runbook(runbook.id)
        result = manager.publish_runbook(runbook.id)  # Already published
        assert result is False

    def test_deprecate_runbook(self):
        """Test deprecating a runbook"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        manager.publish_runbook(runbook.id)
        result = manager.deprecate_runbook(runbook.id)
        assert result is True
        assert runbook.status == RunbookStatus.DEPRECATED

    def test_execute_runbook(self):
        """Test executing a runbook"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        manager.add_step(runbook.id, "Step 1", "Description")
        manager.publish_runbook(runbook.id)

        execution = manager.execute_runbook(runbook.id, executor="admin")
        assert execution is not None
        assert execution.status == "running"
        assert execution.executor == "admin"

    def test_execute_unpublished_runbook(self):
        """Test executing unpublished runbook"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        execution = manager.execute_runbook(runbook.id)
        assert execution is None

    def test_complete_step(self):
        """Test completing a step in execution"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        step = manager.add_step(runbook.id, "Step 1", "Description")
        manager.publish_runbook(runbook.id)
        execution = manager.execute_runbook(runbook.id)

        result = manager.complete_step(execution.id, step.id, "Step completed")
        assert result is True
        assert len(execution.steps_completed) == 1

    def test_fail_execution(self):
        """Test failing an execution"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        manager.add_step(runbook.id, "Step", "Description")
        manager.publish_runbook(runbook.id)
        execution = manager.execute_runbook(runbook.id)

        result = manager.fail_execution(execution.id, "Connection timeout")
        assert result is True
        assert execution.status == "failed"

    def test_get_runbooks_by_category(self):
        """Test getting runbooks by category"""
        manager = RunbookManager()
        manager.create_runbook("DB Backup", category="Database")
        manager.create_runbook("Server Restart", category="Infrastructure")
        manager.create_runbook("DB Restore", category="Database")

        db_runbooks = manager.get_runbooks_by_category("Database")
        assert len(db_runbooks) == 2

    def test_get_runbooks_by_tag(self):
        """Test getting runbooks by tag"""
        manager = RunbookManager()
        manager.create_runbook("Test 1", tags=["critical", "database"])
        manager.create_runbook("Test 2", tags=["routine"])

        critical = manager.get_runbooks_by_tag("critical")
        assert len(critical) == 1

    def test_get_published_runbooks(self):
        """Test getting published runbooks"""
        manager = RunbookManager()
        r1 = manager.create_runbook("Published 1")
        manager.publish_runbook(r1.id)
        manager.create_runbook("Draft 1")
        r2 = manager.create_runbook("Published 2")
        manager.publish_runbook(r2.id)

        published = manager.get_published_runbooks()
        assert len(published) == 2

    def test_search_runbooks(self):
        """Test searching runbooks"""
        manager = RunbookManager()
        manager.create_runbook("Database Backup", "Backup database")
        manager.create_runbook("Server Restart", "Restart servers")

        results = manager.search_runbooks("database")
        assert len(results) == 1

    def test_add_prerequisite(self):
        """Test adding prerequisite"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test")
        result = manager.add_prerequisite(runbook.id, "SSH access required")
        assert result is True
        assert len(runbook.prerequisites) == 1

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = RunbookManager()
        runbook = manager.create_runbook("Test", priority=RunbookPriority.HIGH)
        manager.add_step(runbook.id, "Step", "Description")
        manager.publish_runbook(runbook.id)
        manager.execute_runbook(runbook.id)

        metrics = manager.get_metrics()
        assert metrics["total_runbooks"] == 1
        assert metrics["total_executions"] == 1
