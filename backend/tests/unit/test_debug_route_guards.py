from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import admin_bootstrap, debug


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_setup_routes_are_disabled_outside_development(monkeypatch, environment):
    monkeypatch.setattr(
        admin_bootstrap,
        "get_settings",
        lambda: SimpleNamespace(ENVIRONMENT=environment),
    )
    with pytest.raises(HTTPException) as exc:
        admin_bootstrap.require_development_only()
    assert exc.value.status_code == 404


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_debug_routes_are_disabled_outside_development(monkeypatch, environment):
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(ENVIRONMENT=environment),
    )
    with pytest.raises(HTTPException) as exc:
        debug.require_debug_not_production()
    assert exc.value.status_code == 404


def test_database_wipe_endpoint_is_permanently_disabled():
    with pytest.raises(HTTPException) as exc:
        admin_bootstrap.nuke_all_data()
    assert exc.value.status_code == 410
