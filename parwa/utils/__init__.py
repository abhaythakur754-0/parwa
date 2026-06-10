"""PARWA utility package.

Provides shared infrastructure for all PARWA nodes:
- llm: LLM client with mock mode, retry, and rate limiting
- node_base: @safe_node decorator for error handling, logging, validation
- retry: Exponential backoff retry for transient failures
- rate_limiter: Token bucket rate limiter for API calls
"""
