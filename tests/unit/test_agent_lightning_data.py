"""
Unit tests for Agent Lightning Data Module.

Tests for:
- Export mistakes in correct format
- Export approvals with reasoning
- JSONL dataset built with 50+ entries
- Model version registered correctly
"""
import pytest
import os
import json
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_lightning.data.export_mistakes import (
    ExportMistakes,
    MistakeEntry,
    MistakeExportResult,
    MockMistakeDatabase,
    get_export_mistakes
)
from agent_lightning.data.export_approvals import (
    ExportApprovals,
    ApprovalEntry,
    ApprovalExportResult,
    MockApprovalDatabase,
    get_export_approvals
)
from agent_lightning.data.dataset_builder import (
    DatasetBuilder,
    DatasetBuildResult,
    DatasetStats,
    get_dataset_builder
)
from agent_lightning.deployment.model_registry import (
    ModelRegistry,
    ModelVersion,
    ModelRegistrationResult,
    ModelActivationResult,
    get_model_registry,
    reset_registry
)


class TestExportMistakes:
    """Tests for ExportMistakes class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database with sample data."""
        db = MockMistakeDatabase()
        # Add sample mistakes
        for i in range(5):
            db.add_mistake(
                company_id="test-company",
                interaction_id=f"int-{i}",
                mistake_type="incorrect_classification",
                original_output=f"Wrong answer {i}",
                correct_output=f"Correct answer {i}",
                context={"ticket_id": f"TKT-{i}"}
            )
        # Add negative rewards
        db.add_negative_reward(
            company_id="test-company",
            interaction_id="int-0",
            reward=-1.0,
            reason="Incorrect refund decision"
        )
        return db

    @pytest.fixture
    def exporter(self, mock_db):
        """Create exporter with mock database."""
        return ExportMistakes(db=mock_db)

    @pytest.mark.asyncio
    async def test_export_mistakes_success(self, exporter):
        """Test successful export of mistakes."""
        result = await exporter.export("test-company", limit=10)

        assert result.success is True
        assert result.company_id == "test-company"
        assert result.total_exported == 5

    @pytest.mark.asyncio
    async def test_export_mistakes_format(self, exporter):
        """Test mistakes exported in correct format for training."""
        result = await exporter.export("test-company")

        assert result.success is True
        assert len(result.mistakes) > 0

        # Verify format
        for mistake in result.mistakes:
            assert isinstance(mistake, MistakeEntry)
            assert mistake.mistake_id is not None
            assert mistake.company_id == "test-company"
            assert mistake.original_output is not None
            assert mistake.correct_output is not None

    @pytest.mark.asyncio
    async def test_get_negative_rewards(self, exporter):
        """Test getting negative reward records."""
        rewards = await exporter.get_negative_rewards("test-company")

        assert len(rewards) == 1
        assert rewards[0]["reward"] == -1.0

    @pytest.mark.asyncio
    async def test_get_correction_data(self, exporter, mock_db):
        """Test getting correction data for an interaction."""
        # Add a correction
        mock_db.add_correction(
            interaction_id="int-0",
            original="Wrong response",
            correction="Correct response",
            corrected_by="human-001"
        )

        correction = await exporter.get_correction_data("int-0")

        assert correction["found"] is True
        assert correction["original"] == "Wrong response"
        assert correction["correction"] == "Correct response"

    @pytest.mark.asyncio
    async def test_get_correction_data_not_found(self, exporter):
        """Test getting correction data for non-existent interaction."""
        correction = await exporter.get_correction_data("nonexistent")

        assert correction["found"] is False

    @pytest.mark.asyncio
    async def test_to_training_format(self, exporter):
        """Test converting mistake to training format."""
        mistake = MistakeEntry(
            mistake_id="MST-001",
            company_id="test-company",
            interaction_id="int-001",
            mistake_type="wrong_answer",
            original_output="Wrong",
            correct_output="Correct",
            context={"question": "What is 2+2?"}
        )

        training_entry = exporter.to_training_format(mistake)

        assert "messages" in training_entry
        assert len(training_entry["messages"]) == 3
        assert training_entry["messages"][0]["role"] == "system"
        assert training_entry["messages"][1]["role"] == "user"
        assert training_entry["messages"][2]["role"] == "assistant"
        assert training_entry["metadata"]["source"] == "mistake_correction"


class TestExportApprovals:
    """Tests for ExportApprovals class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database with sample approvals."""
        db = MockApprovalDatabase()
        # Add approved refunds
        for i in range(3):
            db.add_approval(
                company_id="test-company",
                ticket_id=f"TKT-{i}",
                amount=50.0 + i * 10,
                decision="approved",
                reasoning=f"Customer eligible for refund {i}",
                context={"order_id": f"ORD-{i}"}
            )
        # Add rejected refunds
        for i in range(3, 5):
            db.add_approval(
                company_id="test-company",
                ticket_id=f"TKT-{i}",
                amount=100.0 + i * 10,
                decision="rejected",
                reasoning=f"Outside refund window {i}",
                context={"order_id": f"ORD-{i}"}
            )
        return db

    @pytest.fixture
    def exporter(self, mock_db):
        """Create exporter with mock database."""
        return ExportApprovals(db=mock_db)

    @pytest.mark.asyncio
    async def test_export_approvals_success(self, exporter):
        """Test successful export of approvals."""
        result = await exporter.export("test-company", limit=10)

        assert result.success is True
        assert result.company_id == "test-company"
        assert result.total_exported == 5
        assert result.approved_count == 3
        assert result.rejected_count == 2

    @pytest.mark.asyncio
    async def test_export_approvals_with_reasoning(self, exporter):
        """Test approvals exported with reasoning."""
        result = await exporter.export("test-company")

        assert result.success is True

        for approval in result.approvals:
            assert isinstance(approval, ApprovalEntry)
            assert approval.decision in ["approved", "rejected"]
            assert approval.reasoning is not None
            assert len(approval.reasoning) > 0

    @pytest.mark.asyncio
    async def test_get_approved_refunds(self, exporter):
        """Test getting approved refunds."""
        approved = await exporter.get_approved_refunds("test-company")

        assert len(approved) == 3
        for record in approved:
            assert record["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_get_rejected_refunds(self, exporter):
        """Test getting rejected refunds."""
        rejected = await exporter.get_rejected_refunds("test-company")

        assert len(rejected) == 2
        for record in rejected:
            assert record["decision"] == "rejected"

    @pytest.mark.asyncio
    async def test_to_training_format_approved(self, exporter):
        """Test converting approved refund to training format."""
        approval = ApprovalEntry(
            approval_id="APR-001",
            company_id="test-company",
            ticket_id="TKT-001",
            amount=75.00,
            decision="approved",
            reasoning="Valid refund request with proof of damage",
            context={"order_id": "ORD-001"}
        )

        training_entry = exporter.to_training_format(approval)

        assert "messages" in training_entry
        assert "APPROVE" in training_entry["messages"][2]["content"]
        assert "Valid refund" in training_entry["messages"][2]["content"]

    @pytest.mark.asyncio
    async def test_to_training_format_rejected(self, exporter):
        """Test converting rejected refund to training format."""
        approval = ApprovalEntry(
            approval_id="APR-002",
            company_id="test-company",
            ticket_id="TKT-002",
            amount=200.00,
            decision="rejected",
            reasoning="Refund request beyond policy window",
            context={"order_id": "ORD-002"}
        )

        training_entry = exporter.to_training_format(approval)

        assert "REJECT" in training_entry["messages"][2]["content"]
        assert "policy window" in training_entry["messages"][2]["content"]


class TestDatasetBuilder:
    """Tests for DatasetBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create dataset builder."""
        return DatasetBuilder()

    @pytest.mark.asyncio
    async def test_build_dataset_creates_file(self, builder):
        """Test that build creates a JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_dataset.jsonl")

            result = await builder.build(
                company_id="test-company",
                output_path=output_path
            )

            assert result.success is True
            assert result.dataset_path == output_path
            assert os.path.exists(output_path)

    @pytest.mark.asyncio
    async def test_build_dataset_has_50_plus_entries(self, builder):
        """CRITICAL: Dataset must have 50+ entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_dataset.jsonl")

            result = await builder.build(
                company_id="test-company",
                output_path=output_path
            )

            assert result.success is True
            assert result.total_entries >= 50, \
                f"CRITICAL: Dataset has {result.total_entries} entries, must have 50+"

    @pytest.mark.asyncio
    async def test_build_dataset_valid_jsonl_format(self, builder):
        """Test that dataset is valid JSONL format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_dataset.jsonl")

            result = await builder.build(
                company_id="test-company",
                output_path=output_path
            )

            assert result.success is True

            # Verify JSONL format
            with open(output_path, 'r') as f:
                lines = f.readlines()

            assert len(lines) >= 50

            for i, line in enumerate(lines):
                entry = json.loads(line)
                assert "messages" in entry, f"Entry {i} missing 'messages'"
                assert len(entry["messages"]) >= 2, f"Entry {i} has insufficient messages"

    @pytest.mark.asyncio
    async def test_merge_exports(self, builder):
        """Test merging mistakes and approvals."""
        # Set up exporters
        builder._mistakes_exporter = ExportMistakes()
        builder._approvals_exporter = ExportApprovals()

        mistakes = [
            MistakeEntry(
                mistake_id="MST-001",
                company_id="test",
                interaction_id="int-1",
                mistake_type="wrong",
                original_output="Wrong",
                correct_output="Correct"
            )
        ]

        approvals = [
            ApprovalEntry(
                approval_id="APR-001",
                company_id="test",
                ticket_id="TKT-1",
                amount=50.0,
                decision="approved",
                reasoning="Valid request"
            )
        ]

        dataset = await builder.merge_exports(mistakes, approvals)

        assert len(dataset) == 2

    @pytest.mark.asyncio
    async def test_validate_format_valid(self, builder):
        """Test format validation with valid dataset."""
        dataset = [
            {
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"}
                ]
            }
        ]

        is_valid = await builder.validate_format(dataset)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_format_missing_messages(self, builder):
        """Test format validation with missing messages."""
        dataset = [
            {"content": "Missing messages field"}
        ]

        is_valid = await builder.validate_format(dataset)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_format_invalid_role(self, builder):
        """Test format validation with invalid role."""
        dataset = [
            {
                "messages": [
                    {"role": "invalid_role", "content": "Hello"}
                ]
            }
        ]

        is_valid = await builder.validate_format(dataset)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_dataset_stats(self, builder):
        """Test getting dataset statistics."""
        dataset = [
            {
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Query"},
                    {"role": "assistant", "content": "Response"}
                ],
                "metadata": {"source": "test"}
            }
        ]

        stats = await builder.get_dataset_stats(dataset)

        assert stats.total_entries == 1
        assert stats.format_valid is True


class TestModelRegistry:
    """Tests for ModelRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create fresh registry for each test."""
        reset_registry()
        return get_model_registry()

    @pytest.mark.asyncio
    async def test_register_model_success(self, registry):
        """Test successful model registration."""
        result = await registry.register_model(
            version="v1.0.0",
            metrics={"accuracy": 0.95, "f1": 0.93},
            company_id="test-company"
        )

        assert result.success is True
        assert result.version == "v1.0.0"
        assert result.model_id is not None

    @pytest.mark.asyncio
    async def test_register_model_duplicate_version(self, registry):
        """Test that duplicate version fails."""
        await registry.register_model("v1.0.0", {"accuracy": 0.95})

        result = await registry.register_model("v1.0.0", {"accuracy": 0.96})

        assert result.success is False
        assert "already exists" in result.error

    @pytest.mark.asyncio
    async def test_get_current_model_none(self, registry):
        """Test getting current model when none is active."""
        result = await registry.get_current_model("test-company")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_set_active_and_get_current(self, registry):
        """Test setting active model and retrieving it."""
        # Register model
        await registry.register_model(
            version="v1.0.0",
            metrics={"accuracy": 0.95},
            company_id="test-company"
        )

        # Set as active
        activation = await registry.set_active("v1.0.0", "test-company")

        assert activation.success is True

        # Get current
        current = await registry.get_current_model("test-company")

        assert current["success"] is True
        assert current["version"] == "v1.0.0"
        assert current["metrics"]["accuracy"] == 0.95

    @pytest.mark.asyncio
    async def test_list_versions(self, registry):
        """Test listing model versions."""
        # Register multiple versions
        await registry.register_model("v1.0.0", {"accuracy": 0.90})
        await registry.register_model("v1.1.0", {"accuracy": 0.93})
        await registry.register_model("v1.2.0", {"accuracy": 0.95})

        versions = await registry.list_versions(limit=10)

        assert len(versions) == 3

    @pytest.mark.asyncio
    async def test_list_versions_is_active_flag(self, registry):
        """Test that list_versions shows which is active."""
        await registry.register_model("v1.0.0", {"accuracy": 0.90})
        await registry.register_model("v1.1.0", {"accuracy": 0.95})

        await registry.set_active("v1.1.0")

        versions = await registry.list_versions()

        active_versions = [v for v in versions if v["is_active"]]
        assert len(active_versions) == 1
        assert active_versions[0]["version"] == "v1.1.0"

    @pytest.mark.asyncio
    async def test_set_active_updates_deployment_count(self, registry):
        """Test that activation increments deployment count."""
        await registry.register_model("v1.0.0", {"accuracy": 0.95})

        await registry.set_active("v1.0.0")
        await registry.set_active("v1.0.0")  # Second activation

        version = await registry.get_version("v1.0.0")

        assert version["deployment_count"] == 2

    @pytest.mark.asyncio
    async def test_previous_version_deprecated(self, registry):
        """Test that previous version is deprecated when new one activates."""
        await registry.register_model("v1.0.0", {"accuracy": 0.90})
        await registry.register_model("v1.1.0", {"accuracy": 0.95})

        await registry.set_active("v1.0.0")
        await registry.set_active("v1.1.0")

        prev = await registry.get_version("v1.0.0")
        current = await registry.get_version("v1.1.0")

        assert prev["status"] == "deprecated"
        assert current["status"] == "production"

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, registry):
        """Test getting non-existent version."""
        result = await registry.get_version("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_compare_versions(self, registry):
        """Test comparing two model versions."""
        await registry.register_model("v1.0.0", {"accuracy": 0.90, "f1": 0.88})
        await registry.register_model("v1.1.0", {"accuracy": 0.95, "f1": 0.92})

        comparison = await registry.compare_versions("v1.0.0", "v1.1.0")

        assert comparison["success"] is True
        assert abs(comparison["comparison"]["accuracy"]["change"] - 0.05) < 0.001
        assert comparison["comparison"]["accuracy"]["change_percent"] > 0

    @pytest.mark.asyncio
    async def test_get_stats(self, registry):
        """Test getting registry statistics."""
        await registry.register_model("v1.0.0", {"accuracy": 0.90})
        await registry.register_model("v1.1.0", {"accuracy": 0.95})
        await registry.set_active("v1.1.0")

        stats = registry.get_stats()

        assert stats["total_versions"] == 2
        assert stats["active_models"] == 1


class TestIntegration:
    """Integration tests for the full data pipeline."""

    @pytest.mark.asyncio
    async def test_full_export_build_pipeline(self):
        """Test full pipeline from export to dataset."""
        # Setup mock databases
        mistake_db = MockMistakeDatabase()
        approval_db = MockApprovalDatabase()

        # Add sample data
        for i in range(10):
            mistake_db.add_mistake(
                company_id="integration-test",
                interaction_id=f"int-{i}",
                mistake_type="wrong_answer",
                original_output=f"Wrong {i}",
                correct_output=f"Correct {i}"
            )

            approval_db.add_approval(
                company_id="integration-test",
                ticket_id=f"TKT-{i}",
                amount=50.0 + i,
                decision="approved" if i % 2 == 0 else "rejected",
                reasoning=f"Reason {i}"
            )

        # Create exporters
        mistakes_exporter = ExportMistakes(db=mistake_db)
        approvals_exporter = ExportApprovals(db=approval_db)

        # Build dataset
        builder = DatasetBuilder(
            mistakes_exporter=mistakes_exporter,
            approvals_exporter=approvals_exporter
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "integration_dataset.jsonl")

            result = await builder.build(
                company_id="integration-test",
                output_path=output_path,
                include_synthetic=True
            )

            assert result.success is True
            assert result.total_entries >= 50

            # Verify file content
            with open(output_path, 'r') as f:
                lines = f.readlines()

            assert len(lines) >= 50

            # Verify format of first few entries
            for line in lines[:5]:
                entry = json.loads(line)
                assert "messages" in entry

    @pytest.mark.asyncio
    async def test_model_lifecycle(self):
        """Test full model lifecycle: register -> activate -> list -> compare."""
        reset_registry()
        registry = get_model_registry()

        # Register initial model
        result1 = await registry.register_model(
            version="v1.0.0",
            metrics={"accuracy": 0.90, "latency_ms": 100},
            company_id="lifecycle-test",
            created_by="test-user"
        )
        assert result1.success is True

        # Activate it
        activation1 = await registry.set_active("v1.0.0", "lifecycle-test")
        assert activation1.success is True

        # Register improved model
        result2 = await registry.register_model(
            version="v1.1.0",
            metrics={"accuracy": 0.95, "latency_ms": 85},
            company_id="lifecycle-test"
        )
        assert result2.success is True

        # Activate new version
        activation2 = await registry.set_active("v1.1.0", "lifecycle-test")
        assert activation2.success is True
        assert activation2.previous_version == "v1.0.0"

        # Get current
        current = await registry.get_current_model("lifecycle-test")
        assert current["version"] == "v1.1.0"

        # List versions
        versions = await registry.list_versions("lifecycle-test")
        assert len(versions) == 2

        # Compare versions
        comparison = await registry.compare_versions("v1.0.0", "v1.1.0")
        assert comparison["success"] is True
        assert abs(comparison["comparison"]["accuracy"]["change"] - 0.05) < 0.001
        assert abs(comparison["comparison"]["latency_ms"]["change"] - (-15)) < 0.001


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_export_mistakes(self):
        """Test get_export_mistakes factory."""
        exporter = get_export_mistakes()
        assert isinstance(exporter, ExportMistakes)

    def test_get_export_approvals(self):
        """Test get_export_approvals factory."""
        exporter = get_export_approvals()
        assert isinstance(exporter, ExportApprovals)

    def test_get_dataset_builder(self):
        """Test get_dataset_builder factory."""
        builder = get_dataset_builder()
        assert isinstance(builder, DatasetBuilder)

    def test_get_model_registry(self):
        """Test get_model_registry returns singleton."""
        reset_registry()
        registry1 = get_model_registry()
        registry2 = get_model_registry()

        assert registry1 is registry2
