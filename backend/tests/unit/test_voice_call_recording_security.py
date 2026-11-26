"""Regression tests for tenant-controlled voice recording and call roles."""

import ast
from pathlib import Path

import pytest

from app.security.voice_call_policy import resolve_recording_enabled


BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "tenant_enabled,requested,expected",
    [
        (False, True, False),
        (False, None, False),
        (True, None, True),
        (True, True, True),
        (True, False, False),
    ],
)
def test_call_recording_never_exceeds_tenant_policy(tenant_enabled, requested, expected):
    assert resolve_recording_enabled(tenant_enabled, requested) is expected


def test_recording_request_must_be_a_boolean():
    with pytest.raises(ValueError):
        resolve_recording_enabled(True, "true")


def _tree(relative_path):
    return ast.parse((BACKEND / relative_path).read_text(encoding="utf-8"))


def test_outbound_call_api_does_not_trust_client_sender_role():
    tree = _tree("app/api/voice_channel.py")
    handler = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "initiate_outbound_call"
    )
    call = next(
        node for node in ast.walk(handler)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "service.initiate_outbound_call"
    )
    keywords = {kw.arg: kw.value for kw in call.keywords}
    assert ast.literal_eval(keywords["sender_role"]) == "agent"
    assert ast.unparse(keywords["enable_recording"]) == "requested_recording"
    assert not any(
        isinstance(node, ast.Call)
        and ast.unparse(node.func) == "body.get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "sender_role"
        for node in ast.walk(handler)
    )


def test_voice_service_uses_tenant_recording_policy_helper():
    tree = _tree("app/services/voice_channel_service.py")
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "initiate_outbound_call"
    )
    assert any(
        isinstance(node, ast.Call)
        and ast.unparse(node.func) == "resolve_recording_enabled"
        and [ast.unparse(arg) for arg in node.args]
        == ["config.enable_recording", "enable_recording"]
        for node in ast.walk(method)
    )


def test_voice_test_call_is_owner_admin_only():
    tree = _tree("app/api/voice_channel.py")
    handler = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "test_call"
    )
    user_arg = next(arg for arg in handler.args.args if arg.arg == "current_user")
    offset = len(handler.args.args) - len(handler.args.defaults)
    default = handler.args.defaults[handler.args.args.index(user_arg) - offset]
    guard = default.args[0]
    assert ast.unparse(guard.func) == "require_roles"
    assert [arg.value for arg in guard.args] == ["owner", "admin"]


def test_voice_configuration_mutations_are_owner_admin_only():
    tree = _tree("app/api/voice_channel.py")
    for name in ("create_voice_config", "update_voice_config", "delete_voice_config"):
        handler = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == name
        )
        user_arg = next(arg for arg in handler.args.args if arg.arg == "current_user")
        offset = len(handler.args.args) - len(handler.args.defaults)
        default = handler.args.defaults[handler.args.args.index(user_arg) - offset]
        guard = default.args[0]
        assert ast.unparse(guard.func) == "require_roles", name
        assert [arg.value for arg in guard.args] == ["owner", "admin"], name
