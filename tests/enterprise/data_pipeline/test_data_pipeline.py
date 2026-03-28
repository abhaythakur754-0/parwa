"""Tests for Data Pipeline Module - Week 56"""
import pytest
from datetime import datetime

from enterprise.data_pipeline.data_ingestion import (
    DataIngestion, IngestionConfig, IngestionSource, IngestionResult,
    StreamProcessor, BatchProcessor
)
from enterprise.data_pipeline.data_validator import (
    DataValidator, ValidationRule, ValidationResult, RuleType,
    SchemaManager, SchemaDefinition, SchemaField, DataCleaner
)
from enterprise.data_pipeline.etl_pipeline import (
    ETLPipeline, PipelineConfig, PipelineStage, PipelineResult,
    TransformEngine, TransformRule, TransformType, DataEnricher
)
from enterprise.data_pipeline.data_warehouse import (
    DataWarehouse, WarehouseTable, StorageFormat,
    QueryOptimizer, AnalyticsEngine
)
from enterprise.data_pipeline.pipeline_monitor import (
    PipelineMonitor, PipelineMetric, MetricType,
    DataQualityManager, QualityDimension, QualityScore,
    LineageTracker, LineageNode
)


# ============== Data Ingestion Tests ==============
class TestDataIngestion:
    def test_init(self):
        config = IngestionConfig(source_type=IngestionSource.API)
        ingestion = DataIngestion(config)
        assert ingestion.config.source_type == IngestionSource.API

    def test_register_source(self):
        config = IngestionConfig(source_type=IngestionSource.API)
        ingestion = DataIngestion(config)
        ingestion.register_source("test", lambda: [{"data": 1}])
        assert "test" in ingestion._sources

    def test_ingest_success(self):
        config = IngestionConfig(source_type=IngestionSource.API)
        ingestion = DataIngestion(config)
        ingestion.register_source("test", lambda: [{"data": 1}])
        result = ingestion.ingest("test")
        assert result.records_ingested == 1

    def test_ingest_source_not_found(self):
        config = IngestionConfig(source_type=IngestionSource.API)
        ingestion = DataIngestion(config)
        result = ingestion.ingest("missing")
        assert result.records_ingested == 0
        assert len(result.errors) > 0

    def test_get_stats(self):
        config = IngestionConfig(source_type=IngestionSource.API)
        ingestion = DataIngestion(config)
        ingestion.register_source("test", lambda: [1, 2, 3])
        ingestion.ingest("test")
        stats = ingestion.get_stats()
        assert stats["total_ingested"] == 3


class TestStreamProcessor:
    def test_init(self):
        processor = StreamProcessor()
        assert processor.max_batch == 100

    def test_process(self):
        processor = StreamProcessor(max_batch=3)
        result = processor.process({"event": 1})
        assert result == 0

    def test_process_flush(self):
        processor = StreamProcessor(max_batch=2)
        processor.process({"event": 1})
        result = processor.process({"event": 2})
        assert result == 2

    def test_add_handler(self):
        processor = StreamProcessor()
        processor.add_handler(lambda x: None)
        assert len(processor._handlers) == 1

    def test_get_buffer_size(self):
        processor = StreamProcessor()
        processor.process({"event": 1})
        assert processor.get_buffer_size() == 1


class TestBatchProcessor:
    def test_init(self):
        processor = BatchProcessor()
        assert processor.batch_size == 100

    def test_process_batch(self):
        processor = BatchProcessor(batch_size=10)
        result = processor.process_batch(list(range(20)), lambda x: None)
        assert result["processed"] == 20

    def test_get_job_status(self):
        processor = BatchProcessor()
        processor.process_batch([1, 2, 3], lambda x: None)
        status = processor.get_job_status("job_0")
        assert status is not None

    def test_list_jobs(self):
        processor = BatchProcessor()
        processor.process_batch([1], lambda x: None)
        jobs = processor.list_jobs()
        assert len(jobs) == 1


# ============== Data Validator Tests ==============
class TestDataValidator:
    def test_init(self):
        validator = DataValidator()
        assert len(validator._rules) == 0

    def test_required_rule(self):
        validator = DataValidator()
        validator.add_rule(ValidationRule(field="name", rule_type=RuleType.REQUIRED))
        result = validator.validate({"name": None})
        assert not result.is_valid

    def test_type_rule(self):
        validator = DataValidator()
        validator.add_rule(ValidationRule(field="age", rule_type=RuleType.TYPE, params={"type": int}))
        result = validator.validate({"age": 25})
        assert result.is_valid

    def test_range_rule(self):
        validator = DataValidator()
        validator.add_rule(ValidationRule(field="score", rule_type=RuleType.RANGE, params={"min": 0, "max": 100}))
        result = validator.validate({"score": 50})
        assert result.is_valid

    def test_pattern_rule(self):
        validator = DataValidator()
        validator.add_rule(ValidationRule(field="email", rule_type=RuleType.PATTERN, params={"pattern": r".+@.+"}))
        result = validator.validate({"email": "test@example.com"})
        assert result.is_valid

    def test_clear_rules(self):
        validator = DataValidator()
        validator.add_rule(ValidationRule(field="test", rule_type=RuleType.REQUIRED))
        validator.clear_rules()
        assert len(validator._rules) == 0


class TestSchemaManager:
    def test_init(self):
        manager = SchemaManager()
        assert len(manager._schemas) == 0

    def test_register(self):
        manager = SchemaManager()
        schema = SchemaDefinition(name="user", fields=[SchemaField(name="id", type=int)])
        manager.register(schema)
        assert "user" in manager._schemas

    def test_get(self):
        manager = SchemaManager()
        schema = SchemaDefinition(name="user", fields=[])
        manager.register(schema)
        assert manager.get("user") is not None

    def test_validate(self):
        manager = SchemaManager()
        schema = SchemaDefinition(name="user", fields=[SchemaField(name="id", type=int, required=True)])
        manager.register(schema)
        result = manager.validate("user", {"id": 1})
        assert result.is_valid

    def test_list_schemas(self):
        manager = SchemaManager()
        manager.register(SchemaDefinition(name="test", fields=[]))
        assert len(manager.list_schemas()) == 1


class TestDataCleaner:
    def test_init(self):
        cleaner = DataCleaner()
        assert len(cleaner._rules) == 0

    def test_trim(self):
        cleaner = DataCleaner()
        cleaner.add_rule("name", "trim")
        result = cleaner.clean({"name": "  test  "})
        assert result["name"] == "test"

    def test_normalize(self):
        cleaner = DataCleaner()
        cleaner.add_rule("name", "normalize")
        result = cleaner.clean({"name": "TEST"})
        assert result["name"] == "test"

    def test_fill(self):
        cleaner = DataCleaner()
        cleaner.add_rule("value", "fill", {"default": 0})
        result = cleaner.clean({"value": None})
        assert result["value"] == 0

    def test_clean_batch(self):
        cleaner = DataCleaner()
        cleaner.add_rule("name", "trim")
        results = cleaner.clean_batch([{"name": " a "}, {"name": " b "}])
        assert results[0]["name"] == "a"


# ============== ETL Pipeline Tests ==============
class TestETLPipeline:
    def test_init(self):
        config = PipelineConfig(name="test")
        pipeline = ETLPipeline(config)
        assert pipeline.config.name == "test"

    def test_run(self):
        config = PipelineConfig(name="test")
        pipeline = ETLPipeline(config)
        pipeline.add_extractor(lambda: [{"id": 1}])
        pipeline.add_transformer(lambda x: x)
        pipeline.add_loader(lambda x: None)
        result = pipeline.run()
        assert result.success

    def test_get_status(self):
        config = PipelineConfig(name="test")
        pipeline = ETLPipeline(config)
        assert pipeline.get_status() == "idle"


class TestTransformEngine:
    def test_init(self):
        engine = TransformEngine()
        assert len(engine._rules) == 0

    def test_map_transform(self):
        engine = TransformEngine()
        engine.add_rule(TransformRule("value", "doubled", TransformType.MAP, {"function": "double"}))
        engine.register_function("double", lambda x: x * 2 if x else x)
        result = engine.transform([{"value": 5}])
        assert result[0]["doubled"] == 10

    def test_filter_transform(self):
        engine = TransformEngine()
        engine.add_rule(TransformRule("value", "", TransformType.FILTER, {"predicate": "positive"}))
        engine.register_function("positive", lambda x: x.get("value", 0) > 0)
        result = engine.transform([{"value": 1}, {"value": -1}])
        assert len(result) == 1


class TestDataEnricher:
    def test_init(self):
        enricher = DataEnricher()
        assert len(enricher._sources) == 0

    def test_enrich(self):
        enricher = DataEnricher()
        enricher.add_source("lookup", {"key1": "value1"})
        enricher.add_enrichment_rule("lookup", "key", "enriched")
        result = enricher.enrich([{"key": "key1"}])
        assert result[0]["enriched"] == "value1"


# ============== Data Warehouse Tests ==============
class TestDataWarehouse:
    def test_init(self):
        warehouse = DataWarehouse("test")
        assert warehouse.name == "test"

    def test_create_table(self):
        warehouse = DataWarehouse()
        table = WarehouseTable(name="users", schema={"id": int})
        assert warehouse.create_table(table)
        assert "users" in warehouse.list_tables()

    def test_insert(self):
        warehouse = DataWarehouse()
        warehouse.create_table(WarehouseTable(name="users"))
        count = warehouse.insert("users", [{"id": 1}, {"id": 2}])
        assert count == 2

    def test_query(self):
        warehouse = DataWarehouse()
        warehouse.create_table(WarehouseTable(name="users"))
        warehouse.insert("users", [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
        result = warehouse.query("users", filters={"id": 1})
        assert len(result) == 1

    def test_get_table_stats(self):
        warehouse = DataWarehouse()
        warehouse.create_table(WarehouseTable(name="users"))
        warehouse.insert("users", [{"id": 1}])
        stats = warehouse.get_table_stats("users")
        assert stats["row_count"] == 1


class TestQueryOptimizer:
    def test_init(self):
        optimizer = QueryOptimizer()
        assert len(optimizer._indexes) == 0

    def test_optimize(self):
        optimizer = QueryOptimizer()
        plan = optimizer.optimize("SELECT * FROM t WHERE x = 1", ["t"])
        assert len(plan.steps) > 0

    def test_suggest_index(self):
        optimizer = QueryOptimizer()
        suggestions = optimizer.suggest_index("t", "SELECT * FROM t WHERE name = 'test'")
        assert len(suggestions) > 0


class TestAnalyticsEngine:
    def test_init(self):
        warehouse = DataWarehouse()
        engine = AnalyticsEngine(warehouse)
        assert engine.warehouse == warehouse

    def test_aggregate(self):
        warehouse = DataWarehouse()
        warehouse.create_table(WarehouseTable(name="sales"))
        warehouse.insert("sales", [{"region": "US", "amount": 100}, {"region": "US", "amount": 200}])
        engine = AnalyticsEngine(warehouse)
        result = engine.aggregate("sales", ["region"], {"amount": "sum"})
        assert len(result) == 1


# ============== Pipeline Monitor Tests ==============
class TestPipelineMonitor:
    def test_init(self):
        monitor = PipelineMonitor()
        assert monitor.alert_threshold == 0.9

    def test_track(self):
        monitor = PipelineMonitor()
        metric = PipelineMetric("test", MetricType.THROUGHPUT, 100.0)
        monitor.track(metric)
        assert len(monitor.get_metrics()) == 1

    def test_alert(self):
        monitor = PipelineMonitor(alert_threshold=0.5)
        metric = PipelineMetric("errors", MetricType.ERROR_RATE, 0.8)
        monitor.track(metric)
        assert len(monitor.get_alerts()) > 0

    def test_get_stats(self):
        monitor = PipelineMonitor()
        monitor.track(PipelineMetric("test", MetricType.THROUGHPUT, 100))
        stats = monitor.get_stats()
        assert stats["total_metrics"] == 1


class TestDataQualityManager:
    def test_init(self):
        manager = DataQualityManager()
        assert len(manager.thresholds) == 5

    def test_check_completeness(self):
        manager = DataQualityManager()
        score = manager.check([{"a": 1, "b": None}, {"a": 2, "b": 3}], QualityDimension.COMPLETENESS)
        assert 0 <= score.score <= 1

    def test_is_acceptable(self):
        score = QualityScore(dimension=QualityDimension.COMPLETENESS, score=0.9)
        assert score.is_acceptable

    def test_get_scores(self):
        manager = DataQualityManager()
        manager.check([{"a": 1}], QualityDimension.COMPLETENESS)
        assert len(manager.get_scores()) == 1


class TestLineageTracker:
    def test_init(self):
        tracker = LineageTracker()
        assert len(tracker._nodes) == 0

    def test_track(self):
        tracker = LineageTracker()
        tracker.track("data_1", "source_a")
        assert "data_1" in tracker.list_nodes()

    def test_add_edge(self):
        tracker = LineageTracker()
        tracker.track("data_1", "source")
        tracker.track("data_2", "transform")
        tracker.add_edge("data_1", "data_2", "transform_1")
        lineage = tracker.get_lineage("data_2")
        assert len(lineage.get("upstream", [])) == 1

    def test_get_lineage(self):
        tracker = LineageTracker()
        tracker.track("data_1", "source_a", ["extract"])
        lineage = tracker.get_lineage("data_1")
        assert lineage["node"]["source"] == "source_a"
