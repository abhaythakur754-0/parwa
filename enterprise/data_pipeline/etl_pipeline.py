"""ETL Pipeline Module - Week 56, Builder 3"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"


class TransformType(Enum):
    MAP = "map"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    JOIN = "join"
    PIVOT = "pivot"


@dataclass
class TransformRule:
    input_field: str
    output_field: str
    transform_type: TransformType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    name: str
    stages: List[PipelineStage] = field(default_factory=list)
    error_handling: str = "continue"
    parallel: bool = False


@dataclass
class PipelineResult:
    success: bool
    records_processed: int
    records_failed: int
    duration_ms: float
    errors: List[str] = field(default_factory=list)


class ETLPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._extractors: List[Callable] = []
        self._transformers: List[Callable] = []
        self._loaders: List[Callable] = []
        self._status = "idle"

    def add_extractor(self, func: Callable) -> None:
        self._extractors.append(func)

    def add_transformer(self, func: Callable) -> None:
        self._transformers.append(func)

    def add_loader(self, func: Callable) -> None:
        self._loaders.append(func)

    def run(self) -> PipelineResult:
        import time
        start = time.time()
        errors = []
        processed = 0
        failed = 0

        self._status = "running"

        try:
            # Extract
            data = []
            for extractor in self._extractors:
                try:
                    result = extractor()
                    if isinstance(result, list):
                        data.extend(result)
                    else:
                        data.append(result)
                except Exception as e:
                    errors.append(f"Extract error: {e}")
                    if self.config.error_handling == "stop":
                        raise

            # Transform
            for transformer in self._transformers:
                try:
                    data = transformer(data)
                except Exception as e:
                    errors.append(f"Transform error: {e}")
                    if self.config.error_handling == "stop":
                        raise

            # Load
            for loader in self._loaders:
                try:
                    loader(data)
                    processed = len(data)
                except Exception as e:
                    errors.append(f"Load error: {e}")
                    failed = len(data)
                    if self.config.error_handling == "stop":
                        raise

        except Exception as e:
            errors.append(f"Pipeline failed: {e}")
            self._status = "failed"
            return PipelineResult(False, processed, failed, (time.time() - start) * 1000, errors)

        self._status = "completed"
        return PipelineResult(True, processed, failed, (time.time() - start) * 1000, errors)

    def get_status(self) -> str:
        return self._status


class TransformEngine:
    def __init__(self):
        self._rules: List[TransformRule] = []
        self._functions: Dict[str, Callable] = {}

    def register_function(self, name: str, func: Callable) -> None:
        self._functions[name] = func

    def add_rule(self, rule: TransformRule) -> None:
        self._rules.append(rule)

    def transform(self, data: List[Dict]) -> List[Dict]:
        result = data

        for rule in self._rules:
            result = self._apply_rule(result, rule)

        return result

    def _apply_rule(self, data: List[Dict], rule: TransformRule) -> List[Dict]:
        if rule.transform_type == TransformType.MAP:
            func = self._functions.get(rule.params.get("function", ""))
            return [
                {**item, rule.output_field: func(item.get(rule.input_field)) if func else item.get(rule.input_field)}
                for item in data
            ]

        elif rule.transform_type == TransformType.FILTER:
            predicate = self._functions.get(rule.params.get("predicate", ""))
            if predicate:
                return [item for item in data if predicate(item)]
            return data

        elif rule.transform_type == TransformType.AGGREGATE:
            agg_func = rule.params.get("aggregation", "count")
            values = [item.get(rule.input_field) for item in data if item.get(rule.input_field) is not None]
            if agg_func == "count":
                return [{rule.output_field: len(values)}]
            elif agg_func == "sum":
                return [{rule.output_field: sum(values)}]
            elif agg_func == "avg":
                return [{rule.output_field: sum(values) / len(values) if values else 0}]

        return data


class DataEnricher:
    def __init__(self):
        self._sources: Dict[str, Dict] = {}
        self._rules: List[Dict] = []

    def add_source(self, name: str, data: Dict) -> None:
        self._sources[name] = data

    def add_enrichment_rule(self, source: str, match_field: str, output_field: str) -> None:
        self._rules.append({
            "source": source,
            "match_field": match_field,
            "output_field": output_field
        })

    def enrich(self, data: List[Dict]) -> List[Dict]:
        result = []

        for item in data:
            enriched = item.copy()

            for rule in self._rules:
                source_data = self._sources.get(rule["source"], {})
                match_value = item.get(rule["match_field"])

                if match_value in source_data:
                    enriched[rule["output_field"]] = source_data[match_value]

            result.append(enriched)

        return result
