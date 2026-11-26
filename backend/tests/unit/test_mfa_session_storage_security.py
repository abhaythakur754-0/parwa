"""Static regression guards for production MFA session fail-closed behavior."""

import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "app" / "api" / "mfa.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def _function(name):
    return next(
        node for node in TREE.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _calls(node, name):
    return [
        child for child in ast.walk(node)
        if isinstance(child, ast.Call) and ast.unparse(child.func) == name
    ]


def test_production_mfa_session_store_failure_returns_service_unavailable():
    function = _function("create_mfa_session_token")
    production_guards = [
        node for node in ast.walk(function)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "get_settings().is_production"
    ]
    assert production_guards, "Redis store failure must check production mode"
    assert any(
        isinstance(child, ast.Raise)
        and any(
            isinstance(call, ast.Call)
            and ast.unparse(call.func) == "HTTPException"
            and any(kw.arg == "status_code" and isinstance(kw.value, ast.Constant) and kw.value.value == 503 for kw in call.keywords)
            for call in ast.walk(child)
        )
        for guard in production_guards
        for child in guard.body
    ), "production must fail closed with HTTP 503"


def test_production_mfa_session_read_failure_never_uses_process_memory():
    function = _function("_retrieve_mfa_session")
    production_guards = [
        node for node in ast.walk(function)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "get_settings().is_production"
    ]
    assert production_guards, "Redis read failure must check production mode"
    assert any(
        any(isinstance(child, ast.Return) and isinstance(child.value, ast.Constant) and child.value.value is None for child in guard.body)
        for guard in production_guards
    ), "production Redis read failure must return no session"
    memory_pops = _calls(function, "_mfa_pending_sessions.pop")
    assert memory_pops, "non-production fallback should remain available"


def test_mfa_session_ttl_remains_configurable():
    function = _function("_get_mfa_session_ttl")
    assert _calls(function, "get_settings")
    assert any(
        isinstance(node, ast.Attribute) and node.attr == "MFA_SESSION_TTL_SECONDS"
        for node in ast.walk(function)
    )
