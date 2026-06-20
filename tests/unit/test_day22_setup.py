"""
Day 22 Test Setup — patches @with_company_id for Celery task testing.
"""
import functools
import importlib


_TASK_MODULES = [
    "backend.app.tasks.email_tasks",
    "backend.app.tasks.analytics_tasks",
    "backend.app.tasks.ai_tasks",
    "backend.app.tasks.training_tasks",
    "backend.app.tasks.approval_tasks",
    "backend.app.tasks.billing_tasks",
    "backend.app.tasks.periodic",
]


def _identity_decorator(func):
    """Pass-through decorator that preserves the function signature."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def setup_day22_tests():
    """Patch @with_company_id and reload task modules."""
    import backend.app.tasks.base as base_mod
    base_mod.with_company_id = _identity_decorator
    for mod_name in _TASK_MODULES:
        try:
            mod = __import__(mod_name, fromlist=[""])
            importlib.reload(mod)
        except (ImportError, Exception):
            pass
