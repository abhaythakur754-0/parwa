"""
Week 7 test configuration — shared fixtures for E2E and load tests.
"""

import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


# Ensure shared.utils is mocked (needed by some schemas)
if "shared.utils" not in sys.modules:
    _fake_shared_utils = types.ModuleType("shared.utils")
    _fake_shared_pag = types.ModuleType("shared.utils.pagination")
    _fake_shared_pag.DEFAULT_PAGE_SIZE = 20
    _fake_shared_pag.MAX_PAGE_SIZE = 100
    _fake_shared_pag.MAX_OFFSET = 10000
    sys.modules.setdefault("shared.utils", _fake_shared_utils)
    sys.modules.setdefault("shared.utils.pagination", _fake_shared_pag)


@pytest.fixture
def mock_auth_service():
    """Mock auth service for register/login flows."""
    svc = MagicMock()

    def _make_register_result(email):
        return {
            "user": {
                "id": "user-abc-123",
                "email": email,
                "full_name": "Test User",
                "role": "owner",
                "is_active": True,
                "is_verified": False,
                "company_id": "company-xyz-789",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "tokens": {
                "access_token": "mock-access-token-xyz",
                "refresh_token": "mock-refresh-token-xyz",
                "token_type": "bearer",
                "expires_in": 900,
            },
            "is_new_user": True,
        }

    svc.register_user.return_value = _make_register_result("test@example.com")
    svc.authenticate_user.return_value = _make_register_result("test@example.com")
    return svc


@pytest.fixture
def mock_ticket_service():
    """Mock ticket service for CRUD operations."""
    svc = MagicMock()

    def _make_ticket(status="open", **overrides):
        ticket = MagicMock()
        ticket.id = "ticket-001"
        ticket.company_id = "company-xyz-789"
        ticket.customer_id = "customer-001"
        ticket.channel = "email"
        ticket.status = status
        ticket.subject = "Cannot access my account"
        ticket.priority = "medium"
        ticket.category = "account_access"
        ticket.tags = "[]"
        ticket.agent_id = None
        ticket.assigned_to = None
        ticket.classification_intent = None
        ticket.classification_type = None
        ticket.metadata_json = "{}"
        ticket.reopen_count = 0
        ticket.frozen = False
        ticket.parent_ticket_id = None
        ticket.duplicate_of_id = None
        ticket.is_spam = False
        ticket.awaiting_human = False
        ticket.awaiting_client = False
        ticket.escalation_level = 1
        ticket.sla_breached = False
        ticket.first_response_at = None
        ticket.resolution_target_at = None
        ticket.client_timezone = None
        ticket.plan_snapshot = None
        ticket.variant_version = None
        ticket.created_at = datetime.now(timezone.utc)
        ticket.updated_at = datetime.now(timezone.utc)
        ticket.closed_at = None
        for k, v in overrides.items():
            setattr(ticket, k, v)
        return ticket

    svc.create_ticket.return_value = _make_ticket()
    svc.get_ticket.return_value = _make_ticket()
    svc.list_tickets.return_value = ([_make_ticket()], 1)
    svc.update_ticket.return_value = _make_ticket()
    svc.assign_ticket.return_value = _make_ticket()
    svc._make_ticket = _make_ticket
    return svc


@pytest.fixture
def mock_jwt_token():
    """Provide a valid mock JWT payload dict."""
    return {
        "sub": "user-abc-123",
        "company_id": "company-xyz-789",
        "email": "test@example.com",
        "role": "owner",
        "plan": "starter",
        "type": "access",
        "jti": "jti-test-12345",
        "exp": int(datetime.now(timezone.utc).timestamp()) + 900,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "nbf": int(datetime.now(timezone.utc).timestamp()),
    }


@pytest.fixture
def mock_current_user(mock_jwt_token):
    """Mock get_current_user dependency returning a dict-like user."""
    user = MagicMock()
    user.id = mock_jwt_token["sub"]
    user.company_id = mock_jwt_token["company_id"]
    user.email = mock_jwt_token["email"]
    user.role = mock_jwt_token["role"]
    user.is_active = True
    user._token_payload = mock_jwt_token
    user.get = MagicMock(side_effect=lambda key, default=None: {
        "company_id": mock_jwt_token["company_id"],
        "user_id": mock_jwt_token["sub"],
        "plan_tier": mock_jwt_token["plan"],
    }.get(key, default))
    return user
