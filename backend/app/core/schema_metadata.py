"""Privacy-preserving database schema metadata normalization."""

from typing import Any, Dict


def sanitize_schema_metadata(schema: Any) -> Dict[str, Any]:
    """Retain structural schema information while excluding row/sample values."""
    if isinstance(schema, str):
        try:
            import json
            schema = json.loads(schema)
        except (TypeError, ValueError):
            return {}
    if not isinstance(schema, dict):
        return {}

    safe: Dict[str, Any] = {}
    for key in ("summary", "database_type", "db_type", "analyzed_at", "source"):
        value = schema.get(key)
        if isinstance(value, (str, int, float, bool)):
            safe[key] = str(value)[:500] if isinstance(value, str) else value

    for collection_key in ("tables", "collections", "schemas"):
        items = schema.get(collection_key)
        if not isinstance(items, list):
            continue
        safe_items = []
        for item in items[:100]:
            if isinstance(item, str):
                safe_items.append({"name": item[:200]})
                continue
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("table_name") or item.get("collection_name")
            entry: Dict[str, Any] = {"name": str(name or "unknown")[:200]}
            schema_name = item.get("schema") or item.get("schema_name")
            if isinstance(schema_name, str):
                entry["schema"] = schema_name[:200]
            table_type = item.get("type") or item.get("table_type")
            if isinstance(table_type, str):
                entry["type"] = table_type[:100]
            columns = item.get("columns") or item.get("fields")
            if isinstance(columns, list):
                entry["columns"] = []
                for column in columns[:100]:
                    if isinstance(column, str):
                        entry["columns"].append({"name": column[:200]})
                    elif isinstance(column, dict):
                        col_name = column.get("name") or column.get("column_name") or column.get("field")
                        col_type = column.get("type") or column.get("data_type")
                        col = {
                            "name": str(col_name or "unknown")[:200],
                            "type": str(col_type or "unknown")[:100],
                        }
                        for flag in ("nullable", "primary_key", "is_primary_key", "foreign_key"):
                            flag_value = column.get(flag)
                            if isinstance(flag_value, (bool, str, int)):
                                col[flag] = flag_value
                        entry["columns"].append(col)
            safe_items.append(entry)
        safe[collection_key] = safe_items

    relationships = schema.get("relationships")
    if isinstance(relationships, list):
        safe["relationships"] = []
        for relationship in relationships[:200]:
            if not isinstance(relationship, dict):
                continue
            safe["relationships"].append({
                key: str(relationship.get(key))[:200]
                for key in (
                    "source_table", "source_column",
                    "target_table", "target_column", "type",
                )
                if relationship.get(key) is not None
            })
    return safe
