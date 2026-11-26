"""Regression contract for tenant-scoped onboarding awareness."""

import ast
from pathlib import Path


def test_onboarding_awareness_uses_authenticated_company_id():
    source_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "jarvis_onboarding.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    handler = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "get_onboarding_awareness"
    )
    service_call = next(
        node
        for node in ast.walk(handler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "get_onboarding_awareness"
    )
    company_id = next(
        keyword.value
        for keyword in service_call.keywords
        if keyword.arg == "company_id"
    )

    assert ast.unparse(company_id) == "_require_company_id(current_user)"
