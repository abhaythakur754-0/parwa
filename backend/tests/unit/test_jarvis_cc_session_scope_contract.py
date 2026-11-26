"""Regression contract for user-owned Jarvis Customer Care sessions."""

import ast
from pathlib import Path


SESSION_SCOPED_HANDLERS = {
    "get_cc_system_prompt": "session_id",
    "get_awareness_snapshot": "session_id",
    "get_awareness_snapshots": "session_id",
    "get_awareness_alerts": "session_id",
    "acknowledge_alert": "session_id",
    "dismiss_alert": "session_id",
    "resolve_alert": "session_id",
    "get_awareness_delta": "session_id",
    "send_command": "body.session_id",
    "execute_quick_command": "body.session_id",
    "undo_command": "body.session_id",
    "get_command_history": "session_id",
    "get_quick_commands": "session_id",
    "get_command_by_id": "session_id",
    "get_co_pilot_suggestion": "session_id",
    "add_custom_quick_command": "body.session_id",
    "remove_custom_quick_command": "body.session_id",
}


def _tree():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "jarvis_cc.py"
    )
    return ast.parse(source.read_text(encoding="utf-8"))


def test_session_scoped_handlers_validate_authenticated_session_owner():
    tree = _tree()
    handlers = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert SESSION_SCOPED_HANDLERS.keys() <= handlers.keys()
    for name, expected_session in SESSION_SCOPED_HANDLERS.items():
        calls = [
            node
            for node in ast.walk(handlers[name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_require_owned_cc_session"
        ]
        assert len(calls) == 1, name
        assert [ast.unparse(arg) for arg in calls[0].args] == [
            "db", "user", expected_session
        ], name


def test_session_owner_guard_uses_service_user_and_company_scope():
    tree = _tree()
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_require_owned_cc_session"
    )
    calls = [
        node
        for node in ast.walk(helper)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "jarvis_cc_service.get_cc_session"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in calls[0].keywords}
    assert keywords == {
        "db": "db",
        "session_id": "session_id",
        "user_id": "str(user.id)",
        "company_id": "str(user.company_id or '')",
    }
