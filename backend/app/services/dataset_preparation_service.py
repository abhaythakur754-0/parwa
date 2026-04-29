"""
Dataset Preparation Service — F-103

Prepares training datasets from various sources:
- Agent mistakes (auto-collected from F-101)
- Manual labeled data
- Ticket history exports
- Knowledge base documents

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped by company_id)
- BC-007: AI Model Interaction (training data format)
- BC-012: Error handling (structured errors)
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, List
from uuid import uuid4

from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.dataset_preparation")

# ── Constants ───────────────────────────────────────────────────────────────

# Dataset status values
DATASET_STATUS_DRAFT = "draft"
DATASET_STATUS_PREPARING = "preparing"
DATASET_STATUS_READY = "ready"
DATASET_STATUS_IN_USE = "in_use"
DATASET_STATUS_ARCHIVED = "archived"
DATASET_STATUS_FAILED = "failed"

# Source types
SOURCE_MISTAKES = "mistakes"
SOURCE_MANUAL = "manual"
SOURCE_EXPORT = "export"
SOURCE_KB = "knowledge_base"

# Minimum samples for training
MIN_SAMPLES_FOR_TRAINING = 50

# Maximum dataset size
MAX_DATASET_SIZE = 10000

# Training data format version
FORMAT_VERSION = "1.0"


class DatasetPreparationService:
    """Service for preparing training datasets (F-103).

    This service handles:
    - Creating datasets from various sources
    - Transforming data into training format
    - Quality validation
    - Dataset versioning

    Usage:
        service = DatasetPreparationService(db)
        result = service.prepare_dataset(company_id, agent_id, source="mistakes")
    """

    def __init__(self, db: Session):
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # Dataset CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def create_dataset(
        self,
        company_id: str,
        agent_id: str,
        name: str,
        source: str = SOURCE_MISTAKES,
        description: Optional[str] = None,
    ) -> Dict:
        """Create a new dataset record.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent this dataset is for.
            name: Dataset name.
            source: Data source type.
            description: Optional description.

        Returns:
            Dict with dataset_id and status.
        """
        from database.models.training import TrainingDataset

        dataset = TrainingDataset(
            company_id=company_id,
            agent_id=agent_id,
            name=name,
            source=source,
            description=description,
            status=DATASET_STATUS_DRAFT,
            record_count=0,
            format_version=FORMAT_VERSION,
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)

        logger.info(
            "dataset_created",
            extra={
                "company_id": company_id,
                "agent_id": agent_id,
                "dataset_id": str(dataset.id),
                "source": source,
            },
        )

        return {
            "status": "created",
            "dataset_id": str(dataset.id),
            "name": name,
            "source": source,
        }

    def prepare_dataset(
        self,
        company_id: str,
        agent_id: str,
        source: str = SOURCE_MISTAKES,
        min_samples: int = MIN_SAMPLES_FOR_TRAINING,
        force_prepare: bool = False,
        name: Optional[str] = None,
    ) -> Dict:
        """Prepare a training dataset from the specified source.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent to prepare dataset for.
            source: Data source (mistakes, manual, export, knowledge_base).
            min_samples: Minimum samples required.
            force_prepare: Skip minimum sample check.
            name: Optional dataset name.

        Returns:
            Dict with dataset_id, sample_count, and quality_score.
        """
        from database.models.training import TrainingDataset

        # Create dataset record
        dataset_name = name or f"Dataset for agent {agent_id[:8]} - {source}"
        create_result = self.create_dataset(
            company_id=company_id,
            agent_id=agent_id,
            name=dataset_name,
            source=source,
        )
        dataset_id = create_result["dataset_id"]

        # Update status to preparing
        dataset = (
            self.db.query(TrainingDataset)
            .filter(
                TrainingDataset.company_id == company_id,
                TrainingDataset.id == dataset_id,
            )
            .first()
        )
        dataset.status = DATASET_STATUS_PREPARING
        self.db.commit()

        try:
            # Collect data from source
            if source == SOURCE_MISTAKES:
                samples = self._collect_from_mistakes(company_id, agent_id)
            elif source == SOURCE_MANUAL:
                samples = self._collect_from_manual_labels(
                    company_id, agent_id)
            elif source == SOURCE_EXPORT:
                samples = self._collect_from_exports(company_id, agent_id)
            elif source == SOURCE_KB:
                samples = self._collect_from_knowledge_base(
                    company_id, agent_id)
            else:
                raise ValueError(f"Unknown source type: {source}")

            # Check minimum samples
            if not force_prepare and len(samples) < min_samples:
                dataset.status = DATASET_STATUS_FAILED
                dataset.error_message = f"Insufficient samples: {
                    len(samples)} < {min_samples}"
                self.db.commit()
                return {
                    "status": "error",
                    "error": dataset.error_message,
                    "sample_count": len(samples),
                    "min_required": min_samples,
                }

            # Transform to training format
            training_data = self._transform_to_training_format(samples, source)

            # Calculate quality score
            quality_score = self._calculate_quality_score(training_data)

            # Store dataset
            storage_path = self._store_dataset(
                company_id, dataset_id, training_data)

            # Update dataset record
            dataset.status = DATASET_STATUS_READY
            dataset.record_count = len(samples)
            dataset.quality_score = quality_score
            dataset.storage_path = storage_path
            dataset.prepared_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                "dataset_prepared",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "dataset_id": dataset_id,
                    "sample_count": len(samples),
                    "quality_score": quality_score,
                },
            )

            return {
                "status": "prepared",
                "dataset_id": dataset_id,
                "sample_count": len(samples),
                "quality_score": quality_score,
                "storage_path": storage_path,
            }

        except Exception as exc:
            dataset.status = DATASET_STATUS_FAILED
            dataset.error_message = str(exc)[:500]
            self.db.commit()

            logger.error(
                "dataset_preparation_failed",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "dataset_id": dataset_id,
                    "error": str(exc)[:200],
                },
            )
            raise

    def get_dataset(self, company_id: str, dataset_id: str) -> Optional[Dict]:
        """Get dataset details.

        Args:
            company_id: Tenant company ID.
            dataset_id: Dataset ID.

        Returns:
            Dict with dataset details or None.
        """
        from database.models.training import TrainingDataset

        dataset = (
            self.db.query(TrainingDataset)
            .filter(
                TrainingDataset.company_id == company_id,
                TrainingDataset.id == dataset_id,
            )
            .first()
        )

        if not dataset:
            return None

        return self._dataset_to_dict(dataset)

    def list_datasets(
        self,
        company_id: str,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """List datasets for a tenant.

        Args:
            company_id: Tenant company ID.
            agent_id: Optional filter by agent.
            status: Optional filter by status.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            Dict with datasets list and total count.
        """
        from database.models.training import TrainingDataset

        query = (
            self.db.query(TrainingDataset)
            .filter(TrainingDataset.company_id == company_id)
        )

        if agent_id:
            query = query.filter(TrainingDataset.agent_id == agent_id)
        if status:
            query = query.filter(TrainingDataset.status == status)

        total = query.count()
        datasets = (
            query
            .order_by(TrainingDataset.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "datasets": [self._dataset_to_dict(d) for d in datasets],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def archive_dataset(self, company_id: str, dataset_id: str) -> Dict:
        """Archive a dataset.

        Args:
            company_id: Tenant company ID.
            dataset_id: Dataset ID.

        Returns:
            Dict with status.
        """
        from database.models.training import TrainingDataset

        dataset = (
            self.db.query(TrainingDataset)
            .filter(
                TrainingDataset.company_id == company_id,
                TrainingDataset.id == dataset_id,
            )
            .first()
        )

        if not dataset:
            return {"status": "error", "error": "Dataset not found"}

        if dataset.status == DATASET_STATUS_IN_USE:
            return {
                "status": "error",
                "error": "Cannot archive dataset in use"}

        dataset.status = DATASET_STATUS_ARCHIVED
        self.db.commit()

        return {"status": "archived", "dataset_id": dataset_id}

    def create_dataset_from_samples(
        self,
        company_id: str,
        agent_id: str,
        samples: List[Dict],
        name: str,
        source: str = "cold_start_template",
    ) -> Dict:
        """Create a dataset directly from provided samples (for cold start).

        Args:
            company_id: Tenant company ID.
            agent_id: Agent this dataset is for.
            samples: List of training samples with 'input' and 'expected_output'.
            name: Dataset name.
            source: Data source type.

        Returns:
            Dict with dataset_id and sample_count.
        """
        from database.models.training import TrainingDataset

        if not samples:
            return {
                "status": "error",
                "error": "No samples provided",
            }

        # Create dataset record
        dataset = TrainingDataset(
            company_id=company_id,
            agent_id=agent_id,
            name=name,
            source=source,
            status=DATASET_STATUS_PREPARING,
            record_count=0,
            format_version=FORMAT_VERSION,
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        dataset_id = str(dataset.id)

        try:
            # Transform to training format
            training_data = []
            for i, sample in enumerate(samples):
                formatted = {
                    "id": sample.get("id", f"{dataset_id}_{i}"),
                    "messages": [
                        {"role": "user", "content": sample.get("input", "")},
                        {"role": "assistant", "content": sample.get("expected_output", "")},
                    ],
                    "metadata": {
                        "source": source,
                        "type": sample.get("type", "template"),
                        "category": sample.get("category"),
                        "industry": sample.get("industry"),
                    },
                }
                training_data.append(formatted)

            # Calculate quality score
            quality_score = self._calculate_quality_score(training_data)

            # Store dataset
            storage_path = self._store_dataset(
                company_id, dataset_id, training_data)

            # Update dataset record
            dataset.status = DATASET_STATUS_READY
            dataset.record_count = len(samples)
            dataset.quality_score = quality_score
            dataset.storage_path = storage_path
            dataset.prepared_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                "dataset_created_from_samples",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "dataset_id": dataset_id,
                    "sample_count": len(samples),
                    "source": source,
                },
            )

            return {
                "status": "created",
                "dataset_id": dataset_id,
                "sample_count": len(samples),
                "quality_score": quality_score,
                "storage_path": storage_path,
            }

        except Exception as exc:
            dataset.status = DATASET_STATUS_FAILED
            dataset.error_message = str(exc)[:500]
            self.db.commit()

            logger.error(
                "create_dataset_from_samples_failed",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "dataset_id": dataset_id,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "error": str(exc)[:500],
            }

    # ══════════════════════════════════════════════════════════════════════════
    # Data Collection Methods
    # ══════════════════════════════════════════════════════════════════════════

    def _collect_from_mistakes(
            self,
            company_id: str,
            agent_id: str) -> List[Dict]:
        """Collect training samples from agent mistakes.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            List of training samples.
        """
        from database.models.training import AgentMistake

        mistakes = (
            self.db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
                AgentMistake.used_in_training == False,
            )
            .order_by(AgentMistake.created_at.desc())
            .limit(MAX_DATASET_SIZE)
            .all()
        )

        samples = []
        for mistake in mistakes:
            samples.append({
                "id": str(mistake.id),
                "type": "mistake_correction",
                "input": {
                    "original_response": mistake.original_response,
                    "ticket_context": mistake.ticket_id,
                },
                "expected_output": mistake.correction or mistake.expected_response,
                "metadata": {
                    "mistake_type": mistake.mistake_type,
                    "severity": mistake.severity,
                    "created_at": mistake.created_at.isoformat() if mistake.created_at else None,
                },
            })

        return samples

    def _collect_from_manual_labels(
            self,
            company_id: str,
            agent_id: str) -> List[Dict]:
        """Collect training samples from manually labeled data.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            List of training samples.
        """
        # Check for manual labels in training_labels table (if exists)
        # For now, return empty list as this is a placeholder
        # In production, this would query a TrainingLabel model
        logger.info(
            "collect_manual_labels",
            extra={"company_id": company_id, "agent_id": agent_id},
        )
        return []

    def _collect_from_exports(
            self,
            company_id: str,
            agent_id: str) -> List[Dict]:
        """Collect training samples from ticket history exports.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            List of training samples.
        """
        # Query resolved tickets with high CSAT for positive examples
        # This is a placeholder for the actual implementation
        logger.info(
            "collect_exports",
            extra={"company_id": company_id, "agent_id": agent_id},
        )
        return []

    def _collect_from_knowledge_base(
            self,
            company_id: str,
            agent_id: str) -> List[Dict]:
        """Collect training samples from knowledge base documents.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent ID.

        Returns:
            List of training samples.
        """
        from database.models.onboarding import KnowledgeDocument

        docs = (
            self.db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id == company_id,
                KnowledgeDocument.status == "completed",
            )
            .limit(MAX_DATASET_SIZE)
            .all()
        )

        samples = []
        for doc in docs:
            # Extract Q&A pairs from knowledge documents
            if doc.content:
                samples.append({
                    "id": str(doc.id),
                    "type": "knowledge_qa",
                    "input": {
                        "document_title": doc.title,
                        "document_type": doc.doc_type,
                    },
                    # Truncate for training
                    "expected_output": doc.content[:1000],
                    "metadata": {
                        "source": "knowledge_base",
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    },
                })

        return samples

    # ══════════════════════════════════════════════════════════════════════════
    # Transformation Methods
    # ══════════════════════════════════════════════════════════════════════════

    def _transform_to_training_format(
            self,
            samples: List[Dict],
            source: str) -> List[Dict]:
        """Transform samples to standard training format.

        Args:
            samples: Raw samples from collection.
            source: Source type.

        Returns:
            List of formatted training samples.
        """
        training_data = []

        for sample in samples:
            formatted = {
                "id": sample.get("id", str(uuid4())),
                "messages": [
                    {"role": "user", "content": self._extract_input_content(sample)},
                    {"role": "assistant", "content": sample.get("expected_output", "")},
                ],
                "metadata": {
                    "source": source,
                    "type": sample.get("type", "unknown"),
                    **sample.get("metadata", {}),
                },
            }
            training_data.append(formatted)

        return training_data

    def _extract_input_content(self, sample: Dict) -> str:
        """Extract input content from sample.

        Args:
            sample: Sample dict.

        Returns:
            String content for training.
        """
        inp = sample.get("input", {})
        if isinstance(inp, str):
            return inp
        if isinstance(inp, dict):
            parts = []
            for key, value in inp.items():
                if value and isinstance(value, str):
                    parts.append(f"{key}: {value}")
            return "\n".join(parts)
        return str(inp)

    # ══════════════════════════════════════════════════════════════════════════
    # Quality Methods
    # ══════════════════════════════════════════════════════════════════════════

    def _calculate_quality_score(self, training_data: List[Dict]) -> float:
        """Calculate quality score for training data.

        Args:
            training_data: Formatted training samples.

        Returns:
            Quality score (0.0 to 1.0).
        """
        if not training_data:
            return 0.0

        scores = []

        for sample in training_data:
            sample_score = 1.0

            # Check for empty content
            messages = sample.get("messages", [])
            for msg in messages:
                content = msg.get("content", "")
                if not content or len(content.strip()) < 10:
                    sample_score *= 0.5
                    break

            # Check for reasonable length
            total_length = sum(len(m.get("content", "")) for m in messages)
            if total_length < 50:
                sample_score *= 0.7
            elif total_length > 5000:
                sample_score *= 0.9  # Slight penalty for very long samples

            scores.append(sample_score)

        # Return average quality score
        return round(sum(scores) / len(scores), 3)

    def _store_dataset(
            self,
            company_id: str,
            dataset_id: str,
            training_data: List[Dict]) -> str:
        """Store training dataset to disk/storage.

        Args:
            company_id: Tenant company ID.
            dataset_id: Dataset ID.
            training_data: Formatted training samples.

        Returns:
            Storage path.
        """
        # Create storage directory if needed
        storage_dir = f"/data/training/{company_id}"
        os.makedirs(storage_dir, exist_ok=True)

        # Write dataset to JSONL file
        file_path = f"{storage_dir}/{dataset_id}.jsonl"
        with open(file_path, "w") as f:
            for sample in training_data:
                f.write(json.dumps(sample) + "\n")

        # Also write metadata
        meta_path = f"{storage_dir}/{dataset_id}_meta.json"
        metadata = {
            "dataset_id": dataset_id,
            "company_id": company_id,
            "record_count": len(training_data),
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return file_path

    # ══════════════════════════════════════════════════════════════════════════
    # Private Helpers
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _dataset_to_dict(dataset) -> Dict:
        """Convert dataset model to dictionary."""
        return {
            "id": str(dataset.id),
            "company_id": str(dataset.company_id),
            "agent_id": str(dataset.agent_id),
            "name": dataset.name,
            "source": dataset.source,
            "description": dataset.description,
            "status": dataset.status,
            "record_count": dataset.record_count or 0,
            "quality_score": float(dataset.quality_score) if dataset.quality_score else 0.0,
            "storage_path": dataset.storage_path,
            "format_version": dataset.format_version,
            "error_message": dataset.error_message,
            "prepared_at": dataset.prepared_at.isoformat() if dataset.prepared_at else None,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        }
