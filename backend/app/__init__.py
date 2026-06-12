"""
PARWA Phase 3 — Application Package

FastAPI application with modular API routes, tenant-scoped data access,
and resilient error handling.

CRITICAL RULES:
- BC-001: All endpoints must use company_id from JWT token for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- Paddle is ONLY for PARWA's own subscription billing — clients can use ANY payment provider
- No mock data, no placeholder emails
"""
