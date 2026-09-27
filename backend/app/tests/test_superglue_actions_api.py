"""
Unit tests for app/api/superglue_actions.py

Covers:
- POST /api/superglue/actions/classify — ephemeral classification
- GET /api/superglue/actions/ — list (no DB = empty)
- POST /api/superglue/actions/persist — classify + persist (no DB = safe default)
- GET /api/superglue/actions/{tool_id} — get one (no DB = 404)
- PATCH /api/superglue/actions/{tool_id}/override — toggle (no DB = 404)

NOTE: We import the module via importlib to avoid the app.api.__init__.py chain
that requires sqlalchemy/database.

Run: pytest backend/app/tests/test_superglue_actions_api.py -v
"""

import sys
import os
import importlib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from fastapi.testclient import TestClient


# Import the router module directly, bypassing app.api.__init__
spec = importlib.util.spec_from_file_location(
    "superglue_actions",
    os.path.join(os.path.dirname(__file__), '..', 'api', 'superglue_actions.py'),
)
_sg_actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_sg_actions)
router = _sg_actions.router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestClassifyEndpoint:
    def test_classify_financial_tool(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/classify", json={
            "tool_name": "process_refund",
            "tool_description": "Refunds a customer",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_level"] == "financial"
        assert data["needs_approval"] is True
        assert data["matched_keyword"] == "refund"
        assert data["confidence"] == 0.9
        assert "PCI-DSS" in data["regulatory_frameworks"]

    def test_classify_read_tool(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/classify", json={
            "tool_name": "get_order_status",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_level"] == "read"
        assert data["needs_approval"] is False

    def test_classify_destructive_tool(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/classify", json={
            "tool_name": "delete_account",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_level"] == "destructive"
        assert data["needs_approval"] is True
        assert "SOX" in data["regulatory_frameworks"]

    def test_classify_write_tool(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/classify", json={
            "tool_name": "update_address",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_level"] == "write"
        assert data["needs_approval"] is False
        assert "SOC-2" in data["regulatory_frameworks"]

    def test_classify_missing_tool_name(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/classify", json={})
        assert resp.status_code == 422

    def test_classify_empty_tool_name(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/classify", json={
            "tool_name": "",
        })
        assert resp.status_code == 422


class TestListActionsEndpoint:
    def test_list_no_db(self):
        client = _make_client()
        resp = client.get("/api/superglue/actions/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_safety_filter(self):
        client = _make_client()
        resp = client.get("/api/superglue/actions/?safety_level=financial")
        assert resp.status_code == 200


class TestGetActionEndpoint:
    def test_get_missing_tool(self):
        client = _make_client()
        resp = client.get("/api/superglue/actions/nonexistent-tool")
        assert resp.status_code == 404


class TestOverrideEndpoint:
    def test_override_missing_tool(self):
        client = _make_client()
        resp = client.patch("/api/superglue/actions/nonexistent-tool/override", json={
            "approval_required_override": True,
        })
        assert resp.status_code == 404


class TestPersistEndpoint:
    def test_persist_no_db(self):
        client = _make_client()
        resp = client.post("/api/superglue/actions/persist", json={
            "tool_id": "refund-tool-1",
            "tool_name": "Process Refund",
            "tool_description": "Refunds a customer",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_level"] == "financial"
        assert data["needs_approval"] is True
