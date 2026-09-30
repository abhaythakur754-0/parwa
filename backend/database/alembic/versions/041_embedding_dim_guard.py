"""Pin document_chunks.embedding to 768 dimensions (Google text-embedding-004)

Revision ID: 041_embedding_dim_guard
Revises: 040_voice_provider_turns
Create Date: 2026-09-27

WHY
---
The runtime embedder has multiple fallbacks (Google 768-dim primary,
LiteLLM text-embedding-3-small 1536-dim, NVIDIA nv-embedqa-e5-v5
1024-dim), but the pgvector lane is pinned to 768:

  - migration 033 created the ivfflat index on `embedding::vector(768)`
  - the retriever casts `dc.embedding::vector` at query time

Any non-768 vector stored as a text literal crashes index maintenance on
insert (HTTP 500 while ingesting KB documents) or crashes every hybrid
query that touches the row. The application-level guard in
app/services/embedding_service.py now rejects wrong-dim vectors; this
constraint is the DB-level safety net so raw SQL, scripts, or future
code regressions cannot poison the column either.

NOT VALID: existing rows are NOT scanned (avoids a full-table rewrite
and a failed migration if legacy bad rows exist). The constraint is
enforced for every NEW insert/update from deployment time onward.

Safe to run multiple times (checks information_schema first).

After deploying, clean any legacy bad rows at leisure:
  UPDATE document_chunks
     SET embedding = NULL
   WHERE embedding IS NOT NULL
     AND vector_dims(embedding::vector) <> 768;
  ALTER TABLE document_chunks VALIDATE CONSTRAINT embedding_dim_ok;
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "041_embedding_dim_guard"
down_revision = "040_voice_provider_turns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add CHECK (vector_dims = 768) on document_chunks.embedding (NOT VALID)."""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'embedding_dim_ok'
                  AND table_name = 'document_chunks'
            ) THEN
                ALTER TABLE document_chunks ADD CONSTRAINT embedding_dim_ok
                    CHECK (embedding IS NULL OR vector_dims(embedding::vector) = 768)
                    NOT VALID;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Drop the dimension guard constraint."""
    op.execute(
        "ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS embedding_dim_ok;"
    )
