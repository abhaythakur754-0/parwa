"""PARWA utility package.

Provides shared infrastructure for all PARWA nodes:
- llm: LLM client with mock mode, retry, rate limiting, circuit breaker, TurboQuant
- node_base: @safe_node decorator for error handling, logging, validation
- retry: Exponential backoff retry for transient failures
- rate_limiter: Token bucket rate limiter for API calls
- circuit_breaker: Circuit breaker for external service resilience
- output_parser: Structured LLM response parsing (replaces fragile split("|"))
- sanitizer: Prompt injection detection and input sanitization
- tenant_rate_limiter: Per-tenant/variant rate limiting
- json_logging: Structured JSON logging for production
"""
