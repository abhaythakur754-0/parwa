"""Command-level RBAC regression tests for Jarvis Customer Care."""

import ast
from pathlib import Path

import pytest

from app.exceptions import AuthorizationError
from app.security.command_authorization import (
    ADMIN_ONLY_COMMAND_ACTIONS,
    require_command_role,
)


BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("action", sorted(ADMIN_ONLY_COMMAND_ACTIONS))
def test_regular_member_cannot_execute_admin_only_commands(action):
    with pytest.raises(AuthorizationError):
        require_command_role(action, "member")


@pytest.mark.parametrize("role", ["owner", "admin", "system"])
@pytest.mark.parametrize("action", sorted(ADMIN_ONLY_COMMAND_ACTIONS))
def test_owner_admin_and_trusted_system_can_execute_protected_commands(action, role):
    require_command_role(action, role)


def test_support_members_can_still_escalate_urgent_tickets():
    require_command_role("escalate_urgent", "member")


def _module_tree(relative_path):
    return ast.parse((BACKEND / relative_path).read_text(encoding="utf-8"))


def _handler(tree, name):
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def test_public_command_entry_points_pass_authenticated_role_to_service():
    tree = _module_tree("app/api/jarvis_cc.py")
    expected_calls = {
        "send_cc_message": "jarvis_cc_service.send_cc_message",
        "send_command": "jarvis_command_service.execute_command",
        "execute_quick_command": "jarvis_command_service.execute_quick_command",
        "undo_command": "jarvis_command_service.undo_command",
    }
    for handler_name, function_name in expected_calls.items():
        calls = [
            node
            for node in ast.walk(_handler(tree, handler_name))
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == function_name
        ]
        assert len(calls) == 1, handler_name
        role_arg = next(k.value for k in calls[0].keywords if k.arg == "user_role")
        assert ast.unparse(role_arg) == "str(user.role)", handler_name


def test_prompt_and_custom_command_mutations_are_owner_admin_only():
    tree = _module_tree("app/api/jarvis_cc.py")
    for name in ("get_cc_system_prompt", "add_custom_quick_command", "remove_custom_quick_command"):
        handler = _handler(tree, name)
        user_arg = next(arg for arg in handler.args.args if arg.arg == "user")
        default_offset = len(handler.args.args) - len(handler.args.defaults)
        default = handler.args.defaults[handler.args.args.index(user_arg) - default_offset]
        assert ast.unparse(default.func) == "Depends", name
        role_guard = default.args[0]
        assert ast.unparse(role_guard.func) == "require_roles", name
        assert [arg.value for arg in role_guard.args] == ["owner", "admin"], name


def test_command_service_checks_role_before_dispatch_and_before_undo():
    tree = _module_tree("app/services/jarvis_command_service.py")
    execute = _handler(tree, "execute_command")
    undo = _handler(tree, "undo_command")

    assert any(
        isinstance(node, ast.Call)
        and ast.unparse(node.func) == "require_command_role"
        and [ast.unparse(arg) for arg in node.args] == ["action", "user_role"]
        for node in ast.walk(execute)
    )
    assert any(
        isinstance(node, ast.Call)
        and ast.unparse(node.func) == "require_command_role"
        and [ast.unparse(arg) for arg in node.args] == ["original_action", "user_role"]
        for node in ast.walk(undo)
    )
