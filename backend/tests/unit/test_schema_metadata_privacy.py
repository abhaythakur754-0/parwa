"""Schema metadata passed to agents must not contain customer row values."""

from app.core.schema_metadata import sanitize_schema_metadata


def test_schema_sanitizer_keeps_structure_and_drops_sample_rows():
    raw = {
        "source": "superglue",
        "summary": "Orders database",
        "sample_rows": [{"email": "private@example.com", "card": "4111111111111111"}],
        "tables": [
            {
                "name": "orders",
                "description": "contains customer order data",
                "rows": [{"email": "private@example.com"}],
                "columns": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "customer_email", "type": "text", "example": "private@example.com"},
                ],
            }
        ],
    }

    safe = sanitize_schema_metadata(raw)

    assert safe["source"] == "superglue"
    assert safe["tables"][0]["name"] == "orders"
    assert safe["tables"][0]["columns"][0]["primary_key"] is True
    serialized = str(safe)
    assert "private@example.com" not in serialized
    assert "4111111111111111" not in serialized
    assert "sample_rows" not in serialized
    assert "rows" not in serialized
