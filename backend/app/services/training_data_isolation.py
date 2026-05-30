"""
DEPRECATED: This service has been removed from the production codebase.
It had zero production callers and was dead code.

If you need this functionality, it has been superseded by:
- ai_service → app.core.ai_pipeline
- training_data_isolation → removed (was only called by dead ai_service)
- technique_cache_service → app.core.technique_caching

This stub exists only to prevent import errors in test files.
Remove the corresponding test files when convenient.
"""
raise DeprecationWarning(
    f"services.{svc} has been removed from the production codebase. "
    f"See module docstring for migration guidance."
)
