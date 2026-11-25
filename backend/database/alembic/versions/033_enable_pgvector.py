"""Enable pgvector extension for semantic knowledge-base search

Revision ID: 033_enable_pgvector
Revises: 032_company_trial_fields
Create Date: 2026-07-26

Enables the `vector` PostgreSQL extension so the knowledge-base retriever
(`app/shared/knowledge_base/retriever.py`) can run cosine-similarity searches
against `document_chunks.embedding`.

Without this extension, the retriever's `dc.embedding::vector` cast raises
`function/vector operator does not exist` on every query and silently falls
back to SQL ILIKE keyword search — which misses semantically relevant chunks
("password reset" never matches "password recovery") and degrades AI answer
quality across the whole customer-care pipeline.

Safe to run multiple times (`CREATE EXTENSION IF NOT EXISTS` is idempotent).
Requires PostgreSQL 13+ and the pgvector package on the DB host (Supabase
ships pgvector by default).
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "033_enable_pgvector"
down_revision = "032_company_trial_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgvector extension (idempotent)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # Embeddings are stored as TEXT and can have either 768 or 1024
    # dimensions, depending on the provider. pgvector requires an explicit
    # dimension for an index over a variable-dimension vector column, so
    # create a partial expression index for each supported dimension.
    for dimension in (768, 1024):
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector_{dimension}
            ON document_chunks
            USING ivfflat ((embedding::vector({dimension})) vector_cosine_ops)
            WITH (lists = 100)
            WHERE embedding IS NOT NULL
              AND vector_dims(embedding::vector) = {dimension};
            """
        )


def downgrade() -> None:
    """Drop the index (keep the extension — other features may depend on it)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_vector;")
