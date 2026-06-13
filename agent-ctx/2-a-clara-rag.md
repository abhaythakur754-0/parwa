---
Task ID: 2-a
Agent: CLARA RAG Agent
Task: Create CLARA RAG Advanced Retrieval system (HyDE, Multi-Query, LLM Reranker)

Files Created:
1. /home/z/my-project/parwa/backend/app/core/rag/__init__.py (1 line)
2. /home/z/my-project/parwa/backend/app/core/rag/hyde.py (425 lines)
3. /home/z/my-project/parwa/backend/app/core/rag/multi_query.py (654 lines)
4. /home/z/my-project/parwa/backend/app/core/rag/llm_reranker.py (523 lines)

Total: 1603 lines across 4 files

Key Design Decisions:
- All files follow existing codebase patterns (get_logger, SmartRouter, Redis cache_get/cache_set)
- BC-008 graceful degradation: every async method returns safe defaults on error
- BC-007: All LLM calls go through SmartRouter's route() + async_execute_llm_call()
- BC-001: All operations scoped by company_id
- Redis caching with 120s TTL for HyDE hypothetical answers and multi-query alternatives
- Lazy imports for SmartRouter and Redis to avoid circular dependencies

Key Classes & Methods:
- HyDEGenerator.generate_hypothetical_answer() → str (BC-008: returns original query on failure)
- HyDEGenerator.get_hyde_embedding() → Optional[List[float]] (BC-008: falls back to query embedding)
- MultiQueryRetriever.generate_alternative_queries() → List[str] (BC-008: returns empty list)
- MultiQueryRetriever.retrieve_with_multi_query() → RAGResult (BC-008: falls back to single query)
- MultiQueryRetriever._merge_and_deduplicate() → List[RAGChunk]
- MultiQueryRetriever._rank_by_aggregate_score() → List[Tuple[str, float]]
- LLMReranker.rerank() → List[RAGChunk] (BC-008: falls back to BM25 reranking)
