---
Task ID: 2-d
Agent: Backend Bug-Fix Agent
Task: Fix two bugs — Redis-backed health tracker for Smart Router and MockVectorStore priority

Files Modified:
1. /home/z/my-project/parwa/backend/app/core/redis_health_tracker.py (NEW — 590 lines)
2. /home/z/my-project/parwa/backend/app/core/smart_router.py (MODIFIED — added Redis delegation)
3. /home/z/my-project/parwa/backend/app/shared/knowledge_base/vector_search.py (MODIFIED — fixed factory)

Work Log:
- Read existing smart_router.py, vector_search.py, redis.py, and config.py
- Created RedisHealthTracker class with Redis hash-backed state and in-memory fallback
- Modified ProviderHealthTracker.__init__ to try RedisHealthTracker first
- Added delegation guards (early return) in all 9 methods of ProviderHealthTracker
- Fixed get_vector_store() to read DATABASE_URL from get_settings() (pydantic .env) first
- Added comprehensive logging for all fallback paths
- Verified syntax and import chain with Python AST and runtime tests

Key Design Decisions:
- Used sync redis.Redis (not aioredis) since ProviderHealthTracker operates synchronously
- Each method in RedisHealthTracker has a _redis and _mem variant for clean delegation
- Every Redis operation is wrapped in try/except with fallback to in-memory
- vector_search.py now reads DATABASE_URL from app.config.get_settings() first (covers .env files)
- Clear log messages distinguish between "no PostgreSQL URL" vs "pgvector not installed"
