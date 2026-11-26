"""Dependency contract: tenant config routes must bind identity to JWT."""

import ast
from pathlib import Path


def test_technique_config_router_requires_owner_or_admin():
    path = Path(__file__).resolve().parents[2] / "app" / "api" / "technique_config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    router_assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets)
    )
    role_guard = next(
        node for node in ast.walk(router_assignment.value)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "require_roles"
    )
    assert [arg.value for arg in role_guard.args] == ["owner", "admin"]


def test_each_technique_route_uses_authenticated_company_dependency():
    path = Path(__file__).resolve().parents[2] / "app" / "api" / "technique_config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    handlers = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {
            "list_technique_configs",
            "update_technique_config",
            "get_technique_config",
        }
    }
    assert set(handlers) == {
        "list_technique_configs",
        "update_technique_config",
        "get_technique_config",
    }
    for handler in handlers.values():
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Depends"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "get_company_id"
            for node in ast.walk(handler)
        )
