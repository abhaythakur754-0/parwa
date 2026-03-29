"""
Data Enrichment System Module
Week 56 - Advanced Data Pipelines

Provides data enrichment capabilities for joining external data
sources and enhancing records with additional information.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime
import logging
import copy

logger = logging.getLogger(__name__)


class EnrichmentSource(Enum):
    """Types of enrichment sources."""
    LOOKUP = "lookup"
    API = "api"
    DERIVED = "derived"
    COMPUTED = "computed"
    DATABASE = "database"
    CACHE = "cache"
    FILE = "file"


class EnrichmentStatus(Enum):
    """Status of an enrichment operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class EnrichmentRule:
    """Rule defining a data enrichment operation."""
    name: str
    source: EnrichmentSource
    match_field: str
    output_field: str
    source_data: Optional[Union[Dict, List, Callable]] = None
    source_mapping: Optional[Dict[str, str]] = None
    default_value: Any = None
    overwrite: bool = False
    required: bool = False
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    batch_size: int = 100
    timeout_seconds: float = 30.0
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate the enrichment rule."""
        errors = []

        if not self.name:
            errors.append("Rule name is required")

        if not isinstance(self.source, EnrichmentSource):
            errors.append("Invalid enrichment source")

        if not self.match_field:
            errors.append("Match field is required")

        if not self.output_field:
            errors.append("Output field is required")

        if self.source in (EnrichmentSource.LOOKUP, EnrichmentSource.DATABASE) and \
           self.source_data is None:
            errors.append(f"Source data is required for {self.source.value} source")

        return errors


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""
    rule_name: str
    source: EnrichmentSource
    status: EnrichmentStatus
    input_records: int = 0
    enriched_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if enrichment succeeded."""
        return self.status == EnrichmentStatus.COMPLETED

    @property
    def enrichment_rate(self) -> float:
        """Calculate enrichment rate."""
        if self.input_records == 0:
            return 0.0
        return self.enriched_records / self.input_records


@dataclass
class EnrichmentStats:
    """Statistics for enrichment operations."""
    total_rules: int = 0
    total_input_records: int = 0
    total_enriched_records: int = 0
    total_failed_records: int = 0
    total_cache_hits: int = 0
    total_cache_misses: int = 0
    total_errors: int = 0
    total_duration_ms: float = 0.0

    @property
    def overall_enrichment_rate(self) -> float:
        """Calculate overall enrichment rate."""
        if self.total_input_records == 0:
            return 0.0
        return self.total_enriched_records / self.total_input_records


class DataEnricher:
    """
    Data enrichment system.

    Supports various enrichment sources including lookups, APIs,
    derived values, and computed fields.
    """

    def __init__(self):
        """Initialize the data enricher."""
        self._rules: Dict[str, EnrichmentRule] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._results: List[EnrichmentResult] = []
        self._external_sources: Dict[str, Callable] = {}
        self._stats = EnrichmentStats()

    def register_rule(self, rule: EnrichmentRule) -> None:
        """
        Register an enrichment rule.

        Args:
            rule: EnrichmentRule to register
        """
        errors = rule.validate()
        if errors:
            raise ValueError(f"Invalid rule: {errors}")

        self._rules[rule.name] = rule

    def register_external_source(
        self,
        name: str,
        source_fn: Callable
    ) -> None:
        """
        Register an external source function.

        Args:
            name: Source name
            source_fn: Function that fetches data from the source
        """
        self._external_sources[name] = source_fn

    def enrich(
        self,
        data: Union[Dict, List],
        rule_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enrich data using registered rules.

        Args:
            data: Input data (dict or list of dicts)
            rule_names: Optional list of specific rules to apply

        Returns:
            Dictionary with enriched data and results
        """
        # Get rules to apply
        if rule_names:
            rules = [self._rules[name] for name in rule_names if name in self._rules]
        else:
            rules = list(self._rules.values())

        # Normalize input to list
        if isinstance(data, dict):
            data_list = [data]
            single_input = True
        else:
            data_list = data
            single_input = False

        # Apply each rule
        enriched_data = copy.deepcopy(data_list)

        for rule in rules:
            if not rule.enabled:
                continue

            result = self._apply_rule(enriched_data, rule)
            self._results.append(result)
            self._update_stats(result)

        # Return in same format as input
        result_data = enriched_data[0] if single_input else enriched_data

        return {
            "data": result_data,
            "results": self._results.copy(),
            "stats": self._get_current_stats()
        }

    def _apply_rule(
        self,
        data: List[Dict],
        rule: EnrichmentRule
    ) -> EnrichmentResult:
        """Apply a single enrichment rule to data."""
        result = EnrichmentResult(
            rule_name=rule.name,
            source=rule.source,
            status=EnrichmentStatus.RUNNING,
            input_records=len(data)
        )

        start_time = datetime.now()

        try:
            # Get enrichment data based on source type
            enrich_data = self._get_enrichment_data(rule)

            # Apply enrichment to each record
            enriched_count = 0
            skipped_count = 0
            failed_count = 0

            for record in data:
                try:
                    enriched = self._enrich_record(record, rule, enrich_data, result)

                    if enriched:
                        enriched_count += 1
                    else:
                        skipped_count += 1

                except Exception as e:
                    failed_count += 1
                    result.errors.append(f"Record enrichment failed: {str(e)}")

            result.enriched_records = enriched_count
            result.skipped_records = skipped_count
            result.failed_records = failed_count

            # Determine final status
            if failed_count == 0:
                result.status = EnrichmentStatus.COMPLETED
            elif enriched_count > 0:
                result.status = EnrichmentStatus.PARTIAL
            else:
                result.status = EnrichmentStatus.FAILED

        except Exception as e:
            result.status = EnrichmentStatus.FAILED
            result.errors.append(str(e))

        result.duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return result

    def _get_enrichment_data(self, rule: EnrichmentRule) -> Any:
        """Get enrichment data based on source type."""
        if rule.source == EnrichmentSource.LOOKUP:
            return self._get_lookup_data(rule)

        elif rule.source == EnrichmentSource.API:
            return self._get_api_data(rule)

        elif rule.source == EnrichmentSource.DERIVED:
            return self._get_derived_data(rule)

        elif rule.source == EnrichmentSource.COMPUTED:
            return rule.source_data

        elif rule.source == EnrichmentSource.DATABASE:
            return self._get_database_data(rule)

        elif rule.source == EnrichmentSource.CACHE:
            return self._get_cached_data(rule)

        elif rule.source == EnrichmentSource.FILE:
            return self._get_file_data(rule)

        return None

    def _get_lookup_data(self, rule: EnrichmentRule) -> Dict:
        """Get lookup data for enrichment."""
        source_data = rule.source_data

        if callable(source_data):
            return source_data()

        if isinstance(source_data, list):
            # Convert list to dict using match_field as key
            lookup_dict = {}
            for item in source_data:
                if isinstance(item, dict):
                    key = item.get(rule.match_field)
                    if key:
                        lookup_dict[key] = item
            return lookup_dict

        if isinstance(source_data, dict):
            return source_data

        return {}

    def _get_api_data(self, rule: EnrichmentRule) -> Any:
        """Get data from external API."""
        source_name = rule.metadata.get("source_name")

        if source_name and source_name in self._external_sources:
            return self._external_sources[source_name]()

        if callable(rule.source_data):
            return rule.source_data()

        return None

    def _get_derived_data(self, rule: EnrichmentRule) -> Callable:
        """Get derived data function."""
        if callable(rule.source_data):
            return rule.source_data

        # Return a simple passthrough function
        return lambda x: x

    def _get_database_data(self, rule: EnrichmentRule) -> Dict:
        """Get data from database source."""
        source_name = rule.metadata.get("source_name")

        if source_name and source_name in self._external_sources:
            return self._external_sources[source_name]()

        if callable(rule.source_data):
            return rule.source_data()

        return {}

    def _get_cached_data(self, rule: EnrichmentRule) -> Dict:
        """Get data from cache."""
        cache_key = rule.metadata.get("cache_key", rule.name)

        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key)
            if timestamp:
                age = (datetime.now() - timestamp).total_seconds()
                if age < rule.cache_ttl_seconds:
                    return self._cache[cache_key]

        # Fetch and cache
        if callable(rule.source_data):
            data = rule.source_data()
            self._cache[cache_key] = data
            self._cache_timestamps[cache_key] = datetime.now()
            return data

        return {}

    def _get_file_data(self, rule: EnrichmentRule) -> Any:
        """Get data from file source."""
        # This would typically load from a file path
        # For now, return source_data if available
        return rule.source_data

    def _enrich_record(
        self,
        record: Dict,
        rule: EnrichmentRule,
        enrich_data: Any,
        result: EnrichmentResult
    ) -> bool:
        """Enrich a single record."""
        if not isinstance(record, dict):
            return False

        match_value = record.get(rule.match_field)

        if match_value is None:
            if rule.required:
                raise ValueError(f"Required match field '{rule.match_field}' is missing")
            return False

        # Check if field already exists
        if rule.output_field in record and not rule.overwrite:
            result.warnings.append(
                f"Field '{rule.output_field}' already exists, skipping"
            )
            return False

        # Get enrichment value based on source type
        enrichment_value = None
        cache_hit = False

        if rule.source == EnrichmentSource.LOOKUP:
            if isinstance(enrich_data, dict):
                match_record = enrich_data.get(match_value)
                if match_record:
                    if rule.source_mapping:
                        enrichment_value = {
                            out_field: match_record.get(in_field)
                            for in_field, out_field in rule.source_mapping.items()
                        }
                    else:
                        enrichment_value = match_record.get(rule.output_field)

        elif rule.source == EnrichmentSource.API:
            cache_key = f"{rule.name}_{match_value}"
            if cache_key in self._cache and rule.cache_enabled:
                enrichment_value = self._cache[cache_key]
                cache_hit = True
                result.cache_hits += 1
            elif callable(enrich_data):
                enrichment_value = enrich_data(match_value)
                if rule.cache_enabled:
                    self._cache[cache_key] = enrichment_value
                result.cache_misses += 1

        elif rule.source == EnrichmentSource.DERIVED:
            if callable(enrich_data):
                enrichment_value = enrich_data(record)

        elif rule.source == EnrichmentSource.COMPUTED:
            if callable(rule.source_data):
                enrichment_value = rule.source_data(record)

        elif rule.source == EnrichmentSource.DATABASE:
            if isinstance(enrich_data, dict):
                enrichment_value = enrich_data.get(match_value)

        elif rule.source == EnrichmentSource.CACHE:
            enrichment_value = enrich_data.get(match_value) if isinstance(enrich_data, dict) else None

        elif rule.source == EnrichmentSource.FILE:
            if isinstance(enrich_data, dict):
                enrichment_value = enrich_data.get(match_value)

        # Apply enrichment
        if enrichment_value is not None:
            if isinstance(enrichment_value, dict):
                record.update(enrichment_value)
            else:
                record[rule.output_field] = enrichment_value
            return True
        elif rule.default_value is not None:
            record[rule.output_field] = rule.default_value
            return True

        return False

    def _update_stats(self, result: EnrichmentResult) -> None:
        """Update enrichment statistics."""
        self._stats.total_rules += 1
        self._stats.total_input_records += result.input_records
        self._stats.total_enriched_records += result.enriched_records
        self._stats.total_failed_records += result.failed_records
        self._stats.total_cache_hits += result.cache_hits
        self._stats.total_cache_misses += result.cache_misses
        self._stats.total_errors += len(result.errors)
        self._stats.total_duration_ms += result.duration_ms

    def _get_current_stats(self) -> EnrichmentStats:
        """Get current enrichment statistics."""
        return self._stats

    def get_rule(self, name: str) -> Optional[EnrichmentRule]:
        """Get a registered rule by name."""
        return self._rules.get(name)

    def remove_rule(self, name: str) -> bool:
        """Remove a registered rule."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def get_results(self) -> List[EnrichmentResult]:
        """Get all enrichment results."""
        return self._results.copy()

    def clear_results(self) -> None:
        """Clear stored results."""
        self._results = []
        self._stats = EnrichmentStats()

    def clear_cache(self) -> None:
        """Clear the enrichment cache."""
        self._cache.clear()
        self._cache_timestamps.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_entries": len(self._cache),
            "cache_hits": self._stats.total_cache_hits,
            "cache_misses": self._stats.total_cache_misses,
            "hit_rate": (
                self._stats.total_cache_hits / 
                (self._stats.total_cache_hits + self._stats.total_cache_misses)
            ) if (self._stats.total_cache_hits + self._stats.total_cache_misses) > 0 else 0
        }

    def join_external_data(
        self,
        data: List[Dict],
        external_data: List[Dict],
        join_key: str,
        output_fields: Optional[List[str]] = None,
        join_type: str = "left"
    ) -> Dict[str, Any]:
        """
        Join external data to input data.

        Args:
            data: Input data records
            external_data: External data to join
            join_key: Field to join on
            output_fields: Fields to include from external data
            join_type: Join type ("left", "inner", "full")

        Returns:
            Dictionary with enriched data and results
        """
        rule = EnrichmentRule(
            name=f"join_{join_key}",
            source=EnrichmentSource.LOOKUP,
            match_field=join_key,
            output_field="_joined",
            source_data=external_data,
            source_mapping={f: f for f in (output_fields or [])} if output_fields else None
        )

        # Temporarily register and apply
        original_rules = self._rules.copy()
        self._rules = {rule.name: rule}

        result = self.enrich(data, [rule.name])

        self._rules = original_rules

        return result

    def add_computed_field(
        self,
        data: Union[Dict, List],
        field_name: str,
        compute_fn: Callable,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Add a computed field to data.

        Args:
            data: Input data
            field_name: Name of the computed field
            compute_fn: Function to compute the field value
            overwrite: Whether to overwrite existing values

        Returns:
            Dictionary with enriched data and results
        """
        rule = EnrichmentRule(
            name=f"computed_{field_name}",
            source=EnrichmentSource.COMPUTED,
            match_field="",
            output_field=field_name,
            source_data=compute_fn,
            overwrite=overwrite
        )

        # Temporarily register and apply
        original_rules = self._rules.copy()
        self._rules = {rule.name: rule}

        result = self.enrich(data, [rule.name])

        self._rules = original_rules

        return result


def create_enrichment_rule(
    name: str,
    source: EnrichmentSource,
    match_field: str,
    output_field: str,
    source_data: Optional[Any] = None,
    **kwargs
) -> EnrichmentRule:
    """
    Create an enrichment rule.

    Args:
        name: Rule name
        source: Enrichment source type
        match_field: Field to match on
        output_field: Field to output to
        source_data: Data source (dict, list, or callable)
        **kwargs: Additional rule parameters

    Returns:
        EnrichmentRule instance
    """
    return EnrichmentRule(
        name=name,
        source=source,
        match_field=match_field,
        output_field=output_field,
        source_data=source_data,
        **kwargs
    )
