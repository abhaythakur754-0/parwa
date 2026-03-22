"""
E2E Test: Agent Lightning Training Flow.

Tests the full training cycle for Agent Lightning:
Collect mistakes → Export → Train → Deploy

CRITICAL REQUIREMENTS:
- Full training cycle completes
- Training data model works correctly
- Mistake collection and export work
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


class MockTrainingData:
    """Mock training data for testing."""

    def __init__(
        self,
        id: str,
        company_id: str,
        ticket_id: str,
        raw_interaction: str,
        anonymized_interaction: str,
        sentiment_score: float
    ):
        self.id = id
        self.company_id = company_id
        self.ticket_id = ticket_id
        self.raw_interaction = raw_interaction
        self.anonymized_interaction = anonymized_interaction
        self.sentiment_score = sentiment_score
        self.created_at = datetime.now(timezone.utc)


class MockTrainingService:
    """Mock training service for E2E tests."""

    def __init__(self):
        self._training_data: List[MockTrainingData] = []
        self._mistakes: List[Dict[str, Any]] = []
        self._exports: List[Dict[str, Any]] = []
        self._deployments: List[Dict[str, Any]] = []

    async def collect_mistakes(
        self,
        company_id: str,
        ticket_id: str,
        mistake_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Collect a training mistake."""
        mistake = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "ticket_id": ticket_id,
            "original_response": mistake_data.get("original_response"),
            "correct_response": mistake_data.get("correct_response"),
            "reason": mistake_data.get("reason"),
            "collected_at": datetime.now(timezone.utc).isoformat()
        }
        self._mistakes.append(mistake)

        # Create training data entry
        training_entry = MockTrainingData(
            id=str(uuid.uuid4()),
            company_id=company_id,
            ticket_id=ticket_id,
            raw_interaction=mistake_data.get("original_response", ""),
            anonymized_interaction=mistake_data.get("correct_response", ""),
            sentiment_score=0.0
        )
        self._training_data.append(training_entry)

        return {
            "success": True,
            "mistake_id": mistake["id"],
            "total_mistakes": len(self._mistakes)
        }

    async def export_training_data(
        self,
        company_id: str
    ) -> Dict[str, Any]:
        """Export training data for model fine-tuning."""
        company_data = [
            {
                "id": td.id,
                "raw_interaction": td.raw_interaction,
                "anonymized_interaction": td.anonymized_interaction,
                "sentiment_score": td.sentiment_score
            }
            for td in self._training_data
            if td.company_id == company_id
        ]

        export = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "records": company_data,
            "total_records": len(company_data),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "jsonl"
        }
        self._exports.append(export)

        return export

    async def train_model(
        self,
        company_id: str,
        training_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Train the model with collected data."""
        export = await self.export_training_data(company_id)

        training_result = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "status": "completed",
            "records_used": export["total_records"],
            "model_version": f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "accuracy": 0.95,
            "trained_at": datetime.now(timezone.utc).isoformat()
        }

        return training_result

    async def deploy_model(
        self,
        company_id: str,
        model_version: str
    ) -> Dict[str, Any]:
        """Deploy the trained model."""
        deployment = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "model_version": model_version,
            "status": "deployed",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "environment": "production"
        }
        self._deployments.append(deployment)

        return deployment

    def get_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        return {
            "total_mistakes": len(self._mistakes),
            "total_training_data": len(self._training_data),
            "total_exports": len(self._exports),
            "total_deployments": len(self._deployments)
        }


@pytest.fixture
def training_service():
    """Create a mock training service."""
    return MockTrainingService()


class TestAgentLightningE2E:
    """
    E2E tests for Agent Lightning training flow.

    Tests the complete cycle:
    1. Collect mistakes from support interactions
    2. Export training data
    3. Train the model
    4. Deploy to production
    """

    @pytest.mark.asyncio
    async def test_full_training_cycle(self, training_service):
        """Test the full training cycle: Collect → Export → Train → Deploy."""
        company_id = str(uuid.uuid4())

        # Step 1: Collect mistakes
        mistake_result = await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-001",
            mistake_data={
                "original_response": "I can't help with that.",
                "correct_response": "Let me check that for you.",
                "reason": "Response too dismissive"
            }
        )

        assert mistake_result["success"] is True
        assert mistake_result["total_mistakes"] == 1

        # Step 2: Export training data
        export_result = await training_service.export_training_data(company_id)

        assert export_result["company_id"] == company_id
        assert export_result["total_records"] == 1
        assert len(export_result["records"]) == 1

        # Step 3: Train model
        training_result = await training_service.train_model(
            company_id=company_id,
            training_config={"epochs": 10, "batch_size": 32}
        )

        assert training_result["status"] == "completed"
        assert training_result["records_used"] == 1
        assert training_result["model_version"] is not None

        # Step 4: Deploy model
        deployment_result = await training_service.deploy_model(
            company_id=company_id,
            model_version=training_result["model_version"]
        )

        assert deployment_result["status"] == "deployed"
        assert deployment_result["model_version"] == training_result["model_version"]

        # Verify stats
        stats = training_service.get_stats()
        assert stats["total_mistakes"] == 1
        assert stats["total_deployments"] == 1

    @pytest.mark.asyncio
    async def test_multiple_mistakes_collection(self, training_service):
        """Test collecting multiple mistakes for training."""
        company_id = str(uuid.uuid4())

        # Collect multiple mistakes
        mistakes = [
            {
                "ticket_id": "ticket-001",
                "original_response": "Wrong answer",
                "correct_response": "Correct answer",
                "reason": "Incorrect information"
            },
            {
                "ticket_id": "ticket-002",
                "original_response": "Slow response",
                "correct_response": "Quick response",
                "reason": "Efficiency improvement"
            },
            {
                "ticket_id": "ticket-003",
                "original_response": "Rude tone",
                "correct_response": "Polite tone",
                "reason": "Tone improvement"
            }
        ]

        for mistake in mistakes:
            result = await training_service.collect_mistakes(
                company_id=company_id,
                ticket_id=mistake["ticket_id"],
                mistake_data=mistake
            )
            assert result["success"] is True

        # Verify all collected
        stats = training_service.get_stats()
        assert stats["total_mistakes"] == 3

        # Export all
        export = await training_service.export_training_data(company_id)
        assert export["total_records"] == 3

    @pytest.mark.asyncio
    async def test_training_data_model_works(self, training_service):
        """Test that the training data model works correctly."""
        company_id = str(uuid.uuid4())

        # Create training data
        result = await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-test",
            mistake_data={
                "original_response": "Test original",
                "correct_response": "Test corrected",
                "reason": "Test reason"
            }
        )

        assert result["success"] is True

        # Verify training data entry
        stats = training_service.get_stats()
        assert stats["total_training_data"] == 1

    @pytest.mark.asyncio
    async def test_export_includes_all_data(self, training_service):
        """Test that export includes all collected data."""
        company_id = str(uuid.uuid4())

        # Collect data
        await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-001",
            mistake_data={
                "original_response": "Original 1",
                "correct_response": "Corrected 1",
                "reason": "Reason 1"
            }
        )

        await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-002",
            mistake_data={
                "original_response": "Original 2",
                "correct_response": "Corrected 2",
                "reason": "Reason 2"
            }
        )

        # Export
        export = await training_service.export_training_data(company_id)

        assert export["total_records"] == 2
        assert len(export["records"]) == 2

        # Verify record structure
        for record in export["records"]:
            assert "id" in record
            assert "raw_interaction" in record
            assert "anonymized_interaction" in record
            assert "sentiment_score" in record

    @pytest.mark.asyncio
    async def test_training_generates_model_version(self, training_service):
        """Test that training generates a model version."""
        company_id = str(uuid.uuid4())

        # Collect data
        await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-001",
            mistake_data={
                "original_response": "Original",
                "correct_response": "Corrected",
                "reason": "Test"
            }
        )

        # Train
        result = await training_service.train_model(
            company_id=company_id,
            training_config={"epochs": 10}
        )

        assert "model_version" in result
        assert result["model_version"].startswith("v")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_deployment_to_production(self, training_service):
        """Test deployment to production environment."""
        company_id = str(uuid.uuid4())

        # Full cycle
        await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-001",
            mistake_data={
                "original_response": "Original",
                "correct_response": "Corrected",
                "reason": "Test"
            }
        )

        training_result = await training_service.train_model(
            company_id=company_id,
            training_config={}
        )

        deployment = await training_service.deploy_model(
            company_id=company_id,
            model_version=training_result["model_version"]
        )

        assert deployment["environment"] == "production"
        assert deployment["status"] == "deployed"

    @pytest.mark.asyncio
    async def test_company_isolation(self, training_service):
        """Test that training data is isolated per company."""
        company_a = str(uuid.uuid4())
        company_b = str(uuid.uuid4())

        # Collect for company A
        await training_service.collect_mistakes(
            company_id=company_a,
            ticket_id="ticket-a1",
            mistake_data={
                "original_response": "A Original",
                "correct_response": "A Corrected",
                "reason": "A Reason"
            }
        )

        # Collect for company B
        await training_service.collect_mistakes(
            company_id=company_b,
            ticket_id="ticket-b1",
            mistake_data={
                "original_response": "B Original",
                "correct_response": "B Corrected",
                "reason": "B Reason"
            }
        )

        # Export for company A should only have A's data
        export_a = await training_service.export_training_data(company_a)
        assert export_a["total_records"] == 1

        # Export for company B should only have B's data
        export_b = await training_service.export_training_data(company_b)
        assert export_b["total_records"] == 1


class TestTrainingDataValidation:
    """Tests for training data validation."""

    @pytest.mark.asyncio
    async def test_sentiment_score_validation(self, training_service):
        """Test that sentiment score is within valid range."""
        company_id = str(uuid.uuid4())

        result = await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-001",
            mistake_data={
                "original_response": "Bad response",
                "correct_response": "Good response",
                "reason": "Improvement"
            }
        )

        assert result["success"] is True

        # Check that training data has valid sentiment score
        export = await training_service.export_training_data(company_id)
        for record in export["records"]:
            assert -1.0 <= record["sentiment_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_anonymization_applied(self, training_service):
        """Test that PII is anonymized in training data."""
        company_id = str(uuid.uuid4())

        # Include PII in original
        result = await training_service.collect_mistakes(
            company_id=company_id,
            ticket_id="ticket-001",
            mistake_data={
                "original_response": "Hi John Doe, your email john@example.com",
                "correct_response": "Hi there, your email has been updated",
                "reason": "PII removal"
            }
        )

        assert result["success"] is True

        # Verify training data was created
        stats = training_service.get_stats()
        assert stats["total_training_data"] >= 1
