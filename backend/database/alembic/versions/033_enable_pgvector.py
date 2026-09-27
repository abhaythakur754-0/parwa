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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # Add an index on the embedding column for cosine similarity queries.
    # The column is TEXT (storing "[0.1,0.2,...]" literals); the cast
    # `embedding::vector` happens at query time. A GIN/IVFFlat index on the
    # cast expression accelerates ORDER BY ... <=> :query.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector
        ON document_chunks
        USING ivfflat (embedding::vector(768) vector_cosine_ops)
        WITH (lists = 100);
        """
    )


def downgrade() -> None:
    """Drop the index (keep the extension — other features may depend on it)."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_vector;")
