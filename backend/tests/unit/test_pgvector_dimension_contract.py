"""Regression checks for pgvector indexes with mixed embedding dimensions."""

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
RETRIEVER = (BACKEND_ROOT / "app/shared/knowledge_base/retriever.py").read_text(encoding="utf-8")
MIGRATION = (BACKEND_ROOT / "database/alembic/versions/033_enable_pgvector.py").read_text(encoding="utf-8")


def test_pgvector_migration_indexes_both_supported_dimensions():
    for dimension in (768, 1024):
        assert f"ix_document_chunks_embedding_vector_{dimension}" in MIGRATION
        assert f"embedding::vector({dimension})" in MIGRATION
        assert f"vector_dims(embedding::vector) = {dimension}" in MIGRATION


def test_retriever_query_uses_matching_dimension_and_partial_index_predicate():
    assert "dimension = len(query_emb)" in RETRIEVER
    assert "vector_expr = f\"dc.embedding::vector({dimension})\"" in RETRIEVER
    assert "vector_dims(dc.embedding::vector) = {dimension}" in RETRIEVER
    assert "CAST(:qemb AS vector({dimension}))" in RETRIEVER
