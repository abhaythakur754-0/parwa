"""Prevent authenticated non-admins from changing Jarvis controls."""

import ast
from pathlib import Path


PROTECTED_HANDLERS = {
    "approve_batch",
    "reject_batch",
    "set_flag",
    "revoke_flag",
    "command_pause",
    "command_resume",
    "command_redirect",
    "command_mode",
    "approval_batch",
    "provision_agent_endpoint",
    "teach_skill_endpoint",
    "dspy_correction_endpoint",
}


def test_sensitive_jarvis_controls_require_owner_or_admin():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "jarvis_routes.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    handlers = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert PROTECTED_HANDLERS <= handlers.keys()
    for name in PROTECTED_HANDLERS:
        handler = handlers[name]
        current_user = next(
            arg for arg in handler.args.args if arg.arg == "current_user"
        )
        default_index = len(handler.args.args) - len(handler.args.defaults)
        default = handler.args.defaults[
            handler.args.args.index(current_user) - default_index
        ]
        assert isinstance(default, ast.Call) and ast.unparse(default.func) == "Depends", name
        role_guard = default.args[0]
        assert isinstance(role_guard, ast.Call) and ast.unparse(role_guard.func) == "require_roles", name
        assert [arg.value for arg in role_guard.args] == ["owner", "admin"], name
