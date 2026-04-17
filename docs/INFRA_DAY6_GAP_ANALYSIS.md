# Infrastructure Day 6: RAG, pgvector, and AI Pipeline Hardening - Gap Analysis

**Date:** April 17, 2026
**Status:** ✅ COMPLETE

---

## Executive Summary

Day 6 RAG, pgvector, and AI Pipeline Hardening is now COMPLETE. Key improvements:

- ✅ Embedding dimension updated to 1536 (OpenAI text-embedding-3-small)
- ✅ PgVectorStore DDL updated with vector(1536) column
- ✅ Weekly reindex Celery beat task added
- ✅ Weekly DSPy optimization Celery beat task added
- ✅ Knowledge queue added to Celery queues
- ✅ Retrieval quality validation test suite created

---

## Component Analysis

### 6.1 pgvector Integration (I1)

**Status: ✅ COMPLETE (Updated)**

| Component | Status | Notes |
|-----------|--------|-------|
| pgvector extension | ✅ Exists | `database/schema.sql:13` |
| Embedding dimension | ✅ Updated | Changed from 768 to 1536 (OpenAI standard) |
| HNSW index | ✅ Complete | In PgVectorStore._ensure_schema() |
| MockVectorStore fallback | ✅ Maintained | Graceful degradation for development |

**Change Applied:**
```python
# shared/knowledge_base/vector_search.py
EMBEDDING_DIMENSION = 1536  # OpenAI text-embedding-3-small dimension (Day 6)
```

**DDL Updated:**
```sql
CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    document_id VARCHAR(36) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT,
    embedding vector(1536),  -- Updated from 768
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
)
```

---

### 6.2 Knowledge Base Pipeline Activation (F-033)

**Status: ✅ COMPLETE (Enhanced)**

| Component | Status | Notes |
|-----------|--------|-------|
| 4-stage pipeline | ✅ Exists | Extract → Chunk → Embed → Index |
| Real embeddings | ✅ Exists | Via EmbeddingService |
| Weekly reindex task | ✅ Added | `reindex_all_knowledge_documents` Celery task |
| Retrieval quality test | ✅ Added | 50-pair test suite with Recall@5, MRR metrics |

**New Celery Beat Schedule:**
```python
"reindex-knowledge-documents-weekly": {
    "task": "app.tasks.periodic.reindex_all_knowledge_documents",
    "schedule": {
        "day_of_week": 0,  # Sunday
        "hour": 2,
        "minute": 0,
    },
}
```

**Retrieval Quality Test:**
- File: `backend/tests/unit/test_retrieval_quality.py`
- 50 query-document ground truth pairs
- Metrics: Recall@5 ≥ 70%, MRR ≥ 60%, Latency < 200ms

---

### 6.3 LiteLLM Integration (LITELLM-1)

**Status: ⚠️ PARTIAL (Documented for Future)**

| Component | Status | Notes |
|-----------|--------|-------|
| litellm package | ✅ Installed | `litellm>=1.40.0,<2.0.0` |
| litellm import | ✅ Exists | In smart_router.py |
| acompletion() usage | ⚠️ NOT Used | Still uses raw httpx calls |
| Usage logging | ✅ Model exists | ModelUsageLog in ai_pipeline.py |

**Recommendation:**
LiteLLM integration requires careful migration from the existing httpx-based Smart Router. The current implementation works reliably with multiple providers (Google, Cerebras, Groq). A full LiteLLM migration should be done in a dedicated refactoring sprint to avoid disrupting the working routing logic.

**Current Smart Router Comment:**
```python
# TODO: LiteLLM is imported for potential future use but is NOT currently
# the primary routing mechanism.  When LiteLLM is integrated as the
# primary call layer, replace execute_llm_call with litellm.acompletion()
```

---

### 6.4 DSPy Optimization Pipeline (DSPY-1)

**Status: ✅ COMPLETE (Enhanced)**

| Component | Status | Notes |
|-----------|--------|-------|
| dspy-ai package | ✅ Installed | `dspy-ai>=2.5.0` |
| DSPy Signatures | ✅ Exists | PREDEFINED_SIGNATURES in dspy_integration.py |
| Optimizers | ✅ Exists | BootstrapFewShot, MIPROv2 |
| Weekly optimization task | ✅ Added | `dspy_weekly_optimization` Celery task |
| DB prompt storage | ⚠️ Pending | Uses file cache currently |

**New Celery Beat Schedule:**
```python
"dspy-weekly-optimization": {
    "task": "app.tasks.periodic.dspy_weekly_optimization",
    "schedule": {
        "day_of_week": 0,  # Sunday
        "hour": 3,
        "minute": 0,
    },
}
```

---

## Celery Queue Updates

**New Queue Added:**
```python
QUEUE_NAMES = [
    ...
    "knowledge",  # Day 6: Knowledge base tasks
    ...
]
```

**New Task Routing:**
```python
"app.tasks.knowledge.*": {"queue": "knowledge"},
```

**New Import:**
```python
"app.tasks.knowledge_tasks",  # Day 6
```

---

## Gap Summary

| Gap ID | Component | Severity | Status |
|--------|-----------|----------|--------|
| D6-G1 | Embedding dimension | HIGH | ✅ FIXED |
| D6-G2 | Reindex Celery task | HIGH | ✅ FIXED |
| D6-G3 | DSPy weekly task | MEDIUM | ✅ FIXED |
| D6-G4 | Knowledge queue | MEDIUM | ✅ FIXED |
| D6-G5 | Retrieval quality test | HIGH | ✅ FIXED |
| D6-G6 | LiteLLM migration | LOW | ⚠️ DEFERRED |
| D6-G7 | DSPy DB storage | LOW | ⚠️ DEFERRED |

---

## Files Created/Modified

### New Files
| File | Purpose |
|------|---------|
| `backend/tests/unit/test_retrieval_quality.py` | 50-pair retrieval quality validation |

### Modified Files
| File | Changes |
|------|---------|
| `shared/knowledge_base/vector_search.py` | Updated EMBEDDING_DIMENSION to 1536, vector(1536) DDL |
| `backend/app/tasks/periodic.py` | Added reindex + DSPy optimization tasks |
| `backend/app/tasks/celery_app.py` | Added knowledge queue + beat schedules |

---

## Deliverables Checklist

| Deliverable | Target | Status | Verification |
|-------------|--------|--------|--------------|
| pgvector extension | Enabled | ✅ DONE | schema.sql has CREATE EXTENSION |
| Embedding dimension | 1536 | ✅ DONE | EMBEDDING_DIMENSION = 1536 |
| HNSW index | Created | ✅ DONE | In _ensure_schema() |
| Weekly reindex task | Celery beat | ✅ DONE | Sunday 2 AM UTC |
| Retrieval quality test | 50 pairs | ✅ DONE | test_retrieval_quality.py |
| DSPy weekly task | Celery beat | ✅ DONE | Sunday 3 AM UTC |

---

## Test Coverage

| Test Suite | Status |
|------------|--------|
| test_retrieval_quality.py | ✅ Created |
| Recall@5 target >= 70% | ✅ Test exists |
| MRR target >= 60% | ✅ Test exists |
| Latency < 200ms | ✅ Test exists |

---

## Next Steps

1. **Day 7:** Shadow Mode Infrastructure & Channel Foundation
   - Shadow hold queue tables
   - Twilio infrastructure
   - Channel interceptors (already partially done)

2. **Deferred Items:**
   - Full LiteLLM migration (requires dedicated sprint)
   - DSPy prompt storage in database (currently file-based)

3. **Recommendations:**
   - Run retrieval quality test against real embeddings
   - Monitor reindex task in first week
   - Consider LiteLLM migration after stability period

---

*End of Day 6 Gap Analysis*
