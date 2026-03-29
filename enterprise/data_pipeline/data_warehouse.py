"""Data Warehouse Module - Week 56, Builder 4"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class StorageFormat(Enum):
    PARQUET = "parquet"
    AVRO = "avro"
    JSON = "json"
    CSV = "csv"


@dataclass
class WarehouseTable:
    name: str
    schema: Dict[str, type] = field(default_factory=dict)
    partitions: List[str] = field(default_factory=list)
    storage_format: StorageFormat = StorageFormat.PARQUET
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QueryPlan:
    steps: List[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_rows: int = 0


class DataWarehouse:
    def __init__(self, name: str = "default"):
        self.name = name
        self._tables: Dict[str, WarehouseTable] = {}
        self._data: Dict[str, List[Dict]] = {}

    def create_table(self, table: WarehouseTable) -> bool:
        if table.name in self._tables:
            return False
        self._tables[table.name] = table
        self._data[table.name] = []
        return True

    def drop_table(self, name: str) -> bool:
        if name not in self._tables:
            return False
        del self._tables[name]
        del self._data[name]
        return True

    def insert(self, table_name: str, records: List[Dict]) -> int:
        if table_name not in self._tables:
            return 0
        self._data[table_name].extend(records)
        return len(records)

    def query(self, table_name: str, filters: Dict = None, columns: List[str] = None) -> List[Dict]:
        if table_name not in self._tables:
            return []

        data = self._data[table_name]

        if filters:
            data = [r for r in data if all(r.get(k) == v for k, v in filters.items())]

        if columns:
            data = [{k: r.get(k) for k in columns if k in r} for r in data]

        return data

    def get_table(self, name: str) -> Optional[WarehouseTable]:
        return self._tables.get(name)

    def list_tables(self) -> List[str]:
        return list(self._tables.keys())

    def get_table_stats(self, name: str) -> Dict:
        if name not in self._tables:
            return {}
        return {
            "row_count": len(self._data[name]),
            "columns": list(self._tables[name].schema.keys()),
            "partitions": self._tables[name].partitions
        }


class QueryOptimizer:
    def __init__(self):
        self._indexes: Dict[str, List[str]] = {}
        self._stats: Dict[str, Dict] = {}

    def create_index(self, table: str, columns: List[str]) -> None:
        self._indexes[f"{table}_{'_'.join(columns)}"] = columns

    def analyze(self, table: str, stats: Dict) -> None:
        self._stats[table] = stats

    def optimize(self, query: str, tables: List[str]) -> QueryPlan:
        steps = []
        cost = 1.0
        rows = 1000

        # Simple heuristic optimization
        if "WHERE" in query.upper():
            steps.append("Apply filters early")
            cost *= 0.5

        if "JOIN" in query.upper():
            steps.append("Optimize join order")
            cost *= 1.5

        if "GROUP BY" in query.upper():
            steps.append("Aggregate after filtering")
            cost *= 1.2

        # Check for index usage
        for table in tables:
            if table in self._stats:
                rows = self._stats[table].get("row_count", rows)

        return QueryPlan(steps=steps, estimated_cost=cost, estimated_rows=rows)

    def suggest_index(self, table: str, query: str) -> List[str]:
        suggestions = []
        import re
        where_match = re.search(r"WHERE\s+(\w+)", query, re.IGNORECASE)
        if where_match:
            suggestions.append(f"Consider index on column: {where_match.group(1)}")
        return suggestions


class AnalyticsEngine:
    def __init__(self, warehouse: DataWarehouse):
        self.warehouse = warehouse

    def aggregate(self, table: str, group_by: List[str], metrics: Dict[str, str]) -> List[Dict]:
        data = self.warehouse.query(table)
        if not data:
            return []

        groups = {}
        for row in data:
            key = tuple(row.get(g) for g in group_by)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        results = []
        for key, rows in groups.items():
            result = dict(zip(group_by, key))
            for metric_name, agg_type in metrics.items():
                values = [r.get(metric_name, 0) for r in rows if r.get(metric_name) is not None]
                if agg_type == "sum":
                    result[f"{metric_name}_sum"] = sum(values)
                elif agg_type == "avg":
                    result[f"{metric_name}_avg"] = sum(values) / len(values) if values else 0
                elif agg_type == "count":
                    result[f"{metric_name}_count"] = len(values)
                elif agg_type == "min":
                    result[f"{metric_name}_min"] = min(values) if values else 0
                elif agg_type == "max":
                    result[f"{metric_name}_max"] = max(values) if values else 0
            results.append(result)

        return results

    def trend(self, table: str, time_column: str, value_column: str, interval: str = "day") -> List[Dict]:
        data = self.warehouse.query(table)
        if not data:
            return []

        # Simple trend calculation
        sorted_data = sorted(data, key=lambda x: x.get(time_column, ""))
        trends = []

        for i, row in enumerate(sorted_data):
            trends.append({
                time_column: row.get(time_column),
                value_column: row.get(value_column),
                "index": i
            })

        return trends

    def correlation(self, table: str, col1: str, col2: str) -> float:
        data = self.warehouse.query(table)
        if len(data) < 2:
            return 0.0

        values1 = [r.get(col1, 0) for r in data]
        values2 = [r.get(col2, 0) for r in data]

        n = len(values1)
        mean1 = sum(values1) / n
        mean2 = sum(values2) / n

        numerator = sum((values1[i] - mean1) * (values2[i] - mean2) for i in range(n))
        denom1 = sum((v - mean1) ** 2 for v in values1) ** 0.5
        denom2 = sum((v - mean2) ** 2 for v in values2) ** 0.5

        if denom1 == 0 or denom2 == 0:
            return 0.0

        return numerator / (denom1 * denom2)
