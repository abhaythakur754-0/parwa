"""
Training Data Isolation Service (SG-12).

Variant-specific training datasets with strict isolation at
storage (Redis paths), processing (variant tag), vector index
(tenant+variant metadata), model configs, and analytics.

Variants mini_parwa / parwa / high_parwa cannot access each
other's training data. Shared datasets at the ``shared``
variant_type are accessible by all variants within a tenant.

# TODO(Day6 — I5): Tenant isolation in this service is enforced via Redis
# key-prefix partitioning (training_data:{company_id}:{variant}:{id}) and
# explicit company_id validation on every public method (BC-001).  However,
# the Celery training workers that consume this data (see
# agent_training_service.py and fallback_training_service.py) must also
# re-validate company_id before accessing any records to prevent cross-tenant
# leakage in background job contexts.  Review training_tasks.py for worker-side
# tenant scoping.

BC-001: All operations scoped by company_id.
BC-008: Graceful degradation on Redis failures.
GAP-024: Validate variant_type on every operation.
GAP-025: Audit logging for cross-variant access attempts.
GAP-026: Shared dataset support.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger("training_data_isolation")

# ── Constants ──────────────────────────────────────────────────────

VALID_VARIANT_TYPES = frozenset(
    {"mini_parwa", "parwa", "high_parwa", "shared"},
)

# Key prefixes
_KEY_PREFIX = "training_data"
_META_SUFFIX = ":meta"
_RECORDS_SUFFIX = ":records"
_INDEX_SUFFIX = ":index"

# Maximum records per dataset (safety cap)
MAX_RECORDS_PER_DATASET = 500_000

# Maximum record content length (chars)
MAX_CONTENT_LENGTH = 100_000

# Maximum datasets per company
MAX_DATASETS_PER_COMPANY = 100


# ── Data Classes ───────────────────────────────────────────────────


@dataclass
class TrainingDataset:
    """Represents a variant-isolated training dataset.

    Attributes:
        dataset_id: Unique identifier.
        company_id: Tenant identifier (BC-001).
        variant_type: Variant tier or ``shared``.
        name: Human-readable name.
        description: Dataset description.
        record_count: Number of records stored.
        created_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 last-update timestamp.
        metadata: Arbitrary key-value metadata.
        storage_path: Redis key prefix for isolation.
        is_active: Whether dataset is active.
    """

    dataset_id: str
    company_id: str
    variant_type: str
    name: str
    description: str
    record_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    storage_path: str = ""
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "dataset_id": self.dataset_id,
            "company_id": self.company_id,
            "variant_type": self.variant_type,
            "name": self.name,
            "description": self.description,
            "record_count": self.record_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "storage_path": self.storage_path,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrainingDataset:
        """Deserialize from dictionary."""
        return cls(
            dataset_id=data.get("dataset_id", ""),
            company_id=data.get("company_id", ""),
            variant_type=data.get("variant_type", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            record_count=data.get("record_count", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
            storage_path=data.get("storage_path", ""),
            is_active=data.get("is_active", True),
        )


@dataclass
class TrainingDataRecord:
    """A single training data record within a dataset.

    Attributes:
        record_id: Unique record identifier.
        dataset_id: Parent dataset identifier.
        content: The training text/content.
        label: Optional classification label.
        intent: Optional detected intent.
        sentiment: Optional sentiment score (-1.0 to 1.0).
        metadata: Arbitrary key-value metadata.
        created_at: ISO-8601 creation timestamp.
    """

    record_id: str
    dataset_id: str
    content: str
    label: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "record_id": self.record_id,
            "dataset_id": self.dataset_id,
            "content": self.content,
            "label": self.label,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any],
    ) -> TrainingDataRecord:
        """Deserialize from dictionary."""
        return cls(
            record_id=data.get("record_id", ""),
            dataset_id=data.get("dataset_id", ""),
            content=data.get("content", ""),
            label=data.get("label"),
            intent=data.get("intent"),
            sentiment=data.get("sentiment"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
        )


@dataclass
class DatasetIsolationResult:
    """Result of an isolation validation check.

    Attributes:
        is_isolated: Whether the dataset is properly isolated.
        violations: List of violation descriptions.
        cross_variant_access_attempted:
            Whether cross-variant access was detected.
        checked_paths: Redis paths that were inspected.
    """

    is_isolated: bool = True
    violations: List[str] = field(default_factory=list)
    cross_variant_access_attempted: bool = False
    checked_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_isolated": self.is_isolated,
            "violations": self.violations,
            "cross_variant_access_attempted": (
                self.cross_variant_access_attempted
            ),
            "checked_paths": self.checked_paths,
        }


# ── Validation Helpers ─────────────────────────────────────────────


def _validate_company_id(company_id: str) -> None:
    """Validate company_id (BC-001).

    Raises:
        ParwaBaseError: If company_id is empty or too long.
    """
    if not company_id or not company_id.strip():
        raise ParwaBaseError(
            error_code="INVALID_COMPANY_ID",
            message=(
                "company_id is required and cannot be empty"
                " (BC-001)"
            ),
            status_code=400,
        )
    if len(company_id) > 128:
        raise ParwaBaseError(
            error_code="INVALID_COMPANY_ID",
            message="company_id must not exceed 128 chars",
            status_code=400,
        )


def _validate_variant_type(variant_type: str) -> None:
    """Validate variant_type (GAP-024).

    Raises:
        ParwaBaseError: If variant_type is not in the allowlist.
    """
    if not variant_type or variant_type not in VALID_VARIANT_TYPES:
        raise ParwaBaseError(
            error_code="INVALID_VARIANT_TYPE",
            message=(
                f"Invalid variant_type '{variant_type}'. "
                f"Must be one of: "
                f"{', '.join(sorted(VALID_VARIANT_TYPES))}"
            ),
            status_code=400,
        )


def _validate_dataset_name(name: str) -> None:
    """Validate dataset name is present and within limits."""
    if not name or not name.strip():
        raise ParwaBaseError(
            error_code="INVALID_DATASET_NAME",
            message="Dataset name is required",
            status_code=400,
        )
    if len(name.strip()) > 256:
        raise ParwaBaseError(
            error_code="INVALID_DATASET_NAME",
            message="Dataset name must not exceed 256 chars",
            status_code=400,
        )


def _validate_record_content(content: str) -> None:
    """Validate record content is present and within limits."""
    if not content or not content.strip():
        raise ParwaBaseError(
            error_code="INVALID_RECORD_CONTENT",
            message="Record content is required",
            status_code=400,
        )
    if len(content) > MAX_CONTENT_LENGTH:
        raise ParwaBaseError(
            error_code="RECORD_TOO_LARGE",
            message=(
                f"Record content exceeds max length "
                f"({MAX_CONTENT_LENGTH} chars)"
            ),
            status_code=400,
        )


def _build_storage_path(
    company_id: str,
    variant_type: str,
    dataset_id: str,
) -> str:
    """Build the Redis storage path for a dataset.

    Format: training_data:{company_id}:{variant_type}:{id}

    This path is the isolation boundary — each variant has
    its own partition under the company namespace.
    """
    return ":".join([
        _KEY_PREFIX, company_id, variant_type, dataset_id,
    ])


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _sanitize_metadata(
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Sanitize metadata dict, stripping null bytes."""
    if not metadata:
        return {}
    result = {}
    for k, v in metadata.items():
        key = str(k).replace("\x00", "")
        if isinstance(v, str):
            val = v.replace("\x00", "")
        else:
            val = v
        result[key] = val
    return result


# ── Service Class ──────────────────────────────────────────────────


class TrainingDataIsolationService:
    """Redis-backed training data isolation service.

    Manages per-variant datasets with strict storage isolation.
    Each dataset lives under a Redis path that includes both
    company_id and variant_type, preventing cross-variant
    data leakage.

    Storage layout per dataset::

        training_data:{company_id}:{variant}:{dataset_id}:meta
            → Redis HASH with dataset metadata fields
        training_data:{company_id}:{variant}:{dataset_id}:records
            → Redis LIST of JSON-serialized records
        training_data:{company_id}:{variant}:{dataset_id}:index
            → Redis HASH mapping record_id → list index

    Shared datasets (variant_type=``shared``) are accessible
    by all variant types within the same company.

    BC-001: All operations scoped by company_id.
    BC-008: Redis failures handled gracefully (fail-open).
    GAP-024: variant_type validated on every operation.
    GAP-025: Cross-variant access attempts are audit-logged.
    GAP-026: Shared dataset support via variant_type=shared.
    """

    def __init__(self) -> None:
        """Initialize the service.

        Redis client is obtained lazily from the connection
        pool via ``get_redis()`` on each call to avoid
        holding connections across operations.
        """

    # ── Dataset CRUD ──────────────────────────────────────────

    async def create_dataset(
        self,
        company_id: str,
        variant_type: str,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TrainingDataset:
        """Create a new variant-isolated training dataset.

        Args:
            company_id: Tenant identifier (BC-001).
            variant_type: Variant tier or ``shared``.
            name: Human-readable dataset name.
            description: Optional description.
            metadata: Optional key-value metadata.

        Returns:
            The created TrainingDataset.

        Raises:
            ParwaBaseError: On validation or Redis errors.
        """
        _validate_company_id(company_id)
        _validate_variant_type(variant_type)  # GAP-024
        _validate_dataset_name(name)

        # Check dataset count limit
        existing = await self.list_datasets(company_id)
        if len(existing) >= MAX_DATASETS_PER_COMPANY:
            raise ParwaBaseError(
                error_code="DATASET_LIMIT_EXCEEDED",
                message=(
                    f"Company has reached the maximum of "
                    f"{MAX_DATASETS_PER_COMPANY} datasets"
                ),
                status_code=400,
            )

        dataset_id = str(uuid.uuid4())
        now = _now_iso()
        storage_path = _build_storage_path(
            company_id, variant_type, dataset_id,
        )
        clean_meta = _sanitize_metadata(metadata)

        dataset = TrainingDataset(
            dataset_id=dataset_id,
            company_id=company_id,
            variant_type=variant_type,
            name=name.strip(),
            description=description.strip(),
            record_count=0,
            created_at=now,
            updated_at=now,
            metadata=clean_meta,
            storage_path=storage_path,
            is_active=True,
        )

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            meta_key = storage_path + _META_SUFFIX

            await redis.hset(meta_key, mapping={
                "dataset_id": dataset_id,
                "company_id": company_id,
                "variant_type": variant_type,
                "name": dataset.name,
                "description": dataset.description,
                "record_count": "0",
                "created_at": now,
                "updated_at": now,
                "metadata": json.dumps(clean_meta),
                "storage_path": storage_path,
                "is_active": "1",
            })

            # Track dataset in company index
            idx_key = ":".join([
                _KEY_PREFIX, company_id, "datasets",
            ])
            await redis.sadd(idx_key, dataset_id)

            logger.info(
                "dataset_created",
                extra={
                    "dataset_id": dataset_id,
                    "company_id": company_id,
                    "variant_type": variant_type,
                    "name": dataset.name,
                },
            )
        except Exception as exc:
            logger.warning(
                "dataset_create_redis_error",
                extra={"error": str(exc)},
            )
            raise ParwaBaseError(
                error_code="DATASET_CREATE_FAILED",
                message=(
                    "Failed to create dataset due to "
                    "storage error"
                ),
                status_code=500,
            )

        return dataset

    async def add_records(
        self,
        dataset_id: str,
        company_id: str,
        records: List[Dict[str, Any]],
    ) -> int:
        """Add training records to a dataset.

        Validates dataset ownership and variant isolation
        before storing. Each record is tagged with the
        dataset's variant_type.

        Args:
            dataset_id: Target dataset identifier.
            company_id: Tenant identifier (BC-001).
            records: List of record dicts with at least
                a ``content`` key.

        Returns:
            Number of records successfully added.

        Raises:
            ParwaBaseError: On validation or ownership errors.
        """
        _validate_company_id(company_id)

        if not records:
            return 0

        if len(records) > 10_000:
            raise ParwaBaseError(
                error_code="BATCH_TOO_LARGE",
                message=(
                    f"Cannot add more than 10,000 records "
                    f"in a single call (got {len(records)})"
                ),
                status_code=400,
            )

        # Fetch dataset to validate ownership and isolation
        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            raise ParwaBaseError(
                error_code="DATASET_NOT_FOUND",
                message=(
                    f"Dataset '{dataset_id}' not found for "
                    f"company '{company_id}'"
                ),
                status_code=404,
            )

        if not dataset.is_active:
            raise ParwaBaseError(
                error_code="DATASET_INACTIVE",
                message=f"Dataset '{dataset_id}' is not active",
                status_code=409,
            )

        # Check record cap
        if dataset.record_count + len(records) > (
            MAX_RECORDS_PER_DATASET
        ):
            raise ParwaBaseError(
                error_code="DATASET_FULL",
                message=(
                    f"Dataset would exceed maximum of "
                    f"{MAX_RECORDS_PER_DATASET} records"
                ),
                status_code=400,
            )

        # Validate all records before storing
        validated: List[TrainingDataRecord] = []
        for rec in records:
            content = rec.get("content", "")
            _validate_record_content(content)

            record_id = str(uuid.uuid4())
            now = _now_iso()
            rec_meta = _sanitize_metadata(rec.get("metadata"))

            # Clamp sentiment to [-1.0, 1.0]
            sentiment = rec.get("sentiment")
            if sentiment is not None:
                try:
                    sentiment = max(-1.0, min(1.0, float(sentiment)))
                except (TypeError, ValueError):
                    sentiment = None

            validated.append(TrainingDataRecord(
                record_id=record_id,
                dataset_id=dataset_id,
                content=content.strip(),
                label=rec.get("label"),
                intent=rec.get("intent"),
                sentiment=sentiment,
                metadata=rec_meta,
                created_at=now,
            ))

        added = 0
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            records_key = (
                dataset.storage_path + _RECORDS_SUFFIX
            )
            index_key = (
                dataset.storage_path + _INDEX_SUFFIX
            )

            pipeline = redis.pipeline()
            for v_rec in validated:
                idx = await redis.rpush(records_key, "dummy")
                pipeline.rpush(
                    records_key,
                    json.dumps(v_rec.to_dict()),
                )
                pipeline.hset(
                    index_key, v_rec.record_id, str(idx),
                )
                added += 1

            # Update metadata record_count
            meta_key = dataset.storage_path + _META_SUFFIX
            new_count = dataset.record_count + added
            pipeline.hset(meta_key, "record_count", str(new_count))
            pipeline.hset(
                meta_key, "updated_at", _now_iso(),
            )

            # Remove the dummy entry we pushed for idx calc
            pipeline.lpop(records_key)

            await pipeline.execute()

            logger.info(
                "records_added",
                extra={
                    "dataset_id": dataset_id,
                    "company_id": company_id,
                    "variant_type": dataset.variant_type,
                    "count": added,
                },
            )
        except Exception as exc:
            logger.warning(
                "records_add_redis_error",
                extra={"error": str(exc)},
            )
            raise ParwaBaseError(
                error_code="RECORD_ADD_FAILED",
                message="Failed to add records to dataset",
                status_code=500,
            )

        return added

    async def get_dataset(
        self,
        dataset_id: str,
        company_id: str,
    ) -> Optional[TrainingDataset]:
        """Retrieve a dataset by ID and company.

        Validates ownership (BC-001) and returns None if
        the dataset does not exist or belongs to another
        company.

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            TrainingDataset or None if not found.
        """
        _validate_company_id(company_id)

        if not dataset_id:
            return None

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            idx_key = ":".join([
                _KEY_PREFIX, company_id, "datasets",
            ])

            # Check dataset belongs to this company
            is_member = await redis.sismember(idx_key, dataset_id)
            if not is_member:
                return None

            # Search across all variant types for the meta
            for vt in VALID_VARIANT_TYPES:
                path = _build_storage_path(
                    company_id, vt, dataset_id,
                )
                meta_key = path + _META_SUFFIX
                meta = await redis.hgetall(meta_key)
                if not meta:
                    continue

                is_active = meta.get("is_active", "1") == "1"
                try:
                    record_count = int(
                        meta.get("record_count", "0"),
                    )
                except (TypeError, ValueError):
                    record_count = 0

                try:
                    stored_meta = json.loads(
                        meta.get("metadata", "{}"),
                    )
                except (json.JSONDecodeError, TypeError):
                    stored_meta = {}

                return TrainingDataset(
                    dataset_id=dataset_id,
                    company_id=company_id,
                    variant_type=vt,
                    name=meta.get("name", ""),
                    description=meta.get("description", ""),
                    record_count=record_count,
                    created_at=meta.get("created_at", ""),
                    updated_at=meta.get("updated_at", ""),
                    metadata=stored_meta,
                    storage_path=meta.get("storage_path", ""),
                    is_active=is_active,
                )
        except Exception as exc:
            logger.warning(
                "dataset_get_redis_error",
                extra={"error": str(exc)},
            )

        return None

    async def list_datasets(
        self,
        company_id: str,
        variant_type: Optional[str] = None,
    ) -> List[TrainingDataset]:
        """List datasets for a company, optionally filtered.

        Args:
            company_id: Tenant identifier (BC-001).
            variant_type: Optional variant filter. If
                ``None``, returns all variants for this
                company including shared datasets.

        Returns:
            List of TrainingDataset objects.
        """
        _validate_company_id(company_id)

        if variant_type is not None:
            _validate_variant_type(variant_type)  # GAP-024

        datasets: List[TrainingDataset] = []

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            idx_key = ":".join([
                _KEY_PREFIX, company_id, "datasets",
            ])
            dataset_ids = await redis.smembers(idx_key)

            if not dataset_ids:
                return datasets

            variant_types_to_check = (
                {variant_type}
                if variant_type
                else VALID_VARIANT_TYPES
            )

            for ds_id in dataset_ids:
                for vt in variant_types_to_check:
                    path = _build_storage_path(
                        company_id, vt, ds_id,
                    )
                    meta_key = path + _META_SUFFIX
                    meta = await redis.hgetall(meta_key)
                    if not meta:
                        continue

                    is_active = (
                        meta.get("is_active", "1") == "1"
                    )
                    try:
                        rec_count = int(
                            meta.get("record_count", "0"),
                        )
                    except (TypeError, ValueError):
                        rec_count = 0

                    try:
                        stored_meta = json.loads(
                            meta.get("metadata", "{}"),
                        )
                    except (json.JSONDecodeError, TypeError):
                        stored_meta = {}

                    datasets.append(TrainingDataset(
                        dataset_id=ds_id,
                        company_id=company_id,
                        variant_type=vt,
                        name=meta.get("name", ""),
                        description=meta.get("description", ""),
                        record_count=rec_count,
                        created_at=meta.get("created_at", ""),
                        updated_at=meta.get("updated_at", ""),
                        metadata=stored_meta,
                        storage_path=meta.get(
                            "storage_path", "",
                        ),
                        is_active=is_active,
                    ))
                    break  # Found dataset, next ds_id
        except Exception as exc:
            logger.warning(
                "dataset_list_redis_error",
                extra={"error": str(exc)},
            )

        return datasets

    # ── Isolation Validation ───────────────────────────────────

    async def validate_isolation(
        self,
        dataset_id: str,
        company_id: str,
    ) -> DatasetIsolationResult:
        """Validate that a dataset has no cross-variant leakage.

        Checks that all records in the dataset's storage path
        match the expected variant_type, and that no records
        have been placed by a different variant.

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            DatasetIsolationResult with detailed findings.
        """
        _validate_company_id(company_id)

        result = DatasetIsolationResult(
            checked_paths=[],
        )

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            result.is_isolated = False
            result.violations.append(
                f"Dataset '{dataset_id}' not found "
                f"for company '{company_id}'"
            )
            return result

        expected_vt = dataset.variant_type
        expected_path_prefix = _build_storage_path(
            company_id, expected_vt, dataset_id,
        )
        result.checked_paths.append(
            expected_path_prefix + _META_SUFFIX,
        )
        result.checked_paths.append(
            expected_path_prefix + _RECORDS_SUFFIX,
        )
        result.checked_paths.append(
            expected_path_prefix + _INDEX_SUFFIX,
        )

        # If shared dataset, no variant boundary to check
        if expected_vt == "shared":
            result.is_isolated = True
            return result

        try:
            from app.core.redis import get_redis

            redis = await get_redis()

            # Check no other variant has a dataset with same ID
            for vt in VALID_VARIANT_TYPES:
                if vt == expected_vt or vt == "shared":
                    continue

                other_path = _build_storage_path(
                    company_id, vt, dataset_id,
                )
                other_meta_key = other_path + _META_SUFFIX
                other_meta = await redis.hgetall(
                    other_meta_key,
                )
                if other_meta:
                    result.checked_paths.append(
                        other_meta_key,
                    )
                    result.is_isolated = False
                    result.violations.append(
                        f"Dataset '{dataset_id}' exists "
                        f"under variant '{vt}' — "
                        f"cross-variant duplication detected"
                    )
                    result.cross_variant_access_attempted = (
                        True
                    )

            # Verify records list is not accessible from
            # another variant's path
            for vt in VALID_VARIANT_TYPES:
                if vt == expected_vt:
                    continue
                check_path = _build_storage_path(
                    company_id, vt, dataset_id,
                )
                check_records = (
                    check_path + _RECORDS_SUFFIX
                )
                exists = await redis.exists(check_records)
                if exists:
                    result.checked_paths.append(
                        check_records,
                    )
                    result.is_isolated = False
                    result.violations.append(
                        f"Records list found at variant "
                        f"'{vt}' path for dataset "
                        f"'{dataset_id}'"
                    )
                    result.cross_variant_access_attempted = (
                        True
                    )

        except Exception as exc:
            logger.warning(
                "isolation_check_redis_error",
                extra={"error": str(exc)},
            )
            # Fail open — don't report false violations
            result.violations.append(
                "Could not complete isolation check "
                "due to storage error"
            )

        return result

    async def check_cross_variant_access(
        self,
        dataset_id: str,
        requesting_variant: str,
        company_id: str,
    ) -> bool:
        """Check if accessing a dataset would cross variant boundary.

        Returns ``True`` if the access would violate isolation
        (i.e., the requesting variant does not own the dataset
        and the dataset is not shared).

        This method also logs an audit entry for every
        cross-variant access attempt (GAP-025).

        Args:
            dataset_id: Dataset identifier.
            requesting_variant: Variant type making the request.
            company_id: Tenant identifier (BC-001).

        Returns:
            ``True`` if cross-variant access would occur.
        """
        _validate_company_id(company_id)
        _validate_variant_type(requesting_variant)  # GAP-024

        if not dataset_id:
            return False

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            return False

        dataset_vt = dataset.variant_type

        # Shared datasets accessible by all variants
        if dataset_vt == "shared":
            return False

        # Same variant — no cross-boundary
        if dataset_vt == requesting_variant:
            return False

        # GAP-025: Audit log the cross-variant attempt
        logger.warning(
            "cross_variant_access_attempt",
            extra={
                "dataset_id": dataset_id,
                "company_id": company_id,
                "requesting_variant": requesting_variant,
                "dataset_variant": dataset_vt,
                "action": "denied",
            },
        )

        try:
            from app.services.audit_service import (
                ActorType,
                create_audit_entry,
            )

            create_audit_entry(
                company_id=company_id,
                actor_type=ActorType.API_KEY.value,
                action="cross_variant_access_denied",
                resource_type="training_dataset",
                resource_id=dataset_id,
                old_value=None,
                new_value=json.dumps({
                    "requesting_variant": requesting_variant,
                    "dataset_variant": dataset_vt,
                }),
            )
        except Exception as exc:
            # Audit failure must not break the flow
            logger.warning(
                "cross_variant_audit_failed",
                extra={"error": str(exc)},
            )

        return True

    # ── Dataset Deletion ───────────────────────────────────────

    async def delete_dataset(
        self,
        dataset_id: str,
        company_id: str,
    ) -> bool:
        """Delete a dataset and all its records.

        Only the owning company can delete a dataset (BC-001).

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        _validate_company_id(company_id)

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            return False

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            meta_key = dataset.storage_path + _META_SUFFIX
            records_key = (
                dataset.storage_path + _RECORDS_SUFFIX
            )
            index_key = (
                dataset.storage_path + _INDEX_SUFFIX
            )

            await redis.delete(meta_key, records_key, index_key)

            # Remove from company index
            idx_key = ":".join([
                _KEY_PREFIX, company_id, "datasets",
            ])
            await redis.srem(idx_key, dataset_id)

            logger.info(
                "dataset_deleted",
                extra={
                    "dataset_id": dataset_id,
                    "company_id": company_id,
                    "variant_type": dataset.variant_type,
                },
            )
        except Exception as exc:
            logger.warning(
                "dataset_delete_redis_error",
                extra={"error": str(exc)},
            )
            raise ParwaBaseError(
                error_code="DATASET_DELETE_FAILED",
                message="Failed to delete dataset",
                status_code=500,
            )

        return True

    # ── Statistics & Analytics ─────────────────────────────────

    async def get_dataset_stats(
        self,
        company_id: str,
        variant_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregated training dataset statistics.

        Args:
            company_id: Tenant identifier (BC-001).
            variant_type: Optional variant filter.

        Returns:
            Dict with aggregate statistics.
        """
        _validate_company_id(company_id)

        if variant_type is not None:
            _validate_variant_type(variant_type)  # GAP-024

        datasets = await self.list_datasets(
            company_id, variant_type,
        )

        total_records = 0
        total_datasets = len(datasets)
        active_datasets = 0
        by_variant: Dict[str, Dict[str, int]] = {}

        for ds in datasets:
            total_records += ds.record_count
            if ds.is_active:
                active_datasets += 1

            vt = ds.variant_type
            if vt not in by_variant:
                by_variant[vt] = {
                    "datasets": 0,
                    "records": 0,
                    "active": 0,
                }
            by_variant[vt]["datasets"] += 1
            by_variant[vt]["records"] += ds.record_count
            if ds.is_active:
                by_variant[vt]["active"] += 1

        return {
            "company_id": company_id,
            "total_datasets": total_datasets,
            "active_datasets": active_datasets,
            "total_records": total_records,
            "max_records_per_dataset": MAX_RECORDS_PER_DATASET,
            "max_datasets_per_company": (
                MAX_DATASETS_PER_COMPANY
            ),
            "by_variant_type": by_variant,
        }

    # ── Export ─────────────────────────────────────────────────

    async def export_dataset(
        self,
        dataset_id: str,
        company_id: str,
        format: str = "json",
    ) -> Dict[str, Any]:
        """Export a dataset with all its records.

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).
            format: Export format (only ``json`` supported).

        Returns:
            Dict with dataset metadata and records list.

        Raises:
            ParwaBaseError: On validation or not found.
        """
        _validate_company_id(company_id)

        if format not in ("json",):
            raise ParwaBaseError(
                error_code="UNSUPPORTED_EXPORT_FORMAT",
                message=(
                    f"Unsupported format '{format}'. "
                    f"Only 'json' is supported."
                ),
                status_code=400,
            )

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            raise ParwaBaseError(
                error_code="DATASET_NOT_FOUND",
                message=(
                    f"Dataset '{dataset_id}' not found "
                    f"for company '{company_id}'"
                ),
                status_code=404,
            )

        records: List[Dict[str, Any]] = []

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            records_key = (
                dataset.storage_path + _RECORDS_SUFFIX
            )

            raw_records = await redis.lrange(
                records_key, 0, -1,
            )
            for raw in raw_records:
                try:
                    rec_data = json.loads(raw)
                    records.append(rec_data)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "export_skip_malformed_record",
                        extra={
                            "dataset_id": dataset_id,
                        },
                    )
                    continue
        except Exception as exc:
            logger.warning(
                "export_redis_error",
                extra={"error": str(exc)},
            )
            raise ParwaBaseError(
                error_code="EXPORT_FAILED",
                message="Failed to export dataset records",
                status_code=500,
            )

        logger.info(
            "dataset_exported",
            extra={
                "dataset_id": dataset_id,
                "company_id": company_id,
                "variant_type": dataset.variant_type,
                "record_count": len(records),
                "format": format,
            },
        )

        return {
            "dataset": dataset.to_dict(),
            "records": records,
            "exported_at": _now_iso(),
            "format": format,
        }

    # ── Record Retrieval ───────────────────────────────────────

    async def get_records(
        self,
        dataset_id: str,
        company_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Retrieve records from a dataset with pagination.

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).
            offset: Number of records to skip.
            limit: Max records to return (max 1000).

        Returns:
            Dict with records list and pagination info.
        """
        _validate_company_id(company_id)

        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            raise ParwaBaseError(
                error_code="DATASET_NOT_FOUND",
                message=(
                    f"Dataset '{dataset_id}' not found "
                    f"for company '{company_id}'"
                ),
                status_code=404,
            )

        records: List[Dict[str, Any]] = []
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            records_key = (
                dataset.storage_path + _RECORDS_SUFFIX
            )

            raw_records = await redis.lrange(
                records_key, offset, offset + limit - 1,
            )
            for raw in raw_records:
                try:
                    records.append(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as exc:
            logger.warning(
                "records_get_redis_error",
                extra={"error": str(exc)},
            )

        return {
            "records": records,
            "offset": offset,
            "limit": limit,
            "returned": len(records),
            "total": dataset.record_count,
        }

    async def get_shared_datasets(
        self,
        company_id: str,
    ) -> List[TrainingDataset]:
        """List shared datasets for a company.

        Shared datasets are accessible by all variant types
        within the same tenant (GAP-026).

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            List of shared TrainingDataset objects.
        """
        return await self.list_datasets(
            company_id, variant_type="shared",
        )

    # ── Dataset Activation ─────────────────────────────────────

    async def set_dataset_active(
        self,
        dataset_id: str,
        company_id: str,
        is_active: bool,
    ) -> Optional[TrainingDataset]:
        """Activate or deactivate a dataset.

        Inactive datasets cannot receive new records but
        existing records remain accessible for read operations.

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).
            is_active: Desired active state.

        Returns:
            Updated TrainingDataset or None if not found.
        """
        _validate_company_id(company_id)

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            return None

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            meta_key = dataset.storage_path + _META_SUFFIX

            await redis.hset(
                meta_key, "is_active", "1" if is_active else "0",
            )
            await redis.hset(
                meta_key, "updated_at", _now_iso(),
            )

            dataset.is_active = is_active
            dataset.updated_at = _now_iso()

            logger.info(
                "dataset_active_state_changed",
                extra={
                    "dataset_id": dataset_id,
                    "company_id": company_id,
                    "is_active": is_active,
                },
            )
        except Exception as exc:
            logger.warning(
                "dataset_state_change_error",
                extra={"error": str(exc)},
            )

        return dataset

    # ── Vector Index Metadata ──────────────────────────────────

    async def update_vector_index_metadata(
        self,
        dataset_id: str,
        company_id: str,
        index_metadata: Dict[str, Any],
    ) -> bool:
        """Update vector index metadata for a dataset.

        Vector indices must include tenant+variant metadata
        for isolation enforcement at the embedding/search layer.

        Args:
            dataset_id: Dataset identifier.
            company_id: Tenant identifier (BC-001).
            index_metadata: Metadata to merge into the
                dataset's metadata field. Must include
                ``tenant_id``, ``variant_type``, and
                ``vector_index_id`` keys.

        Returns:
            ``True`` if updated successfully.

        Raises:
            ParwaBaseError: On validation errors.
        """
        _validate_company_id(company_id)

        required_keys = {"tenant_id", "variant_type"}
        missing = required_keys - set(index_metadata.keys())
        if missing:
            raise ParwaBaseError(
                error_code="INVALID_INDEX_METADATA",
                message=(
                    f"Missing required keys: "
                    f"{', '.join(sorted(missing))}"
                ),
                status_code=400,
            )

        _validate_variant_type(
            index_metadata["variant_type"],
        )

        # Ensure tenant_id matches company_id
        if index_metadata["tenant_id"] != company_id:
            logger.warning(
                "vector_index_tenant_mismatch",
                extra={
                    "dataset_id": dataset_id,
                    "company_id": company_id,
                    "metadata_tenant": (
                        index_metadata["tenant_id"]
                    ),
                },
            )
            raise ParwaBaseError(
                error_code="TENANT_MISMATCH",
                message="tenant_id in metadata does not "
                "match company_id",
                status_code=400,
            )

        dataset = await self.get_dataset(dataset_id, company_id)
        if dataset is None:
            raise ParwaBaseError(
                error_code="DATASET_NOT_FOUND",
                message=(
                    f"Dataset '{dataset_id}' not found "
                    f"for company '{company_id}'"
                ),
                status_code=404,
            )

        merged_meta = {**dataset.metadata, **index_metadata}

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            meta_key = dataset.storage_path + _META_SUFFIX

            await redis.hset(
                meta_key,
                "metadata",
                json.dumps(merged_meta),
            )
            await redis.hset(
                meta_key, "updated_at", _now_iso(),
            )

            dataset.metadata = merged_meta
            dataset.updated_at = _now_iso()

            logger.info(
                "vector_index_metadata_updated",
                extra={
                    "dataset_id": dataset_id,
                    "company_id": company_id,
                    "variant_type": (
                        index_metadata["variant_type"]
                    ),
                },
            )
        except Exception as exc:
            logger.warning(
                "vector_meta_update_error",
                extra={"error": str(exc)},
            )
            raise ParwaBaseError(
                error_code="VECTOR_META_UPDATE_FAILED",
                message=(
                    "Failed to update vector index "
                    "metadata"
                ),
                status_code=500,
            )

        return True

    # ── Model Configuration ────────────────────────────────────

    async def get_model_config(
        self,
        company_id: str,
        variant_type: str,
    ) -> Dict[str, Any]:
        """Get model configuration for a variant.

        Model configs are variant-specific — each variant
        tier may use different models, hyperparameters, or
        technique tiers.

        Args:
            company_id: Tenant identifier (BC-001).
            variant_type: Variant tier.

        Returns:
            Dict with model configuration or defaults.
        """
        _validate_company_id(company_id)
        _validate_variant_type(variant_type)  # GAP-024

        default_configs: Dict[str, Dict[str, Any]] = {
            "mini_parwa": {
                "max_tokens": 256,
                "temperature": 0.3,
                "technique_tier": "tier_1",
                "confidence_threshold": 0.95,
                "models": ["gpt-4o-mini"],
            },
            "parwa": {
                "max_tokens": 1024,
                "temperature": 0.5,
                "technique_tier": "tier_2",
                "confidence_threshold": 0.85,
                "models": ["gpt-4o", "claude-sonnet"],
            },
            "high_parwa": {
                "max_tokens": 4096,
                "temperature": 0.7,
                "technique_tier": "tier_3",
                "confidence_threshold": 0.75,
                "models": [
                    "gpt-4o", "claude-opus", "gemini-pro",
                ],
            },
        }

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            config_key = ":".join([
                _KEY_PREFIX, company_id, "model_config",
                variant_type,
            ])
            stored = await redis.hgetall(config_key)
            if stored and stored.get("config"):
                try:
                    return json.loads(stored["config"])
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception as exc:
            logger.warning(
                "model_config_get_error",
                extra={"error": str(exc)},
            )

        return default_configs.get(variant_type, {})

    async def set_model_config(
        self,
        company_id: str,
        variant_type: str,
        config: Dict[str, Any],
    ) -> bool:
        """Set model configuration for a variant.

        Args:
            company_id: Tenant identifier (BC-001).
            variant_type: Variant tier.
            config: Model configuration dict.

        Returns:
            ``True`` if set successfully.
        """
        _validate_company_id(company_id)
        _validate_variant_type(variant_type)  # GAP-024

        if not isinstance(config, dict) or not config:
            raise ParwaBaseError(
                error_code="INVALID_MODEL_CONFIG",
                message="Model config must be a non-empty dict",
                status_code=400,
            )

        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            config_key = ":".join([
                _KEY_PREFIX, company_id, "model_config",
                variant_type,
            ])

            await redis.hset(
                config_key,
                mapping={
                    "config": json.dumps(config),
                    "updated_at": _now_iso(),
                    "variant_type": variant_type,
                },
            )

            logger.info(
                "model_config_updated",
                extra={
                    "company_id": company_id,
                    "variant_type": variant_type,
                },
            )
        except Exception as exc:
            logger.warning(
                "model_config_set_error",
                extra={"error": str(exc)},
            )
            raise ParwaBaseError(
                error_code="MODEL_CONFIG_SET_FAILED",
                message="Failed to set model configuration",
                status_code=500,
            )

        return True
