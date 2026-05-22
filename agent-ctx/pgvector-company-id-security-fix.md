# Task: pgvector company_id Security Fix — Cross-Tenant Data Leakage

## Date: 2026-03-04

## Summary
Fixed critical cross-tenant data leakage vulnerabilities in pgvector queries across the PARWA RAG pipeline. Multiple code paths were missing `company_id` filters, which could allow one company to read, write, or delete another company's document chunks.

## Files Modified

### 1. `backend/app/shared/knowledge_base/vector_search.py` (3 CRITICAL fixes)
- **PgVectorStore.add_document()**: INSERT was missing `company_id` as a first-class column. It was only stored in `metadata_json` (a non-existent column). Fixed to include `company_id` as a proper column in the INSERT statement. Also removed reference to non-existent `metadata_json` column.
- **PgVectorStore.search()**: Was using fragile `metadata_json::text LIKE :company_pattern` instead of `WHERE company_id = :company_id`. Fixed to use proper column filter. Added safety assertion for None/empty company_id.
- **PgVectorStore.delete_document()**: **CRITICAL** — Was missing company_id filter entirely! `DELETE FROM document_chunks WHERE document_id = :document_id` would delete ALL chunks for a document across ALL companies. Fixed to add `AND company_id = :company_id`.
- **PgVectorStore.get_all_documents()**: Added new method with `WHERE company_id = :company_id`.
- **PgVectorStore.get_document()**: Added new method with `WHERE document_id = :document_id AND company_id = :company_id`.
- **VectorStore ABC**: Added `get_document()` abstract method.
- **MockVectorStore**: Added `get_document()` implementation. Added safety assertions to `add_document()`, `search()`, and `delete_document()`.
- Also fixed: SQL queries referenced non-existent `metadata_json` column — removed all references.

### 2. `shared/knowledge_base/vector_search.py` (parallel copy)
- Added safety assertions to ALL methods in both `MockVectorStore` and `PgVectorStore`:
  - `search()`: Raises ValueError if company_id is None/empty
  - `add_chunks()` / `add_document()`: Raises ValueError if company_id is None/empty
  - `delete_document()`: Raises ValueError if company_id is None/empty
- Added safety assertion to `vector_search()` convenience function
- Note: This file already had proper company_id filters in SQL queries (it was the more complete implementation).

### 3. `backend/app/api/rag.py` (2 API fixes)
- **trigger_reindex()**: Was calling non-existent `manager.mark_for_reindex()`. Fixed to use `manager.create_job()`.
- **get_reindex_status()**: Was calling non-existent `manager.get_reindex_status()`. Fixed to use `manager.list_jobs()` with proper aggregation.

## Files Audited (already correct — no changes needed)
- `backend/app/shared/knowledge_base/retriever.py` — All queries filter by `DocumentChunk.company_id == self.company_id`
- `backend/app/shared/knowledge_base/manager.py` — All queries filter by `DocumentChunk.company_id == self.company_id`
- `backend/app/api/knowledge_base.py` — All queries filter by `KnowledgeDocument.company_id == user.company_id` or `DocumentChunk.company_id == user.company_id`
- `backend/app/tasks/knowledge_tasks.py` — All queries filter by `company_id`
- `backend/app/core/rag_retrieval.py` — Uses `self._store.search(..., company_id=company_id)` which is now properly enforced
- `backend/app/core/rag_reranking.py` — No direct DB queries, operates on in-memory chunks
- `backend/app/core/rag/hyde.py` — No direct DB queries
- `backend/app/core/rag/multi_query.py` — No direct DB queries, delegates to RAGRetriever
- `backend/app/core/rag/llm_reranker.py` — No direct DB queries
- `backend/app/services/embedding_service.py` — No DB queries
- `backend/app/services/jarvis_knowledge_service.py` — No DB queries (reads JSON files only)
- `backend/app/shared/knowledge_base/chunker.py` — No DB queries
- `backend/app/shared/knowledge_base/reindexing.py` — No direct DB queries

## Security Impact

### Before Fix
1. **PgVectorStore.search()**: Any user could search across ALL companies' document chunks via the fragile JSON LIKE pattern.
2. **PgVectorStore.delete_document()**: Any user could delete another company's document chunks by knowing the document_id.
3. **PgVectorStore.add_document()**: Chunks were stored without a proper `company_id` column, making tenant isolation impossible.
4. **No safety assertions**: Code could accidentally call methods with `company_id=None`, resulting in unscoped queries.

### After Fix
1. All SELECT, INSERT, DELETE queries include `company_id = :company_id` with parameterized queries.
2. Safety assertions raise `ValueError` if company_id is None, empty, or not a string.
3. The `vector_search()` convenience function enforces company_id.
4. Non-existent `metadata_json` column references removed (was causing SQL errors).
5. Missing `get_document()` method added to VectorStore ABC and both implementations.
