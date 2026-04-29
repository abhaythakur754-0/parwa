"""
Tests for Training Data Isolation Service (SG-12) — Week 9 Day 6

Covers: TrainingDataset, TrainingDataRecord, DatasetIsolationResult,
create_dataset, add_records, get_dataset, list_datasets,
validate_isolation, delete_dataset, get_dataset_stats,
export_dataset, check_cross_variant_access, Redis failures.
BC-001: company_id scoping, BC-008: graceful Redis degradation,
GAP-024: variant_type validation, GAP-025: cross-variant audit,
GAP-026: shared dataset support.
Target: 80+ tests
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Module-level stubs
DatasetIsolationResult = None  # type: ignore[assignment,misc]
TrainingDataIsolationService = None  # type: ignore[assignment,misc]
TrainingDataRecord = None  # type: ignore[assignment,misc]
TrainingDataset = None  # type: ignore[assignment,misc]
VALID_VARIANT_TYPES = None  # type: ignore[assignment,misc]


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.services.training_data_isolation import (  # noqa: F811,F401
            DatasetIsolationResult,
            TrainingDataIsolationService,
            TrainingDataRecord,
            TrainingDataset,
            VALID_VARIANT_TYPES,
        )
        globals().update({
            "DatasetIsolationResult": DatasetIsolationResult,
            "TrainingDataIsolationService": TrainingDataIsolationService,
            "TrainingDataRecord": TrainingDataRecord,
            "TrainingDataset": TrainingDataset,
            "VALID_VARIANT_TYPES": VALID_VARIANT_TYPES,
        })


# ═══════════════════════════════════════════════════════════════════════
# Mock Redis store and helpers
# ═══════════════════════════════════════════════════════════════════════


class _MockPipeline:
    """Collects Redis pipeline commands and executes them in batch."""

    def __init__(self, store: dict):
        self._store = store
        self._commands: list = []

    def rpush(self, name, *values):
        self._commands.append(("rpush", name, values))

    def hset(self, name, *args):
        self._commands.append(
            ("hset", name, args),
        )

    def lpop(self, name):
        self._commands.append(("lpop", name))

    async def execute(self):
        results = []
        for cmd in self._commands:
            if cmd[0] == "rpush":
                _, name, values = cmd
                lst = self._store.get(name, [])
                if not isinstance(lst, list):
                    lst = []
                for v in values:
                    lst.append(v)
                self._store[name] = lst
                results.append(len(lst))
            elif cmd[0] == "hset":
                _, name, args = cmd
                h = self._store.get(name, {})
                if not isinstance(h, dict):
                    h = {}
                if len(args) == 1 and isinstance(args[0], dict):
                    h.update(args[0])
                elif len(args) == 2:
                    h[args[0]] = args[1]
                elif len(args) == 3 and isinstance(args[0], dict):
                    h.update(args[0])
                    if args[1] is not None:
                        h[args[1]] = args[2]
                self._store[name] = h
                results.append(1)
            elif cmd[0] == "lpop":
                _, name = cmd
                lst = self._store.get(name, [])
                if not isinstance(lst, list) or not lst:
                    results.append(None)
                else:
                    results.append(lst.pop(0))
                self._store[name] = lst
        self._commands.clear()
        return results


@pytest.fixture
def mock_redis():
    """Create an in-memory mock Redis store.

    The underlying store dict is accessible via ``mock_redis._store``
    so that test helpers can pre-populate data.
    """
    store: dict = {}

    # ── hash ops ──

    async def _hset(name, mapping=None, key=None, value=None):
        h = store.get(name, {})
        if not isinstance(h, dict):
            h = {}
        if mapping:
            h.update(mapping)
        if key is not None:
            h[key] = value
        store[name] = h
        return 1

    async def _hgetall(name):
        val = store.get(name)
        if val is None:
            return {}
        if isinstance(val, dict):
            return dict(val)
        return {}

    # ── set ops ──

    async def _sadd(name, *values):
        s = store.get(name)
        if not isinstance(s, set):
            s = set()
            store[name] = s
        for v in values:
            s.add(v)
        return len(s)

    async def _sismember(name, value):
        s = store.get(name)
        return value in s if isinstance(s, set) else False

    async def _smembers(name):
        s = store.get(name)
        if isinstance(s, set):
            return set(s)
        return set()

    async def _srem(name, *values):
        s = store.get(name, set())
        if not isinstance(s, set):
            return 0
        removed = 0
        for v in values:
            if v in s:
                s.discard(v)
                removed += 1
        return removed

    # ── list ops ──

    async def _rpush(name, *values):
        lst = store.get(name, [])
        if not isinstance(lst, list):
            lst = []
        for v in values:
            lst.append(v)
        store[name] = lst
        return len(lst)

    async def _lpop(name):
        lst = store.get(name, [])
        if not isinstance(lst, list) or not lst:
            return None
        return lst.pop(0)

    async def _lrange(name, start, stop):
        lst = store.get(name, [])
        if not isinstance(lst, list):
            return []
        if stop == -1:
            return list(lst[start:])
        return list(lst[start: stop + 1])

    # ── key ops ──

    async def _delete(*names):
        count = 0
        for n in names:
            if n in store:
                del store[n]
                count += 1
        return count

    async def _exists(name):
        if name not in store:
            return 0
        val = store[name]
        if isinstance(val, (list, set, dict)) and len(val) == 0:
            return 0
        return 1

    # ── pipeline ──

    def _pipeline():
        return _MockPipeline(store)

    redis_mock = MagicMock()
    redis_mock.hset = AsyncMock(side_effect=_hset)
    redis_mock.hgetall = AsyncMock(side_effect=_hgetall)
    redis_mock.sadd = AsyncMock(side_effect=_sadd)
    redis_mock.sismember = AsyncMock(side_effect=_sismember)
    redis_mock.smembers = AsyncMock(side_effect=_smembers)
    redis_mock.srem = AsyncMock(side_effect=_srem)
    redis_mock.rpush = AsyncMock(side_effect=_rpush)
    redis_mock.lpop = AsyncMock(side_effect=_lpop)
    redis_mock.lrange = AsyncMock(side_effect=_lrange)
    redis_mock.delete = AsyncMock(side_effect=_delete)
    redis_mock.exists = AsyncMock(side_effect=_exists)
    redis_mock.pipeline = _pipeline
    # Expose internal store for test helpers
    redis_mock._store = store
    return redis_mock


def _patch_get_redis(mock_redis_obj):
    """Return a patcher for ``backend.app.core.redis.get_redis``."""
    return patch(
        "app.core.redis.get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis_obj,
    )


def _seed_dataset(
    mock_redis_obj,
    dataset_id: str,
    company_id: str,
    variant_type: str = "parwa",
    name: str = "Test Dataset",
    description: str = "",
    record_count: int = 0,
    is_active: bool = True,
    metadata: dict | None = None,
) -> str:
    """Insert a dataset directly into the mock Redis store.

    Returns the storage_path string.
    """
    store = mock_redis_obj._store
    storage_path = ":".join([
        "training_data", company_id, variant_type, dataset_id,
    ])
    meta_key = storage_path + ":meta"
    store[meta_key] = {
        "dataset_id": dataset_id,
        "company_id": company_id,
        "variant_type": variant_type,
        "name": name,
        "description": description,
        "record_count": str(record_count),
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
        "metadata": json.dumps(metadata or {}),
        "storage_path": storage_path,
        "is_active": "1" if is_active else "0",
    }
    idx_key = ":".join([
        "training_data", company_id, "datasets",
    ])
    s = store.get(idx_key)
    if not isinstance(s, set):
        s = set()
        store[idx_key] = s
    s.add(dataset_id)
    return storage_path


# ═══════════════════════════════════════════════════════════════════════
# 1. TestTrainingDataset (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTrainingDataset:

    def test_default_values(self):
        ds = TrainingDataset(
            dataset_id="d1",
            company_id="c1",
            variant_type="parwa",
            name="Test",
            description="desc",
        )
        assert ds.record_count == 0
        assert ds.created_at == ""
        assert ds.updated_at == ""
        assert ds.metadata == {}
        assert ds.storage_path == ""
        assert ds.is_active is True

    def test_to_dict_serialization(self):
        ds = TrainingDataset(
            dataset_id="d1",
            company_id="c1",
            variant_type="mini_parwa",
            name="Test",
            description="A test dataset",
            record_count=5,
            created_at="2025-01-01",
            updated_at="2025-01-02",
            metadata={"key": "val"},
            storage_path="training_data:c1:mini_parwa:d1",
            is_active=True,
        )
        d = ds.to_dict()
        assert d["dataset_id"] == "d1"
        assert d["company_id"] == "c1"
        assert d["variant_type"] == "mini_parwa"
        assert d["name"] == "Test"
        assert d["description"] == "A test dataset"
        assert d["record_count"] == 5
        assert d["created_at"] == "2025-01-01"
        assert d["updated_at"] == "2025-01-02"
        assert d["metadata"] == {"key": "val"}
        assert d["storage_path"] == "training_data:c1:mini_parwa:d1"
        assert d["is_active"] is True

    def test_from_dict_deserialization(self):
        data = {
            "dataset_id": "d2",
            "company_id": "c2",
            "variant_type": "parwa_high",
            "name": "High",
            "description": "High tier",
            "record_count": 10,
            "created_at": "2025-02-01",
            "updated_at": "2025-02-02",
            "metadata": {"source": "upload"},
            "storage_path": "training_data:c2:parwa_high:d2",
            "is_active": False,
        }
        ds = TrainingDataset.from_dict(data)
        assert ds.dataset_id == "d2"
        assert ds.company_id == "c2"
        assert ds.variant_type == "parwa_high"
        assert ds.name == "High"
        assert ds.record_count == 10
        assert ds.is_active is False
        assert ds.metadata == {"source": "upload"}

    def test_active_status_default_true(self):
        ds = TrainingDataset(
            dataset_id="d1",
            company_id="c1",
            variant_type="parwa",
            name="Test",
            description="",
        )
        assert ds.is_active is True

    def test_inactive_status(self):
        ds = TrainingDataset(
            dataset_id="d1",
            company_id="c1",
            variant_type="parwa",
            name="Test",
            description="",
            is_active=False,
        )
        assert ds.is_active is False

    def test_created_at_and_updated_at_set(self):
        ds = TrainingDataset(
            dataset_id="d1",
            company_id="c1",
            variant_type="parwa",
            name="Test",
            description="",
            created_at="2025-06-15T10:00:00+00:00",
            updated_at="2025-06-15T12:00:00+00:00",
        )
        assert ds.created_at == "2025-06-15T10:00:00+00:00"
        assert ds.updated_at == "2025-06-15T12:00:00+00:00"

    def test_storage_path_format(self):
        ds = TrainingDataset(
            dataset_id="abc-123",
            company_id="company-x",
            variant_type="parwa",
            name="Test",
            description="",
            storage_path="training_data:company-x:parwa:abc-123",
        )
        assert "company-x" in ds.storage_path
        assert "parwa" in ds.storage_path
        assert "abc-123" in ds.storage_path
        assert ds.storage_path.startswith("training_data:")

    def test_variant_type_in_path(self):
        ds = TrainingDataset(
            dataset_id="v1",
            company_id="c1",
            variant_type="parwa_high",
            name="Test",
            description="",
            storage_path="training_data:c1:parwa_high:v1",
        )
        assert "parwa_high" in ds.storage_path


# ═══════════════════════════════════════════════════════════════════════
# 2. TestTrainingDataRecord (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTrainingDataRecord:

    def test_default_values(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Hello world",
        )
        assert rec.label is None
        assert rec.intent is None
        assert rec.sentiment is None
        assert rec.metadata == {}
        assert rec.created_at == ""

    def test_to_dict_serialization(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Hello",
            label="greeting",
            intent="hello",
            sentiment=0.8,
            metadata={"lang": "en"},
            created_at="2025-01-01",
        )
        d = rec.to_dict()
        assert d["record_id"] == "r1"
        assert d["content"] == "Hello"
        assert d["label"] == "greeting"
        assert d["intent"] == "hello"
        assert d["sentiment"] == 0.8
        assert d["metadata"] == {"lang": "en"}
        assert d["created_at"] == "2025-01-01"

    def test_optional_fields_none(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Test",
        )
        d = rec.to_dict()
        assert d["label"] is None
        assert d["intent"] is None
        assert d["sentiment"] is None

    def test_created_at_set(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Test",
            created_at="2025-03-01T08:00:00+00:00",
        )
        assert rec.created_at == "2025-03-01T08:00:00+00:00"

    def test_metadata_default(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Test",
        )
        assert rec.metadata == {}

    def test_sentiment_bounds_positive(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Test",
            sentiment=1.0,
        )
        assert rec.sentiment == 1.0

    def test_sentiment_bounds_negative(self):
        rec = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Test",
            sentiment=-1.0,
        )
        assert rec.sentiment == -1.0

    def test_label_optional(self):
        rec_with = TrainingDataRecord(
            record_id="r1",
            dataset_id="d1",
            content="Test",
            label="complaint",
        )
        assert rec_with.label == "complaint"
        rec_without = TrainingDataRecord(
            record_id="r2",
            dataset_id="d1",
            content="Test2",
        )
        assert rec_without.label is None


# ═══════════════════════════════════════════════════════════════════════
# 3. TestCreateDataset (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCreateDataset:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_create_with_valid_variant_mini_parwa(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="c1",
                variant_type="mini_parwa",
                name="Mini Dataset",
            )
        assert ds.variant_type == "mini_parwa"
        assert ds.company_id == "c1"
        assert ds.name == "Mini Dataset"

    @pytest.mark.asyncio
    async def test_create_with_valid_variant_parwa(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="c1",
                variant_type="parwa",
                name="Parwa Dataset",
            )
        assert ds.variant_type == "parwa"
        assert ds.is_active is True

    @pytest.mark.asyncio
    async def test_create_with_valid_variant_parwa_high(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="c1",
                variant_type="parwa_high",
                name="High Dataset",
            )
        assert ds.variant_type == "parwa_high"

    @pytest.mark.asyncio
    async def test_invalid_variant_raises_error(self, mock_redis):
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.create_dataset(
                    company_id="c1",
                    variant_type="unknown_variant",
                    name="Bad",
                )
            assert exc_info.value.error_code == "INVALID_VARIANT_TYPE"

    @pytest.mark.asyncio
    async def test_generates_unique_dataset_id(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds1 = await self.service.create_dataset(
                company_id="c1", variant_type="parwa", name="DS1",
            )
            ds2 = await self.service.create_dataset(
                company_id="c1", variant_type="parwa", name="DS2",
            )
        assert ds1.dataset_id != ds2.dataset_id

    @pytest.mark.asyncio
    async def test_storage_path_includes_company_and_variant(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="my-company",
                variant_type="parwa_high",
                name="Test",
            )
        assert "my-company" in ds.storage_path
        assert "parwa_high" in ds.storage_path
        assert ds.dataset_id in ds.storage_path

    @pytest.mark.asyncio
    async def test_default_is_active_true(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="c1", variant_type="parwa", name="Test",
            )
        assert ds.is_active is True

    @pytest.mark.asyncio
    async def test_custom_metadata_stored(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="c1",
                variant_type="parwa",
                name="Test",
                metadata={"source": "csv", "version": 2},
            )
        assert ds.metadata["source"] == "csv"
        assert ds.metadata["version"] == 2

    @pytest.mark.asyncio
    async def test_description_stored(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.create_dataset(
                company_id="c1",
                variant_type="parwa",
                name="Test",
                description="A detailed description here",
            )
        assert ds.description == "A detailed description here"

    @pytest.mark.asyncio
    async def test_company_isolation_different_companies(self, mock_redis):
        """Datasets for different companies do not share IDs."""
        with _patch_get_redis(mock_redis):
            ds1 = await self.service.create_dataset(
                company_id="company-A",
                variant_type="parwa",
                name="Company A Dataset",
            )
            ds2 = await self.service.create_dataset(
                company_id="company-B",
                variant_type="parwa",
                name="Company B Dataset",
            )
        assert ds1.company_id == "company-A"
        assert ds2.company_id == "company-B"
        assert ds1.dataset_id != ds2.dataset_id


# ═══════════════════════════════════════════════════════════════════════
# 4. TestAddRecords (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestAddRecords:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_add_single_record(self, mock_redis):
        ds_id = "ds-add-1"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa")
        with _patch_get_redis(mock_redis):
            count = await self.service.add_records(
                dataset_id=ds_id,
                company_id="c1",
                records=[{"content": "Hello world"}],
            )
        assert count == 1

    @pytest.mark.asyncio
    async def test_add_multiple_records(self, mock_redis):
        ds_id = "ds-add-multi"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa")
        with _patch_get_redis(mock_redis):
            count = await self.service.add_records(
                dataset_id=ds_id,
                company_id="c1",
                records=[
                    {"content": "First record"},
                    {"content": "Second record"},
                    {"content": "Third record"},
                ],
            )
        assert count == 3

    @pytest.mark.asyncio
    async def test_invalid_dataset_id_raises_error(self, mock_redis):
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.add_records(
                    dataset_id="nonexistent",
                    company_id="c1",
                    records=[{"content": "test"}],
                )
            assert exc_info.value.error_code == "DATASET_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_wrong_company_id_raises_error(self, mock_redis):
        ds_id = "ds-wrong-co"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa")
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.add_records(
                    dataset_id=ds_id,
                    company_id="wrong-company",
                    records=[{"content": "test"}],
                )
            assert exc_info.value.error_code == "DATASET_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_count_of_added_records(self, mock_redis):
        ds_id = "ds-count"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa")
        with _patch_get_redis(mock_redis):
            count = await self.service.add_records(
                dataset_id=ds_id,
                company_id="c1",
                records=[{"content": f"Record {i}"} for i in range(5)],
            )
        assert count == 5

    @pytest.mark.asyncio
    async def test_records_stored_with_variant_isolation(self, mock_redis):
        """Records are stored under the variant-isolated path."""
        ds_id = "ds-isolated"
        sp = _seed_dataset(
            mock_redis, ds_id, "c1", "mini_parwa",
        )
        with _patch_get_redis(mock_redis):
            await self.service.add_records(
                dataset_id=ds_id,
                company_id="c1",
                records=[{"content": "Isolated record"}],
            )
            records = await mock_redis.lrange(
                sp + ":records", 0, -1,
            )
        assert len(records) == 1
        data = json.loads(records[0])
        assert data["content"] == "Isolated record"

    @pytest.mark.asyncio
    async def test_empty_records_list_returns_zero(self, mock_redis):
        with _patch_get_redis(mock_redis):
            count = await self.service.add_records(
                dataset_id="any-id",
                company_id="c1",
                records=[],
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_empty_content_raises_error(self, mock_redis):
        ds_id = "ds-null"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa")
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.add_records(
                    dataset_id=ds_id,
                    company_id="c1",
                    records=[{"content": ""}],
                )
            assert exc_info.value.error_code == "INVALID_RECORD_CONTENT"


# ═══════════════════════════════════════════════════════════════════════
# 5. TestGetDataset (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetDataset:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_get_existing_dataset(self, mock_redis):
        ds_id = "ds-get-1"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "My Dataset",
        )
        with _patch_get_redis(mock_redis):
            ds = await self.service.get_dataset(ds_id, "c1")
        assert ds is not None
        assert ds.dataset_id == ds_id
        assert ds.name == "My Dataset"
        assert ds.variant_type == "parwa"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, mock_redis):
        with _patch_get_redis(mock_redis):
            ds = await self.service.get_dataset("nonexistent", "c1")
        assert ds is None

    @pytest.mark.asyncio
    async def test_wrong_company_returns_none(self, mock_redis):
        ds_id = "ds-get-wrong"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa")
        with _patch_get_redis(mock_redis):
            ds = await self.service.get_dataset(
                ds_id, "other-company",
            )
        assert ds is None

    @pytest.mark.asyncio
    async def test_returns_full_dataset_with_all_fields(self, mock_redis):
        ds_id = "ds-full"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa_high",
            name="Full DS",
            description="Full description",
            record_count=42,
            metadata={"tag": "full"},
        )
        with _patch_get_redis(mock_redis):
            ds = await self.service.get_dataset(ds_id, "c1")
        assert ds is not None
        assert ds.description == "Full description"
        assert ds.record_count == 42
        assert ds.metadata == {"tag": "full"}
        assert ds.variant_type == "parwa_high"

    @pytest.mark.asyncio
    async def test_inactive_dataset_still_returned(self, mock_redis):
        ds_id = "ds-inactive"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", is_active=False,
        )
        with _patch_get_redis(mock_redis):
            ds = await self.service.get_dataset(ds_id, "c1")
        assert ds is not None
        assert ds.is_active is False

    @pytest.mark.asyncio
    async def test_metadata_included(self, mock_redis):
        ds_id = "ds-meta"
        _seed_dataset(
            mock_redis, ds_id, "c1", "shared",
            metadata={"shared_with": "all"},
        )
        with _patch_get_redis(mock_redis):
            ds = await self.service.get_dataset(ds_id, "c1")
        assert ds is not None
        assert ds.metadata == {"shared_with": "all"}


# ═══════════════════════════════════════════════════════════════════════
# 6. TestListDatasets (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestListDatasets:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_list_all_for_company(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-list-1", "c1", "parwa", "DS1",
        )
        _seed_dataset(
            mock_redis, "ds-list-2", "c1", "mini_parwa", "DS2",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets("c1")
        assert len(result) == 2
        names = {ds.name for ds in result}
        assert "DS1" in names
        assert "DS2" in names

    @pytest.mark.asyncio
    async def test_filter_by_variant_type(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-f1", "c1", "parwa", "Parwa DS",
        )
        _seed_dataset(
            mock_redis, "ds-f2", "c1", "mini_parwa", "Mini DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets(
                "c1", variant_type="parwa",
            )
        assert len(result) == 1
        assert result[0].variant_type == "parwa"

    @pytest.mark.asyncio
    async def test_empty_company_returns_empty_list(self, mock_redis):
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets("empty-co")
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_datasets_returned(self, mock_redis):
        for i in range(4):
            _seed_dataset(
                mock_redis,
                f"ds-multi-{i}", "c1", "parwa", f"Dataset {i}",
            )
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets("c1")
        assert len(result) == 4

    @pytest.mark.asyncio
    async def test_shared_datasets_included(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-shared-1", "c1", "shared", "Shared",
        )
        _seed_dataset(
            mock_redis, "ds-priv-1", "c1", "parwa", "Private",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.list_datasets("c1")
        variants = {ds.variant_type for ds in result}
        assert "shared" in variants
        assert "parwa" in variants

    @pytest.mark.asyncio
    async def test_different_companies_not_leaked(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-co-a", "company-A", "parwa", "A",
        )
        _seed_dataset(
            mock_redis, "ds-co-b", "company-B", "parwa", "B",
        )
        with _patch_get_redis(mock_redis):
            result_a = await self.service.list_datasets("company-A")
            result_b = await self.service.list_datasets("company-B")
        assert len(result_a) == 1
        assert len(result_b) == 1
        assert result_a[0].company_id == "company-A"
        assert result_b[0].company_id == "company-B"


# ═══════════════════════════════════════════════════════════════════════
# 7. TestValidateIsolation (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestValidateIsolation:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_valid_isolated_dataset(self, mock_redis):
        ds_id = "ds-iso-clean"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Clean DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.validate_isolation(
                ds_id, "c1",
            )
        assert result.is_isolated is True
        assert result.violations == []

    @pytest.mark.asyncio
    async def test_cross_variant_contamination_violations(self, mock_redis):
        """Dataset metadata found under another variant → violation."""
        ds_id = "ds-contam"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Main")
        # Inject metadata under mini_parwa path (simulates leakage)
        with _patch_get_redis(mock_redis):
            other_meta_key = (
                "training_data:c1:mini_parwa:" + ds_id + ":meta"
            )
            await mock_redis.hset(other_meta_key, mapping={
                "dataset_id": ds_id,
                "variant_type": "mini_parwa",
            })
            result = await self.service.validate_isolation(
                ds_id, "c1",
            )
        assert result.is_isolated is False
        assert len(result.violations) > 0
        assert result.cross_variant_access_attempted is True

    @pytest.mark.asyncio
    async def test_nonexistent_dataset_safe_default(self, mock_redis):
        with _patch_get_redis(mock_redis):
            result = await self.service.validate_isolation(
                "ghost-id", "c1",
            )
        assert result.is_isolated is False
        assert len(result.violations) > 0

    @pytest.mark.asyncio
    async def test_wrong_company_safe_default(self, mock_redis):
        ds_id = "ds-iso-wrong-co"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Mine")
        with _patch_get_redis(mock_redis):
            result = await self.service.validate_isolation(
                ds_id, "other-company",
            )
        assert result.is_isolated is False

    @pytest.mark.asyncio
    async def test_shared_dataset_no_violations(self, mock_redis):
        ds_id = "ds-iso-shared"
        _seed_dataset(
            mock_redis, ds_id, "c1", "shared", "Shared DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.validate_isolation(
                ds_id, "c1",
            )
        assert result.is_isolated is True
        assert result.violations == []

    @pytest.mark.asyncio
    async def test_all_variant_paths_checked(self, mock_redis):
        ds_id = "ds-iso-paths"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Paths DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.validate_isolation(
                ds_id, "c1",
            )
        # Should have checked meta, records, index for expected path
        assert len(result.checked_paths) >= 3

    @pytest.mark.asyncio
    async def test_checked_paths_populated(self, mock_redis):
        ds_id = "ds-iso-cp"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "CP DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.validate_isolation(
                ds_id, "c1",
            )
        for path in result.checked_paths:
            assert isinstance(path, str)
            assert len(path) > 0

    @pytest.mark.asyncio
    async def test_cross_variant_access_attempted_flag(self, mock_redis):
        """Records found under another variant's path sets flag."""
        ds_id = "ds-iso-flag"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Flag DS")
        with _patch_get_redis(mock_redis):
            other_records_key = (
                "training_data:c1:mini_parwa:" + ds_id + ":records"
            )
            await mock_redis.rpush(other_records_key, "contaminated")
            result = await self.service.validate_isolation(
                ds_id, "c1",
            )
        assert result.cross_variant_access_attempted is True


# ═══════════════════════════════════════════════════════════════════════
# 8. TestDeleteDataset (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteDataset:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self, mock_redis):
        ds_id = "ds-del-1"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Del Me")
        with _patch_get_redis(mock_redis):
            result = await self.service.delete_dataset(ds_id, "c1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, mock_redis):
        with _patch_get_redis(mock_redis):
            result = await self.service.delete_dataset("ghost", "c1")
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_company_returns_false(self, mock_redis):
        ds_id = "ds-del-wrong"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Not Yours",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.delete_dataset(
                ds_id, "wrong-company",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_records_also_deleted(self, mock_redis):
        ds_id = "ds-del-records"
        sp = _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "With Recs",
        )
        with _patch_get_redis(mock_redis):
            await mock_redis.rpush(
                sp + ":records",
                json.dumps({"content": "test"}),
            )
            await self.service.delete_dataset(ds_id, "c1")
            exists = await mock_redis.exists(sp + ":records")
        assert exists == 0

    @pytest.mark.asyncio
    async def test_metadata_cleaned_up(self, mock_redis):
        ds_id = "ds-del-meta"
        sp = _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Cleanup",
        )
        with _patch_get_redis(mock_redis):
            await self.service.delete_dataset(ds_id, "c1")
            exists = await mock_redis.exists(sp + ":meta")
        assert exists == 0

    @pytest.mark.asyncio
    async def test_shared_dataset_deletion(self, mock_redis):
        ds_id = "ds-del-shared"
        _seed_dataset(
            mock_redis, ds_id, "c1", "shared", "Shared Del",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.delete_dataset(ds_id, "c1")
        assert result is True


# ═══════════════════════════════════════════════════════════════════════
# 9. TestGetDatasetStats (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetDatasetStats:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_empty_company_returns_zeros(self, mock_redis):
        with _patch_get_redis(mock_redis):
            stats = await self.service.get_dataset_stats("empty-co")
        assert stats["total_datasets"] == 0
        assert stats["total_records"] == 0
        assert stats["active_datasets"] == 0
        assert stats["by_variant_type"] == {}

    @pytest.mark.asyncio
    async def test_single_dataset_stats(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-stat-1", "c1", "parwa",
            record_count=25, is_active=True,
        )
        with _patch_get_redis(mock_redis):
            stats = await self.service.get_dataset_stats("c1")
        assert stats["total_datasets"] == 1
        assert stats["total_records"] == 25
        assert stats["active_datasets"] == 1
        assert stats["company_id"] == "c1"

    @pytest.mark.asyncio
    async def test_multiple_datasets_aggregated(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-stat-a", "c1", "parwa", record_count=10,
        )
        _seed_dataset(
            mock_redis, "ds-stat-b", "c1", "mini_parwa",
            record_count=20,
        )
        with _patch_get_redis(mock_redis):
            stats = await self.service.get_dataset_stats("c1")
        assert stats["total_datasets"] == 2
        assert stats["total_records"] == 30

    @pytest.mark.asyncio
    async def test_per_variant_breakdown(self, mock_redis):
        _seed_dataset(
            mock_redis, "ds-vb-1", "c1", "parwa", record_count=10,
        )
        _seed_dataset(
            mock_redis, "ds-vb-2", "c1", "parwa", record_count=15,
        )
        _seed_dataset(
            mock_redis, "ds-vb-3", "c1", "mini_parwa",
            record_count=5,
        )
        with _patch_get_redis(mock_redis):
            stats = await self.service.get_dataset_stats("c1")
        bv = stats["by_variant_type"]
        assert "parwa" in bv
        assert bv["parwa"]["datasets"] == 2
        assert bv["parwa"]["records"] == 25
        assert "mini_parwa" in bv
        assert bv["mini_parwa"]["records"] == 5

    @pytest.mark.asyncio
    async def test_total_records_count(self, mock_redis):
        for i in range(5):
            _seed_dataset(
                mock_redis,
                f"ds-trc-{i}", "c1", "parwa",
                record_count=(i + 1) * 10,
            )
        with _patch_get_redis(mock_redis):
            stats = await self.service.get_dataset_stats("c1")
        assert stats["total_records"] == 10 + 20 + 30 + 40 + 50

    @pytest.mark.asyncio
    async def test_storage_limit_keys_in_stats(self, mock_redis):
        _seed_dataset(mock_redis, "ds-sue-1", "c1", "parwa")
        with _patch_get_redis(mock_redis):
            stats = await self.service.get_dataset_stats("c1")
        assert "max_records_per_dataset" in stats
        assert "max_datasets_per_company" in stats
        assert stats["max_records_per_dataset"] == 500_000
        assert stats["max_datasets_per_company"] == 100


# ═══════════════════════════════════════════════════════════════════════
# 10. TestExportDataset (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestExportDataset:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_export_json_format(self, mock_redis):
        ds_id = "ds-exp-json"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Export Me",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.export_dataset(
                ds_id, "c1", format="json",
            )
        assert "dataset" in result
        assert "records" in result
        assert result["format"] == "json"
        assert "exported_at" in result

    @pytest.mark.asyncio
    async def test_export_with_records(self, mock_redis):
        ds_id = "ds-exp-recs"
        sp = _seed_dataset(
            mock_redis, ds_id, "c1", "parwa",
            "With Recs", record_count=2,
        )
        rec1 = json.dumps({"record_id": "r1", "content": "Hello"})
        rec2 = json.dumps({"record_id": "r2", "content": "World"})
        with _patch_get_redis(mock_redis):
            await mock_redis.rpush(sp + ":records", rec1, rec2)
            result = await self.service.export_dataset(ds_id, "c1")
        assert len(result["records"]) == 2
        assert result["records"][0]["content"] == "Hello"
        assert result["records"][1]["content"] == "World"

    @pytest.mark.asyncio
    async def test_nonexistent_dataset_raises_error(self, mock_redis):
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.export_dataset("ghost", "c1")
            assert exc_info.value.error_code == "DATASET_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_wrong_company_raises_error(self, mock_redis):
        ds_id = "ds-exp-wrong"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Not Yours",
        )
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.export_dataset(
                    ds_id, "wrong-company",
                )
            assert exc_info.value.error_code == "DATASET_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_records_included_in_export(self, mock_redis):
        ds_id = "ds-exp-inc"
        sp = _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Export Inc",
        )
        with _patch_get_redis(mock_redis):
            await mock_redis.rpush(
                sp + ":records",
                json.dumps({"content": "only record"}),
            )
            result = await self.service.export_dataset(ds_id, "c1")
        assert isinstance(result["records"], list)
        assert len(result["records"]) >= 1
        assert result["dataset"]["name"] == "Export Inc"


# ═══════════════════════════════════════════════════════════════════════
# 11. TestCheckCrossVariantAccess (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckCrossVariantAccess:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_same_variant_no_cross(self, mock_redis):
        ds_id = "ds-cv-same"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Same")
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                ds_id, "parwa", "c1",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_different_variant_is_cross(self, mock_redis):
        ds_id = "ds-cv-diff"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa", "Owned by Parwa",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                ds_id, "mini_parwa", "c1",
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_mini_parwa_to_parwa_is_cross(self, mock_redis):
        ds_id = "ds-cv-mp"
        _seed_dataset(
            mock_redis, ds_id, "c1", "mini_parwa", "Mini DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                ds_id, "parwa", "c1",
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_parwa_to_parwa_high_is_cross(self, mock_redis):
        ds_id = "ds-cv-ph"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Parwa DS")
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                ds_id, "parwa_high", "c1",
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_parwa_high_to_mini_parwa_is_cross(self, mock_redis):
        ds_id = "ds-cv-hm"
        _seed_dataset(
            mock_redis, ds_id, "c1", "parwa_high", "High DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                ds_id, "mini_parwa", "c1",
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_shared_dataset_no_cross(self, mock_redis):
        ds_id = "ds-cv-shared"
        _seed_dataset(
            mock_redis, ds_id, "c1", "shared", "Shared DS",
        )
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                ds_id, "parwa", "c1",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_nonexistent_dataset_safe_default(self, mock_redis):
        with _patch_get_redis(mock_redis):
            result = await self.service.check_cross_variant_access(
                "ghost", "parwa", "c1",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_requesting_variant_raises_error(self, mock_redis):
        ds_id = "ds-cv-unk"
        _seed_dataset(mock_redis, ds_id, "c1", "parwa", "Unk")
        with _patch_get_redis(mock_redis):
            with pytest.raises(Exception) as exc_info:
                await self.service.check_cross_variant_access(
                    ds_id, "unknown_variant", "c1",
                )
            assert exc_info.value.error_code == "INVALID_VARIANT_TYPE"


# ═══════════════════════════════════════════════════════════════════════
# 12. TestRedisFailures (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestRedisFailures:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_redis_down_on_create_raises_error(self):
        broken_redis = MagicMock()
        broken_redis.hset = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        broken_redis.sadd = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=broken_redis,
        ):
            with pytest.raises(Exception) as exc_info:
                await self.service.create_dataset(
                    company_id="c1",
                    variant_type="parwa",
                    name="Fail Create",
                )
            assert exc_info.value.error_code == "DATASET_CREATE_FAILED"

    @pytest.mark.asyncio
    async def test_redis_down_on_add_records_raises_error(self):
        ds_id = "ds-fail-add"
        good_redis = MagicMock()
        # get_dataset works but pipeline fails
        good_redis.sismember = AsyncMock(return_value=True)
        good_redis.hgetall = AsyncMock(return_value={
            "dataset_id": ds_id,
            "company_id": "c1",
            "variant_type": "parwa",
            "name": "Test",
            "description": "",
            "record_count": "0",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
            "metadata": "{}",
            "storage_path": f"training_data:c1:parwa:{ds_id}",
            "is_active": "1",
        })
        good_redis.rpush = AsyncMock(return_value=1)
        mock_pipeline = MagicMock()
        mock_pipeline.rpush = MagicMock()
        mock_pipeline.hset = MagicMock()
        mock_pipeline.lpop = MagicMock()
        mock_pipeline.execute = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        good_redis.pipeline = MagicMock(return_value=mock_pipeline)
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=good_redis,
        ):
            with pytest.raises(Exception) as exc_info:
                await self.service.add_records(
                    dataset_id=ds_id,
                    company_id="c1",
                    records=[{"content": "test record"}],
                )
            assert exc_info.value.error_code == "RECORD_ADD_FAILED"

    @pytest.mark.asyncio
    async def test_redis_down_on_get_returns_none(self):
        broken_redis = MagicMock()
        broken_redis.sismember = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=broken_redis,
        ):
            result = await self.service.get_dataset("any-id", "c1")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_down_on_delete_returns_false(self):
        """When Redis is down, get_dataset fails so delete returns False."""
        broken_redis = MagicMock()
        broken_redis.sismember = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=broken_redis,
        ):
            result = await self.service.delete_dataset("any-id", "c1")
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_down_on_validate_safe_defaults(self):
        """Validate isolation returns safe defaults on Redis failure."""
        broken_redis = MagicMock()
        broken_redis.sismember = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=broken_redis,
        ):
            result = await self.service.validate_isolation(
                "any-id", "c1",
            )
        # Safe default: is_isolated=False, violation about not found
        assert result.is_isolated is False
        assert len(result.violations) > 0


# ═══════════════════════════════════════════════════════════════════════
# 13. TestDatasetIsolationResult (4 extra tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDatasetIsolationResult:

    def test_default_values(self):
        r = DatasetIsolationResult()
        assert r.is_isolated is True
        assert r.violations == []
        assert r.cross_variant_access_attempted is False
        assert r.checked_paths == []

    def test_to_dict_keys(self):
        r = DatasetIsolationResult(
            is_isolated=False,
            violations=["violation1"],
            cross_variant_access_attempted=True,
            checked_paths=["path1"],
        )
        d = r.to_dict()
        assert set(d.keys()) == {
            "is_isolated",
            "violations",
            "cross_variant_access_attempted",
            "checked_paths",
        }
        assert d["is_isolated"] is False
        assert d["violations"] == ["violation1"]

    def test_multiple_violations(self):
        r = DatasetIsolationResult(
            is_isolated=False,
            violations=["v1", "v2", "v3"],
        )
        assert len(r.violations) == 3
        d = r.to_dict()
        assert len(d["violations"]) == 3

    def test_to_dict_types(self):
        r = DatasetIsolationResult()
        d = r.to_dict()
        assert isinstance(d["is_isolated"], bool)
        assert isinstance(d["violations"], list)
        assert isinstance(d["cross_variant_access_attempted"], bool)
        assert isinstance(d["checked_paths"], list)


# ═══════════════════════════════════════════════════════════════════════
# 14. TestValidationHelpers (4 extra tests to exceed 80)
# ═══════════════════════════════════════════════════════════════════════


class TestValidationHelpers:

    def setup_method(self):
        self.service = TrainingDataIsolationService()

    @pytest.mark.asyncio
    async def test_empty_company_id_raises(self):
        with pytest.raises(Exception) as exc_info:
            await self.service.create_dataset(
                company_id="", variant_type="parwa", name="Test",
            )
        assert exc_info.value.error_code == "INVALID_COMPANY_ID"

    @pytest.mark.asyncio
    async def test_whitespace_company_id_raises(self):
        with pytest.raises(Exception) as exc_info:
            await self.service.create_dataset(
                company_id="   ", variant_type="parwa", name="Test",
            )
        assert exc_info.value.error_code == "INVALID_COMPANY_ID"

    @pytest.mark.asyncio
    async def test_long_company_id_raises(self):
        with pytest.raises(Exception) as exc_info:
            await self.service.create_dataset(
                company_id="x" * 200,
                variant_type="parwa",
                name="Test",
            )
        assert exc_info.value.error_code == "INVALID_COMPANY_ID"

    @pytest.mark.asyncio
    async def test_empty_dataset_name_raises(self):
        list_mock = MagicMock()
        list_mock.smembers = AsyncMock(return_value=set())
        list_mock.hgetall = AsyncMock(return_value={})
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=list_mock,
        ):
            with pytest.raises(Exception) as exc_info:
                await self.service.create_dataset(
                    company_id="c1", variant_type="parwa", name="",
                )
            assert exc_info.value.error_code == "INVALID_DATASET_NAME"
