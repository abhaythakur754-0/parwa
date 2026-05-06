"""
Tests for Batch Client Setup Script
"""

import pytest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.batch_client_setup import BatchClientSetup, ValidationResult, SetupResult, validate_batch


class TestBatchClientSetup:
    def test_init_creates_instance(self):
        setup = BatchClientSetup()
        assert setup is not None
    
    def test_validate_missing_client(self):
        setup = BatchClientSetup()
        config = {"client_name": "Test Client"}
        result = setup.validate_client_config(config)
        assert result.is_valid is False
    
    def test_validate_existing_client(self):
        setup = BatchClientSetup()
        result = setup.validate_existing_client("client_001")
        assert result.client_id == "client_001"


class TestValidationResult:
    def test_create_validation_result(self):
        result = ValidationResult(client_id="test_client", is_valid=True)
        assert result.client_id == "test_client"
        assert result.is_valid is True
    
    def test_invalid_result_has_errors(self):
        result = ValidationResult(client_id="test_client", is_valid=False, errors=["Missing field"])
        assert result.is_valid is False
        assert len(result.errors) > 0


class TestSetupResult:
    def test_create_setup_result(self):
        result = SetupResult(client_id="test_client", success=True, message="Setup complete")
        assert result.client_id == "test_client"
        assert result.success is True


class TestBatchValidation:
    def test_validate_batch_returns_all_results(self):
        clients = ["client_001", "client_002"]
        results = validate_batch(clients)
        assert len(results) == len(clients)


class TestDirectoryCreation:
    def test_create_client_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = BatchClientSetup(base_path=tmpdir)
            result = setup.create_client_directory("client_test_001")
            assert result is True
            assert (Path(tmpdir) / "client_test_001").exists()
    
    def test_create_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = BatchClientSetup(base_path=tmpdir)
            setup.create_client_directory("client_test_002")
            result = setup.create_client_directory("client_test_002")
            assert result is True


class TestKnowledgeBaseInit:
    def test_initialize_knowledge_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = BatchClientSetup(base_path=tmpdir)
            setup.create_client_directory("client_test_003")
            faqs = [{"id": "faq_001", "question": "Q", "answer": "A"}]
            result = setup.initialize_knowledge_base("client_test_003", faqs)
            assert result is True
    
    def test_faq_structure(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = BatchClientSetup(base_path=tmpdir)
            setup.create_client_directory("client_test_004")
            faqs = [{"id": "faq_001", "question": "Q", "answer": "A"}]
            setup.initialize_knowledge_base("client_test_004", faqs)
            faq_path = Path(tmpdir) / "client_test_004" / "knowledge_base" / "faq.json"
            with open(faq_path) as f:
                data = json.load(f)
            assert "client_id" in data
            assert "faqs" in data


class TestMonitoringDashboard:
    def test_create_dashboard(self):
        setup = BatchClientSetup()
        dashboard = setup.create_monitoring_dashboard("client_test_005")
        assert "dashboard" in dashboard
        assert "panels" in dashboard["dashboard"]


class TestReportGeneration:
    def test_generate_report(self):
        setup = BatchClientSetup()
        results = [
            SetupResult(client_id="client_a", success=True, message="Done"),
            SetupResult(client_id="client_b", success=False, message="Failed")
        ]
        report = setup.generate_setup_report(results)
        assert report["total_clients"] == 2
        assert report["successful"] == 1
        assert report["failed"] == 1


class TestBatchSetup:
    def test_setup_batch_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = BatchClientSetup(base_path=tmpdir)
            clients = [{
                "client_id": "client_test_001",
                "client_name": "Test Client 1",
                "industry": "ecommerce",
                "variant": "parwa_junior",
                "faqs": [{"id": "faq_001", "question": "Q", "answer": "A"}]
            }]
            results = setup.setup_batch(clients)
            assert len(results) == 1
            assert results[0].success is True
    
    def test_setup_batch_with_missing_client_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = BatchClientSetup(base_path=tmpdir)
            clients = [{"client_name": "Invalid Client"}]
            results = setup.setup_batch(clients)
            assert len(results) == 1
            assert results[0].success is False
